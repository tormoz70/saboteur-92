"""Erase fan-map chrome and screenshot artifacts before atlas / collision.

Guard cleanup is pixel-surgical: black silhouette pixels of small standing
figures and outdoor grass panthers. Lattice, earth, START/glider, furniture
and tree leaves stay untouched.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

CELL = 8
SKY_BLUE = (0, 0, 206)
LATTICE = (255, 251, 255)

# Pavero logo, mission legend, ninja art — cell rects, x1/y1 exclusive.
FAN_SKY_CELLS = (
    (0, 0, 140, 112),
    (936, 0, 1024, 500),
)
# Hang-glider + START caption sit in open sky. Keep the pixels; never a floor.
FAN_SKY_DECOR_CELLS = (
    (535, 0, 555, 16),
)


def paint_fan_chrome(img: Image.Image) -> None:
    """Paint logo / legend / ninja art to sky."""
    draw = ImageDraw.Draw(img)
    for cx0, cy0, cx1, cy1 in FAN_SKY_CELLS:
        draw.rectangle(
            [cx0 * CELL, cy0 * CELL, cx1 * CELL - 1, cy1 * CELL - 1],
            fill=SKY_BLUE,
        )


def clear_fan_sky_collision(collision: np.ndarray, empty_id: int = 0) -> int:
    """Force empty collision in fan-chrome and sky-sprite rects."""
    cleared = 0
    for cx0, cy0, cx1, cy1 in FAN_SKY_CELLS + FAN_SKY_DECOR_CELLS:
        sl = collision[cy0:cy1, cx0:cx1]
        cleared += int((sl != empty_id).sum())
        sl[:] = empty_id
    return cleared


def _in_chrome(cx: int, cy: int) -> bool:
    for x0, y0, x1, y1 in FAN_SKY_CELLS:
        if x0 <= cx < x1 and y0 <= cy < y1:
            return True
    return False


def paint_fan_guard_sprites(img: Image.Image) -> int:
    """Erase black standing figures and outdoor panthers baked into screenshots."""
    arr = np.array(img)
    h, w, _ = arr.shape
    ch, cw = h // CELL, w // CELL
    grid = arr.reshape(ch, CELL, cw, CELL, 3).transpose(0, 2, 1, 3, 4)

    black = (grid == (0, 0, 0)).all(axis=4).sum(axis=(2, 3))
    red = (
        (grid[:, :, :, :, 0] >= 200)
        & (grid[:, :, :, :, 1] < 40)
        & (grid[:, :, :, :, 2] < 40)
    ).sum(axis=(2, 3))
    green = (
        (grid[:, :, :, :, 1] >= 200)
        & (grid[:, :, :, :, 0] < 40)
        & (grid[:, :, :, :, 2] < 40)
    ).sum(axis=(2, 3))
    white = (grid == LATTICE).all(axis=4).sum(axis=(2, 3))
    yellow = (
        (grid[:, :, :, :, 0] >= 180)
        & (grid[:, :, :, :, 1] >= 180)
        & (grid[:, :, :, :, 2] < 40)
    ).sum(axis=(2, 3))
    sky = (grid == SKY_BLUE).all(axis=4).sum(axis=(2, 3))

    # Body in open sky: black + sky only. Architecture tiles never qualify.
    sky_sil = (
        (black >= 4)
        & (red == 0)
        & (green == 0)
        & (white == 0)
        & (yellow == 0)
        & (black + sky >= 60)
    )
    # Outdoor grass figures: black silhouette, not brick/furniture ink.
    grass_sil = (
        (black >= 8)
        & (red == 0)
        & (white == 0)
        & (yellow == 0)
        & (green < 24)
    )

    sky_cells = _collect_blobs(
        sky_sil,
        ch,
        cw,
        lambda cells: _is_standing_figure(cells, red, white, green, ch, cw),
    )
    grass_cells = _collect_blobs(
        grass_sil,
        ch,
        cw,
        lambda cells: (
            _is_standing_figure(cells, red, white, green, ch, cw)
            or _is_grass_animal(cells, green, sky, ch, cw)
        ),
    )
    unique = list(dict.fromkeys(sky_cells + grass_cells))
    extra: list[tuple[int, int]] = []
    seen = set(unique)
    for cx, cy in grass_cells:
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < cw and 0 <= ny < ch and (nx, ny) not in seen:
                seen.add((nx, ny))
                extra.append((nx, ny))
    if not unique and not extra:
        return 0
    painted = 0
    for cx, cy in unique + extra:
        painted += _erase_black_cell(arr, cx, cy, ch, cw, green, sky)
    img.paste(Image.fromarray(arr))
    return painted


def _collect_blobs(
    mask: np.ndarray,
    ch: int,
    cw: int,
    keep,
) -> list[tuple[int, int]]:
    seen = np.zeros((ch, cw), dtype=bool)
    out: list[tuple[int, int]] = []
    for y in range(ch):
        for x in range(cw):
            if not mask[y, x] or seen[y, x] or _in_chrome(x, y):
                continue
            stack = [(x, y)]
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                if not (0 <= cx < cw and 0 <= cy < ch):
                    continue
                if not mask[cy, cx] or seen[cy, cx] or _in_chrome(cx, cy):
                    continue
                seen[cy, cx] = True
                cells.append((cx, cy))
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            if keep(cells):
                out.extend(cells)
    return out


def _erase_black_cell(
    arr: np.ndarray,
    cx: int,
    cy: int,
    ch: int,
    cw: int,
    green: np.ndarray,
    sky: np.ndarray,
) -> int:
    tile = arr[cy * CELL : (cy + 1) * CELL, cx * CELL : (cx + 1) * CELL]
    mask = (tile == (0, 0, 0)).all(axis=2)
    n = int(mask.sum())
    if n == 0:
        return 0
    on_grass = cy + 1 < ch and green[cy + 1, cx] >= 8
    if on_grass:
        grass = arr[(cy + 1) * CELL : (cy + 2) * CELL, cx * CELL : (cx + 1) * CELL]
        tile[mask] = grass[mask]
        return n
    fill = _fill_for_erased_cell(arr, cx, cy, ch, cw, green, sky)
    tile[mask] = fill
    return n


def _fill_for_erased_cell(
    arr: np.ndarray,
    cx: int,
    cy: int,
    ch: int,
    cw: int,
    green: np.ndarray,
    sky: np.ndarray,
) -> tuple[int, int, int]:
    """Replace a screenshot silhouette with sky or neighbouring grass."""
    tile = arr[cy * CELL : (cy + 1) * CELL, cx * CELL : (cx + 1) * CELL]
    mask = (tile == (0, 0, 0)).all(axis=2)
    near_sky = sky[cy, cx] >= 8 or (cy > 0 and sky[cy - 1, cx] >= 16)
    on_grass = cy + 1 < ch and green[cy + 1, cx] >= 8

    def grass_pixel() -> tuple[int, int, int] | None:
        ny = cy + 1
        if ny >= ch or green[ny, cx] < 8:
            return None
        grass = arr[ny * CELL : (ny + 1) * CELL, cx * CELL : (cx + 1) * CELL]
        gmask = (
            (grass[:, :, 1] >= 180)
            & (grass[:, :, 0] < 80)
            & (grass[:, :, 2] < 80)
        )
        if int(gmask.sum()) < 4:
            return None
        return tuple(int(v) for v in grass[gmask][0])

    if near_sky and not on_grass:
        return SKY_BLUE
    if on_grass:
        gp = grass_pixel()
        if gp:
            return gp
    others = tile[~mask]
    if len(others):
        cols, counts = np.unique(others.reshape(-1, 3), axis=0, return_counts=True)
        return tuple(int(v) for v in cols[counts.argmax()])
    return SKY_BLUE


def _is_standing_figure(
    cells: list[tuple[int, int]],
    red: np.ndarray,
    white: np.ndarray,
    green: np.ndarray,
    ch: int,
    cw: int,
) -> bool:
    """Humanoid black blob on lattice, red roof, or grass — not a pole or glider."""
    if not (12 <= len(cells) <= 24):
        return False
    xs = [p[0] for p in cells]
    ys = [p[1] for p in cells]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    if not (2 <= w <= 4 and 6 <= h <= 8):
        return False
    y1 = max(ys) + 1
    if y1 >= ch:
        return False
    for px in range(max(0, min(xs) - 1), min(cw, max(xs) + 2)):
        if white[y1, px] >= 16 or red[y1, px] >= 8 or green[y1, px] >= 8:
            return True
    return False


def _is_grass_animal(
    cells: list[tuple[int, int]],
    green: np.ndarray,
    sky: np.ndarray,
    ch: int,
    cw: int,
) -> bool:
    """Low wide panther silhouette on outdoor grass, with sky around it."""
    if not (4 <= len(cells) <= 22):
        return False
    xs = [p[0] for p in cells]
    ys = [p[1] for p in cells]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    if not (3 <= w <= 12 and 2 <= h <= 5):
        return False
    y1 = max(ys) + 1
    if y1 >= ch:
        return False
    on_grass = False
    for px in range(max(0, min(xs) - 1), min(cw, max(xs) + 2)):
        if green[y1, px] >= 8:
            on_grass = True
            break
    if not on_grass:
        return False
    for cx, cy in cells:
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < cw and 0 <= ny < ch and sky[ny, nx] >= 32:
                return True
    return False
