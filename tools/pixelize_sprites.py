#!/usr/bin/env python3
"""Pack chroma-key animation strips into pixel-art sprite sheets.

Each source PNG is one animation: N figures in a row on a flat background.
The script keys that background, isolates each figure, scales it into a
fixed cell, snaps colours to a small palette, draws a 1 px outline, and
packs the cells left to right in the order the game already uses.

    python tools/pixelize_sprites.py

Sources live in assets/sprites/_source/ (kept out of Godot by .gdignore).
The script is deterministic: the same inputs write the same bytes.
Requires Pillow and numpy.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "sprites" / "_source"
OUT = ROOT / "assets" / "sprites"

# Art-bible roles, plus a few steps so folds survive the snap.
GUARD = [
    (12, 16, 28),
    (30, 58, 138),
    (70, 110, 190),
    (139, 94, 60),
    (196, 164, 130),
    (232, 232, 232),
    (40, 44, 52),
    (180, 40, 40),
    (5, 6, 10),
]
PANTHER = [
    (8, 8, 10),
    (36, 32, 34),
    (78, 70, 68),
    (140, 128, 120),
    (220, 180, 40),
    (40, 160, 70),
    (5, 6, 10),
]
OUTLINE = (5, 6, 10)
KEY_DISTANCE = 55.0


def _palette(name: str) -> np.ndarray:
    table = {"guard": GUARD, "panther": PANTHER}[name]
    return np.array(table, dtype=np.float64)


def _corner_key(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    samples = np.stack(
        [
            rgb[0, 0],
            rgb[0, w - 1],
            rgb[h - 1, 0],
            rgb[h - 1, w - 1],
            rgb[0, w // 2],
            rgb[h // 2, 0],
        ]
    )
    return np.median(samples, axis=0)


def _opaque_mask(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    key = _corner_key(rgb)
    dist = np.linalg.norm(rgb - key, axis=2)
    # Magenta and green screens count even if the corners were cropped.
    magenta = np.linalg.norm(rgb - np.array([255.0, 0.0, 255.0]), axis=2)
    green = np.linalg.norm(rgb - np.array([0.0, 255.0, 0.0]), axis=2)
    # Pink fringe where the key colour mixed with the figure.
    fringe = (rgb[:, :, 0] > 160.0) & (rgb[:, :, 2] > 120.0) & (rgb[:, :, 1] < 140.0)
    background = (dist < KEY_DISTANCE) | (magenta < 80.0) | (green < 80.0) | fringe
    return (alpha > 16) & ~background


def _segments(mask: np.ndarray, expected: int) -> list[tuple[int, int]]:
    columns = np.flatnonzero(mask.any(axis=0))
    if columns.size == 0:
        return []
    gaps = np.flatnonzero(np.diff(columns) > 2)
    starts = [int(columns[0])]
    ends = []
    for gap in gaps:
        ends.append(int(columns[gap]) + 1)
        starts.append(int(columns[gap + 1]))
    ends.append(int(columns[-1]) + 1)
    spans = list(zip(starts, ends))
    if len(spans) == expected:
        return spans
    # Figures touched. Cut the content span into equal slices.
    left, right = int(columns[0]), int(columns[-1]) + 1
    width = right - left
    return [
        (left + width * i // expected, left + width * (i + 1) // expected)
        for i in range(expected)
    ]


def _quantize(rgb: np.ndarray, palette: np.ndarray) -> np.ndarray:
    # (H, W, K) squared distance, lowest palette index wins ties.
    delta = rgb[:, :, None, :] - palette[None, None, :, :]
    dist = np.sum(delta * delta, axis=3)
    index = np.argmin(dist, axis=2)
    return palette[index]


def _outline(color: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    opaque = alpha > 0
    padded = np.pad(opaque, 1, mode="constant")
    neighbour = (
        padded[:-2, 1:-1]
        | padded[2:, 1:-1]
        | padded[1:-1, :-2]
        | padded[1:-1, 2:]
    )
    edge = neighbour & ~opaque
    color[edge] = OUTLINE
    alpha[edge] = 255
    return color, alpha


def _fit_cell(
    rgb: np.ndarray,
    mask: np.ndarray,
    x0: int,
    x1: int,
    cell: tuple[int, int],
    palette: np.ndarray,
) -> Image.Image:
    cell_w, cell_h = cell
    column = mask[:, x0:x1]
    rows = np.flatnonzero(column.any(axis=1))
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    if rows.size == 0:
        return canvas
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    crop_rgb = rgb[y0:y1, x0:x1]
    crop_mask = column[y0:y1]
    # Leave a 1 px outline margin. Feet sit on the bottom row.
    max_w = cell_w - 4
    max_h = cell_h - 3
    scale = min(max_w / crop_rgb.shape[1], max_h / crop_rgb.shape[0])
    scaled_w = max(1, int(round(crop_rgb.shape[1] * scale)))
    scaled_h = max(1, int(round(crop_rgb.shape[0] * scale)))
    figure = Image.fromarray(np.dstack([
        crop_rgb.astype(np.uint8),
        np.where(crop_mask, 255, 0).astype(np.uint8),
    ]))
    figure = figure.resize((scaled_w, scaled_h), Image.Resampling.BOX)
    arr = np.array(figure).astype(np.float64)
    snapped = _quantize(arr[:, :, :3], palette)
    alpha = arr[:, :, 3]
    snapped[alpha < 128] = 0
    alpha = np.where(alpha >= 128, 255, 0).astype(np.uint8)
    snapped, alpha = _outline(snapped, alpha)
    placed = Image.fromarray(
        np.dstack([snapped.astype(np.uint8), alpha]).astype(np.uint8)
    )
    dest_x = (cell_w - placed.width) // 2
    dest_y = cell_h - placed.height - 1
    canvas.alpha_composite(placed, (dest_x, dest_y))
    return canvas


def pack_strip(
    path: Path,
    count: int,
    cell: tuple[int, int],
    palette: np.ndarray,
) -> list[Image.Image]:
    image = Image.open(path).convert("RGBA")
    arr = np.array(image).astype(np.float64)
    rgb = arr[:, :, :3]
    mask = _opaque_mask(rgb, arr[:, :, 3])
    spans = _segments(mask, count)
    if len(spans) != count:
        raise SystemExit(f"{path.name}: expected {count} figures, found {len(spans)}")
    return [_fit_cell(rgb, mask, x0, x1, cell, palette) for x0, x1 in spans]


def _sheet(cells: list[Image.Image], cell: tuple[int, int]) -> Image.Image:
    width = cell[0] * len(cells)
    sheet = Image.new("RGBA", (width, cell[1]), (0, 0, 0, 0))
    for index, frame in enumerate(cells):
        sheet.alpha_composite(frame, (index * cell[0], 0))
    return sheet


# Order matches the atlas regions in the character scenes. Nina's sheets
# come from tools/sprites/remaster_zx_nina.py.
SHEETS: list[dict] = [
    {
        "out": "saboteur26_guard.png",
        "cell": (96, 112),
        "palette": "guard",
        "parts": [
            ("guard_idle.png", 2),
            ("guard_run.png", 4),
            ("guard_punch.png", 1),
        ],
    },
    {
        "out": "saboteur26_panther.png",
        "cell": (128, 64),
        "palette": "panther",
        "parts": [
            ("panther_run.png", 4),
            ("panther_crouch.png", 1),
        ],
    },
]


def build() -> None:
    ignore = SOURCE / ".gdignore"
    SOURCE.mkdir(parents=True, exist_ok=True)
    if not ignore.exists():
        ignore.write_bytes(b"")
    for spec in SHEETS:
        palette = _palette(spec["palette"])
        cells: list[Image.Image] = []
        for name, count in spec["parts"]:
            path = SOURCE / name
            if not path.exists():
                raise SystemExit(f"missing {path}")
            cells.extend(pack_strip(path, count, spec["cell"], palette))
        dest = OUT / spec["out"]
        _sheet(cells, spec["cell"]).save(dest)
        print(f"{dest.relative_to(ROOT).as_posix()}  {len(cells)} frames")


if __name__ == "__main__":
    build()
