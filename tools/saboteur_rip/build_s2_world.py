#!/usr/bin/env python3
"""Build a playable Saboteur II world from the screenshot mosaic.

Floors are brick strips, cave earth (black with blue specks), the white
diamond slab (two white bars around a blue chevron) that divides rooms and
forms outdoor girder decks, and the top/bottom lining of thin blue-brick
cave tunnels. Blue brick is room wallpaper — a lift shaft stays walkable.
Green wallpaper, furniture and interior black air stay empty.
Ladders are the original rail tiles (interior green pair, outdoor white
X-lattice, and the white-on-blue sky pair that continues a green shaft above
the roof). Yellow crates and interior bookcases are foreground-only.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "reference" / "original" / "maps" / "Saboteur2_speccy.png"
OUT_DIR = ROOT / "assets" / "world"
TILESET_DIR = ROOT / "assets" / "tilesets"
CELL = 8
SCREEN_W, SCREEN_H = 256, 192
SCALE = 2


def _col(r: int, g: int, b: int) -> str:
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


def _ink(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    if r == 0 and g == 0 and b == 0:
        return "k"
    if r == 0 and g == 0 and b >= 200:
        return "b"
    if r == 0 and g >= 200 and b < 40:
        return "g"
    if r == 0 and g >= 200 and b >= 200:
        return "c"
    if r >= 200 and g >= 200 and b >= 200:
        return "w"
    return "o"


def _cell_rows(px, cx: int, cy: int) -> list[list[str]]:
    x0, y0 = cx * CELL, cy * CELL
    return [[_ink(px[x0 + x, y0 + y]) for x in range(CELL)] for y in range(CELL)]


def cell_is_ladder(px, cx: int, cy: int) -> bool:
    """Match original Saboteur II ladder character graphics.

    Interior ladders are a 16px pair of green rail tiles punched through
    wallpaper. Outdoor ladders are either a thin white X-lattice with rails
    on both edges, or the white-on-blue sky pair that continues a green
    shaft above the roof — not windows, lift shafts, or picket fences.
    """
    rows = _cell_rows(px, cx, cy)
    return (
        _is_green_rail_tile(rows)
        or _is_x_lattice_tile(rows)
        or _is_sky_rail_tile(rows)
    )


def cell_is_diamond_floor(px, cx: int, cy: int) -> bool:
    return _is_diamond_floor_tile(_cell_rows(px, cx, cy))


def _is_green_rail_tile(rows: list[list[str]]) -> bool:
    if any(p not in "kg" for row in rows for p in row):
        return False
    left = all(row[0] == "g" and row[1] == "k" and row[2] == "k" and row[3] == "g" for row in rows[:2])
    right = all(row[4] == "g" and row[5] == "k" and row[6] == "k" and row[7] == "g" for row in rows[:2])
    return left or right


def _is_sky_rail_tile(rows: list[list[str]]) -> bool:
    """16px outdoor pair: 3px white rail + blue rungs against sky paper.

    Left half is `wwwb` plus a 4-row rung cycle on the inner nibble; the
    right half mirrors it. Same shafts as the interior green pair, just
    above the roofline where the paper turns blue.
    """
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


def _is_diamond_floor_tile(rows: list[list[str]]) -> bool:
    """Walkable 8px slab: two white bars around a blue downward diamond.

    Same character is the interior room divider (green wallpaper above, blue
    brick below) and the outdoor girder deck. Not a window, rail, or sky bar.
    """
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


def _is_x_lattice_tile(rows: list[list[str]]) -> bool:
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


def cell_is_crate(counts: dict[str, int]) -> bool:
    # Wooden crates are yellow on black, not yellow books on blue paper.
    return counts["y"] >= 12 and counts["r"] < 10 and counts["k"] >= 16 and counts["b"] < 10


def cell_is_red_brick(counts: dict[str, int]) -> bool:
    return counts["r"] >= 10 and counts["k"] >= 4


def _cell_counts(px, cx: int, cy: int) -> dict[str, int]:
    counts = {k: 0 for k in "kbgrcywmo"}
    x0, y0 = cx * CELL, cy * CELL
    for y in range(y0, y0 + CELL):
        for x in range(x0, x0 + CELL):
            counts[_col(*px[x, y])] += 1
    return counts


def _is_cave_paper(counts: dict[str, int]) -> bool:
    """Blue brick wallpaper — walkable room interior, not cyan trim or sky."""
    return (
        counts["b"] >= 20
        and counts["k"] >= 6
        and counts["g"] < 8
        and counts["c"] < 8
        and counts["r"] < 8
        and counts["y"] < 4
        and counts["w"] <= 8
    )


def _is_cave_void(counts: dict[str, int]) -> bool:
    """Black cave around a tunnel: earth, specks, or empty void."""
    return (
        counts["k"] >= 24
        and counts["b"] < 20
        and counts["g"] < 8
        and counts["c"] < 8
        and counts["r"] < 8
        and counts["w"] < 8
        and counts["y"] < 8
    )


def _is_speckled_earth(counts: dict[str, int]) -> bool:
    """Black field with sparse blue dots — impermeable cave earth."""
    return (
        counts["k"] >= 48
        and 1 <= counts["b"] <= 8
        and counts["g"] < 8
        and counts["r"] < 8
        and counts["c"] < 8
    )


def _is_cave_fringe(counts: dict[str, int]) -> bool:
    """Jagged black/blue lining on a tunnel's ceiling or floor."""
    if counts["g"] >= 8 or counts["c"] >= 8 or counts["r"] >= 8 or counts["y"] >= 4:
        return False
    if _is_cave_paper(counts) or _is_cave_void(counts):
        return False
    return counts["b"] >= 6 and counts["k"] >= 16


# Thin cave corridor: enough cells for a crouch (24px) between 8px lining.
_TUNNEL_MIN_H = 5
_TUNNEL_MAX_H = 10
_TUNNEL_MIN_WIDTH = 6
# Black gap between two blue-brick masses (air, or air over water).
_GAP_MIN_H = 5
_GAP_MAX_H = 12
# Thin red post in a room: not a floor strip, not a 1-cell speck.
_PILLAR_MIN_H = 3


def _cave_cell_masks(
    px, cw: int, ch: int
) -> tuple[list[list[bool]], list[list[bool]], list[list[bool]]]:
    paper = [[False] * cw for _ in range(ch)]
    void = [[False] * cw for _ in range(ch)]
    fringe = [[False] * cw for _ in range(ch)]
    for cy in range(ch):
        for cx in range(cw):
            counts = _cell_counts(px, cx, cy)
            paper[cy][cx] = _is_cave_paper(counts)
            void[cy][cx] = _is_cave_void(counts)
            fringe[cy][cx] = _is_cave_fringe(counts)
    return paper, void, fringe


