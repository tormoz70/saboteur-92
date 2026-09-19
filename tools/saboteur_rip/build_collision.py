"""Stamp the CollisionLayer grid from the pixel-perfect fan map.

The S2ROOM decoder's geometry does not align with saboteur2_world2.png
(measured in s2_decoder_geometry.json: F1 ~0.32, 7% of solids on sky, decoder
ladders land in solid rock), so physics is derived from the map itself:

  solid  = rock + drawn earth/structure + plain black + black with sparse
           ZX-blue specks (the ground mass; not sky, not wallpaper brick)
  ladder = cells whose 8x8 tile matches a ladder glyph from the decoder's
           ladder sprites (ladder_green / ladder_black / ladder_wide / …),
           including white/cyan hatches drawn through the building monolith
           (ZX blue paper instead of black), in a tall run
  empty  = sky, mosaic/wallpaper back-walls, interior/fg that is not black
           speckle, red-brick wall cladding (structure tile 3 — secret rooms),
           and 1-cell indoor seam bars
  oneway = horizontal or sloped iron grating (I-beam floors, cyan balconies,
           45° braces). Vertical I-beams / drain pipes stay empty.
  rope   = long horizontal fg spans (tightropes between buildings). Nina runs
           along them; stopping drops straight down.

Mosaic is the painted back wall of a room: Nina walks in front of it.
The 1-cell black bars between rooms are Spectrum screen seams; in the
original they are not collision.

Output: assets/world/s2_collision_grid.json  (per-cell collision_type ids)
Also patches lift top/bottom in assets/world/s2_collision.json from the
fan-map shafts (decoder ranges collapse to top==bottom).
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fan_map_cleanup import clear_fan_sky_collision, paint_fan_chrome, paint_fan_guard_sprites

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "assets" / "world" / "saboteur2_world2.png"
CELLS = ROOT / "assets" / "world" / "s2_world_cells.json"
AIR = ROOT / "assets" / "world" / "s2_air_regions.json"
LADDER_SPRITES = ROOT / "assets" / "world" / "objects" / "interior" / "ladder_*.png"
OUT = ROOT / "assets" / "world" / "s2_collision_grid.json"
COLLISION_EXTRAS = ROOT / "assets" / "world" / "s2_collision.json"
OVERLAY = ROOT / "docs" / "audit_views" / "collision_overlay.png"

CELL = 8
# collision_type ids matching s2_collision_tileset custom data order.
EMPTY, SOLID, LADDER, ONEWAY, ROPE = 0, 1, 2, 3, 4
ROPE_MIN_RUN = 16
ROPE_MAX_RUN = 80
ROPE_SPAN_LONG = 160
# Only the hang-glider drop west of the HQ east wall — not the HQ→rocket span.
ROPE_EXCLUDE_CELLS = (
    (430, 8, 540, 50),
)
ZX_BLACK = (0, 0, 0)
ZX_BLUE = (0, 0, 206)
# Wallpaper/cave brick is black+blue but dense (~20–63 blue pixels / 8x8).
# Ground is plain black or a sparse blue speckle.
SPECKLE_BLUE_MAX = 19
# Red brick that lines a secret room (INVINCIBILITY) — veneer, not a wall.
CLADDING_STRUCTURE_TILES = {3}


def _ladder_half_masks() -> list[np.ndarray]:
    """Foreground (glyph) masks of the decoder's ladder sprites, split into the
    two 8x8 halves of the 16x8 repeat module. Foreground = not the background
    colour, so this is colour-agnostic (fan map brightens 206 -> 251)."""
    masks: list[np.ndarray] = []
    for path in glob.glob(str(LADDER_SPRITES)):
        sp = np.array(Image.open(path).convert("RGB"))
        flat = sp.reshape(-1, 3)
        colors, counts = np.unique(flat, axis=0, return_counts=True)
        bg = colors[counts.argmax()]
        fg = (flat != bg).any(axis=1).reshape(CELL, CELL * 2)
        masks.append(fg[:, :CELL])
        masks.append(fg[:, CELL:])
    return masks


def _tile_ink_masks(tile: np.ndarray) -> list[np.ndarray]:
    """Ink bitmaps of an 8x8 cell for matching against ladder sprites.

    Room ladders are bright ink on true black, so 'any non-black' is the glyph.
    Ladders that pass through the building monolith are drawn on ZX blue paper
    (white/cyan hatch on dark blue). Every pixel is then 'lit' and the dense
    non-black test rejects them — fall back to majority-colour paper, the same
    rule the sprites use.
    """
    lit = tile.sum(axis=2) > 0
    masks = [lit]
    if not (tile == 0).all(axis=2).any():
        flat = tile.reshape(-1, 3)
        colors, counts = np.unique(flat, axis=0, return_counts=True)
        bg = colors[counts.argmax()]
        masks.append((flat != bg).any(axis=1).reshape(CELL, CELL))
    return masks


def _matches_ladder_half(mask: np.ndarray, halves: list[np.ndarray]) -> bool:
    tc = int(mask.sum())
    for fg in halves:
        fc = int(fg.sum())
        if fc == 0:
            continue
        overlap = int((mask & fg).sum())
        if overlap >= 0.9 * fc and 0.5 * fc <= tc <= 1.5 * fc:
            return True
    return False


def _ladder_tile_set(
    img: np.ndarray, layer_of: np.ndarray, tile_of: np.ndarray, cw: int, ch: int
) -> set[tuple[int, int]]:
    """(layer, tile_id) pairs whose 8x8 bitmap is a ladder-glyph half.

    A tile qualifies when its ink mask covers most of the glyph yet is not much
    denser — that keeps real ladder halves and rejects solid blocks (which only
    share the rails) and wall cells with a ladder baked on top (too dense).
    """
    halves = _ladder_half_masks()
    bitmap: dict[tuple[int, int], list[np.ndarray]] = {}
    for i in range(cw * ch):
        li = int(layer_of.flat[i])
        if li < 0:
            continue
        k = (li, int(tile_of.flat[i]))
        if k not in bitmap:
            y, x = divmod(i, cw)
            bitmap[k] = _tile_ink_masks(
                img[y * CELL : (y + 1) * CELL, x * CELL : (x + 1) * CELL]
            )
    ladder_tiles: set[tuple[int, int]] = set()
    for k, masks in bitmap.items():
        if any(_matches_ladder_half(mask, halves) for mask in masks):
            ladder_tiles.add(k)
    return ladder_tiles


def _seam_structure_tiles(
    img: np.ndarray, layer_of: np.ndarray, tile_of: np.ndarray, structure_idx: int
) -> set[int]:
    """Structure tile ids whose 8x8 glyph is a thin vertical bar (1–3 lit columns).

    These are screen-seam markers on the fan map, not load-bearing walls.
    """
    ch, cw = layer_of.shape
    first: dict[int, tuple[int, int]] = {}
    for y in range(ch):
        for x in range(cw):
            if int(layer_of[y, x]) != structure_idx:
                continue
            tid = int(tile_of[y, x])
            first.setdefault(tid, (x, y))
    seams: set[int] = set()
    for tid, (x, y) in first.items():
        tile = img[y * CELL : (y + 1) * CELL, x * CELL : (x + 1) * CELL]
        lit = tile.sum(axis=2) > 0
        width = int(lit.any(axis=0).sum())
        if 1 <= width <= 3:
            seams.add(tid)
    return seams


def _black_ground(grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Plain black and black-with-sparse-blue-specks 8x8 cells.

    Sky is solid ZX blue. Cave/HQ wallpaper uses the same two colours but as
    a dense brick hatch — those stay paper. Speckle (1–19 blue pixels) is the
    thin fill that ladders pass through as hatches; pure black is bulk ground.
    """
    is_black = (grid == ZX_BLACK).all(axis=-1)
    is_blue = (grid == ZX_BLUE).all(axis=-1)
    only = (is_black | is_blue).all(axis=(2, 3))
    blue_n = is_blue.sum(axis=(2, 3))
    pure_sky = is_blue.all(axis=(2, 3))
    speckle = only & (blue_n >= 1) & (blue_n <= SPECKLE_BLUE_MAX)
    ground = speckle | (only & (blue_n == 0) & ~pure_sky)
    return ground, speckle


