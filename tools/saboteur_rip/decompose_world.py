#!/usr/bin/python3
"""Decompose the original Saboteur II world into a typed object registry.

Source of truth: S2ROOM.MAC room sequences + S2CORE marker table + BCHRS.
The screenshot mosaic is only used to verify reconstruction and to crop
prefab pixels when a ROM tile list is empty.
"""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from macparse import parse_mac_bytes
from opcode_catalog import (
    CELL,
    EMPTY_TILES,
    LAYER_NAMES,
    LAYER_Z,
    MAP_W,
    PLAYFIELD_H,
    ROOM_COLS,
    ROOM_ROWS,
    SCREEN_H,
    SCREEN_W,
    SKIP_TILE,
    SKY_TILES,
    WALLPAPER_TILE,
    WALLPAPER_TYPE,
    WALLPAPER_Z,
    WORLD_ROWS,
)
from room_bytecode import (
    DISASM,
    RoomObject,
    interpret_room,
    load_rooms,
    load_smap,
    place_world,
    prepare,
    apply_room_paper,
    connect_ladders,
    indoor_force_mask,
    is_generic_interior,
    reachable_indoor_mask,
    room_objects_for_world,
    snap_ladders,
    unique_world_objects,
)

OUT = ROOT / "assets" / "world"
OBJECTS_DIR = OUT / "objects"
MOSAIC = ROOT / "assets" / "reference" / "original" / "maps" / "Saboteur2_speccy.png"
SPRT = DISASM / "S2SPRT.MAC"
OCHRS_MAC = DISASM / "S242E2.MAC"
SCALE = 2
# Interior overlay: desk/chair stamps on top of room paper (not wallpaper pixels).
DESK_TYPE = "desk"
ZX_PAPER_GREEN = ((0, 206, 0, 255), (0, 255, 0, 255))
ZX_BLACK = (0, 0, 0, 255)
# BOX1C / BOX4C stamps (tiles 002–012) are OCHRS crate glyphs, not BCHRS.
BOX_TILES = frozenset(range(2, 11))

SPEC_PAL = [
    (0, 0, 0),
    (0, 0, 206),
    (206, 0, 0),
    (206, 0, 206),
    (0, 206, 0),
    (0, 206, 206),
    (206, 206, 0),
    (206, 206, 206),
    (0, 0, 0),
    (0, 0, 255),
    (255, 0, 0),
    (255, 0, 255),
    (0, 255, 0),
    (0, 255, 255),
    (255, 255, 0),
    (255, 255, 255),
]


def spec_color(attr: int, ink: bool) -> tuple[int, int, int, int]:
    bright = (attr >> 6) & 1
    idx = ((attr & 7) if ink else ((attr >> 3) & 7)) + (8 if bright else 0)
    r, g, b = SPEC_PAL[idx]
    return (r, g, b, 255)


def load_ochrs() -> list[bytes]:
    """OCHRS: 8 mask/pixel pairs + attr. Crate glyphs live here (S242E2.MAC)."""
    blocks = parse_mac_bytes(OCHRS_MAC)
    keys = sorted(
        (k for k in blocks if k[:1] in "KL" and k[1:].isdigit()),
        key=lambda k: int(k[1:], 8),
    )
    tiles: list[bytes] = []
    for k in keys:
        raw = blocks[k]
        if len(raw) >= 17:
            tiles.append(bytes(raw[:17]))
    return tiles


def render_ochrs(tile17: bytes) -> Image.Image:
    pix = bytes(tile17[y * 2 + 1] for y in range(8))
    attr = tile17[16]
    # Mosaic / Spectrum display uses the bright palette for yellow crate paper.
    if ((attr >> 3) & 7) == 6:
        attr |= 0o100
    return render_bchr(pix + bytes([attr]))


