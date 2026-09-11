"""Collision from object bounds and types — not per-brick, not colour counts.

Pipeline:
  mosaic → objects {type, x, y, w, h} → stamp by type rule onto solid/climb.

Fingerprints are ZX character graphics (same class as bookcase planks):
they mark *what* an object is. Neighbour growth finds the rectangle.
Collision is a property of the type applied to that rect.
"""
from __future__ import annotations

from collections import deque

CELL = 8

# Collision rule for each object type.
# floor  — walkable top row of the rect (one cell thick)
# solid  — fill the rect (earth / rock contour)
# climb  — fill the rect as a ladder zone
# none   — ignored at stamp time (furniture, wallpaper, sky)
TYPE_COLLISION: dict[str, str] = {
    "floor_brick": "floor",
    "floor_diamond": "floor",
    "sky_girder": "floor",
    "earth": "solid",
    "ladder": "climb",
    "bookcase": "none",
    "furniture": "none",
    "crate": "none",
    "wallpaper": "none",
    "sky": "none",
}

# Exact bookcase plank characters (also used by build_s2_world).
PLANK_TILES = {
    "L": (
        "kkkkkkkk",
        "kkkkkkkk",
        "kkgggggg",
        "kgkgggkg",
        "ggkkkgkg",
        "ggggggkg",
        "gkkkkkkg",
        "gggggggg",
    ),
    "M": (
        "kkkkkkkk",
        "kkkkkkkk",
        "gggggggg",
        "kgkgggkg",
        "kgkkkgkg",
        "kgggggkg",
        "kkkkkkkg",
        "gggggggg",
    ),
    "R": (
        "kkkkkkkk",
        "kkkkkkkk",
        "ggggggkk",
        "kgkggggk",
        "kgkkkggk",
        "kgggggkg",
        "kkkkkkkg",
        "gggggggg",
    ),
}


def col(r: int, g: int, b: int) -> str:
    if r == 0 and g == 0 and b == 0:
        return "k"
    if r == 0 and g == 0 and b >= 200:
        return "b"
    if r == 0 and g >= 200 and b < 40:
        return "g"
    if r == 0 and g >= 200 and b >= 200:
        return "c"
    if r >= 200 and g < 40 and b < 40:
        return "r"
    if r >= 200 and g >= 200 and b < 40:
        return "y"
    if r >= 200 and g >= 200 and b >= 200:
        return "w"
    if r >= 200 and g < 40 and b >= 200:
        return "m"
    return "o"


def cell_rows(px, cx: int, cy: int) -> list[list[str]]:
    x0, y0 = cx * CELL, cy * CELL
    return [[col(*px[x0 + x, y0 + y]) for x in range(CELL)] for y in range(CELL)]


def _inks(rows: list[list[str]]) -> set[str]:
    return {p for row in rows for p in row}


def is_green_rail_tile(rows: list[list[str]]) -> bool:
    if any(p not in "kg" for row in rows for p in row):
        return False
    left = all(row[0] == "g" and row[1] == "k" and row[2] == "k" and row[3] == "g" for row in rows[:2])
    right = all(row[4] == "g" and row[5] == "k" and row[6] == "k" and row[7] == "g" for row in rows[:2])
    return left or right


def is_sky_rail_tile(rows: list[list[str]]) -> bool:
    if any(p not in "wb" for row in rows for p in row):
        return False
    left = all(row[0] == "w" and row[1] == "w" and row[2] == "w" for row in rows)
    right = all(row[5] == "w" and row[6] == "w" and row[7] == "w" for row in rows)
    if left == right:
        return False
    if left:
        gap_ok = all(row[3] == "b" for row in rows)
        inner = [sum(1 for x in range(4, CELL) if row[x] == "w") for row in rows]
    else:
        gap_ok = all(row[4] == "b" for row in rows)
        inner = [sum(1 for x in range(4) if row[x] == "w") for row in rows]
    if not gap_ok:
        return False
    rung_rows = sum(1 for n in inner if n >= 3)
    blue = sum(1 for row in rows for p in row if p == "b")
    return rung_rows >= 2 and 16 <= blue <= 40


def is_x_lattice_tile(rows: list[list[str]]) -> bool:
    flat = [p for row in rows for p in row]
    inks = {p for p in flat if p != "k"}
    inks.discard("b")
    if inks != {"w"} and inks != {"c"}:
        return False
    ink = next(iter(inks))

    def col_n(x: int) -> int:
        return sum(1 for y in range(CELL) if rows[y][x] == ink)

    if col_n(0) < 4 or col_n(7) < 4:
        return False
    if col_n(3) + col_n(4) > 8:
        return False
    bright = sum(1 for p in flat if p == ink)
    return 16 <= bright <= 48


def is_ladder_tile(rows: list[list[str]]) -> bool:
    return is_green_rail_tile(rows) or is_sky_rail_tile(rows) or is_x_lattice_tile(rows)


