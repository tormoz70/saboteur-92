#!/usr/bin/env python3
"""Build a playable Saboteur II world from the screenshot mosaic.

Floors are brick strips; cave earth (black with blue specks) is solid. Blue
brick is room wallpaper — a lift shaft stays walkable. Green wallpaper,
furniture and interior black air stay empty. Ladders are the original rail
tiles (interior green pair, outdoor white X-lattice). Yellow crates and
interior bookcases are foreground-only.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "reference" / "original" / "maps" / "Saboteur2_speccy.png"
OUT_DIR = ROOT / "assets" / "world"
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


def cell_is_ladder(px, cx: int, cy: int) -> bool:
    """Match original Saboteur II ladder character graphics.

    Interior ladders are a 16px pair of green rail tiles punched through
    wallpaper. Outdoor ladders are a thin white X-lattice with rails on both
    edges — not windows, lift shafts, or picket fences.
    """
    x0, y0 = cx * CELL, cy * CELL
    rows = [[_ink(px[x0 + x, y0 + y]) for x in range(CELL)] for y in range(CELL)]
    return _is_green_rail_tile(rows) or _is_x_lattice_tile(rows)


def _is_green_rail_tile(rows: list[list[str]]) -> bool:
    if any(p not in "kg" for row in rows for p in row):
        return False
    left = all(row[0] == "g" and row[1] == "k" and row[2] == "k" and row[3] == "g" for row in rows[:2])
    right = all(row[4] == "g" and row[5] == "k" and row[6] == "k" and row[7] == "g" for row in rows[:2])
    return left or right


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
    biomes: list[str] = []
    for sy in range(sy_n):
        for sx in range(sx_n):
            sky = blk = grn = 0
            n = SCREEN_W * SCREEN_H
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
            red_brick = counts["r"] >= 10 and counts["k"] >= 4
            # Black field with sparse blue dots is impermeable cave earth.
            speckled_earth = (
                counts["k"] >= 48
                and 1 <= counts["b"] <= 8
                and counts["g"] < 8
                and counts["r"] < 8
                and counts["c"] < 8
            )
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
    fill_cave_earth(solid, biomes, sx_n)
    thicken_floors(solid, 3)
    punch_ladder_shafts(solid, keep)
    cap_ladder_hatches(solid, keep)
    for cy in range(ch):
        for cx in range(cw):
            if fg[cy][cx]:
                solid[cy][cx] = 0
    return solid, keep, fg, bookcase, cases, biomes


def _biome_at(biomes: list[str], sx_n: int, cx: int, cy: int) -> str:
    sy = (cy * CELL) // SCREEN_H
    sx = (cx * CELL) // SCREEN_W
    return biomes[sy * sx_n + sx]


def fill_cave_earth(solid: list[list[int]], biomes: list[str], sx_n: int) -> None:
    """Black mass in caves that is not reachable air above a floor becomes rock."""
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
            if _biome_at(biomes, sx_n, cx, cy) == "cave":
                solid[cy][cx] = 1


def thicken_floors(solid: list[list[int]], depth: int) -> None:
    """Grow floors downward so fast falls cannot tunnel through 8px bricks."""
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


def find_spawn(solid: list[list[int]]) -> list[int]:
    ch = len(solid)
    cw = len(solid[0])
    # Prefer an early rooftop / tower floor with air above.
    for cy in range(4, ch - 2):
        run = 0
        run_x = 0
        for cx in range(8, min(cw, 40 * 4)):
            air = cy >= 3 and not solid[cy - 1][cx] and not solid[cy - 2][cx]
            if solid[cy][cx] and air:
                if run == 0:
                    run_x = cx
                run += 1
                if run >= 6:
                    px = (run_x + 2) * CELL * SCALE
                    py = cy * CELL * SCALE - 56 * SCALE
                    return [px, py]
            else:
                run = 0
    return [64, 200]


def preview(im: Image.Image, solid: list[list[int]], ladders: list[list[int]], spawn: list[int]) -> Image.Image:
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
    sx, sy = spawn[0] // SCALE, (spawn[1] + 56) // SCALE
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


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    print(f"mosaic {im.size}")
    solid, ladders, fg, bookcase, cases, biomes = classify_cells(im)
    solids = greedy_rects(solid)
    raw_ladders = greedy_rects(ladders)
    ladder_rects: list[list[int]] = []
    for x, y, w, h in raw_ladders:
        if h < 24:
            continue
        # Keep the hit box close to the 8–16px rails so windows and wallpaper
        # next to a shaft are not climbable.
        ladder_rects.append([x - 4, y, w + 8, h])
    spawn = [4480, 1584]
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
    crate_overlay(im, fg, bookcase, cases).save(OUT_DIR / "saboteur2_fg.png")
    car_img.save(OUT_DIR / "s2_lift.png")
    payload = {
        "source": "Saboteur2_speccy.png",
        "scale": SCALE,
        "cell": CELL,
        "screen": [SCREEN_W, SCREEN_H],
        "size": [im.width, im.height],
        "spawn": spawn,
        "solids": solids,
        "ladders": ladder_rects,
        "lifts": lifts,
        "bookcases": [[x * CELL, y * CELL, bw * CELL, bh * CELL] for x, y, bw, bh in cases],
    }
    (OUT_DIR / "s2_collision.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