def _metal_ink(tile: np.ndarray) -> np.ndarray:
    """Bright iron ink: white, cyan, or yellow. Not ZX-blue paper, green, or red."""
    r = tile[:, :, 0].astype(np.int16)
    g = tile[:, :, 1].astype(np.int16)
    b = tile[:, :, 2].astype(np.int16)
    white = (r > 200) & (g > 200) & (b > 200)
    cyan = (r < 80) & (g > 180) & (b > 180)
    yellow = (r > 180) & (g > 180) & (b < 80)
    return white | cyan | yellow


def _is_wall_decoration(tile: np.ndarray) -> bool:
    """Wall-mounted monitor, window trim, and furniture — never an iron floor.

    Same rule as mosaic/wallpaper/fg: Nina walks in front of the sprite.
    """
    r = tile[:, :, 0].astype(np.int16)
    g = tile[:, :, 1].astype(np.int16)
    b = tile[:, :, 2].astype(np.int16)
    if int(((r > 180) & (g < 80)).sum()) >= 4:
        return True
    if int(((r < 80) & (g > 200) & (b < 80)).sum()) >= 12:
        return True
    lit = tile.sum(axis=2) > 40
    rows = lit.mean(axis=1)
    # CRT monitor: open top, boxed screen mid-band, optional base rail.
    if float(rows[:2].mean()) < 0.2 and float(rows[2:6].mean()) > 0.55:
        return True
    return False


def _fill_one_cell_notches(collision: np.ndarray) -> int:
    """Fill 1-cell holes in a solid (hatch crumbs), not alcoves between walls.

    A notch is empty with solid left, right and below, and at least one of the
    cells above-left / above-right open. True 1-cell alcoves (walls going up
    on both sides) stay empty. The INVINCIBILITY lid leftover is this shape.
    """
    ch, cw = collision.shape
    filled = 0
    for y in range(1, ch - 1):
        for x in range(1, cw - 1):
            if collision[y, x] != EMPTY:
                continue
            if collision[y, x - 1] != SOLID or collision[y, x + 1] != SOLID:
                continue
            if collision[y + 1, x] != SOLID:
                continue
            up_left = collision[y - 1, x - 1] == SOLID
            up_right = collision[y - 1, x + 1] == SOLID
            if up_left and up_right:
                continue
            collision[y, x] = SOLID
            filled += 1
    return filled


def _clear_indoor_window_nubs(
    collision: np.ndarray,
    layer_of: np.ndarray,
    paper_layers: set[int],
) -> int:
    """1-cell indoor teeth boxed by mosaic/wallpaper/interior are CRT/window trim."""
    ch, cw = collision.shape
    floorish = collision == SOLID
    cleared = 0
    for y in range(1, ch):
        for x in range(cw):
            if collision[y, x] != SOLID or collision[y - 1, x] != EMPTY:
                continue
            left = x > 0 and bool(floorish[y, x - 1])
            right = x + 1 < cw and bool(floorish[y, x + 1])
            if left or right:
                continue
            boxed = True
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if not (0 <= nx < cw and 0 <= ny < ch):
                    boxed = False
                    break
                if int(layer_of[ny, nx]) not in paper_layers:
                    boxed = False
                    break
            if not boxed:
                continue
            collision[y, x] = EMPTY
            cleared += 1
    return cleared


