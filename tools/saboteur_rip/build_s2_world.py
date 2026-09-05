#!/usr/bin/env python3
"""Build a playable Saboteur II world from the screenshot mosaic.

Floors are brick strips; cave earth and skyline black walls are solid. Green
wallpaper, furniture and interior black air stay empty. Ladders are the
original rail tiles (interior green pair, outdoor white X-lattice). Yellow
crates are foreground-only.
"""
from __future__ import annotations

import json
import shutil
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


def classify_cells(im: Image.Image) -> tuple[list[list[int]], list[list[int]], list[str]]:
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

    solid = [[0] * cw for _ in range(ch)]
    ladder = [[0] * cw for _ in range(ch)]
    crates = [[0] * cw for _ in range(ch)]
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
            # Yellow crates sit in the foreground and are never collision.
            if counts["y"] >= 12 and counts["r"] < 10:
                crates[cy][cx] = 1
            red_brick = counts["r"] >= 10 and counts["k"] >= 4
            # Interior blue is windows on the back wall, not a floor.
            blue_brick = (
                biome == "cave"
                and counts["b"] >= 10
                and counts["k"] >= 6
                and counts["b"] < 48
            )
            black_wall = counts["k"] >= 40 and counts["g"] < 20
            if biome == "sky":
                if counts["b"] >= 40:
                    pass
                elif red_brick or black_wall:
                    solid[cy][cx] = 1
            elif biome == "interior":
                if red_brick:
                    solid[cy][cx] = 1
                elif black_wall and (cx < 3 or cx >= cw - 3 or cy >= ch - 3):
                    solid[cy][cx] = 1
            else:
                if red_brick or blue_brick:
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
    return solid, keep, crates, biomes


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


def crate_overlay(im: Image.Image, crates: list[list[int]]) -> Image.Image:
    w, h = im.size
    src = im.convert("RGBA")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    ch, cw = len(crates), len(crates[0])
    for cy in range(ch):
        for cx in range(cw):
            if not crates[cy][cx]:
                continue
            for y in range(cy * CELL, (cy + 1) * CELL):
                for x in range(cx * CELL, (cx + 1) * CELL):
                    op[x, y] = sp[x, y]
    return out


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    print(f"mosaic {im.size}")
    solid, ladders, crates, biomes = classify_cells(im)
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
    n_solid = sum(sum(row) for row in solid)
    n_lad = sum(sum(row) for row in ladders)
    n_crate = sum(sum(row) for row in crates)
    print(f"solid cells {n_solid} -> {len(solids)} rects")
    print(f"ladder cells {n_lad} -> {len(ladder_rects)} rects")
    print(f"crate cells {n_crate}")
    from collections import Counter
    print("biomes", Counter(biomes))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, OUT_DIR / "saboteur2_world.png")
    crate_overlay(im, crates).save(OUT_DIR / "saboteur2_fg.png")
    payload = {
        "source": "Saboteur2_speccy.png",
        "scale": SCALE,
        "cell": CELL,
        "screen": [SCREEN_W, SCREEN_H],
        "size": [im.width, im.height],
        "spawn": spawn,
        "solids": solids,
        "ladders": ladder_rects,
    }
    (OUT_DIR / "s2_collision.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
