"""Erase fan-map chrome and screenshot artifacts before atlas / collision.

Guard cleanup is pixel-surgical: black silhouette pixels of small standing
figures and outdoor grass panthers. Lattice, earth, START/glider, furniture
and tree leaves stay untouched.
"""

from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CELL = 8
SKY_BLUE = (0, 0, 206)
GRASS_GREEN = (0, 251, 0)
LATTICE = (255, 251, 255)
ROOT = Path(__file__).resolve().parents[2]
# Last mosaic where lawn trees were intact and panther/guard still present.
_LAWN_DONOR_REV = "1d41a6f"

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
    painted = _patch_outdoor_lawns_from_donor(arr)
    stats = _cell_color_stats(arr)
    ch, cw = stats["ch"], stats["cw"]
    sky_cells = _collect_blobs(
        stats["sky_sil"],
        ch,
        cw,
        lambda cells: _is_standing_figure(
            cells, stats["red"], stats["white"], stats["green"], ch, cw
        ),
    )
    grass_cells = _collect_blobs(
        stats["grass_sil"],
        ch,
        cw,
        lambda cells: (
            _is_standing_figure(
                cells, stats["red"], stats["white"], stats["green"], ch, cw
            )
            or _is_grass_animal(cells, stats["green"], stats["sky"], ch, cw)
        ),
    )
    unique = list(dict.fromkeys(sky_cells + grass_cells))
    if unique:
        for cx, cy in unique:
            painted += _erase_black_cell(
                arr, cx, cy, ch, cw, stats["green"], stats["sky"]
            )
    if painted:
        img.paste(Image.fromarray(arr))
    return painted


def _cell_color_stats(arr: np.ndarray) -> dict:
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
    sky_sil = (
        (black >= 4)
        & (red == 0)
        & (green == 0)
        & (white == 0)
        & (yellow == 0)
        & (black + sky >= 60)
    )
    grass_sil = (
        (black >= 8)
        & (red == 0)
        & (white == 0)
        & (yellow == 0)
        & (green < 24)
    )
    return {
        "ch": ch,
        "cw": cw,
        "black": black,
        "red": red,
        "green": green,
        "white": white,
        "yellow": yellow,
        "sky": sky,
        "sky_sil": sky_sil,
        "grass_sil": grass_sil,
    }