def _clear_wall_screen_solids(
    collision: np.ndarray,
    layer_of: np.ndarray,
    mosaic_idx: int,
    interior_idx: int,
    wallpaper_idx: int,
    earth_idx: int,
) -> int:
    """Earth blobs floating in mosaic rooms are CRT screens, not ground."""
    ch, cw = collision.shape
    paper = {mosaic_idx, interior_idx, wallpaper_idx}
    earth_solid = (collision == SOLID) & (layer_of == earth_idx)
    seen = np.zeros((ch, cw), dtype=bool)
    cleared = 0
    for y in range(ch):
        for x in range(cw):
            if not earth_solid[y, x] or seen[y, x]:
                continue
            stack = [(x, y)]
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                if not (0 <= cx < cw and 0 <= cy < ch):
                    continue
                if seen[cy, cx] or not earth_solid[cy, cx]:
                    continue
                seen[cy, cx] = True
                cells.append((cx, cy))
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            if not (1 <= len(cells) <= 24):
                continue
            xs = [p[0] for p in cells]
            ys = [p[1] for p in cells]
            if max(xs) - min(xs) > 7 or max(ys) - min(ys) > 7:
                continue
            cellset = set(cells)
            indoor = True
            for cx, cy in cells:
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if (nx, ny) in cellset:
                        continue
                    if not (0 <= nx < cw and 0 <= ny < ch):
                        indoor = False
                        break
                    if int(layer_of[ny, nx]) not in paper:
                        indoor = False
                        break
                if not indoor:
                    break
            if not indoor:
                continue
            for cx, cy in cells:
                collision[cy, cx] = EMPTY
            cleared += len(cells)
    return cleared


def _clear_tree_trunks(
    collision: np.ndarray,
    layer_of: np.ndarray,
    img: np.ndarray,
    structure_idx: int,
    mosaic_idx: int,
) -> int:
    """Thin outdoor trunks are scenery; Nina walks past the tree."""
    ch, cw = collision.shape
    trunk = (collision == SOLID) & (layer_of == structure_idx)
    seen = np.zeros((ch, cw), dtype=bool)
    cleared = 0
    for y in range(ch):
        for x in range(cw):
            if not trunk[y, x] or seen[y, x]:
                continue
            stack = [(x, y)]
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                if not (0 <= cx < cw and 0 <= cy < ch):
                    continue
                if seen[cy, cx] or not trunk[cy, cx]:
                    continue
                seen[cy, cx] = True
                cells.append((cx, cy))
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            if not (3 <= len(cells) <= 24):
                continue
            xs = [p[0] for p in cells]
            ys = [p[1] for p in cells]
            w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if not (1 <= w <= 3 and h >= 4):
                continue
            top = min(ys)
            canopy = False
            y0, y1 = max(0, top - 6), min(ch, top + 2)
            x0, x1 = max(0, min(xs) - 6), min(cw, max(xs) + 7)
            for cy in range(y0, y1):
                for cx in range(x0, x1):
                    if int(layer_of[cy, cx]) == mosaic_idx:
                        canopy = True
                        break
                    tile = img[cy * CELL : (cy + 1) * CELL, cx * CELL : (cx + 1) * CELL]
                    green = (tile[:, :, 1] >= 180) & (tile[:, :, 0] < 80) & (
                        tile[:, :, 2] < 80
                    )
                    if int(green.sum()) >= 20:
                        canopy = True
                        break
                if canopy:
                    break
            if not canopy:
                continue
            for cx, cy in cells:
                collision[cy, cx] = EMPTY
            cleared += len(cells)
    return cleared


def _solid_outdoor_grass(
    collision: np.ndarray,
    img: np.ndarray,
    layer_of: np.ndarray,
    mosaic_idx: int,
) -> int:
    """The green grass strip is the floor. Indoor mosaic wallpaper stays empty.

    Mosaic cells are paper inside the HQ. Outdoors the same layer is a 1–2 cell
    grass cap on black earth; without this, Nina walks on the dirt under it.
    """
    ch, cw = collision.shape
    grid = img.reshape(ch, CELL, cw, CELL, 3).transpose(0, 2, 1, 3, 4)
    sky = (grid == ZX_BLUE).all(axis=(2, 3, 4))
    green = (
        (grid[:, :, :, :, 1] >= 180)
        & (grid[:, :, :, :, 0] < 80)
        & (grid[:, :, :, :, 2] < 80)
    )
    gfrac = green.mean(axis=(2, 3))
    floorish = (collision == SOLID) | (collision == ONEWAY)
    n = 0
    seeds: list[tuple[int, int]] = []
    for y in range(1, ch - 1):
        for x in range(cw):
            if collision[y, x] != EMPTY:
                continue
            if gfrac[y, x] < 0.25:
                continue
            if not bool(sky[y - 1, x]):
                continue
            below_floor = bool(floorish[y + 1, x])
            grass_then_floor = (
                y + 2 < ch
                and gfrac[y + 1, x] >= 0.25
                and collision[y + 1, x] == EMPTY
                and bool(floorish[y + 2, x])
            )
            if not below_floor and not grass_then_floor:
                continue
            collision[y, x] = SOLID
            seeds.append((x, y))
            n += 1
            if grass_then_floor:
                collision[y + 1, x] = SOLID
                seeds.append((x, y + 1))
                n += 1
    # Tree / panther / crate sprites sit on the grass, so those cells have no
    # sky above. Grow along the strip; do not promote indoor mosaic on the
    # same world row.
    i = 0
    while i < len(seeds):
        x, y = seeds[i]
        i += 1
        for nx in (x - 1, x + 1):
            if not (0 <= nx < cw) or collision[y, nx] != EMPTY:
                continue
            if int(layer_of[y, nx]) != mosaic_idx:
                continue
            if gfrac[y, nx] < 0.25:
                continue
            if y + 1 >= ch or collision[y + 1, nx] not in (SOLID, ONEWAY):
                continue
            collision[y, nx] = SOLID
            seeds.append((nx, y))
            n += 1
    return n