def is_diamond_floor_tile(rows: list[list[str]]) -> bool:
    if any(p not in "wb" for row in rows for p in row):
        return False
    if any(p != "w" for p in rows[0] + rows[1] + rows[6] + rows[7]):
        return False
    diamond = ((0, 7), (1, 6), (2, 5), (3, 4))
    for i, (a, b) in enumerate(diamond):
        row = rows[2 + i]
        whites = [x for x, p in enumerate(row) if p == "w"]
        if whites != [a, b]:
            return False
    return True


def is_red_brick_char(rows: list[list[str]]) -> bool:
    """ZX red-brick character: only red/black, with a mortar row of black."""
    inks = _inks(rows)
    if inks - {"r", "k"}:
        return False
    if "r" not in inks or "k" not in inks:
        return False
    return any(all(p == "k" for p in row) for row in rows)


def is_blue_brick_char(rows: list[list[str]]) -> bool:
    """Blue-brick wallpaper: mortar row plus a mostly-blue brick face."""
    inks = _inks(rows)
    if inks - {"b", "k"}:
        return False
    if "b" not in inks or "k" not in inks:
        return False
    if not any(all(p == "k" for p in row) for row in rows):
        return False
    face = [p for row in rows for p in row if not all(c == "k" for c in row)]
    if not face:
        return False
    return sum(p == "b" for p in face) > sum(p == "k" for p in face)


def is_earth_char(rows: list[list[str]]) -> bool:
    """Black field with blue specks/cracks — ground, not sky, not wallpaper.

    Night sky is blue paper (all-blue, or mostly-blue dither). Earth is the
    opposite: a black cell with blue dots. Majority-black is the fingerprint;
    do not punch it to air because a neighbour is open sky.
    """
    inks = _inks(rows)
    if inks - {"k", "b"}:
        return False
    if "k" not in inks or "b" not in inks:
        return False
    if is_blue_brick_char(rows):
        return False
    flat = [p for row in rows for p in row]
    return sum(p == "k" for p in flat) > sum(p == "b" for p in flat)


def is_girder_char(rows: list[list[str]]) -> bool:
    """Outdoor deck: a white slab on blue. Not diamond, rail, or lattice."""
    if is_diamond_floor_tile(rows) or is_sky_rail_tile(rows) or is_x_lattice_tile(rows):
        return False
    inks = _inks(rows)
    if inks - {"w", "b"}:
        return False
    if "w" not in inks or "b" not in inks:
        return False
    slab_rows = sum(1 for row in rows if sum(p == "w" for p in row) >= 6)
    return slab_rows >= 3


def collision_for_type(tid: str) -> str:
    return TYPE_COLLISION.get(tid, "none")


def _mask(cw: int, ch: int, pred, px) -> list[list[int]]:
    out = [[0] * cw for _ in range(ch)]
    for cy in range(ch):
        for cx in range(cw):
            if pred(cell_rows(px, cx, cy)):
                out[cy][cx] = 1
    return out


def _horizontal_strips(mask: list[list[int]], *, min_w: int, occupied: list[list[int]] | None = None) -> list[dict]:
    ch = len(mask)
    cw = len(mask[0]) if ch else 0
    rects: list[dict] = []
    for cy in range(ch):
        cx = 0
        while cx < cw:
            if not mask[cy][cx] or (occupied and occupied[cy][cx]):
                cx += 1
                continue
            x0 = cx
            while cx < cw and mask[cy][cx] and not (occupied and occupied[cy][cx]):
                cx += 1
            if cx - x0 >= min_w:
                rects.append({"x": x0, "y": cy, "w": cx - x0, "h": 1})
    return rects


def _connected_rects(mask: list[list[int]], *, min_cells: int = 2) -> list[dict]:
    """Bounding boxes of 4-connected components."""
    ch = len(mask)
    cw = len(mask[0]) if ch else 0
    seen = [[False] * cw for _ in range(ch)]
    rects: list[dict] = []
    for sy in range(ch):
        for sx in range(cw):
            if not mask[sy][sx] or seen[sy][sx]:
                continue
            q: deque[tuple[int, int]] = deque([(sx, sy)])
            seen[sy][sx] = True
            cells: list[tuple[int, int]] = []
            while q:
                x, y = q.popleft()
                cells.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        continue
                    if seen[ny][nx] or not mask[ny][nx]:
                        continue
                    seen[ny][nx] = True
                    q.append((nx, ny))
            if len(cells) < min_cells:
                continue
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            x0, y0 = min(xs), min(ys)
            rects.append(
                {
                    "x": x0,
                    "y": y0,
                    "w": max(xs) - x0 + 1,
                    "h": max(ys) - y0 + 1,
                    "_cells": cells,
                }
            )
    return rects


def _mark_occupied(occupied: list[list[int]], placements: list[dict]) -> None:
    for p in placements:
        cells = p.get("_cells")
        if cells:
            for x, y in cells:
                occupied[y][x] = 1
            continue
        for dy in range(p["h"]):
            for dx in range(p["w"]):
                occupied[p["y"] + dy][p["x"] + dx] = 1