def _wide_horizontal_groups(
    raw: list[tuple[int, int, int]], min_width: int
) -> list[list[tuple[int, int, int]]]:
    """Connected (cx, y0, y1) columns that form a corridor at least min_width wide."""
    by_col: dict[int, list[tuple[int, int, int]]] = {}
    for rec in raw:
        by_col.setdefault(rec[0], []).append(rec)
    used = [False] * len(raw)
    index = {rec: i for i, rec in enumerate(raw)}
    groups: list[list[tuple[int, int, int]]] = []
    for i, rec in enumerate(raw):
        if used[i]:
            continue
        stack = [rec]
        used[i] = True
        members: list[tuple[int, int, int]] = []
        while stack:
            cx, y0, y1 = stack.pop()
            members.append((cx, y0, y1))
            for dx in (-1, 1):
                for ocx, oy0, oy1 in by_col.get(cx + dx, []):
                    j = index[(ocx, oy0, oy1)]
                    if used[j]:
                        continue
                    if oy0 <= y1 and y0 <= oy1:
                        used[j] = True
                        stack.append((ocx, oy0, oy1))
        xs = [m[0] for m in members]
        if max(xs) - min(xs) + 1 >= min_width:
            groups.append(members)
    return groups


def _wide_horizontal_runs(
    raw: list[tuple[int, int, int]], min_width: int
) -> list[tuple[int, int, int]]:
    """Keep (cx, y0, y1) columns that form a corridor at least min_width wide."""
    return [m for g in _wide_horizontal_groups(raw, min_width) for m in g]


def _corridor_abuts_green_wallpaper(px, members: list[tuple[int, int, int]], cw: int) -> bool:
    """True if this paper band is a room wall beside green interior wallpaper.

    Cave earth counts as void, so a basement blue-brick panel above a diamond
    deck looks like a tunnel. The valid-column run can stop at a screen edge
    before it actually touches the green, so walk onward through paper.
    Real corridors sit in rock; walking off their end hits void, not a room.
    Drop the whole run: leaving the far columns would still pass min-width.
    """
    min_x = min(m[0] for m in members)
    max_x = max(m[0] for m in members)
    for cx, y0, y1 in members:
        if cx != min_x and cx != max_x:
            continue
        mid = (y0 + y1) // 2
        step = -1 if cx == min_x else 1
        x = cx
        for _ in range(12):
            x += step
            if x < 0 or x >= cw:
                break
            counts = _cell_counts(px, x, mid)
            if counts["g"] >= 16 and not cell_is_ladder(px, x, mid):
                return True
            if not _is_cave_paper(counts):
                break
    return False


def find_cave_tunnels(
    px,
    cw: int,
    ch: int,
    biomes: list[str],
    sx_n: int,
) -> list[tuple[int, int, int]]:
    """Horizontal blue-brick cave corridors with void above and below.

    Each hit is `(cx, y0, y1)`: ceiling cell, floor cell, interior between.
    """
    paper, void, fringe = _cave_cell_masks(px, cw, ch)
    raw: list[tuple[int, int, int]] = []
    for cx in range(cw):
        cy = 0
        while cy < ch:
            if not paper[cy][cx]:
                cy += 1
                continue
            y0 = cy
            while cy < ch and paper[cy][cx]:
                cy += 1
            y1 = cy - 1
            while y0 > 0 and fringe[y0 - 1][cx]:
                y0 -= 1
            while y1 + 1 < ch and fringe[y1 + 1][cx]:
                y1 += 1
            h = y1 - y0 + 1
            if h < _TUNNEL_MIN_H or h > _TUNNEL_MAX_H:
                continue
            if y0 == 0 or y1 + 1 >= ch:
                continue
            if not (void[y0 - 1][cx] and void[y1 + 1][cx]):
                continue
            # Both ends must be cave. A paper band that starts in a cave
            # screen and ends in an interior room is a basement far-wall,
            # not a corridor — treating y1 as a floor puts an invisible
            # slab through the room below the wallpaper.
            if _biome_at(biomes, sx_n, cx, y0) != "cave":
                continue
            if _biome_at(biomes, sx_n, cx, y1) != "cave":
                continue
            if cell_is_diamond_floor(px, cx, y1 + 1):
                continue
            if _floor_slab_along_row(px, cx, y1 + 1, cw, biomes, sx_n):
                continue
            raw.append((cx, y0, y1))
    out: list[tuple[int, int, int]] = []
    for members in _wide_horizontal_groups(raw, _TUNNEL_MIN_WIDTH):
        if _corridor_abuts_green_wallpaper(px, members, cw):
            continue
        out.extend(members)
    return out


def _floor_slab_along_row(
    px, cx: int, cy: int, cw: int, biomes: list[str], sx_n: int, reach: int = 16
) -> bool:
    """True if an interior diamond deck sits on this row beside the column.

    Cave earth is 'void' in the tunnel mask, so a wallpaper panel above a
    green-room diamond looks like a corridor. Outdoor girder diamonds stay
    ignored so real cave tunnels are not dropped.
    """
    for step in (-1, 1):
        x = cx
        for _ in range(reach):
            x += step
            if x < 0 or x >= cw:
                break
            if cell_is_diamond_floor(px, x, cy):
                if _biome_at(biomes, sx_n, x, cy) == "interior":
                    return True
                break
            counts = _cell_counts(px, x, cy)
            if _is_cave_paper(counts):
                break
    return False


def find_cave_gaps(
    px,
    cw: int,
    ch: int,
    biomes: list[str],
    sx_n: int,
) -> list[tuple[int, int, int]]:
    """Walkable black corridors between two blue-brick masses.

    Flooded tunnels look like this: air in the upper half of the gap, water
    (blue brick / jagged fringe) in the lower half. Each hit is
    `(cx, y_ceil, y_floor)` with the gap interior between them.
    """
    paper, void, fringe = _cave_cell_masks(px, cw, ch)
    lining = [
        [paper[cy][cx] or fringe[cy][cx] for cx in range(cw)] for cy in range(ch)
    ]
    raw: list[tuple[int, int, int]] = []
    for cx in range(cw):
        cy = 0
        while cy < ch:
            if not void[cy][cx]:
                cy += 1
                continue
            y0 = cy
            while cy < ch and void[cy][cx]:
                cy += 1
            y1 = cy - 1
            h = y1 - y0 + 1
            if h < _GAP_MIN_H or h > _GAP_MAX_H:
                continue
            if y0 == 0 or y1 + 1 >= ch:
                continue
            if not (lining[y0 - 1][cx] and lining[y1 + 1][cx]):
                continue
            if _biome_at(biomes, sx_n, cx, y0) != "cave":
                continue
            raw.append((cx, y0 - 1, y1 + 1))
    return _wide_horizontal_runs(raw, _TUNNEL_MIN_WIDTH)


def find_red_pillars(px, cw: int, ch: int) -> list[tuple[int, int, int]]:
    """Vertical red posts: 1 cell wide, not a floor strip.

    Horizontal red brick has neighbours on the left or right. A post does not.
    Each hit is `(cx, y0, y1)` inclusive.
    """
    red = [[False] * cw for _ in range(ch)]
    for cy in range(ch):
        for cx in range(cw):
            red[cy][cx] = cell_is_red_brick(_cell_counts(px, cx, cy))
    runs: list[tuple[int, int, int]] = []
    for cx in range(cw):
        cy = 0
        while cy < ch:
            left = cx > 0 and red[cy][cx - 1]
            right = cx + 1 < cw and red[cy][cx + 1]
            if not red[cy][cx] or left or right:
                cy += 1
                continue
            y0 = cy
            while cy < ch and red[cy][cx]:
                left = cx > 0 and red[cy][cx - 1]
                right = cx + 1 < cw and red[cy][cx + 1]
                if left or right:
                    break
                cy += 1
            y1 = cy - 1
            if y1 - y0 + 1 >= _PILLAR_MIN_H:
                runs.append((cx, y0, y1))
    return runs