def _clear_facade_nubs(
    collision: np.ndarray,
    img: np.ndarray,
    layer_of: np.ndarray,
    paper_layers: set[int],
) -> int:
    """1–4 cell teeth on an outdoor wall are scenery, not floors.

    Original Saboteur II does not let Nina stand on those brick nubs.
    Wide balconies and building-base ledges stay.
    """
    ch, cw = collision.shape
    grid = img.reshape(ch, CELL, cw, CELL, 3).transpose(0, 2, 1, 3, 4)
    sky = (grid == ZX_BLUE).all(axis=(2, 3, 4))
    floorish = (collision == SOLID) | (collision == ONEWAY)

    def is_open(cx: int, cy: int) -> bool:
        if not (0 <= cx < cw and 0 <= cy < ch):
            return False
        if collision[cy, cx] != EMPTY:
            return False
        if bool(sky[cy, cx]):
            return True
        return int(layer_of[cy, cx]) not in paper_layers

    cleared = 0
    for y in range(1, ch):
        x = 0
        while x < cw:
            if not floorish[y, x] or collision[y - 1, x] != EMPTY:
                x += 1
                continue
            x0 = x
            while (
                x < cw
                and floorish[y, x]
                and collision[y - 1, x] == EMPTY
            ):
                x += 1
            w = x - x0
            if not (1 <= w <= 4):
                continue
            left = x0 > 0 and bool(floorish[y, x0 - 1])
            right = x < cw and bool(floorish[y, x])
            left_wall = left and collision[y - 1, x0 - 1] != EMPTY
            right_wall = right and collision[y - 1, x] != EMPTY
            open_left = (not left) and (is_open(x0 - 1, y - 1) or is_open(x0 - 1, y))
            open_right = (not right) and (is_open(x, y - 1) or is_open(x, y))
            if (left_wall and open_right) or (right_wall and open_left):
                collision[y, x0:x] = EMPTY
                cleared += w
                continue
            if w != 1:
                continue
            near_sky = False
            for ny in range(max(0, y - 1), min(ch, y + 3)):
                for nx in range(max(0, x0 - 3), min(cw, x + 3)):
                    if bool(sky[ny, nx]):
                        near_sky = True
                        break
                if near_sky:
                    break
            if near_sky:
                collision[y, x0] = EMPTY
                cleared += 1
    return cleared


def _iron_walkable(mask: np.ndarray) -> bool:
    """True if the 8×8 metal mask is a floor Nina can stand on.

    Horizontal I-beams and cyan grating have rails on the top and bottom of the
    cell. Filled wedges are ramps. A thin 45° slash is a balcony strut — not a
    floor. Vertical I-beams, drain pipes, and furniture boxes are rejected.
    """
    tc = int(mask.sum())
    if not (18 <= tc <= 50):
        return False
    rows = mask.mean(axis=1)
    cols = mask.mean(axis=0)
    top, bot = float(rows[0]), float(rows[7])
    left, right = float(cols[0]), float(cols[7])
    if top >= 0.85 and bot >= 0.85 and left >= 0.85 and right >= 0.85:
        return False
    strong_top = top >= 0.95 or float(rows[:2].mean()) >= 0.95
    strong_bot = bot >= 0.95 or float(rows[6:].mean()) >= 0.95
    if strong_top and strong_bot:
        return True
    if left >= 0.85 and right >= 0.85:
        return False
    corners = (mask[:3, :3], mask[:3, 5:], mask[5:, :3], mask[5:, 5:])
    fills = [float(c.mean()) for c in corners]
    if min(fills) <= 0.15 and max(fills) >= 0.75 and 44 <= tc <= 50:
        return True
    return False


def _cyan_hatch(tile: np.ndarray) -> bool:
    """Silo-lid grate: cyan/black checkerboard, not yellow crates or blue windows."""
    r = tile[:, :, 0].astype(np.int16)
    g = tile[:, :, 1].astype(np.int16)
    b = tile[:, :, 2].astype(np.int16)
    cyan = (r < 80) & (g > 180) & (b > 180)
    black = (tile == 0).all(axis=2)
    yellow = (r > 180) & (g > 180) & (b < 80)
    blue = (r < 40) & (g < 40) & (b > 180)
    if int(yellow.sum()) >= 4 or int(blue.sum()) >= 8:
        return False
    tc = int(cyan.sum())
    if not (20 <= tc <= 36):
        return False
    if int(black.sum()) + tc < 48:
        return False
    cols = cyan.mean(axis=0)
    even, odd = float(cols[0::2].mean()), float(cols[1::2].mean())
    return abs(even - odd) >= 0.25 and 0.3 <= float(cyan.mean()) <= 0.7


def _iron_platform_tiles(
    img: np.ndarray, layer_of: np.ndarray, tile_of: np.ndarray, interior_idx: int
) -> set[tuple[int, int]]:
    """(layer, tile_id) of interior iron floors and ramps."""
    ch, cw = layer_of.shape
    first: dict[int, tuple[int, int]] = {}
    for y in range(ch):
        for x in range(cw):
            if int(layer_of[y, x]) != interior_idx:
                continue
            first.setdefault(int(tile_of[y, x]), (x, y))
    walk: set[tuple[int, int]] = set()
    for tid, (x, y) in first.items():
        tile = img[y * CELL : (y + 1) * CELL, x * CELL : (x + 1) * CELL]
        if _is_wall_decoration(tile):
            continue
        if _iron_walkable(_metal_ink(tile)) or _cyan_hatch(tile):
            walk.add((interior_idx, tid))
    return walk


def _rope_exclude_mask(ch: int, cw: int) -> np.ndarray:
    mask = np.zeros((ch, cw), dtype=bool)
    for cx0, cy0, cx1, cy1 in ROPE_EXCLUDE_CELLS:
        mask[cy0:cy1, cx0:cx1] = True
    return mask