def load_bchrs() -> list[bytes]:
    blocks = parse_mac_bytes(SPRT)
    bchrs: list[bytes] = []
    for key in sorted(k for k in blocks if k >= "K77531"):
        block = blocks[key]
        if len(block) == 9:
            bchrs.append(bytes(block))
        elif len(block) >= 9 and len(block) % 9 == 0:
            for i in range(0, len(block), 9):
                bchrs.append(bytes(block[i : i + 9]))
    return bchrs


def render_bchr(tile9: bytes, attr: int | None = None) -> Image.Image:
    pix = tile9[:8]
    a = attr if attr is not None else (tile9[8] if len(tile9) > 8 else 0)
    img = Image.new("RGBA", (CELL, CELL), spec_color(a, False))
    ink = spec_color(a, True)
    for y, raw in enumerate(pix[:8]):
        for x in range(CELL):
            if (raw >> (7 - x)) & 1:
                img.putpixel((x, y), ink)
    return img


def blit_tiles(
    tiles: list[int],
    w: int,
    h: int,
    bchrs: list[Image.Image],
    skip_sky: bool = False,
    cells: list[Image.Image] | None = None,
) -> Image.Image:
    src = cells if cells is not None else bchrs
    img = Image.new("RGBA", (w * CELL, h * CELL), (0, 0, 0, 0))
    n = len(src)
    for ty in range(h):
        for tx in range(w):
            t = tiles[ty * w + tx] if ty * w + tx < len(tiles) else SKIP_TILE
            if t == SKIP_TILE or t >= n:
                continue
            if skip_sky and t in SKY_TILES:
                continue
            img.paste(src[t], (tx * CELL, ty * CELL), src[t])
    return img


def is_box_prefab(o: RoomObject) -> bool:
    """BOX1C/BOX4C stamps: tiles 002–012 only (not fill_v chr_002 walls)."""
    if o.mode != "prefab" or not o.tiles:
        return False
    used = {t for t in o.tiles if t != SKIP_TILE}
    return bool(used) and used <= BOX_TILES


def apply_hatches(solid: list[list[int]], ladder: list[list[int]]) -> None:
    ch = len(solid)
    cw = len(solid[0]) if ch else 0
    lids: list[tuple[int, int]] = []
    for y in range(ch):
        for x in range(cw):
            if not ladder[y][x]:
                continue
            for dx in (-1, 1):
                nx = x + dx
                if 0 <= nx < cw and solid[y][nx] and not ladder[y][nx]:
                    lids.append((x, y))
                    break
    for x, y in lids:
        solid[y][x] = 1


def greedy_rects(grid: list[list[int]]) -> list[list[int]]:
    h = len(grid)
    w = len(grid[0]) if h else 0
    seen = [[False] * w for _ in range(h)]
    rects: list[list[int]] = []
    for y in range(h):
        for x in range(w):
            if not grid[y][x] or seen[y][x]:
                continue
            x1 = x
            while x1 < w and grid[y][x1] and not seen[y][x1]:
                x1 += 1
            y1 = y + 1
            grow = True
            while y1 < h and grow:
                for xx in range(x, x1):
                    if not grid[y1][xx] or seen[y1][xx]:
                        grow = False
                        break
                if grow:
                    y1 += 1
            for yy in range(y, y1):
                for xx in range(x, x1):
                    seen[yy][xx] = True
            rects.append([x * CELL, y * CELL, (x1 - x) * CELL, (y1 - y) * CELL])
    return rects