def _clear_red_pillars(px, solid: list[list[int]]) -> int:
    """Remove collision from decorative red posts, including thicken stubs."""
    ch = len(solid)
    cw = len(solid[0])
    cleared = 0
    for cx, y0, y1 in find_red_pillars(px, cw, ch):
        for cy in range(y0, y1 + 1):
            if solid[cy][cx]:
                cleared += 1
            solid[cy][cx] = 0
        for d in range(1, 4):
            yy = y1 + d
            if yy >= ch:
                break
            left = cx > 0 and solid[yy][cx - 1]
            right = cx + 1 < cw and solid[yy][cx + 1]
            if solid[yy][cx] and not left and not right:
                solid[yy][cx] = 0
                cleared += 1
            else:
                break
    return cleared


# The bookcase is built from three fixed shelf-plank characters: a left end, a
# repeated middle, and a right end. Books above them are random attributes, so
# the planks are the only reliable fingerprint of a cabinet.
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
# One shelf is a books row followed by a plank row.
SHELF_PITCH = 2


def plank_kind(px, cx: int, cy: int) -> str:
    x0, y0 = cx * CELL, cy * CELL
    if _col(*px[x0, y0]) != "k" or _col(*px[x0 + 7, y0]) != "k":
        return ""
    if _col(*px[x0, y0 + 7]) != "g" or _col(*px[x0 + 7, y0 + 7]) != "g":
        return ""
    rows = tuple("".join(_col(*px[x0 + x, y0 + y]) for x in range(CELL)) for y in range(CELL))
    for kind, tile in PLANK_TILES.items():
        if rows == tile:
            return kind
    return ""


def find_bookcases(im: Image.Image) -> list[tuple[int, int, int, int]]:
    """Cell rects of every bookcase: a stack of shelves, books row on top."""
    px = im.load()
    cw, ch = im.width // CELL, im.height // CELL
    kind = [["" for _ in range(cw)] for _ in range(ch)]
    for cy in range(ch):
        for cx in range(cw):
            kind[cy][cx] = plank_kind(px, cx, cy)

    runs: dict[tuple[int, int], list[int]] = {}
    for cy in range(ch):
        cx = 0
        while cx < cw:
            if kind[cy][cx] != "L":
                cx += 1
                continue
            x1 = cx + 1
            while x1 < cw and kind[cy][x1] == "M":
                x1 += 1
            if x1 > cx + 1 and x1 < cw and kind[cy][x1] == "R":
                runs.setdefault((cx, x1), []).append(cy)
                cx = x1 + 1
            else:
                cx += 1

    cases: list[tuple[int, int, int, int]] = []
    for (x0, x1), rows in runs.items():
        rows.sort()
        i = 0
        while i < len(rows):
            j = i
            while j + 1 < len(rows) and rows[j + 1] - rows[j] == SHELF_PITCH:
                j += 1
            first, last = rows[i], rows[j]
            # Guard sprites baked into the map rip cover the middle of some
            # shelves, but the plank ends survive — follow those.
            while first - SHELF_PITCH > 0 and plank_ends(kind, x0, x1, first - SHELF_PITCH):
                first -= SHELF_PITCH
            while last + SHELF_PITCH < ch and plank_ends(kind, x0, x1, last + SHELF_PITCH):
                last += SHELF_PITCH
            top = first - 1
            cases.append((x0, top, x1 - x0 + 1, last - top + 1))
            i = j + 1
    return sorted(cases)


def plank_ends(kind: list[list[str]], x0: int, x1: int, cy: int) -> bool:
    return kind[cy][x0] == "L" and kind[cy][x1] == "R"


def classify_cells(
    im: Image.Image,
) -> tuple[
    list[list[int]],
    list[list[int]],
    list[list[int]],
    list[list[int]],
    list[tuple[int, int, int, int]],
    list[str],
]:
    px = im.load()
    w, h = im.size
    cw, ch = w // CELL, h // CELL
    sx_n, sy_n = w // SCREEN_W, h // SCREEN_H
    biomes = _detect_biomes(px, sx_n, sy_n)

    cases = find_bookcases(im)
    bookcase = [[0] * cw for _ in range(ch)]
    for x0, y0, bw, bh in cases:
        for cy in range(y0, y0 + bh):
            for cx in range(x0, x0 + bw):
                bookcase[cy][cx] = 1

    solid = [[0] * cw for _ in range(ch)]
    ladder = [[0] * cw for _ in range(ch)]
    fg = [[0] * cw for _ in range(ch)]
    for cy in range(ch):
        sy = (cy * CELL) // SCREEN_H
        for cx in range(cw):
            sx = (cx * CELL) // SCREEN_W
            biome = biomes[sy * sx_n + sx]
            counts = {k: 0 for k in "kbgrcywmo"}
            x0, y0 = cx * CELL, cy * CELL
            for y in range(y0, y0 + CELL):
                for x in range(x0, x0 + CELL):
                    counts[_col(*px[x, y])] += 1
            # Crates and bookcases sit in the foreground and are never collision.
            if cell_is_crate(counts) or bookcase[cy][cx]:
                fg[cy][cx] = 1
            if fg[cy][cx]:
                if cell_is_ladder(px, cx, cy):
                    ladder[cy][cx] = 1
                continue
            # Blue brick is the far wall of a basement, never a collider.
            if _is_cave_paper(counts):
                if cell_is_ladder(px, cx, cy):
                    ladder[cy][cx] = 1
                continue
            red_brick = cell_is_red_brick(counts)
            speckled_earth = _is_speckled_earth(counts)
            black_wall = counts["k"] >= 40 and counts["g"] < 20
            if biome == "sky":
                if counts["b"] >= 40:
                    pass
                elif red_brick or black_wall or speckled_earth:
                    solid[cy][cx] = 1
            elif biome == "interior":
                if red_brick:
                    solid[cy][cx] = 1
                elif speckled_earth:
                    # Biome is per flip-screen, so interior rooms still contain
                    # cave earth. Sky/cave already mark it solid; this branch did not.
                    solid[cy][cx] = 1
                elif black_wall and (cx < 3 or cx >= cw - 3 or cy >= ch - 3):
                    # cw/ch are the mosaic, so this is the world border, not
                    # each 256×192 screen edge. Per-screen walls would solidify
                    # black interior floors along every flip-screen seam.
                    solid[cy][cx] = 1
            else:
                # Blue brick is a room (lift shaft, cave hall), not a wall.
                if red_brick or speckled_earth:
                    solid[cy][cx] = 1
            if cell_is_ladder(px, cx, cy):
                ladder[cy][cx] = 1
    # Keep only thin vertical ladder runs.
    keep = [[0] * cw for _ in range(ch)]
    for cx in range(cw):
        cy = 0
        while cy < ch:
            if not ladder[cy][cx]:
                cy += 1
                continue
            y0 = cy
            while cy < ch and ladder[cy][cx]:
                cy += 1
            if cy - y0 >= 3:
                for y in range(y0, cy):
                    wide = 0
                    for dx in (-1, 0, 1):
                        xx = cx + dx
                        if 0 <= xx < cw and ladder[y][xx]:
                            wide += 1
                    if wide <= 2:
                        keep[y][cx] = 1
    fill_cave_earth(solid, biomes, sx_n, px)
    thicken_floors(solid, 3)
    # Paper and crates must not keep thicken stubs; tunnel linings are
    # re-applied after this punch.
    _clear_walkable_decor(px, solid)
    # Isolated red posts are wallpaper, not walls. Clear after thicken so a
    # hanging post does not leave a 24px stub in the room below.
    _clear_red_pillars(px, solid)
    # Slabs after thicken: growing them down would hang 24px into the room
    # below and turn the underside of a floor into an invisible wall.
    _apply_diamond_floors(px, solid)
    # After thicken: a 1-cell ceiling must not grow down into the corridor.
    _apply_cave_tunnels(px, solid, biomes)
    _apply_cave_gaps(px, solid, biomes)
    punch_ladder_shafts(solid, keep)
    cap_ladder_hatches(solid, keep)
    for cy in range(ch):
        for cx in range(cw):
            if fg[cy][cx]:
                solid[cy][cx] = 0
    return solid, keep, fg, bookcase, cases, biomes