def _rope_cells(
    img: np.ndarray,
    collision: np.ndarray,
    min_run: int = ROPE_MIN_RUN,
    max_run: int = ROPE_MAX_RUN,
) -> np.ndarray:
    """Horizontal pure-sky spans anchored to a roof edge — tightropes."""
    ch, cw = collision.shape
    exclude = _rope_exclude_mask(ch, cw)
    grid = img.reshape(ch, CELL, cw, CELL, 3).transpose(0, 2, 1, 3, 4)
    sky_cell = (grid == ZX_BLUE).all(axis=(2, 3, 4))
    rope = np.zeros((ch, cw), dtype=bool)
    for y in range(ch):
        if exclude[y, :].all():
            continue
        run_start: int | None = None
        for x in range(cw):
            if exclude[y, x]:
                if run_start is not None:
                    _maybe_rope_run(
                        rope, sky_cell, collision, y, run_start, x, min_run, max_run
                    )
                    run_start = None
                continue
            is_line = bool(sky_cell[y, x]) and collision[y, x] == EMPTY
            if is_line:
                if run_start is None:
                    run_start = x
            elif run_start is not None:
                _maybe_rope_run(
                    rope, sky_cell, collision, y, run_start, x, min_run, max_run
                )
                run_start = None
        if run_start is not None:
            _maybe_rope_run(
                rope, sky_cell, collision, y, run_start, cw, min_run, max_run
            )

    # Real tightropes are a 1–2 cell tall band, not wide sky seams.
    kept = np.zeros_like(rope)
    seen = np.zeros_like(rope)
    for y in range(ch):
        for x in range(cw):
            if not rope[y, x] or seen[y, x]:
                continue
            stack = [(x, y)]
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                if not (0 <= cx < cw and 0 <= cy < ch) or not rope[cy, cx] or seen[cy, cx]:
                    continue
                seen[cy, cx] = True
                cells.append((cx, cy))
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            xs = [p[0] for p in cells]
            ys = [p[1] for p in cells]
            w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if w >= min_run and h <= 2 and len(cells) <= 240 * h:
                for cx, cy in cells:
                    kept[cy, cx] = True
    kept[exclude] = False
    return _drop_parallel_sky_stripes(kept, ROPE_SPAN_LONG)


def _is_rope_landing(collision: np.ndarray, y: int, x: int) -> bool:
    """Far end of a short tightrope must be a floor, not a wall or sky sprite."""
    ch, cw = collision.shape
    if not (0 <= x < cw and 0 <= y < ch):
        return False
    if collision[y, x] == ONEWAY:
        return True
    if y + 1 < ch and collision[y, x] == EMPTY and collision[y + 1, x] in (SOLID, ONEWAY):
        return True
    return False


def _drop_parallel_sky_stripes(rope: np.ndarray, min_span: int) -> np.ndarray:
    """Keep the roof-level span of a crossing; drop lower copies on the same sky."""
    ch, cw = rope.shape
    runs: list[tuple[int, int, int]] = []
    for y in range(ch):
        x = 0
        while x < cw:
            if not rope[y, x]:
                x += 1
                continue
            x0 = x
            while x < cw and rope[y, x]:
                x += 1
            if x - x0 >= min_span:
                runs.append((y, x0, x))
    runs.sort()
    accepted: list[tuple[int, int, int]] = []
    drop = np.zeros_like(rope)
    for y, x0, x1 in runs:
        span = x1 - x0
        dup = False
        for ay, ax0, ax1 in accepted:
            overlap = min(x1, ax1) - max(x0, ax0)
            if overlap >= 0.5 * span and y - ay > 2:
                dup = True
                break
        if dup:
            drop[y, x0:x1] = True
        else:
            accepted.append((y, x0, x1))
    out = rope.copy()
    out[drop] = False
    return out


def _maybe_rope_run(
    rope: np.ndarray,
    sky_cell: np.ndarray,
    collision: np.ndarray,
    y: int,
    run_start: int,
    run_end: int,
    min_run: int,
    max_run: int,
) -> None:
    span = run_end - run_start
    if span < min_run:
        return
    if not any(not sky_cell[y, ax] for ax in range(max(0, run_start - 4), run_start)):
        return
    floor_hits = 0
    has_oneway = False
    for ax in range(max(0, run_start - 8), run_start + 1):
        if collision[y, ax] == ONEWAY:
            has_oneway = True
            floor_hits += 1
        elif (
            y + 1 < collision.shape[0]
            and collision[y, ax] == EMPTY
            and collision[y + 1, ax] in (SOLID, ONEWAY)
        ):
            floor_hits += 1
    if floor_hits < 1:
        return
    if span > max_run:
        # Long both-anchored sky runs are screenshot seams, not tightropes.
        return
    # Sky sitting on outdoor grass / floor is not a tightrope.
    if y + 1 < collision.shape[0]:
        below = collision[y + 1, run_start:run_end]
        if int(np.isin(below, [SOLID, ONEWAY]).sum()) >= span // 2:
            return
    # Local rope: a real roof, not a 1–2 cell facade nub.
    if not has_oneway and floor_hits < 3:
        return
    # Local run into a wall or sprite is a sky stripe, not a landing.
    if run_end < collision.shape[1] and not _is_rope_landing(collision, y, run_end):
        return
    rope[y, run_start:run_end] = True


def _open_ladder_hatches(collision: np.ndarray, speckle: np.ndarray) -> None:
    """Punch thick speckle stacks on a ladder; keep 1–2 cell lids solid.

    Speckle is the thin fill a ladder already occupies. A 1–2 cell lid is a
    hatch Nina walks on (she only passes it while climbing). Three or more
    cells is a plug through the ground mass and becomes climbable.
    """
    ch, cw = collision.shape
    for x in range(cw):
        y = 0
        while y < ch:
            if collision[y, x] != LADDER:
                y += 1
                continue
            y1 = y
            while y1 < ch and collision[y1, x] == LADDER:
                y1 += 1
            stack: list[int] = []
            yy = y - 1
            while yy >= 0 and speckle[yy, x] and collision[yy, x] == SOLID:
                stack.append(yy)
                yy -= 1
            if len(stack) >= 3:
                for sy in stack:
                    collision[sy, x] = LADDER
            stack = []
            yy = y1
            while yy < ch and speckle[yy, x] and collision[yy, x] == SOLID:
                stack.append(yy)
                yy += 1
            if len(stack) >= 3:
                for sy in stack:
                    collision[sy, x] = LADDER
            y = y1