def _load_world_rev(rev: str) -> Image.Image | None:
    try:
        data = subprocess.check_output(
            ["git", "show", f"{rev}:assets/world/saboteur2_world2.png"],
            cwd=ROOT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    try:
        return Image.open(BytesIO(data)).convert("RGB")
    except OSError:
        return None


def _patch_outdoor_lawns_from_donor(arr: np.ndarray) -> int:
    """Restore lawn trees and finish erasing panther/guard feet.

    Incomplete grass fills left green stubs; neighbour expansion nicked the
    east trunk. Donor is the last intact mosaic; only outdoor lawn columns
    are touched, never crates / ? / indoor furniture.
    """
    donor_img = _load_world_rev(_LAWN_DONOR_REV)
    if donor_img is None:
        return 0
    donor = np.array(donor_img)
    if donor.shape != arr.shape:
        return 0
    stats = _cell_color_stats(donor)
    ch, cw = stats["ch"], stats["cw"]
    figure_cells = list(
        dict.fromkeys(
            _collect_blobs(
                stats["sky_sil"],
                ch,
                cw,
                lambda cells: _is_standing_figure(
                    cells, stats["red"], stats["white"], stats["green"], ch, cw
                ),
            )
            + _collect_blobs(
                stats["grass_sil"],
                ch,
                cw,
                lambda cells: (
                    _is_standing_figure(
                        cells, stats["red"], stats["white"], stats["green"], ch, cw
                    )
                    or _is_grass_animal(cells, stats["green"], stats["sky"], ch, cw)
                ),
            )
        )
    )
    if not figure_cells:
        return 0
    outdoor = _outdoor_lawn_columns(donor, stats)
    figure_cells = [(cx, cy) for cx, cy in figure_cells if outdoor[cx]]
    if not figure_cells:
        return 0
    tree_cell = (stats["red"] >= 4) | (
        (stats["green"] >= 20) & (stats["sky"] >= 8) & (stats["black"] < 40)
    )
    figure_mask = np.zeros(arr.shape[:2], dtype=bool)
    for cx, cy in figure_cells:
        if tree_cell[cy, cx]:
            continue
        tile = donor[cy * CELL : (cy + 1) * CELL, cx * CELL : (cx + 1) * CELL]
        black = (tile == (0, 0, 0)).all(axis=2)
        yellow = (
            (tile[:, :, 0] >= 180)
            & (tile[:, :, 1] >= 180)
            & (tile[:, :, 2] < 40)
        )
        figure_mask[cy * CELL : (cy + 1) * CELL, cx * CELL : (cx + 1) * CELL] = (
            black | yellow
        )
    if not figure_mask.any():
        return 0
    painted = 0
    grass_y = _grass_horizon_ys(donor, outdoor, stats)
    lawn = _lawn_band_mask(arr.shape, grass_y)
    figure_mask &= lawn
    ys, xs = np.where(figure_mask)
    for y, x in zip(ys, xs):
        gy = grass_y[x]
        if gy is not None and y >= gy:
            fill = tuple(int(v) for v in donor[gy, x])
            if fill != GRASS_GREEN and not (
                fill[1] >= 200 and fill[0] < 40 and fill[2] < 40
            ):
                fill = GRASS_GREEN
        else:
            fill = SKY_BLUE
        if tuple(int(v) for v in arr[y, x]) != fill:
            arr[y, x] = fill
            painted += 1
    # Leftover grass stubs in open sky (donor was sky, current still grass).
    donor_sky = (donor == SKY_BLUE).all(axis=2)
    cur_grass = (
        (arr[:, :, 1] >= 200) & (arr[:, :, 0] < 40) & (arr[:, :, 2] < 40)
    )
    extra = donor_sky & cur_grass & lawn
    n_extra = int(extra.sum())
    if n_extra:
        arr[extra] = SKY_BLUE
        painted += n_extra
    # Put back any tree ink the earlier neighbour expansion ate.
    donor_tree = (
        ((donor[:, :, 0] >= 200) & (donor[:, :, 1] < 40) & (donor[:, :, 2] < 40))
        | (
            (donor[:, :, 1] >= 200)
            & (donor[:, :, 0] < 40)
            & (donor[:, :, 2] < 40)
            & ~_grass_strip_mask(donor, grass_y)
        )
    )
    tree_restore = donor_tree & ~figure_mask & lawn
    differ = (arr != donor).any(axis=2) & tree_restore
    n_tree = int(differ.sum())
    if n_tree:
        arr[differ] = donor[differ]
        painted += n_tree
    return painted


def _lawn_band_mask(shape: tuple, grass_y: list[int | None]) -> np.ndarray:
    """Pixels from canopy-height down to the grass strip, outdoor columns only."""
    h, w = shape[0], shape[1]
    mask = np.zeros((h, w), dtype=bool)
    tree_h = 14 * CELL
    for x, gy in enumerate(grass_y):
        if gy is None:
            continue
        y0 = max(0, gy - tree_h)
        y1 = min(h, gy + CELL)
        mask[y0:y1, x] = True
    return mask


def _outdoor_lawn_columns(arr: np.ndarray, stats: dict) -> np.ndarray:
    """True for x-cells whose ground is earth+grass, not mosaic building."""
    ch, cw = stats["ch"], stats["cw"]
    outdoor = np.zeros(cw, dtype=bool)
    for cx in range(cw):
        for cy in range(ch - 1):
            if stats["green"][cy, cx] < 16:
                continue
            below = arr[(cy + 1) * CELL : (cy + 2) * CELL, cx * CELL : (cx + 1) * CELL]
            black_n = int((below == (0, 0, 0)).all(axis=2).sum())
            green_n = int(
                (
                    (below[:, :, 1] >= 200)
                    & (below[:, :, 0] < 40)
                    & (below[:, :, 2] < 40)
                ).sum()
            )
            red_n = int(
                (
                    (below[:, :, 0] >= 200)
                    & (below[:, :, 1] < 40)
                    & (below[:, :, 2] < 40)
                ).sum()
            )
            if black_n >= 32 and green_n < 8 and red_n < 8:
                outdoor[cx] = True
                break
    return outdoor


def _grass_horizon_ys(
    arr: np.ndarray, outdoor: np.ndarray, stats: dict
) -> list[int | None]:
    h, w, _ = arr.shape
    ch, cw = stats["ch"], stats["cw"]
    out: list[int | None] = [None] * w
    green = (arr[:, :, 1] >= 200) & (arr[:, :, 0] < 40) & (arr[:, :, 2] < 40)
    for cx in range(cw):
        if not outdoor[cx]:
            continue
        x0, x1 = cx * CELL, (cx + 1) * CELL
        grass_cy = None
        for cy in range(ch - 1):
            if stats["green"][cy, cx] < 16:
                continue
            below = arr[(cy + 1) * CELL : (cy + 2) * CELL, x0:x1]
            black_n = int((below == (0, 0, 0)).all(axis=2).sum())
            green_n = int(
                (
                    (below[:, :, 1] >= 200)
                    & (below[:, :, 0] < 40)
                    & (below[:, :, 2] < 40)
                ).sum()
            )
            red_n = int(
                (
                    (below[:, :, 0] >= 200)
                    & (below[:, :, 1] < 40)
                    & (below[:, :, 2] < 40)
                ).sum()
            )
            if black_n >= 32 and green_n < 8 and red_n < 8:
                grass_cy = cy
                break
        if grass_cy is None:
            continue
        y0 = grass_cy * CELL
        y1 = min(h, y0 + CELL)
        for y in range(y0, y1):
            if int(green[y, x0:x1].sum()) >= 4:
                for x in range(x0, x1):
                    out[x] = y
                break
    return out


def _grass_strip_mask(arr: np.ndarray, grass_y: list[int | None]) -> np.ndarray:
    mask = np.zeros(arr.shape[:2], dtype=bool)
    h, w = mask.shape
    for x, gy in enumerate(grass_y):
        if gy is None:
            continue
        y1 = min(h, gy + 8)
        mask[gy:y1, x] = True
    return mask


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