def _detect_biomes(px, sx_n: int, sy_n: int) -> list[str]:
    biomes: list[str] = []
    n = SCREEN_W * SCREEN_H
    for sy in range(sy_n):
        for sx in range(sx_n):
            sky = blk = grn = 0
            for y in range(sy * SCREEN_H, (sy + 1) * SCREEN_H):
                for x in range(sx * SCREEN_W, (sx + 1) * SCREEN_W):
                    k = _col(*px[x, y])
                    if k == "b":
                        sky += 1
                    elif k == "k":
                        blk += 1
                    elif k == "g":
                        grn += 1
            if sky / n > 0.55:
                biomes.append("sky")
            elif grn / n > 0.12:
                biomes.append("interior")
            else:
                biomes.append("cave")
    return biomes


def _biome_at(biomes: list[str], sx_n: int, cx: int, cy: int) -> str:
    sy = (cy * CELL) // SCREEN_H
    sx = (cx * CELL) // SCREEN_W
    return biomes[sy * sx_n + sx]


def fill_cave_earth(solid: list[list[int]], biomes: list[str], sx_n: int, px) -> None:
    """Black mass in caves that is not reachable air above a floor becomes rock.

    Blue brick rooms and yellow crates stay air: they are wallpaper / furniture,
    not the cave earth this fill is for.
    """
    from collections import deque

    ch = len(solid)
    cw = len(solid[0])
    air = [[False] * cw for _ in range(ch)]
    q: deque[tuple[int, int]] = deque()
    for cy in range(ch):
        for cx in range(cw):
            if not solid[cy][cx]:
                continue
            if _biome_at(biomes, sx_n, cx, cy) != "cave":
                continue
            ny = cy - 1
            if ny < 0 or solid[ny][cx] or air[ny][cx]:
                continue
            if _biome_at(biomes, sx_n, cx, ny) != "cave":
                continue
            air[ny][cx] = True
            q.append((cx, ny))
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                continue
            if air[ny][nx] or solid[ny][nx]:
                continue
            if _biome_at(biomes, sx_n, nx, ny) != "cave":
                continue
            air[ny][nx] = True
            q.append((nx, ny))
    for cy in range(ch):
        for cx in range(cw):
            if solid[cy][cx] or air[cy][cx]:
                continue
            if _biome_at(biomes, sx_n, cx, cy) != "cave":
                continue
            counts = _cell_counts(px, cx, cy)
            if _is_cave_paper(counts) or cell_is_crate(counts):
                continue
            solid[cy][cx] = 1


def _clear_walkable_decor(px, solid: list[list[int]]) -> int:
    """Blue brick wallpaper and crates are never collision."""
    ch = len(solid)
    cw = len(solid[0])
    cleared = 0
    for cy in range(ch):
        for cx in range(cw):
            if not solid[cy][cx]:
                continue
            counts = _cell_counts(px, cx, cy)
            if _is_cave_paper(counts) or cell_is_crate(counts):
                solid[cy][cx] = 0
                cleared += 1
    return cleared


def thicken_floors(solid: list[list[int]], depth: int) -> None:
    """Grow floors downward so fast falls cannot tunnel through 8px bricks.

    Not idempotent: each call grows every current underside by `depth` cells.
    """
    ch = len(solid)
    cw = len(solid[0])
    extra = [[0] * cw for _ in range(ch)]
    for y in range(ch - 1):
        for x in range(cw):
            if not solid[y][x] or solid[y + 1][x]:
                continue
            for d in range(1, depth + 1):
                yy = y + d
                if yy >= ch or solid[yy][x]:
                    break
                extra[yy][x] = 1
    for y in range(ch):
        for x in range(cw):
            if extra[y][x]:
                solid[y][x] = 1


def punch_ladder_shafts(solid: list[list[int]], ladders: list[list[int]]) -> None:
    """Open the shaft under a hatch, but keep the walkable floor lid."""
    ch = len(solid)
    cw = len(solid[0])

    def is_walkable_lid(x: int, y: int) -> bool:
        if y < 0 or y >= ch or x < 0 or x >= cw:
            return False
        if not solid[y][x]:
            return False
        return y == 0 or not solid[y - 1][x]

    for y in range(ch):
        for x in range(cw):
            if not ladders[y][x] or is_walkable_lid(x, y):
                continue
            for dx in (-1, 0, 1):
                xx = x + dx
                if 0 <= xx < cw and not is_walkable_lid(xx, y):
                    solid[y][xx] = 0


def cap_ladder_hatches(solid: list[list[int]], ladders: list[list[int]]) -> None:
    """Fill the hatch so a floor opening with a ladder is still walkable."""
    ch = len(solid)
    cw = len(solid[0])
    for y in range(ch):
        x = 0
        while x < cw:
            if not ladders[y][x]:
                x += 1
                continue
            x0 = x
            while x < cw and ladders[y][x]:
                x += 1
            beside_floor = False
            for xx in (x0 - 1, x):
                if 0 <= xx < cw and solid[y][xx] and (y == 0 or not solid[y - 1][xx]):
                    beside_floor = True
                    break
            if not beside_floor:
                continue
            for xx in range(x0, x):
                solid[y][xx] = 1


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


def load_mission_spawn() -> list[int]:
    """Player spawn lives in hand-authored s2_entities.json, not this generator."""
    data = json.loads((OUT_DIR / "s2_entities.json").read_text(encoding="utf-8"))
    spawn = data["spawn"]
    return [int(spawn[0]), int(spawn[1])]