def _seal_ladder_hatches(collision: np.ndarray) -> int:
    """Walkable lids on any floor a ladder punches through.

    Indoor hatches are 1–2 cells. White roof ladders go through 3–4 cells of
    speckle; leaving the whole stack as LADDER is a hole Nina falls through.
    Seal the top 1–2 cells of each floor-embedded run (walk on the lid, pass
    only while climbing). A 2-wide shaft still counts when the floor continues
    on both sides of the pair.
    """
    ch, cw = collision.shape
    floorish = (collision == SOLID) | (collision == ONEWAY)

    def floor_beyond(x: int, y: int, dx: int) -> bool:
        xx = x + dx
        while 0 <= xx < cw and collision[y, xx] == LADDER:
            xx += dx
        return 0 <= xx < cw and bool(floorish[y, xx])

    sealed = 0
    for x in range(cw):
        y = 0
        while y < ch:
            if collision[y, x] != LADDER:
                y += 1
                continue
            y_end = y
            while y_end < ch and collision[y_end, x] == LADDER:
                y_end += 1
            yy = y
            while yy < y_end:
                if not (floor_beyond(x, yy, -1) and floor_beyond(x, yy, 1)):
                    yy += 1
                    continue
                y1 = yy
                while y1 < y_end and floor_beyond(x, y1, -1) and floor_beyond(x, y1, 1):
                    y1 += 1
                if (
                    yy > 0
                    and collision[yy - 1, x] == SOLID
                    and floor_beyond(x, yy - 1, -1)
                    and floor_beyond(x, yy - 1, 1)
                    and y1 < y_end
                ):
                    yy = y1
                    continue
                if y1 >= y_end:
                    # Plug through a floor with no shaft below: fill it.
                    collision[yy:y1, x] = SOLID
                    sealed += y1 - yy
                else:
                    lid = min(2, y1 - yy)
                    collision[yy : yy + lid, x] = SOLID
                    sealed += lid
                yy = y1
            y = y_end
    return sealed


def _bridge_ladder_gaps(
    collision: np.ndarray, layer_of: np.ndarray, paper: set[int]
) -> int:
    """Join a ladder that stops short of the floor (baked figures cover rungs)."""
    ch, cw = collision.shape
    bridged = 0
    for x in range(cw):
        y = 0
        while y < ch:
            if collision[y, x] != LADDER:
                y += 1
                continue
            y1 = y
            while y1 < ch and collision[y1, x] == LADDER:
                y1 += 1
            y2 = y1
            while (
                y2 < ch
                and (y2 - y1) <= 8
                and collision[y2, x] == EMPTY
                and int(layer_of[y2, x]) in paper
            ):
                y2 += 1
            if (
                y2 > y1
                and y2 < ch
                and (y2 - y1) <= 8
                and collision[y2, x] in (SOLID, ONEWAY)
            ):
                collision[y1:y2, x] = LADDER
                bridged += y2 - y1
            y = y2 if y2 > y1 else y1
    return bridged


def _thin_hatch_lids(collision: np.ndarray, ladder_mask: np.ndarray) -> int:
    """Keep a 1–2 cell lid; extra solid on a ladder glyph is a climbable shaft.

    Sealing twice (before and after floor nubs) can stack two lids on one
    2-wide hatch so Nina never overlaps the climb Area2D.
    """
    ch, cw = collision.shape
    restored = 0
    for x in range(cw):
        y = 0
        while y < ch:
            if not (
                collision[y, x] in (SOLID, ONEWAY)
                and (y == 0 or collision[y - 1, x] == EMPTY)
            ):
                y += 1
                continue
            y_end = y
            while y_end < ch and collision[y_end, x] in (SOLID, ONEWAY):
                y_end += 1
            has_glyph = bool(ladder_mask[y:y_end, x].any())
            has_shaft = bool((collision[y:y_end, x] == LADDER).any()) or (
                y_end < ch and collision[y_end, x] == LADDER
            )
            if not (has_glyph and has_shaft):
                y = y_end
                continue
            lid = 2
            for k, yy in enumerate(range(y, y_end)):
                if not ladder_mask[yy, x] and collision[yy, x] != LADDER:
                    continue
                if k < lid:
                    if collision[yy, x] == LADDER:
                        collision[yy, x] = SOLID
                elif collision[yy, x] != LADDER:
                    collision[yy, x] = LADDER
                    restored += 1
            y = y_end
    return restored


def _is_flood_water(tile: np.ndarray) -> bool:
    """Cave flood fill: dense ZX-blue brick, not pure sky and not a ladder glyph."""
    blue = (tile == ZX_BLUE).all(axis=2)
    frac = float(blue.mean())
    return 0.70 <= frac < 0.98


def _extend_ladders_through_water(
    collision: np.ndarray,
    img: np.ndarray,
    layer_of: np.ndarray,
    tile_of: np.ndarray,
    interior_idx: int,
    max_gap: int = 12,
) -> int:
    """Grow painted cave ladders down through flood water to the floor.

    The fan map stops white ladders at the waterline; original Saboteur II
    lets Nina climb out of the drink. Only interior blue-brick water is
    extended — sky shafts and HQ wallpaper are left alone.
    """
    ch, cw = collision.shape
    extended = 0
    for x in range(cw):
        y = 0
        while y < ch:
            if collision[y, x] != LADDER:
                y += 1
                continue
            while y < ch and collision[y, x] == LADDER:
                y += 1
            src_y = y - 1
            src_li = int(layer_of[src_y, x])
            src_tid = int(tile_of[src_y, x])
            water: list[int] = []
            yy = y
            while yy < ch and len(water) < max_gap:
                if collision[yy, x] in (SOLID, ONEWAY, LADDER, ROPE):
                    break
                if int(layer_of[yy, x]) != interior_idx:
                    water = []
                    break
                tile = img[yy * CELL : (yy + 1) * CELL, x * CELL : (x + 1) * CELL]
                if not _is_flood_water(tile):
                    water = []
                    break
                water.append(yy)
                yy += 1
            if not water:
                continue
            if yy >= ch or collision[yy, x] not in (SOLID, ONEWAY):
                continue
            for wy in water:
                collision[wy, x] = LADDER
                layer_of[wy, x] = src_li
                tile_of[wy, x] = src_tid
            extended += len(water)
    return extended