def stamp_world(
    instances: list[RoomObject], map_w: int, map_h: int
) -> tuple[list[list[int]], list[list[int]]]:
    cw, ch = map_w * ROOM_COLS, map_h * ROOM_ROWS
    solid = [[0] * cw for _ in range(ch)]
    climb = [[0] * cw for _ in range(ch)]
    for o in instances:
        x0, y0 = o.x // CELL, o.y // CELL
        tw, th = max(o.w // CELL, 1), max(o.h // CELL, 1)
        kind = o.collision
        if kind == "none" or kind == "machine":
            continue
        for dy in range(th):
            for dx in range(tw):
                cx, cy = x0 + dx, y0 + dy
                if not (0 <= cx < cw and 0 <= cy < ch):
                    continue
                if kind == "floor":
                    if dy == 0:
                        solid[cy][cx] = 1
                elif kind == "solid":
                    if o.tiles:
                        tx = dx if dx < (o.w // CELL) else 0
                        ty = dy if dy < (o.h // CELL) else 0
                        twid = o.w // CELL
                        ti = ty * twid + tx
                        t = o.tiles[ti] if ti < len(o.tiles) else SKIP_TILE
                        if t not in EMPTY_TILES:
                            solid[cy][cx] = 1
                    else:
                        solid[cy][cx] = 1
                elif kind == "climb":
                    climb[cy][cx] = 1
    return solid, climb


def ladder_rects(climb: list[list[int]]) -> list[list[int]]:
    rects: list[list[int]] = []
    for x, y, w, h in greedy_rects(climb):
        if h < 24:
            continue
        rects.append([x - 4, y, w + 8, h])
    return rects


def lifts_from_instances(instances: list[RoomObject], solid: list[list[int]]) -> list[dict]:
    lifts: list[dict] = []
    ch, cw = len(solid), len(solid[0]) if solid else 0
    for o in instances:
        if o.kind != "lift_platform" and o.type_id != "lift_platform":
            continue
        cx = (o.x + o.w // 2) // CELL
        cy = o.y // CELL
        if not (0 <= cx < cw):
            continue
        top = cy
        while top > 0 and not solid[top - 1][cx]:
            top -= 1
        bot = cy
        while bot + 1 < ch and not solid[bot + 1][cx]:
            bot += 1
        lifts.append(
            {
                "x": o.x,
                "y": o.y,
                "w": o.w,
                "h": max(o.h, CELL),
                "top": top * CELL,
                "bottom": bot * CELL,
            }
        )
    return lifts


def build_type_sprite(
    o: RoomObject, bchrs: list[Image.Image], box_bchrs: list[Image.Image] | None = None
) -> Image.Image:
    skip_sky = o.type_id.startswith("tree_")
    cells = box_bchrs if box_bchrs is not None and is_box_prefab(o) else None
    if o.mode == "module_repeat" and o.kind == "ladder" and len(o.tiles) >= 2:
        return blit_tiles(list(o.tiles), 2, 1, bchrs)
    if o.tiles and o.mode == "prefab":
        tw, th = max(o.w // CELL, 1), max(o.h // CELL, 1)
        if len(o.tiles) >= tw * th:
            return blit_tiles(list(o.tiles), tw, th, bchrs, skip_sky=skip_sky, cells=cells)
    if o.tile >= 0 and o.tile < len(bchrs):
        return bchrs[o.tile].copy()
    if o.tiles:
        tw = max(o.w // CELL, 1)
        th = max(len(o.tiles) // tw, 1)
        return blit_tiles(list(o.tiles), tw, th, bchrs, skip_sky=skip_sky, cells=cells)
    return Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))


def world_to_mosaic(x: int, y: int) -> tuple[int, int]:
    """Fan mosaic is 256×192 screenshots; our world stacks 144px playfields."""
    my, ly = divmod(y, PLAYFIELD_H)
    return x, my * SCREEN_H + ly


def crop_prefab_from_mosaic(mosaic: Image.Image, o: RoomObject) -> Image.Image | None:
    if mosaic is None:
        return None
    x0, y0 = world_to_mosaic(o.x, o.y)
    box = (x0, y0, x0 + o.w, y0 + o.h)
    if box[2] > mosaic.width or box[3] > mosaic.height or o.w <= 0 or o.h <= 0:
        return None
    return mosaic.crop(box).convert("RGBA")


def punch_wallpaper(img: Image.Image) -> Image.Image:
    """Drop ZX green paper (and black only if it is not part of the object)."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    keep = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if c[3] == 0:
                continue
            if c in ZX_PAPER_GREEN or c == ZX_BLACK:
                continue
            keep[y][x] = True
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not keep[ny][nx] and px[nx, ny] == ZX_BLACK:
                keep[ny][nx] = True
                q.append((nx, ny))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            if keep[y][x]:
                op[x, y] = px[x, y]
    return out


def render_room_rgb(buf: list[int], bchrs: list[Image.Image]) -> Image.Image:
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    n = len(bchrs)
    for row in range(ROOM_ROWS):
        for col in range(ROOM_COLS):
            t = buf[row * ROOM_COLS + col]
            if t >= n:
                continue
            img.paste(bchrs[t].convert("RGB"), (col * CELL, row * CELL))
    return img


def verify_mosaic(rooms: list[list[int]], smap: list[list[int]], bchrs: list[Image.Image]) -> dict:
    if not MOSAIC.exists():
        return {"skipped": True, "reason": "mosaic missing"}
    mosaic = Image.open(MOSAIC).convert("RGB")
    map_h = min(len(smap), mosaic.height // SCREEN_H)
    map_w = min(MAP_W, mosaic.width // SCREEN_W)
    screens = 0
    pixel_diff = 0
    compared = 0
    for my in range(map_h):
        for mx in range(map_w):
            rid = smap[my][mx]
            if rid < 0 or rid >= len(rooms):
                continue
            objs, buf = interpret_room(rooms[rid])
            recon = render_room_rgb(buf, bchrs)
            crop = mosaic.crop(
                (mx * SCREEN_W, my * SCREEN_H, (mx + 1) * SCREEN_W, my * SCREEN_H + PLAYFIELD_H)
            )
            if recon.size != crop.size:
                crop = mosaic.crop(
                    (mx * SCREEN_W, my * SCREEN_H, (mx + 1) * SCREEN_W, my * SCREEN_H + recon.height)
                )
            a, b = recon.load(), crop.load()
            d = 0
            h = min(recon.height, crop.height)
            n = 0
            for y in range(0, h, 4):
                for x in range(0, recon.width, 4):
                    n += 1
                    ra, ga, ba = a[x, y]
                    rb, gb, bb = b[x, y]
                    if abs(ra - rb) + abs(ga - gb) + abs(ba - bb) > 24:
                        d += 1
            pixel_diff += d
            compared += n
            screens += 1
    loc = locate_room_on_mosaic(rooms, mosaic, bchrs, 1) if len(rooms) > 1 else {}
    return {
        "skipped": False,
        "screens": screens,
        "pixels_compared": compared,
        "pixels_differ": pixel_diff,
        "match_ratio": (1.0 - pixel_diff / compared) if compared else 0.0,
        "room1_best_screen": loc,
    }


def locate_room_on_mosaic(
    rooms: list[list[int]], mosaic: Image.Image, bchrs: list[Image.Image], rid: int
) -> dict:
    """Where a reconstructed room best matches the stitched mosaic (SMAP origin check)."""
    if rid < 0 or rid >= len(rooms):
        return {}
    recon = render_room_rgb(interpret_room(rooms[rid])[1], bchrs)
    map_h = min(mosaic.height // SCREEN_H, WORLD_ROWS)
    map_w = min(MAP_W, mosaic.width // SCREEN_W)
    best = {"mx": -1, "my": -1, "match_ratio": 0.0}
    a = recon.load()
    for my in range(map_h):
        for mx in range(map_w):
            crop = mosaic.crop(
                (mx * SCREEN_W, my * SCREEN_H, (mx + 1) * SCREEN_W, my * SCREEN_H + PLAYFIELD_H)
            )
            b = crop.load()
            n = 0
            d = 0
            h = min(recon.height, crop.height)
            for y in range(0, h, 8):
                for x in range(0, recon.width, 8):
                    n += 1
                    ra, ga, ba = a[x, y]
                    rb, gb, bb = b[x, y]
                    if abs(ra - rb) + abs(ga - gb) + abs(ba - bb) > 24:
                        d += 1
            ratio = (1.0 - d / n) if n else 0.0
            if ratio > best["match_ratio"]:
                best = {"mx": mx, "my": my, "match_ratio": round(ratio, 4)}
    return best


def main() -> None:
    prepare()
    rooms = load_rooms()
    smap = load_smap()
    bchr_raw = load_bchrs()
    bchrs = [render_bchr(t) for t in bchr_raw]
    ochrs_raw = load_ochrs()
    ochrs = [render_ochrs(t) for t in ochrs_raw]
    print(f"rooms={len(rooms)} smap={len(smap)}x{len(smap[0]) if smap else 0} bchrs={len(bchrs)} ochrs={len(ochrs)}")
    if rooms:
        o0, buf0 = interpret_room(rooms[0])
        print(f"room0 objects={len(o0)} kinds={[o.kind for o in o0[:8]]}")

    map_h = len(smap)
    map_w = MAP_W
    force_indoor = indoor_force_mask(smap, rooms)
    indoor_ok = reachable_indoor_mask(smap, rooms)
    instances: list[RoomObject] = []
    placed = 0
    skipped = 0
    for my, row in enumerate(smap[:map_h]):
        for mx, rid in enumerate(row[:map_w]):
            if rid < 0 or rid >= len(rooms):
                skipped += 1
                continue
            objs, _buf = interpret_room(rooms[rid])
            if is_generic_interior(objs) and not indoor_ok[my][mx]:
                skipped += 1
                continue
            placed += 1
            objs = snap_ladders(
                apply_room_paper(room_objects_for_world(objs), force_indoor=force_indoor[my][mx])
            )
            instances.extend(place_world(objs, mx, my))
    instances.extend(unique_world_objects(rooms))
    instances = connect_ladders(instances)
    print(f"screens={placed} skipped={skipped} instances={len(instances)}")

    mosaic = Image.open(MOSAIC).convert("RGB") if MOSAIC.exists() else None

    types: dict[str, dict] = {}
    sprites: dict[str, Image.Image] = {}
    for o in instances:
        if o.type_id in types:
            continue
        img = build_type_sprite(o, bchrs, ochrs)
        if o.type_id == WALLPAPER_TYPE:
            raw = bchr_raw[WALLPAPER_TILE]
            img = render_bchr(raw, raw[8] | 0o100)
        if (
            o.mode == "prefab"
            and not is_box_prefab(o)
            and mosaic is not None
            and (not o.tiles or img.getextrema()[3] == (0, 0))
        ):
            crop = crop_prefab_from_mosaic(mosaic, o)
            if crop is not None and crop.size[0] > 0:
                img = crop
        if o.type_id == DESK_TYPE:
            img = punch_wallpaper(img)
        z = LAYER_Z[o.layer]
        if o.type_id == DESK_TYPE:
            z = LAYER_Z[o.layer] + 1
        elif o.type_id == WALLPAPER_TYPE:
            z = WALLPAPER_Z
        types[o.type_id] = {
            "layer": LAYER_NAMES[o.layer],
            "mode": o.mode,
            "collision": o.collision,
            "axis": o.axis,
            "module": list(o.module),
            "size": [img.size[0], img.size[1]],
            "z": z,
            "overlay": o.type_id == DESK_TYPE,
            "sprite": f"res://assets/world/objects/{LAYER_NAMES[o.layer]}/{o.type_id}.png",
        }
        sprites[o.type_id] = img

    OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    for tid, spec in types.items():
        layer = spec["layer"]
        sub = OBJECTS_DIR / layer
        sub.mkdir(parents=True, exist_ok=True)
        sprites[tid].save(sub / f"{tid}.png")

    inst_out = []
    for o in instances:
        inst_out.append(
            {
                "type": o.type_id,
                "x": o.x,
                "y": o.y,
                "w": o.w,
                "h": o.h,
                "layer": LAYER_NAMES[o.layer],
            }
        )
    catalog = {
        "cell": CELL,
        "scale": SCALE,
        "screen": [SCREEN_W, SCREEN_H],
        "playfield": [SCREEN_W, PLAYFIELD_H],
        "map": [map_w, map_h],
        "size": [map_w * SCREEN_W, map_h * PLAYFIELD_H],
        "source": "S2ROOM.MAC + S2CORE markers",
        "layer_z": {LAYER_NAMES[k]: v for k, v in LAYER_Z.items()},
        "types": types,
        "instances": inst_out,
    }
    out_json = OUT / "s2_objects.json"
    out_json.write_text(json.dumps(catalog, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out_json} types={len(types)} instances={len(inst_out)}")

    solid, climb = stamp_world(instances, map_w, map_h)
    apply_hatches(solid, climb)
    lifts = lifts_from_instances(instances, solid)
    solids = greedy_rects(solid)
    ladders = ladder_rects(climb)
    bookcases = [
        [o.x, o.y, o.w, o.h]
        for o in instances
        if o.type_id == "bookcase" or o.kind.startswith("bookcase")
    ]
    collision = {
        "source": "S2ROOM.MAC object bounds",
        "scale": SCALE,
        "cell": CELL,
        "screen": [SCREEN_W, SCREEN_H],
        "playfield": [SCREEN_W, PLAYFIELD_H],
        "map": [map_w, map_h],
        "size": [map_w * SCREEN_W, map_h * PLAYFIELD_H],
        "collision_layers": ["earth", "structure"],
        "collision_source": "object_bounds",
        "collision_note": "solids/ladders from bytecode object {type,rect}. No pixel heuristics.",
        "solids": solids,
        "ladders": ladders,
        "lifts": lifts,
        "bookcases": bookcases,
        "objects": [
            {"type": o.type_id, "x": o.x, "y": o.y, "w": o.w, "h": o.h}
            for o in instances
            if o.collision != "none"
        ],
    }
    cpath = OUT / "s2_collision.json"
    cpath.write_text(json.dumps(collision, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {cpath} solids={len(solids)} ladders={len(ladders)} lifts={len(lifts)}")

    report = verify_mosaic(rooms, smap, bchrs)
    print("verify", json.dumps(report))
    (OUT / "s2_decompose_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    render_object_world(catalog, sprites, OUT / "s2_object_world.png")


def render_object_world(
    catalog: dict, sprites: dict[str, Image.Image], path: Path
) -> None:
    w, h = catalog["size"]
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    types = catalog["types"]
    instances = sorted(
        catalog["instances"],
        key=lambda inst: int(types.get(inst["type"], {}).get("z", 0)),
    )
    for inst in instances:
        tex = sprites.get(inst["type"])
        if tex is None:
            continue
        iw, ih = int(inst["w"]), int(inst["h"])
        x, y = int(inst["x"]), int(inst["y"])
        tw, th = tex.size
        if tw <= 0 or th <= 0 or iw <= 0 or ih <= 0:
            continue
        if (tw, th) == (iw, ih):
            canvas.paste(tex, (x, y), tex)
            continue
        for ty in range(0, ih, th):
            for tx in range(0, iw, tw):
                cw, ch = min(tw, iw - tx), min(th, ih - ty)
                if cw == tw and ch == th:
                    canvas.paste(tex, (x + tx, y + ty), tex)
                else:
                    crop = tex.crop((0, 0, cw, ch))
                    canvas.paste(crop, (x + tx, y + ty), crop)
    canvas.convert("RGB").save(path)
    overview = canvas.resize((w // 8, h // 8), Image.NEAREST).convert("RGB")
    overview.save(path.with_name("s2_object_world_overview.png"))
    print(f"wrote {path} and overview")


if __name__ == "__main__":
    main()