def preview(
    im: Image.Image,
    solid: list[list[int]],
    ladders: list[list[int]],
    spawn: list[int] | None = None,
) -> Image.Image:
    overlay = im.copy().convert("RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")
    ch = len(solid)
    cw = len(solid[0])
    for cy in range(ch):
        for cx in range(cw):
            x0, y0 = cx * CELL, cy * CELL
            if solid[cy][cx]:
                draw.rectangle((x0, y0, x0 + CELL - 1, y0 + CELL - 1), fill=(255, 40, 40, 110))
            if ladders[cy][cx]:
                draw.rectangle((x0, y0, x0 + CELL - 1, y0 + CELL - 1), fill=(40, 220, 255, 140))
    # PNG pixels, same space as solids/ladders/lifts. World = spawn * SCALE.
    # Marker sits on the feet.
    if spawn is None:
        spawn = load_mission_spawn()
    sx, sy = spawn[0], spawn[1] + 56
    draw.rectangle((sx - 4, sy - 28, sx + 12, sy), outline=(255, 255, 0, 255))
    return overlay.resize((im.width // 4, im.height // 4), Image.NEAREST)


def crate_overlay(
    im: Image.Image,
    fg: list[list[int]],
    bookcase: list[list[int]],
    cases: list[tuple[int, int, int, int]],
) -> Image.Image:
    """Foreground art Nina walks behind.

    Black is the empty space of the cabinet, so it stays transparent and Nina
    shows through the gaps between the shelves. Crates keep their own pixels.
    """
    w, h = im.size
    src = im.convert("RGBA")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    ch, cw = len(fg), len(fg[0])
    for cy in range(ch):
        for cx in range(cw):
            if not fg[cy][cx] or bookcase[cy][cx]:
                continue
            _blit_ink(sp, op, cx, cy)
    for x0, y0, bw, bh in cases:
        _blit_bookcase(sp, op, x0, y0, bw, bh)
    return out


def _blit_ink(sp, op, cx: int, cy: int) -> None:
    x0, y0 = cx * CELL, cy * CELL
    for y in range(y0, y0 + CELL):
        for x in range(x0, x0 + CELL):
            pix = sp[x, y]
            if pix[0] < 20 and pix[1] < 20 and pix[2] < 20:
                continue
            op[x, y] = pix


def _blit_bookcase(sp, op, x0: int, y0: int, bw: int, bh: int) -> None:
    """Redraw the cabinet from its own parts, dropping the map rip's guards.

    Shelf rows are the three known plank characters; book rows keep every
    column that is one solid bar top to bottom.
    """
    green = _cabinet_green(sp, x0, y0, bw, bh)
    for cy in range(y0, y0 + bh):
        if (cy - y0) % SHELF_PITCH:
            for cx in range(x0, x0 + bw):
                tile = (
                    PLANK_TILES["L"]
                    if cx == x0
                    else PLANK_TILES["R"] if cx == x0 + bw - 1 else PLANK_TILES["M"]
                )
                px0, py0 = cx * CELL, cy * CELL
                for y in range(CELL):
                    for x in range(CELL):
                        if tile[y][x] == "g":
                            op[px0 + x, py0 + y] = green
            continue
        for x in range(x0 * CELL, (x0 + bw) * CELL):
            _blit_book_column(sp, op, x, cy * CELL)


def _cabinet_green(sp, x0: int, y0: int, bw: int, bh: int) -> tuple[int, int, int, int]:
    for y in range((y0 + 1) * CELL, (y0 + bh) * CELL):
        for x in range(x0 * CELL, (x0 + bw) * CELL):
            pix = sp[x, y]
            if _col(*pix[:3]) == "g":
                return pix
    return (0, 255, 0, 255)


def _blit_book_column(sp, op, x: int, y0: int) -> None:
    """A book is a full-height coloured bar; green or black is cabinet air.

    Guards baked into the map rip break the bar, so their columns drop out.
    """
    counts: dict[tuple, int] = {}
    for y in range(y0, y0 + CELL):
        pix = sp[x, y]
        counts[pix] = counts.get(pix, 0) + 1
    pix, n = max(counts.items(), key=lambda kv: kv[1])
    if n < CELL - 2 or _col(*pix[:3]) in "kg":
        return
    for y in range(y0, y0 + CELL):
        op[x, y] = sp[x, y]


def cell_is_lift_car(counts: dict[str, int]) -> bool:
    """Cyan lift platform tile — not a crate, window, or blue brick."""
    return (
        counts["c"] >= 18
        and counts["k"] >= 4
        and counts["r"] < 8
        and counts["g"] < 12
        and counts["y"] < 20
        and counts["b"] < 24
    )


def find_lifts(
    im: Image.Image, solid: list[list[int]]
) -> tuple[list[dict], Image.Image, list[tuple[int, int, int, int]]]:
    """Locate original 6-tile cyan cars in vertical shafts.

    UP/DOWN while standing in the centre starts the car; it travels the
    shaft and stops at the far end (S2CORE LIFTU/LIFTD).
    """
    px = im.load()
    ch, cw = len(solid), len(solid[0])
    cars: list[tuple[int, int, int]] = []
    cy = 1
    while cy < ch - 1:
        cx = 0
        while cx < cw:
            counts = _cell_counts(px, cx, cy)
            if not cell_is_lift_car(counts):
                cx += 1
                continue
            x0 = cx
            while cx < cw and cell_is_lift_car(_cell_counts(px, cx, cy)):
                cx += 1
            run = cx - x0
            if run < 6 or run > 8:
                continue
            above = sum(
                1 for i in range(run) if cell_is_lift_car(_cell_counts(px, x0 + i, cy - 1))
            )
            below = sum(
                1 for i in range(run) if cell_is_lift_car(_cell_counts(px, x0 + i, cy + 1))
            )
            if above >= 3 or below >= 3:
                continue
            mid = x0 + run // 2
            up = 0
            y = cy - 1
            while y >= 0 and not solid[y][mid] and up < 400:
                up += 1
                y -= 1
            down = 0
            y = cy + 1
            while y < ch and not solid[y][mid] and down < 400:
                down += 1
                y += 1
            if up + down < 48:
                continue
            cars.append((x0, cy, run))
        cy += 1

    lifts: list[dict] = []
    car_rows: list[tuple[int, int, int, int]] = []
    car_img = Image.new("RGB", (6 * CELL, CELL), (0, 255, 255))
    got_sprite = False
    for x0, cy, run in cars:
        mid = x0 + run // 2
        top = cy
        while top > 0 and not solid[top - 1][mid]:
            top -= 1
        bot = cy
        while bot + 1 < ch and not solid[bot + 1][mid]:
            bot += 1
        spec = {
            "x": x0 * CELL,
            "y": cy * CELL,
            "w": run * CELL,
            "h": CELL,
            "top": top * CELL,
            "bottom": bot * CELL,
        }
        car_rows.append((x0 * CELL, cy * CELL, run * CELL, CELL))
        merged = False
        for prev in lifts:
            same_x = abs(prev["x"] - spec["x"]) <= CELL * 2
            overlap = not (spec["bottom"] < prev["top"] or spec["top"] > prev["bottom"])
            if same_x and overlap:
                prev["top"] = min(prev["top"], spec["top"])
                prev["bottom"] = max(prev["bottom"], spec["bottom"])
                prev["w"] = min(prev["w"], spec["w"])
                merged = True
                break
        if not merged:
            lifts.append(spec)
        if not got_sprite and run >= 6:
            car_img = im.crop((x0 * CELL, cy * CELL, (x0 + 6) * CELL, (cy + 1) * CELL))
            got_sprite = True
    for spec in lifts:
        x0 = spec["x"] // CELL
        run = max(spec["w"] // CELL, 6)
        cy = spec["y"] // CELL
        ceil = spec["top"] // CELL
        pit = spec["bottom"] // CELL
        top_y, bot_y = _shaft_stops(solid, x0, run, cy, ceil, pit)
        spec["top"] = top_y * CELL
        spec["bottom"] = bot_y * CELL
        spec["w"] = min(spec["w"], 6 * CELL)
    return lifts, car_img, car_rows


def _is_floor_ledge(solid: list[list[int]], y: int, x: int) -> bool:
    if x < 0 or x >= len(solid[0]) or y < 0 or y >= len(solid):
        return False
    return bool(solid[y][x]) and (y == 0 or not solid[y - 1][x])


def _shaft_landings(
    solid: list[list[int]], x0: int, run: int, y0: int, y1: int, reach: int
) -> list[int]:
    mid = min(max(x0 + run // 2, 0), len(solid[0]) - 1)
    found: list[int] = []
    for y in range(max(0, y0), min(len(solid), y1 + 1)):
        if solid[y][mid]:
            continue
        ledge = False
        for dx in range(1, reach + 1):
            if _is_floor_ledge(solid, y, x0 - dx) or _is_floor_ledge(solid, y, x0 + run + dx - 1):
                ledge = True
                break
        if ledge:
            found.append(y)
    return found


def _shaft_stops(
    solid: list[list[int]], x0: int, run: int, cy: int, ceil: int, pit: int
) -> tuple[int, int]:
    """Far-end floors, not the ceiling/pit of the open column.

    Original cars travel the whole shaft and stop where you can walk off
    (S2CORE LIFTU/LIFTD). Intermediate ledges are skipped.
    """
    near = _shaft_landings(solid, x0, run, ceil, pit, 8)
    if cy not in near:
        near.append(cy)
    near.sort()
    return near[0], near[-1]


def _cell_counts(px, cx: int, cy: int) -> dict[str, int]:
    counts = {k: 0 for k in "kbgrcywmo"}
    x0, y0 = cx * CELL, cy * CELL
    for y in range(y0, y0 + CELL):
        for x in range(x0, x0 + CELL):
            counts[_col(*px[x, y])] += 1
    return counts


def paint_lift_cars(world: Image.Image, car_rows: list[tuple[int, int, int, int]]) -> None:
    """Erase baked cars so the moving sprite is the only platform."""
    wp = world.load()
    for x, y, w, h in car_rows:
        src_y = y - CELL if y >= CELL else y + h
        for dy in range(h):
            for dx in range(w):
                pix = wp[x + dx, y + dy]
                ink = _col(*pix[:3])
                if ink != "c":
                    continue
                wp[x + dx, y + dy] = wp[x + dx, src_y + dy]


def paint_cabinet_backs(world: Image.Image, bookcase: list[list[int]]) -> None:
    """Black out bookcase cells so FG books sit on a dark cabinet, not wallpaper."""
    wp = world.load()
    ch, cw = len(bookcase), len(bookcase[0])
    for cy in range(ch):
        for cx in range(cw):
            if not bookcase[cy][cx]:
                continue
            x0, y0 = cx * CELL, cy * CELL
            for y in range(y0, y0 + CELL):
                for x in range(x0, x0 + CELL):
                    wp[x, y] = (0, 0, 0)


def reconstruct_world_from_tiles() -> Image.Image:
    """Rebuild the mosaic from the committed visual tileset when the rip is absent."""
    spec = json.loads((OUT_DIR / "s2_world_tiles.json").read_text(encoding="utf-8"))
    ids = rle_decode(spec["world"]["rle"])
    cw, ch = spec["grid"]
    atlas_cols = spec["world"]["atlas_tiles"][0]
    atlas_name = Path(spec["world"]["atlas"]).name
    atlas = Image.open(TILESET_DIR / atlas_name).convert("RGB")
    out = Image.new("RGB", (cw * CELL, ch * CELL))
    for i, tid in enumerate(ids):
        ax, ay = (tid % atlas_cols) * CELL, (tid // atlas_cols) * CELL
        cx, cy = i % cw, i // cw
        out.paste(atlas.crop((ax, ay, ax + CELL, ay + CELL)), (cx * CELL, cy * CELL))
    return out


def load_world_image() -> Image.Image:
    if SRC.exists():
        return Image.open(SRC).convert("RGB")
    print(f"rip missing at {SRC}; reconstructing world from tileset")
    return reconstruct_world_from_tiles()


def ladder_rects_from_grid(ladders: list[list[int]]) -> list[list[int]]:
    rects: list[list[int]] = []
    for x, y, w, h in greedy_rects(ladders):
        if h < 24:
            continue
        # Keep the hit box close to the 8–16px rails so windows and wallpaper
        # next to a shaft are not climbable.
        rects.append([x - 4, y, w + 8, h])
    return rects


def detect_ladder_grid(im: Image.Image) -> list[list[int]]:
    """Pixel ladder mask after the thin-run filter, no solid/fg side effects."""
    px = im.load()
    cw, ch = im.width // CELL, im.height // CELL
    raw = [[0] * cw for _ in range(ch)]
    for cy in range(ch):
        for cx in range(cw):
            if cell_is_ladder(px, cx, cy):
                raw[cy][cx] = 1
    keep = [[0] * cw for _ in range(ch)]
    for cx in range(cw):
        cy = 0
        while cy < ch:
            if not raw[cy][cx]:
                cy += 1
                continue
            y0 = cy
            while cy < ch and raw[cy][cx]:
                cy += 1
            if cy - y0 >= 3:
                for y in range(y0, cy):
                    wide = 0
                    for dx in (-1, 0, 1):
                        xx = cx + dx
                        if 0 <= xx < cw and raw[y][xx]:
                            wide += 1
                    if wide <= 2:
                        keep[y][cx] = 1
    return keep


def update_collision_ladders(im: Image.Image) -> list[list[int]]:
    """Rewrite only the ladders array in the committed collision JSON."""
    keep = detect_ladder_grid(im)
    rects = ladder_rects_from_grid(keep)
    path = OUT_DIR / "s2_collision.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ladders"] = rects
    path.write_text(json.dumps(data), encoding="utf-8")
    n_lad = sum(sum(row) for row in keep)
    print(f"ladder cells {n_lad} -> {len(rects)} rects")
    print(f"updated {path}")
    return rects


def _paint_solid_rects(rects: list[list[int]], cw: int, ch: int) -> list[list[int]]:
    grid = [[0] * cw for _ in range(ch)]
    for x, y, w, h in rects:
        x0 = max(0, x // CELL)
        y0 = max(0, y // CELL)
        x1 = min(cw, (x + w + CELL - 1) // CELL)
        y1 = min(ch, (y + h + CELL - 1) // CELL)
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                px, py = cx * CELL + CELL // 2, cy * CELL + CELL // 2
                if x <= px < x + w and y <= py < y + h:
                    grid[cy][cx] = 1
    return grid


def _world_border_pads(w: int, h: int) -> list[list[int]]:
    pad = CELL * 2
    return [
        [-pad, -pad, w + pad * 2, pad],
        [-pad, h, w + pad * 2, pad],
        [-pad, 0, pad, h],
        [w, 0, pad, h],
    ]


def _apply_diamond_floors(px, solid: list[list[int]]) -> int:
    """Mark white diamond slabs solid without thickening them."""
    ch = len(solid)
    cw = len(solid[0])
    added = 0
    for cy in range(ch):
        for cx in range(cw):
            if not cell_is_diamond_floor(px, cx, cy):
                continue
            if not solid[cy][cx]:
                added += 1
            solid[cy][cx] = 1
    return added


def _apply_cave_tunnels(px, solid: list[list[int]], biomes: list[str]) -> tuple[int, int, int]:
    """Thin blue-brick cave corridors: solid ceiling, solid floor, air inside.

    `fill_cave_earth` can seal an unreached corridor as rock; the interior is
    punched open here. Not thickened — growing the ceiling would fill the gap.
    """
    ch = len(solid)
    cw = len(solid[0])
    sx_n = (cw * CELL) // SCREEN_W
    added_ceil = 0
    added_floor = 0
    punched = 0
    for cx, y0, y1 in find_cave_tunnels(px, cw, ch, biomes, sx_n):
        if not solid[y0][cx]:
            added_ceil += 1
        solid[y0][cx] = 1
        if not solid[y1][cx]:
            added_floor += 1
        solid[y1][cx] = 1
        for cy in range(y0 + 1, y1):
            if solid[cy][cx]:
                punched += 1
            solid[cy][cx] = 0
    return added_ceil, added_floor, punched


def _apply_cave_gaps(px, solid: list[list[int]], biomes: list[str]) -> tuple[int, int, int]:
    """Open black cave corridors between brick masses; lining is not thickened.

    Flooded tunnels are this shape: walkable air above water, solid ceiling
    on the brick above, solid floor on the brick below.
    """
    ch = len(solid)
    cw = len(solid[0])
    sx_n = (cw * CELL) // SCREEN_W
    added_ceil = 0
    added_floor = 0
    punched = 0
    for cx, y0, y1 in find_cave_gaps(px, cw, ch, biomes, sx_n):
        if not solid[y0][cx]:
            added_ceil += 1
        solid[y0][cx] = 1
        if not solid[y1][cx]:
            added_floor += 1
        solid[y1][cx] = 1
        for cy in range(y0 + 1, y1):
            if solid[cy][cx]:
                punched += 1
            solid[cy][cx] = 0
    return added_ceil, added_floor, punched


def update_collision_diamond_floors(im: Image.Image) -> list[list[int]]:
    """Add diamond slabs and cave-tunnel linings without re-thickening."""
    px = im.load()
    cw, ch = im.width // CELL, im.height // CELL
    sx_n, sy_n = im.width // SCREEN_W, im.height // SCREEN_H
    path = OUT_DIR / "s2_collision.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    solid = _paint_solid_rects(data["solids"], cw, ch)
    decor = _clear_walkable_decor(px, solid)
    added = _apply_diamond_floors(px, solid)
    biomes = _detect_biomes(px, sx_n, sy_n)
    ceil_n, floor_n, punched = _apply_cave_tunnels(px, solid, biomes)
    g_ceil, g_floor, g_punch = _apply_cave_gaps(px, solid, biomes)
    pillars = _clear_red_pillars(px, solid)
    cap_ladder_hatches(solid, detect_ladder_grid(im))
    rects = greedy_rects(solid)
    rects.extend(_world_border_pads(im.width, im.height))
    data["solids"] = rects
    path.write_text(json.dumps(data), encoding="utf-8")
    print(f"walkable decor cleared {decor}")
    print(f"diamond floor cells added {added} -> {len(rects)} solid rects")
    print(f"cave tunnel ceiling {ceil_n} floor {floor_n} interior opened {punched}")
    print(f"cave gap ceiling {g_ceil} floor {g_floor} interior opened {g_punch}")
    print(f"red posts cleared {pillars}")
    print(f"updated {path}")
    return rects


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    print(f"mosaic {im.size}")
    solid, ladders, fg, bookcase, cases, biomes = classify_cells(im)
    solids = greedy_rects(solid)
    ladder_rects = ladder_rects_from_grid(ladders)
    w, h = im.size
    pad = CELL * 2
    solids.extend(
        [
            [-pad, -pad, w + pad * 2, pad],
            [-pad, h, w + pad * 2, pad],
            [-pad, 0, pad, h],
            [w, 0, pad, h],
        ]
    )
    lifts, car_img, car_rows = find_lifts(im, solid)
    n_solid = sum(sum(row) for row in solid)
    n_lad = sum(sum(row) for row in ladders)
    n_fg = sum(sum(row) for row in fg)
    n_case = sum(sum(row) for row in bookcase)
    print(f"solid cells {n_solid} -> {len(solids)} rects")
    print(f"ladder cells {n_lad} -> {len(ladder_rects)} rects")
    print(f"foreground cells {n_fg} (bookcase {n_case} in {len(cases)} cabinets)")
    print(f"lifts {len(lifts)}")
    for spec in lifts:
        print(f"  car ({spec['x']},{spec['y']}) {spec['w']}x{spec['h']} shaft {spec['top']}..{spec['bottom']}")
    from collections import Counter
    print("biomes", Counter(biomes))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    world = im.copy()
    paint_cabinet_backs(world, bookcase)
    paint_lift_cars(world, car_rows)
    world.save(OUT_DIR / "saboteur2_world.png")
    fg_img = crate_overlay(im, fg, bookcase, cases)
    fg_img.save(OUT_DIR / "saboteur2_fg.png")
    car_img.save(OUT_DIR / "s2_lift.png")
    export_visual_tilesets(world, fg_img)
    payload = {
        "source": "Saboteur2_speccy.png",
        "scale": SCALE,
        "cell": CELL,
        "screen": [SCREEN_W, SCREEN_H],
        "size": [im.width, im.height],
        "solids": solids,
        "ladders": ladder_rects,
        "lifts": lifts,
        "bookcases": [[x * CELL, y * CELL, bw * CELL, bh * CELL] for x, y, bw, bh in cases],
    }
    (OUT_DIR / "s2_collision.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {OUT_DIR}")


def rle_encode(indices: list[int]) -> list[int]:
    """Flat [value, count, ...] run-length encoding of a row-major tile grid."""
    if not indices:
        return []
    out: list[int] = []
    prev = indices[0]
    count = 1
    for value in indices[1:]:
        if value == prev:
            count += 1
        else:
            out.extend((prev, count))
            prev = value
            count = 1
    out.extend((prev, count))
    return out


def rle_decode(runs: list[int]) -> list[int]:
    out: list[int] = []
    for i in range(0, len(runs), 2):
        out.extend([runs[i]] * runs[i + 1])
    return out


def _is_fully_transparent(tile: Image.Image) -> bool:
    if tile.mode != "RGBA":
        return False
    extrema = tile.getextrema()
    return extrema is not None and extrema[3] == (0, 0)


def collect_unique_cells(
    im: Image.Image, mode: str
) -> tuple[list[Image.Image], list[int], int, int, int | None]:
    """Return (tiles, row-major ids, cols, rows, empty_id).

    `empty_id` is the fully-transparent cell for RGBA layers, else None.
    Every distinct 8×8 cell — including empty — keeps a stable index so a
    later re-rip does not shuffle atlas coordinates.
    """
    src = im.convert(mode)
    cw, ch = src.width // CELL, src.height // CELL
    index_of: dict[bytes, int] = {}
    tiles: list[Image.Image] = []
    ids: list[int] = []
    empty_id: int | None = None
    for cy in range(ch):
        for cx in range(cw):
            tile = src.crop((cx * CELL, cy * CELL, cx * CELL + CELL, cy * CELL + CELL))
            key = tile.tobytes()
            tid = index_of.get(key)
            if tid is None:
                tid = len(tiles)
                index_of[key] = tid
                tiles.append(tile)
                if empty_id is None and _is_fully_transparent(tile):
                    empty_id = tid
            ids.append(tid)
    return tiles, ids, cw, ch, empty_id


def pack_atlas(tiles: list[Image.Image]) -> tuple[Image.Image, int, int]:
    n = max(len(tiles), 1)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    mode = tiles[0].mode if tiles else "RGBA"
    fill = (0, 0, 0, 0) if mode == "RGBA" else (0, 0, 0)
    atlas = Image.new(mode, (cols * CELL, rows * CELL), fill)
    for i, tile in enumerate(tiles):
        atlas.paste(tile, ((i % cols) * CELL, (i // cols) * CELL))
    return atlas, cols, rows


def reconstruct_from_atlas(
    atlas: Image.Image,
    ids: list[int],
    cw: int,
    ch: int,
    atlas_cols: int,
    mode: str,
) -> Image.Image:
    out = Image.new(mode, (cw * CELL, ch * CELL))
    for i, tid in enumerate(ids):
        ax, ay = (tid % atlas_cols) * CELL, (tid // atlas_cols) * CELL
        cell = atlas.crop((ax, ay, ax + CELL, ay + CELL))
        cx, cy = i % cw, i // cw
        out.paste(cell, (cx * CELL, cy * CELL))
    return out


def _write_tileset_tres(
    path: Path,
    texture_res: str,
    texture_uid: str,
    atlas_cols: int,
    atlas_rows: int,
    tile_count: int,
) -> None:
    """Visual-only TileSet: 8×8 atlas, no physics. Collision stays in JSON."""
    lines = [
        "[gd_resource type=\"TileSet\" load_steps=2 format=3]",
        "",
        f"[ext_resource type=\"Texture2D\" uid=\"{texture_uid}\" path=\"{texture_res}\" id=\"1\"]",
        "",
        "[sub_resource type=\"TileSetAtlasSource\" id=\"TileSetAtlasSource_1\"]",
        "texture = ExtResource(\"1\")",
        "texture_region_size = Vector2i(8, 8)",
        "use_texture_padding = true",
    ]
    written = 0
    for y in range(atlas_rows):
        for x in range(atlas_cols):
            if written >= tile_count:
                break
            lines.append(f"{x}:{y}/0 = 0")
            written += 1
        if written >= tile_count:
            break
    lines.extend(
        [
            "",
            "[resource]",
            "tile_size = Vector2i(8, 8)",
            "sources/0 = SubResource(\"TileSetAtlasSource_1\")",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_visual_tilesets(world: Image.Image, fg: Image.Image) -> dict:
    """Dump unique 8×8 cells to atlases + a cell-index JSON.

    Passability is *not* encoded here. Two identical pictures can still
    differ in s2_collision.json (fill_cave_earth, thicken_floors, …).
    """
    TILESET_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    layers = {
        "world": {
            "image": world,
            "mode": "RGB",
            "atlas_name": "s2_world_tileset.png",
            "tres_name": "s2_world_tileset.tres",
            "texture_uid": "uid://dma7fdoakrrr6",
        },
        "fg": {
            "image": fg,
            "mode": "RGBA",
            "atlas_name": "s2_fg_tileset.png",
            "tres_name": "s2_fg_tileset.tres",
            "texture_uid": "uid://s2fgatlas8px",
        },
    }
    payload: dict = {
        "cell": CELL,
        "scale": SCALE,
        "size": [world.width, world.height],
        "grid": [world.width // CELL, world.height // CELL],
        "note": "Visual tile indices only. Collision stays in s2_collision.json.",
    }
    for name, spec in layers.items():
        tiles, ids, cw, ch, empty_id = collect_unique_cells(spec["image"], spec["mode"])
        atlas, atlas_cols, atlas_rows = pack_atlas(tiles)
        atlas_path = TILESET_DIR / spec["atlas_name"]
        atlas.save(atlas_path)
        # Round-trip through PNG so the file on disk is what Godot will import.
        saved = Image.open(atlas_path).convert(spec["mode"])
        rebuilt = reconstruct_from_atlas(saved, ids, cw, ch, atlas_cols, spec["mode"])
        original = spec["image"].convert(spec["mode"])
        if rebuilt.tobytes() != original.tobytes():
            raise RuntimeError(f"{name} tileset is not pixel-identical to the mosaic")
        rle = rle_encode(ids)
        texture_res = f"res://assets/tilesets/{spec['atlas_name']}"
        _write_tileset_tres(
            TILESET_DIR / spec["tres_name"],
            texture_res,
            spec["texture_uid"],
            atlas_cols,
            atlas_rows,
            len(tiles),
        )
        layer_payload = {
            "atlas": texture_res,
            "tileset": f"res://assets/tilesets/{spec['tres_name']}",
            "atlas_tiles": [atlas_cols, atlas_rows],
            "tile_count": len(tiles),
            "empty": empty_id,
            "rle": rle,
        }
        payload[name] = layer_payload
        print(
            f"{name} unique {len(tiles)} atlas {atlas.size} "
            f"rle {len(rle)//2} runs ({len(rle)} ints) empty_id={empty_id}"
        )

    json_path = OUT_DIR / "s2_world_tiles.json"
    json_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {json_path} ({json_path.stat().st_size} bytes)")
    return payload


def export_tilesets_from_mosaics() -> None:
    """Build atlases from the already-exported mosaics when the rip is absent."""
    world_path = OUT_DIR / "saboteur2_world.png"
    fg_path = OUT_DIR / "saboteur2_fg.png"
    if not world_path.exists() or not fg_path.exists():
        raise SystemExit(
            f"need {world_path.name} and {fg_path.name}, or the original rip at {SRC}"
        )
    print(f"rip missing at {SRC}; exporting tilesets from existing mosaics")
    export_visual_tilesets(Image.open(world_path), Image.open(fg_path))


if __name__ == "__main__":
    import sys

    if "--ladders-only" in sys.argv:
        update_collision_ladders(load_world_image())
    elif "--floors-only" in sys.argv:
        update_collision_diamond_floors(load_world_image())
    elif SRC.exists():
        main()
    else:
        export_tilesets_from_mosaics()
