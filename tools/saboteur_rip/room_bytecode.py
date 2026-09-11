"""Interpret Saboteur II room sequences (S2ROOM.MAC) using the S2CORE marker table."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from macparse import parse_mac_bytes, parse_octal_tokens, parse_word_table
from opcode_catalog import (
    CELL,
    EMPTY_TILES,
    L25424,
    MAP_ROWS,
    MAP_W,
    MARKERS,
    EARTH,
    INTERIOR,
    PLAYFIELD_H,
    ROOM_COLS,
    ROOM_ROWS,
    SCREEN_W,
    SKIP_TILE,
    SKY,
    START_RMAC,
    START_RMDN,
    WALLPAPER_TYPE,
    WORLD_ROWS,
    WORLD_UNIQUE_TYPES,
    INDOOR_TYPE_PREFIXES,
    OUTDOOR_TYPE_PREFIXES,
    TEMPLATE_LABELS,
    apply_template_bytes,
    dest_to_cell,
    fill_collision,
    tile_is_sky,
    type_id_chr,
    type_id_ladder,
    type_id_prefab,
    type_id_stile,
)

ROOT = Path(__file__).resolve().parents[2]
DISASM = ROOT / "assets" / "reference" / "original" / "s2" / "ms0515-various" / "SABOT2-DISASM"
ROOM_MAC = DISASM / "S2ROOM.MAC"
TILE_MAC = DISASM / "S2TILE.MAC"
CORE_MAC = DISASM / "S2CORE.MAC"
CORE_TEMPLATES = (
    DISASM / "S217E6.MAC",
    DISASM / "S21E80.MAC",
    DISASM / "S2CORE.MAC",
)


@dataclass
class RoomObject:
    kind: str
    type_id: str
    layer: int
    collision: str
    mode: str  # module_repeat | prefab
    x: int
    y: int
    w: int
    h: int
    tile: int = -1
    tiles: tuple[int, ...] = ()
    module: tuple[int, int] = (CELL, CELL)
    axis: str = "xy"


def load_stiles() -> list[list[int]]:
    ordered: list[list[int]] = []
    grab = False
    acc: list[int] = []
    for raw in TILE_MAC.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if line.startswith("STILES:"):
            grab = True
            continue
        if not grab:
            continue
        if line.startswith("K23030:") or line.startswith("; Stashes") or line.startswith(";   +000"):
            if acc:
                ordered.append(acc[:48])
            break
        if ":" in line and line[0] == "K" and ".BYTE" in line.upper():
            if acc:
                ordered.append(acc[:48])
            acc = parse_octal_tokens(line.split(".BYTE", 1)[-1])
            continue
        if line.endswith(":") and line[0] == "K":
            if acc:
                ordered.append(acc[:48])
            acc = []
            continue
        if ".BYTE" in line.upper():
            acc.extend(parse_octal_tokens(line.split(".BYTE", 1)[-1]))
    if acc:
        ordered.append(acc[:48])
    return [s for s in ordered if len(s) >= 48][:25]


def load_rooms() -> list[list[int]]:
    labels = parse_word_table(ROOM_MAC, "K72572")
    if not labels:
        labels = parse_word_table(ROOM_MAC, "ROOMSA")
    blocks = parse_mac_bytes(ROOM_MAC)
    # ROOMSA words are addresses; match by collecting sequences in file order.
    seqs: list[list[int]] = []
    grab = False
    current: list[int] = []
    for raw in ROOM_MAC.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.split(";", 1)[0].rstrip()
        line = stripped.strip()
        if line.startswith("ROOMS:") or line.startswith("K55764:"):
            grab = True
        if line.startswith("SMAP:") or line.startswith("K70572:"):
            if current:
                seqs.append(current)
            break
        if not grab:
            continue
        if ":" in line and line[0].isalnum() and ".BYTE" in line.upper():
            name, rest = line.split(":", 1)
            if name[0] in "KL" or name.startswith("K") or name[0].isalpha():
                if current:
                    seqs.append(current)
                current = []
                if ".BYTE" in rest.upper():
                    current.extend(parse_octal_tokens(rest.split(".BYTE", 1)[-1]))
                continue
        if line.endswith(":") and ".BYTE" not in line.upper() and line[0].isalnum():
            if current:
                seqs.append(current)
            current = []
            continue
        if ".BYTE" in line.upper():
            current.extend(parse_octal_tokens(line.split(".BYTE", 1)[-1]))
    if current:
        seqs.append(current)
    # First sequence is room 0 (K55764). Keep 246.
    return seqs[:246]


def load_smap() -> list[list[int]]:
    """World grid indexed as [RMDN][RMAC], 32 columns × 32 levels.

    The engine (S2CORE K13332): RMDN==0 does not read MAP and always uses
    ROOMSA[0] (sky). MAP itself is 32×31 at K70632. ms0515 labels K70572
    32 bytes earlier — leftover tiles + rocket, not a map row.
    A MAP byte of 0 is room 0, not an empty hole.
    """
    grab = False
    vals: list[int] = []
    for raw in ROOM_MAC.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if line.startswith("K70632:"):
            grab = True
            rest = line.split(":", 1)[-1].strip() if ":" in line else ""
            if ".BYTE" in rest.upper():
                vals.extend(parse_octal_tokens(rest.split(".BYTE", 1)[-1]))
            continue
        if line.startswith("SMAP:") or line.startswith("K70572:"):
            grab = True
            rest = line.split(":", 1)[-1].strip() if ":" in line else ""
            if ".BYTE" in rest.upper():
                vals.extend(parse_octal_tokens(rest.split(".BYTE", 1)[-1]))
            continue
        if grab:
            if line.startswith("ROOMSA:") or line.startswith("K72572:"):
                break
            if ".BYTE" in line.upper():
                vals.extend(parse_octal_tokens(line.split(".BYTE", 1)[-1]))
    # K70572 prefix is 32 bytes; K70632 is already MAP. Detect by row signature.
    map_row0 = [0, 0, 0, 0, 0, 0, 0, 0o144, 0o145, 0o023, 0, 0, 0, 0, 0o210, 0]
    off = 0
    for i in range(0, max(0, len(vals) - MAP_W + 1), MAP_W):
        if vals[i : i + 16] == map_row0:
            off = i
            break
    body = vals[off:]
    grid = [body[i : i + MAP_W] for i in range(0, MAP_ROWS * MAP_W, MAP_W)]
    grid = [(row + [0] * MAP_W)[:MAP_W] for row in grid[:MAP_ROWS]]
    while len(grid) < MAP_ROWS:
        grid.append([0] * MAP_W)
    sky = [[0] * MAP_W]
    world = sky + grid
    return world[:WORLD_ROWS]


def load_templates() -> None:
    merged: dict[str, list[int]] = {}
    for path in CORE_TEMPLATES:
        if path.exists():
            merged.update(parse_mac_bytes(path))
    for label, ops in TEMPLATE_LABELS.items():
        data = merged.get(label, [])
        for op in ops:
            apply_template_bytes(op, data)


def _word(seq: list[int], i: int) -> int:
    return (seq[i] | (seq[i + 1] << 8)) & 0xFFFF


def _stamp_fill(buf: list[int], col: int, row: int, tile: int, count: int, stride: int) -> None:
    idx = row * ROOM_COLS + col
    for _ in range(count):
        if 0 <= idx < len(buf):
            buf[idx] = tile
        idx += stride


def _rect_from_cells(cells: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [c for c, _ in cells]
    ys = [r for _, r in cells]
    x0, y0 = min(xs), min(ys)
    return x0 * CELL, y0 * CELL, (max(xs) - x0 + 1) * CELL, (max(ys) - y0 + 1) * CELL


def _stride1_runs(col: int, row: int, count: int, buf: list[int], tile: int) -> list[list[tuple[int, int]]]:
    """Stamp consecutive tiles; split when the run wraps to the next row."""
    runs: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    idx = row * ROOM_COLS + col
    for _ in range(count):
        if 0 <= idx < len(buf):
            buf[idx] = tile
            c, r = idx % ROOM_COLS, idx // ROOM_COLS
            if current and (r != current[-1][1] or c != current[-1][0] + 1):
                runs.append(current)
                current = []
            current.append((c, r))
        idx += 1
    if current:
        runs.append(current)
    return runs


def _emit_fill(kind: str, tile: int) -> bool:
    """Tile 001 is sky paper: write the buffer, but it is not a structure object."""
    if kind == "fill_room":
        return True
    return tile != 1


def interpret_room(seq: list[int]) -> tuple[list[RoomObject], list[int]]:
    """Return objects and the 32×18 back-buffer tile indices."""
    buf = [1] * (ROOM_COLS * ROOM_ROWS)  # default paper; $03 overwrites
    objs: list[RoomObject] = []
    i = 0
    n = len(seq)
    while i < n:
        op = seq[i]
        if op == SKIP_TILE:
            break
        i += 1
        m = MARKERS.get(op)
        if m is None:
            break
        kind = m.consume
        if kind == "none":
            continue
        if kind == "fill_room":
            if i >= n:
                break
            tile = seq[i]
            i += 1
            for k in range(len(buf)):
                buf[k] = tile
            objs.append(
                RoomObject(
                    kind="fill_room",
                    type_id=type_id_chr(tile),
                    layer=SKY if tile_is_sky(tile) else m.layer,
                    collision="none",
                    mode="module_repeat",
                    x=0,
                    y=0,
                    w=SCREEN_W,
                    h=PLAYFIELD_H,
                    tile=tile,
                    module=(CELL, CELL),
                )
            )
            continue
        if kind == "fill_h":
            if i + 3 >= n:
                break
            count, tile, dest = seq[i], seq[i + 1], _word(seq, i + 2)
            i += 4
            col, row = dest_to_cell(dest)
            for cells in _stride1_runs(col, row, count, buf, tile):
                if not _emit_fill("fill_h", tile):
                    continue
                x, y, w, h = _rect_from_cells(cells)
                cw = max(c[0] for c in cells) - min(c[0] for c in cells) + 1
                ch = max(c[1] for c in cells) - min(c[1] for c in cells) + 1
                objs.append(
                    RoomObject(
                        "fill_h",
                        type_id_chr(tile),
                        m.layer,
                        fill_collision(cw, ch),
                        "module_repeat",
                        x,
                        y,
                        w,
                        h,
                        tile=tile,
                        module=(CELL, CELL),
                        axis="x",
                    )
                )
            continue
        if kind == "fill_v":
            if i + 3 >= n:
                break
            count, tile, dest = seq[i], seq[i + 1], _word(seq, i + 2)
            i += 4
            col, row = dest_to_cell(dest)
            _stamp_fill(buf, col, row, tile, count, ROOM_COLS)
            if _emit_fill("fill_v", tile):
                objs.append(
                    RoomObject(
                        "fill_v",
                        type_id_chr(tile),
                        m.layer,
                        "solid",
                        "module_repeat",
                        col * CELL,
                        row * CELL,
                        CELL,
                        count * CELL,
                        tile=tile,
                        module=(CELL, CELL),
                        axis="y",
                    )
                )
            continue
        if kind == "fill_rect":
            if i + 4 >= n:
                break
            w, h, tile, dest = seq[i], seq[i + 1], seq[i + 2], _word(seq, i + 3)
            i += 5
            col, row = dest_to_cell(dest)
            for dy in range(h):
                for dx in range(w):
                    idx = (row + dy) * ROOM_COLS + (col + dx)
                    if 0 <= idx < len(buf):
                        buf[idx] = tile
            if _emit_fill("fill_rect", tile):
                objs.append(
                    RoomObject(
                        "fill_rect",
                        type_id_chr(tile),
                        m.layer,
                        fill_collision(w, h),
                        "module_repeat",
                        col * CELL,
                        row * CELL,
                        w * CELL,
                        h * CELL,
                        tile=tile,
                        module=(CELL, CELL),
                    )
                )
            continue
        if kind == "fill_one":
            if i + 2 >= n:
                break
            tile, dest = seq[i], _word(seq, i + 1)
            i += 3
            col, row = dest_to_cell(dest)
            idx = row * ROOM_COLS + col
            if 0 <= idx < len(buf):
                buf[idx] = tile
            if _emit_fill("fill_one", tile):
                objs.append(
                    RoomObject(
                        "fill_one",
                        type_id_chr(tile),
                        m.layer,
                        "floor",
                        "prefab",
                        col * CELL,
                        row * CELL,
                        CELL,
                        CELL,
                        tile=tile,
                        module=(CELL, CELL),
                    )
                )
            continue
        if kind in ("diag_rd", "diag_ld"):
            if i + 3 >= n:
                break
            count, tile, dest = seq[i], seq[i + 1], _word(seq, i + 2)
            i += 4
            stride = 33 if kind == "diag_rd" else 31
            col, row = dest_to_cell(dest)
            _stamp_fill(buf, col, row, tile, count, stride)
            objs.append(
                RoomObject(
                    kind,
                    type_id_chr(tile),
                    m.layer,
                    "solid",
                    "module_repeat",
                    col * CELL,
                    row * CELL,
                    CELL,
                    count * CELL,
                    tile=tile,
                    module=(CELL, CELL),
                    axis="y",
                )
            )
            continue
        if kind == "triangle":
            if i + 3 >= n:
                break
            count, tile, dest = seq[i], seq[i + 1], _word(seq, i + 2)
            i += 4
            col, row = dest_to_cell(dest)
            stride = m.triangle_stride
            width = count
            cells: list[tuple[int, int]] = []
            idx = row * ROOM_COLS + col
            for _ in range(count):
                for dx in range(max(width, 0)):
                    p = idx + dx
                    if 0 <= p < len(buf):
                        buf[p] = tile
                        cells.append((p % ROOM_COLS, p // ROOM_COLS))
                idx += stride
                width -= 1
            if cells:
                x, y, w, h = _rect_from_cells(cells)
                objs.append(
                    RoomObject(
                        "triangle",
                        type_id_chr(tile),
                        m.layer,
                        "solid",
                        "module_repeat",
                        x,
                        y,
                        w,
                        h,
                        tile=tile,
                        module=(CELL, CELL),
                    )
                )
            continue
        if kind == "ladder":
            if i + 2 >= n:
                break
            height, dest = seq[i], _word(seq, i + 1)
            i += 3
            tile0 = m.ladder_tile
            col, row = dest_to_cell(dest)
            for dy in range(height):
                for dx, t in enumerate((tile0, tile0 + 1)):
                    idx = (row + dy) * ROOM_COLS + (col + dx)
                    if 0 <= idx < len(buf):
                        buf[idx] = t
            objs.append(
                RoomObject(
                    "ladder",
                    type_id_ladder(op),
                    m.layer,
                    "climb",
                    "module_repeat",
                    col * CELL,
                    row * CELL,
                    2 * CELL,
                    height * CELL,
                    tile=tile0,
                    tiles=(tile0, tile0 + 1),
                    module=(2 * CELL, CELL),
                    axis="y",
                )
            )
            continue
        if kind == "joint":
            if i + 1 >= n:
                break
            dest = _word(seq, i)
            i += 2
            col, row = dest_to_cell(dest)
            for dx, t in enumerate((0o312, 0o313)):
                idx = row * ROOM_COLS + col + dx
                if 0 <= idx < len(buf):
                    buf[idx] = t
            objs.append(
                RoomObject(
                    "joint",
                    "ladder_joint",
                    m.layer,
                    "climb",
                    "prefab",
                    col * CELL,
                    row * CELL,
                    2 * CELL,
                    CELL,
                    tiles=(0o312, 0o313),
                )
            )
            continue
        if kind == "stile":
            stiles = interpret_room.stiles  # type: ignore[attr-defined]
            ids = seq[i : i + 12]
            i += 12
            if len(ids) < 12:
                break
            for nstile, sid in enumerate(ids):
                if sid >= len(stiles):
                    continue
                data = stiles[sid]
                sx, sy = (nstile % 4) * 8, (nstile // 4) * 6
                for ty in range(6):
                    for tx in range(8):
                        buf[(sy + ty) * ROOM_COLS + (sx + tx)] = data[ty * 8 + tx]
                objs.append(
                    RoomObject(
                        "stile",
                        type_id_stile(sid),
                        m.layer,
                        "solid",
                        "prefab",
                        sx * CELL,
                        sy * CELL,
                        8 * CELL,
                        6 * CELL,
                        tile=sid,
                        tiles=tuple(data[:48]),
                    )
                )
            continue
        if kind in ("fixed", "dest"):
            pf = m.prefab
            if pf is None:
                continue
            dest = pf.dest
            if kind == "dest":
                if i + 1 >= n:
                    break
                dest = _word(seq, i)
                i += 2
            if dest is None:
                continue
            col, row = dest_to_cell(dest)
            tiles = pf.tiles
            cells: list[tuple[int, int]] = []
            for dy in range(pf.h):
                for dx in range(pf.w):
                    t = tiles[dy * pf.w + dx] if tiles else SKIP_TILE
                    idx = (row + dy) * ROOM_COLS + (col + dx)
                    if 0 <= idx < len(buf) and t != SKIP_TILE:
                        buf[idx] = t
                        cells.append((col + dx, row + dy))
            if not cells and not tiles:
                cells = [(col + dx, row + dy) for dy in range(pf.h) for dx in range(pf.w)]
            if cells:
                x, y, w, h = _rect_from_cells(cells)
                objs.append(
                    RoomObject(
                        m.name,
                        type_id_prefab(op) if pf.name else type_id_prefab(op),
                        pf.layer,
                        pf.collision,
                        "prefab",
                        x,
                        y,
                        w,
                        h,
                        tiles=tiles,
                    )
                )
            continue
        break
    return objs, buf


interpret_room.stiles = []  # type: ignore[attr-defined]


def prepare() -> None:
    load_templates()
    interpret_room.stiles = load_stiles()  # type: ignore[attr-defined]


def room_objects_for_world(objs: list[RoomObject]) -> list[RoomObject]:
    """Drop flip-screen stamps that must exist once in the continuous world."""
    return [o for o in objs if o.type_id not in WORLD_UNIQUE_TYPES]


def is_cave_room(objs: list[RoomObject]) -> bool:
    return any(o.kind == "stile" for o in objs)


def _has_indoor_contents(objs: list[RoomObject]) -> bool:
    for o in objs:
        if o.type_id == "ladder_green":
            return True
        if any(o.type_id.startswith(p) for p in INDOOR_TYPE_PREFIXES):
            return True
    return False


def _has_windows(objs: list[RoomObject]) -> bool:
    return any("window" in o.type_id for o in objs)


def _has_structure_shell(objs: list[RoomObject]) -> bool:
    return any(o.kind in ("fill_h", "fill_v", "fill_one", "fill_rect") for o in objs)


def _has_sky_paper(objs: list[RoomObject]) -> bool:
    return any(o.kind == "fill_room" and tile_is_sky(o.tile) for o in objs)


def _is_sky_cutout(objs: list[RoomObject]) -> bool:
    """Landscape slope stamped with sky/empty tiles — a hole, not a green room."""
    return any(o.layer == EARTH and tile_is_sky(o.tile) for o in objs)


def is_bare_sky(objs: list[RoomObject]) -> bool:
    """Room 0 / empty sky: only sky paper and the moon stamp."""
    if is_cave_room(objs) or not objs:
        return False
    for o in objs:
        if o.type_id == "moon":
            continue
        if o.kind == "fill_room" and tile_is_sky(o.tile):
            continue
        return False
    return True


def is_outdoor_room(objs: list[RoomObject]) -> bool:
    """Sky paper: trees, rooftops, or a sky-tile cutout that is not an interior."""
    if is_cave_room(objs) or is_bare_sky(objs):
        return False
    if _has_indoor_contents(objs):
        return False
    if any(any(o.type_id.startswith(p) for p in OUTDOOR_TYPE_PREFIXES) for o in objs):
        return True
    if _has_sky_paper(objs):
        return True
    # Brick triangles are building fabric. Sky-tile earth without windows is a courtyard.
    if _is_sky_cutout(objs) and not _has_windows(objs):
        return True
    return False


def _facade_walls(objs: list[RoomObject]) -> list[RoomObject]:
    return [
        o
        for o in objs
        if o.kind in ("fill_rect", "fill_v")
        and o.h >= PLAYFIELD_H // 2
        and o.w <= 2 * CELL
    ]


def _is_facade_shell(objs: list[RoomObject]) -> bool:
    """Tall thin wall with few floors: the outer face, not a wallpapered room."""
    if _has_windows(objs) or _has_indoor_contents(objs):
        return False
    if not _facade_walls(objs):
        return False
    wide_floors = [o for o in objs if o.kind == "fill_h" and o.w >= SCREEN_W // 2]
    return len(wide_floors) <= 2


def is_indoor_room(objs: list[RoomObject]) -> bool:
    """Furniture, or a window/wall shell that the original paints with indoor paper."""
    if is_cave_room(objs) or is_outdoor_room(objs):
        return False
    if _has_indoor_contents(objs):
        return True
    if _has_windows(objs):
        return True
    if _is_facade_shell(objs):
        return False
    return _has_structure_shell(objs)


def is_generic_interior(objs: list[RoomObject]) -> bool:
    """Room 1: floors, windows, a green ladder. No furniture — cave MAP filler.

    Floor-only shells are real building fabric and must stay placed.
    """
    if not is_indoor_room(objs):
        return False
    if not any(o.type_id == "ladder_green" for o in objs):
        return False
    for o in objs:
        if o.type_id == "moon":
            continue
        if o.kind in ("fill_h", "fill_v", "fill_one", "fill_rect", "ladder"):
            continue
        if o.type_id.startswith("window") or o.type_id.startswith("chr_"):
            continue
        return False
    return True


def _smap_kinds(smap: list[list[int]], rooms: list[list[int]]) -> list[list[str]]:
    h, w = len(smap), len(smap[0]) if smap else 0
    kind = [["sky"] * w for _ in range(h)]
    for my, row in enumerate(smap):
        for mx, rid in enumerate(row):
            if rid < 0 or rid >= len(rooms):
                continue
            objs, _ = interpret_room(rooms[rid])
            if is_cave_room(objs):
                kind[my][mx] = "cave"
            elif is_outdoor_room(objs):
                kind[my][mx] = "outdoor"
            elif is_indoor_room(objs):
                kind[my][mx] = "indoor"
            elif not is_bare_sky(objs):
                kind[my][mx] = "outdoor"
    return kind


def _has_furniture(objs: list[RoomObject]) -> bool:
    return any(any(o.type_id.startswith(p) for p in INDOOR_TYPE_PREFIXES) for o in objs)


def reachable_indoor_mask(smap: list[list[int]], rooms: list[list[int]]) -> list[list[bool]]:
    """True for generic interiors that share a 4-block with furniture/doors.

    Cave MAP repeats room 1 in black void. Those islands touch outdoor shafts
    but have no walk-in from the building, and the mosaic leaves them empty.
    Floor-only shells are indoor paper, not a bridge into that void.
    """
    kind = _smap_kinds(smap, rooms)
    h, w = len(kind), len(kind[0]) if kind else 0
    generic = [[False] * w for _ in range(h)]
    real = [[False] * w for _ in range(h)]
    for my, row in enumerate(smap):
        for mx, rid in enumerate(row):
            if kind[my][mx] != "indoor" or rid < 0 or rid >= len(rooms):
                continue
            objs, _ = interpret_room(rooms[rid])
            if is_generic_interior(objs):
                generic[my][mx] = True
            elif _has_furniture(objs):
                real[my][mx] = True
    keep = [row[:] for row in real]
    seen = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not real[y][x] or seen[y][x]:
                continue
            q = [(x, y)]
            seen[y][x] = True
            i = 0
            while i < len(q):
                cx, cy = q[i]
                i += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if not (0 <= nx < w and 0 <= ny < h) or seen[ny][nx]:
                        continue
                    if not (real[ny][nx] or generic[ny][nx]):
                        continue
                    seen[ny][nx] = True
                    q.append((nx, ny))
                    if generic[ny][nx]:
                        keep[ny][nx] = True
    return keep


def make_sky_fill() -> RoomObject:
    return RoomObject(
        kind="fill_room",
        type_id=type_id_chr(1),
        layer=SKY,
        collision="none",
        mode="module_repeat",
        x=0,
        y=0,
        w=SCREEN_W,
        h=PLAYFIELD_H,
        tile=1,
        module=(CELL, CELL),
    )


def make_wallpaper(x: int = 0, y: int = 0, w: int = SCREEN_W, h: int = PLAYFIELD_H) -> RoomObject:
    return RoomObject(
        kind="fill_room",
        type_id=WALLPAPER_TYPE,
        layer=INTERIOR,
        collision="none",
        mode="module_repeat",
        x=x,
        y=y,
        w=w,
        h=h,
        tile=-1,
        module=(CELL, CELL),
    )


def apply_indoor_wallpaper(objs: list[RoomObject]) -> list[RoomObject]:
    """Sky-paper fill becomes indoor brick paper; rooms without a fill get one."""
    out: list[RoomObject] = []
    replaced = False
    for o in objs:
        if o.kind == "fill_room" and tile_is_sky(o.tile):
            out.append(make_wallpaper(o.x, o.y, o.w, o.h))
            replaced = True
        else:
            out.append(o)
    if not replaced:
        out.insert(0, make_wallpaper())
    return out


def ensure_sky_fill(objs: list[RoomObject]) -> list[RoomObject]:
    if any(o.kind == "fill_room" for o in objs):
        return objs
    return [make_sky_fill(), *objs]


def apply_facade_paper(objs: list[RoomObject]) -> list[RoomObject]:
    """Sky outside a facade wall, indoor brick on the interior side.

    Floor strips that the template wrapped across the sky are clipped so the
    outer face matches the original silhouette.
    """
    walls = _facade_walls(objs)
    wall = walls[0]
    wr = wall.x + wall.w
    left = 0
    right = 0
    for o in objs:
        if o.kind not in ("fill_h", "fill_rect", "fill_one"):
            continue
        if o.w >= SCREEN_W - CELL:
            continue
        if o.x >= wr:
            right += o.w * o.h
        elif o.x + o.w <= wall.x:
            left += o.w * o.h
    if right >= left:
        x0, x1 = wr, SCREEN_W
    else:
        x0, x1 = 0, wall.x
    out: list[RoomObject] = [make_sky_fill()]
    if x1 > x0:
        out.append(make_wallpaper(x0, 0, x1 - x0, PLAYFIELD_H))
    wall_ids = {id(o) for o in walls}
    for o in objs:
        if o.kind == "fill_room":
            continue
        if id(o) in wall_ids:
            out.append(o)
            continue
        if o.kind in ("fill_h", "fill_rect", "fill_one"):
            clipped = _clip_x(o, x0, x1)
            if clipped is not None:
                out.append(clipped)
            continue
        out.append(o)
    return out


def _clip_x(o: RoomObject, x0: int, x1: int) -> RoomObject | None:
    nx = max(o.x, x0)
    nx1 = min(o.x + o.w, x1)
    if nx1 <= nx:
        return None
    if nx == o.x and nx1 == o.x + o.w:
        return o
    return RoomObject(
        o.kind,
        o.type_id,
        o.layer,
        o.collision,
        o.mode,
        nx,
        o.y,
        nx1 - nx,
        o.h,
        o.tile,
        o.tiles,
        o.module,
        o.axis,
    )


def apply_room_paper(objs: list[RoomObject], force_indoor: bool = False) -> list[RoomObject]:
    """Green brick wallpaper is interior only. Caves keep stiles. Outdoor keeps sky paper."""
    if is_cave_room(objs):
        return [o for o in objs if not (o.kind == "fill_room" and tile_is_sky(o.tile))]
    if is_outdoor_room(objs):
        return ensure_sky_fill(objs)
    if force_indoor or is_indoor_room(objs):
        return apply_indoor_wallpaper(objs)
    if _is_facade_shell(objs):
        return apply_facade_paper(objs)
    return ensure_sky_fill(objs)


def _with_ladder_span(o: RoomObject, y0: int, y1: int) -> RoomObject:
    if y0 == o.y and y1 == o.y + o.h:
        return o
    return RoomObject(
        o.kind,
        o.type_id,
        o.layer,
        o.collision,
        o.mode,
        o.x,
        y0,
        o.w,
        y1 - y0,
        o.tile,
        o.tiles,
        o.module,
        o.axis,
    )


def snap_ladders(objs: list[RoomObject]) -> list[RoomObject]:
    """Flip-screen shafts stop short of the HUD; stack them to the playfield seam.

    Do not punch through a floor/joint already in this room.
    """
    platforms = [
        o
        for o in objs
        if o.collision in ("floor", "solid") and o.h <= 4 * CELL and o.w >= CELL
    ]
    out: list[RoomObject] = []
    for o in objs:
        if o.kind != "ladder":
            out.append(o)
            continue
        y0, y1 = o.y, o.y + o.h
        hits_top = any(
            _x_overlap(o, p) and y0 - 2 * CELL <= p.y + p.h <= y0 + CELL for p in platforms
        )
        hits_bot = any(
            _x_overlap(o, p) and y1 - CELL <= p.y <= y1 + 3 * CELL for p in platforms
        )
        if y0 <= 2 * CELL and not hits_top:
            y0 = 0
        if y1 >= PLAYFIELD_H - 3 * CELL and not hits_bot:
            y1 = PLAYFIELD_H
        out.append(_with_ladder_span(o, y0, y1))
    return out


def _x_overlap(a: RoomObject, b: RoomObject, pad: int = 0) -> bool:
    return a.x < b.x + b.w + pad and b.x < a.x + a.w + pad


def connect_ladders(instances: list[RoomObject], snap: int = 5 * CELL) -> list[RoomObject]:
    """Stretch mid-building shafts to the nearest floor/ceiling instead of stopping short.

    Full-screen outdoor shafts already meet the playfield seam — leave them.
    """
    platforms = [
        o
        for o in instances
        if o.collision in ("floor", "solid") and o.h <= 4 * CELL and o.w >= CELL
    ]
    out: list[RoomObject] = []
    for o in instances:
        if o.kind != "ladder":
            out.append(o)
            continue
        y0, y1 = o.y, o.y + o.h
        best_up: int | None = None
        best_down: int | None = None
        at_top_seam = y0 % PLAYFIELD_H == 0
        at_bot_seam = y1 % PLAYFIELD_H == 0
        for p in platforms:
            if not _x_overlap(o, p):
                continue
            pbot = p.y + p.h
            gap_up = y0 - pbot
            if not at_top_seam and 0 <= gap_up <= snap and (best_up is None or pbot > best_up):
                best_up = pbot
            gap_down = p.y - y1
            if not at_bot_seam and 0 <= gap_down <= snap and (best_down is None or p.y < best_down):
                best_down = p.y
        if best_up is not None:
            y0 = best_up
        if best_down is not None:
            y1 = best_down
        out.append(_with_ladder_span(o, y0, y1))
    return out


def indoor_force_mask(smap: list[list[int]], rooms: list[list[int]]) -> list[list[bool]]:
    """Sky templates sitting in a hole in the building get interior paper."""
    kind = _smap_kinds(smap, rooms)
    h, w = len(kind), len(kind[0]) if kind else 0
    reached = [[False] * w for _ in range(h)]
    q: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            edge = y in (0, h - 1) or x in (0, w - 1)
            if edge and kind[y][x] in ("sky", "outdoor"):
                reached[y][x] = True
                q.append((x, y))
    i = 0
    while i < len(q):
        x, y = q[i]
        i += 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not reached[ny][nx] and kind[ny][nx] in ("sky", "outdoor"):
                reached[ny][nx] = True
                q.append((nx, ny))
    force = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if kind[y][x] != "sky":
                continue
            if not reached[y][x]:
                force[y][x] = True
                continue
            n = 0
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and kind[ny][nx] == "indoor":
                    n += 1
            if n >= 2:
                force[y][x] = True
    return force


def unique_world_objects(rooms: list[list[int]]) -> list[RoomObject]:
    """Place WORLD_UNIQUE_TYPES once, at the engine start screen."""
    if not rooms:
        return []
    objs, _ = interpret_room(rooms[0])
    once = [o for o in objs if o.type_id in WORLD_UNIQUE_TYPES]
    return place_world(once, START_RMAC, START_RMDN)


def place_world(objs: list[RoomObject], mx: int, my: int) -> list[RoomObject]:
    ox, oy = mx * SCREEN_W, my * PLAYFIELD_H
    out: list[RoomObject] = []
    for o in objs:
        out.append(
            RoomObject(
                o.kind,
                o.type_id,
                o.layer,
                o.collision,
                o.mode,
                o.x + ox,
                o.y + oy,
                o.w,
                o.h,
                o.tile,
                o.tiles,
                o.module,
                o.axis,
            )
        )
    return out