def _shaft_empty(collision: np.ndarray, x0: int, x1: int, row: int) -> bool:
    """True if at least half of the lift columns at `row` are not solid."""
    span = x1 - x0 + 1
    if span <= 0 or not (0 <= row < collision.shape[0]):
        return False
    empty = int((collision[row, x0 : x1 + 1] != SOLID).sum())
    return empty * 2 >= span


def _shaft_step(
    collision: np.ndarray,
    x0: int,
    x1: int,
    row: int,
    dy: int,
    sky: np.ndarray | None = None,
) -> int | None:
    """Next open shaft row in direction `dy`, skipping 1–3 cell floor hatches.

    Stops at sky — the well is indoor/cave, not the outdoor void.
    """
    ch = collision.shape[0]
    y = row + dy
    if not (0 <= y < ch):
        return None
    span = x1 - x0 + 1
    if sky is not None and int(sky[y, x0 : x1 + 1].sum()) * 2 >= span:
        return None
    if _shaft_empty(collision, x0, x1, y):
        return y
    n = 0
    yy = y
    while 0 <= yy < ch and not _shaft_empty(collision, x0, x1, yy):
        n += 1
        yy += dy
        if n > 3:
            return None
    if not (0 <= yy < ch):
        return None
    if sky is not None and int(sky[yy, x0 : x1 + 1].sum()) * 2 >= span:
        return None
    if _shaft_empty(collision, x0, x1, yy):
        return yy
    return None