def _girder_lips(mask: list[list[int]], occupied: list[list[int]]) -> list[list[int]]:
    """Keep only the top cell of a vertical girder stack (the walkable lip)."""
    ch = len(mask)
    cw = len(mask[0]) if ch else 0
    lips = [[0] * cw for _ in range(ch)]
    for cx in range(cw):
        cy = 0
        while cy < ch:
            if not mask[cy][cx] or occupied[cy][cx]:
                cy += 1
                continue
            y0 = cy
            while cy < ch and mask[cy][cx] and not occupied[cy][cx]:
                cy += 1
            lips[y0][cx] = 1
    return lips


def is_open_sky_char(rows: list[list[str]]) -> bool:
    return all(p == "b" for row in rows for p in row)


def scan_objects(im) -> list[dict]:
    """Find world objects as {type, x, y, w, h} in cell units."""
    px = im.load()
    cw, ch = im.width // CELL, im.height // CELL
    occupied = [[0] * cw for _ in range(ch)]
    placements: list[dict] = []

    ladders = _connected_rects(_mask(cw, ch, is_ladder_tile, px), min_cells=2)
    for p in ladders:
        placements.append({"type": "ladder", "x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"]})
    _mark_occupied(occupied, ladders)

    diamonds = _horizontal_strips(
        _mask(cw, ch, is_diamond_floor_tile, px), min_w=1, occupied=occupied
    )
    for p in diamonds:
        placements.append({"type": "floor_diamond", **{k: p[k] for k in "xywh"}})
    _mark_occupied(occupied, diamonds)

    brick = _horizontal_strips(
        _mask(cw, ch, is_red_brick_char, px), min_w=2, occupied=occupied
    )
    for p in brick:
        placements.append({"type": "floor_brick", **{k: p[k] for k in "xywh"}})
    _mark_occupied(occupied, brick)

    lips = _girder_lips(_mask(cw, ch, is_girder_char, px), occupied)
    girders = _horizontal_strips(lips, min_w=1, occupied=occupied)
    for p in girders:
        placements.append({"type": "sky_girder", **{k: p[k] for k in "xywh"}})
    _mark_occupied(occupied, girders)

    earth_mask = _mask(cw, ch, is_earth_char, px)
    for p in _connected_rects(earth_mask, min_cells=1):
        cells = [(x, y) for x, y in p["_cells"] if not occupied[y][x]]
        if not cells:
            continue
        # Tight rects from the remaining cells, not the cave's AABB
        # (AABB would swallow rooms). Stamp cell-accurate via _cells.
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        placements.append(
            {
                "type": "earth",
                "x": min(xs),
                "y": min(ys),
                "w": max(xs) - min(xs) + 1,
                "h": max(ys) - min(ys) + 1,
                "_cells": cells,
            }
        )
    return placements


def type_grid_from_placements(placements: list[dict], cw: int, ch: int) -> list[list[str]]:
    grid = [[""] * cw for _ in range(ch)]
    for p in placements:
        tid = p["type"]
        cells = p.get("_cells")
        if cells:
            for x, y in cells:
                grid[y][x] = tid
            continue
        for dy in range(p["h"]):
            for dx in range(p["w"]):
                grid[p["y"] + dy][p["x"] + dx] = tid
    return grid


def _apply_hatches(solid: list[list[int]], ladder: list[list[int]]) -> None:
    """Lid = climb cell on the same row as a floor, touching it.

    Shaft cells below stay climb and not solid. No downward thicken.
    """
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


def stamp_collision(
    placements: list[dict], cw: int, ch: int
) -> tuple[list[list[int]], list[list[int]]]:
    """Apply each object's type rule to its rect / cells."""
    solid = [[0] * cw for _ in range(ch)]
    ladder = [[0] * cw for _ in range(ch)]
    for p in placements:
        kind = collision_for_type(p["type"])
        if kind == "none":
            continue
        cells = p.get("_cells")
        if kind == "floor":
            for dx in range(p["w"]):
                solid[p["y"]][p["x"] + dx] = 1
        elif kind == "solid":
            if cells:
                for x, y in cells:
                    solid[y][x] = 1
            else:
                for dy in range(p["h"]):
                    for dx in range(p["w"]):
                        solid[p["y"] + dy][p["x"] + dx] = 1
        elif kind == "climb":
            if cells:
                for x, y in cells:
                    ladder[y][x] = 1
            else:
                for dy in range(p["h"]):
                    for dx in range(p["w"]):
                        ladder[p["y"] + dy][p["x"] + dx] = 1
    _apply_hatches(solid, ladder)
    return solid, ladder


def type_catalog_export() -> dict[str, dict]:
    return {
        tid: {"collision": kind}
        for tid, kind in TYPE_COLLISION.items()
    }