def _expand_lifts(collision: np.ndarray, sky: np.ndarray | None = None) -> list[dict]:
    """Rewrite lift top/bottom from the fan-map shaft (empty well around the car)."""
    if not COLLISION_EXTRAS.exists():
        return []
    doc = json.loads(COLLISION_EXTRAS.read_text(encoding="utf-8"))
    lifts = doc.get("lifts", [])
    ch, cw = collision.shape
    patched: list[dict] = []
    for spec in lifts:
        spec = dict(spec)
        x, y, w = int(spec["x"]), int(spec["y"]), int(spec["w"])
        x0, x1 = x // CELL, (x + max(w, 1) - 1) // CELL
        x0, x1 = max(0, x0), min(cw - 1, x1)
        cy = max(0, min(ch - 1, y // CELL))
        top = cy
        while True:
            nxt = _shaft_step(collision, x0, x1, top, -1, sky)
            if nxt is None:
                break
            top = nxt
        bot = cy
        while True:
            nxt = _shaft_step(collision, x0, x1, bot, 1, sky)
            if nxt is None:
                break
            bot = nxt
        old_top, old_bot = int(spec.get("top", y)), int(spec.get("bottom", y))
        spec["top"] = top * CELL
        spec["bottom"] = bot * CELL
        patched.append(spec)
        print(
            f"  lift x={x} y={y} shaft {spec['top']}-{spec['bottom']} "
            f"(was {old_top}-{old_bot})"
        )
    doc["lifts"] = patched
    COLLISION_EXTRAS.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(f"patched {len(patched)} lifts in {COLLISION_EXTRAS}")
    return patched


def main() -> None:
    src = Image.open(WORLD).convert("RGB")
    paint_fan_chrome(src)
    n_guard = paint_fan_guard_sprites(src)
    src.save(WORLD)
    img = np.array(src)
    H, W, _ = img.shape
    cw, ch = W // CELL, H // CELL

    cells_doc = json.loads(CELLS.read_text(encoding="utf-8"))
    layer_names = [l["name"] for l in cells_doc["layers"]]
    flat = cells_doc["cells"]
    layer_of = np.array([p[0] for p in flat], dtype=np.int16).reshape(ch, cw)
    tile_of = np.array([p[1] for p in flat], dtype=np.int32).reshape(ch, cw)
    interior_idx = layer_names.index("interior")
    fg_idx = layer_names.index("fg")
    wallpaper_idx = layer_names.index("wallpaper")
    mosaic_idx = layer_names.index("mosaic")
    structure_idx = layer_names.index("structure")
    earth_idx = layer_names.index("earth")

    air = json.loads(AIR.read_text(encoding="utf-8"))
    rock = np.zeros((ch, cw), dtype=bool)
    is_black = np.zeros((ch, cw), dtype=bool)
    for region in air["regions"]:
        for x, y in region["cells"]:
            is_black[y, x] = True
            if region["kind"] == "rock":
                rock[y, x] = True

    # Per-cell lit fraction and sky mask.
    grid = img.reshape(ch, CELL, cw, CELL, 3).transpose(0, 2, 1, 3, 4)
    sky = (grid == (0, 0, 206)).all(axis=4).all(axis=(2, 3))

    # Ladder cells: tile matches a decoder ladder glyph, kept in tall runs.
    ladder_tiles = _ladder_tile_set(img, layer_of, tile_of, cw, ch)
    ladder = np.zeros((ch, cw), dtype=bool)
    for y in range(ch):
        for x in range(cw):
            if (int(layer_of[y, x]), int(tile_of[y, x])) in ladder_tiles:
                ladder[y, x] = True
    for x in range(cw):
        run = 0
        for y in range(ch):
            if ladder[y, x]:
                run += 1
            else:
                if 0 < run < 3:
                    ladder[y - run : y, x] = False
                run = 0
        if 0 < run < 3:
            ladder[ch - run : ch, x] = False

    # Load-bearing: drawn earth/structure. Mosaic and wallpaper are paper
    # Nina walks in front of. Interior/fg are decor unless they are the
    # black speckle fill. Thin structure bars (screen seams) are visual
    # joins, not walls.
    seam_tids = _seam_structure_tiles(img, layer_of, tile_of, structure_idx)
    is_seam = (layer_of == structure_idx) & np.isin(tile_of, list(seam_tids) or [-1])
    is_load_bearing = (layer_of == structure_idx) | (layer_of == earth_idx)
    is_decor_layer = (layer_of == interior_idx) | (layer_of == fg_idx)
    is_background = (layer_of == wallpaper_idx) | (layer_of == mosaic_idx)
    is_cladding = (layer_of == structure_idx) & np.isin(
        tile_of, list(CLADDING_STRUCTURE_TILES)
    )
    black_ground, speckle = _black_ground(grid)
    if COLLISION_EXTRAS.exists():
        for spec in json.loads(COLLISION_EXTRAS.read_text(encoding="utf-8")).get("lifts", []):
            x, w = int(spec["x"]), int(spec["w"])
            x0, x1 = x // CELL, (x + max(w, 1) - 1) // CELL
            x0, x1 = max(0, x0), min(cw - 1, x1)
            black_ground[:, x0 : x1 + 1] = False
            speckle[:, x0 : x1 + 1] = False
    drawn = (~is_black) & (~sky)

    collision = np.full((ch, cw), EMPTY, dtype=np.uint8)
    collision[rock] = SOLID
    collision[drawn & is_load_bearing & ~is_seam] = SOLID
    collision[drawn & is_decor_layer] = EMPTY  # furniture: never solid
    collision[drawn & is_background] = EMPTY
    collision[black_ground] = SOLID  # after paper/decor: speckle fill wins
    collision[is_cladding] = EMPTY  # red-brick veneer on solid earth
    collision[ladder] = LADDER  # climbable overrides solid/empty
    _open_ladder_hatches(collision, speckle)
    n_bridge = _bridge_ladder_gaps(
        collision, layer_of, {mosaic_idx, interior_idx, wallpaper_idx}
    )
    n_hatches = _seal_ladder_hatches(collision)
    n_water_ladders = _extend_ladders_through_water(
        collision, img, layer_of, tile_of, interior_idx
    )
    if n_water_ladders:
        cells_doc["cells"] = np.stack(
            (layer_of.reshape(-1), tile_of.reshape(-1)), axis=1
        ).tolist()
        CELLS.write_text(
            json.dumps(cells_doc, separators=(",", ":")), encoding="utf-8"
        )
        print(f"stamped {n_water_ladders} flood-ladder cells into {CELLS}")
    # Iron balconies / I-beams / 45° braces: walk on top, not a climb.
    iron_tiles = _iron_platform_tiles(img, layer_of, tile_of, interior_idx)
    iron_tids = [tid for li, tid in iron_tiles if li == interior_idx]
    iron = (layer_of == interior_idx) & np.isin(tile_of, iron_tids or [-1])
    collision[iron & (collision == EMPTY)] = ONEWAY
    n_screens = _clear_wall_screen_solids(
        collision, layer_of, mosaic_idx, interior_idx, wallpaper_idx, earth_idx
    )
    n_notches = _fill_one_cell_notches(collision)
    n_window_nubs = _clear_indoor_window_nubs(
        collision, layer_of, {mosaic_idx, interior_idx, wallpaper_idx}
    )
    n_trees = _clear_tree_trunks(
        collision, layer_of, img, structure_idx, mosaic_idx
    )
    n_nubs = 0
    paper = {mosaic_idx, interior_idx, wallpaper_idx}
    for _ in range(8):
        n = _clear_facade_nubs(collision, img, layer_of, paper)
        n_nubs += n
        if n == 0:
            break
    n_grass = _solid_outdoor_grass(collision, img, layer_of, mosaic_idx)
    n_hatches += _seal_ladder_hatches(collision)
    n_thin = _thin_hatch_lids(collision, ladder)
    rope = _rope_cells(img, collision)
    collision[rope] = ROPE
    n_fan_sky = clear_fan_sky_collision(collision, EMPTY)

    counts = {
        "empty": int((collision == EMPTY).sum()),
        "solid": int((collision == SOLID).sum()),
        "ladder": int((collision == LADDER).sum()),
        "oneway": int((collision == ONEWAY).sum()),
        "rope": int((collision == ROPE).sum()),
    }
    doc = {
        "source": "fan map (air regions + earth/structure; mosaic paper; seam bars empty)",
        "cell": CELL,
        "grid": [cw, ch],
        "ids": {
            "empty": EMPTY,
            "solid": SOLID,
            "ladder": LADDER,
            "oneway": ONEWAY,
            "rope": ROPE,
        },
        "ladder_tile_count": len(ladder_tiles),
        "iron_platform_tiles": sorted(tid for _li, tid in iron_tiles),
        "seam_structure_tiles": sorted(seam_tids),
        "counts": counts,
        "cells": collision.flatten().tolist(),
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(
        f"grid={cw}x{ch} counts={counts} guard_cells_erased={n_guard} "
        f"fan_sky_cleared={n_fan_sky} screens_cleared={n_screens} "
        f"notches_filled={n_notches} window_nubs={n_window_nubs} "
        f"trees_cleared={n_trees} nubs_cleared={n_nubs} grass={n_grass} "
        f"ladder_tiles={len(ladder_tiles)} "
        f"water_ladders={n_water_ladders} hatches_sealed={n_hatches} "
        f"ladder_gaps={n_bridge} hatch_shafts={n_thin} "
        f"iron_tiles={sorted(tid for _li, tid in iron_tiles)} "
        f"seam_tiles={sorted(seam_tids)}"
    )
    print(f"wrote {OUT}")
    _expand_lifts(collision, sky)

    # Audit overlay: solid=white, ladder=green, oneway=yellow, empty=transparent.
    ov = np.zeros((ch, cw, 4), dtype=np.uint8)
    ov[collision == SOLID] = (255, 255, 255, 90)
    ov[collision == LADDER] = (0, 255, 0, 255)
    ov[collision == ONEWAY] = (255, 255, 0, 255)
    ov[collision == ROPE] = (255, 128, 0, 255)
    base = img[::CELL, ::CELL].copy()
    over = Image.fromarray(ov, "RGBA").resize((cw, ch), Image.NEAREST)
    base_img = Image.fromarray(base).convert("RGBA")
    base_img.alpha_composite(over)
    OVERLAY.parent.mkdir(parents=True, exist_ok=True)
    base_img.save(OVERLAY)
    print(f"wrote {OVERLAY}")


if __name__ == "__main__":
    main()
