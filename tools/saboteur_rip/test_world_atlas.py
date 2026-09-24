#!/usr/bin/env python3
"""Roundtrip gate: rebuilding the map from the emitted atlases and grid must
equal the source image with fan chrome painted to sky, pixel for pixel.

Run either way:
  python tools/saboteur_rip/test_world_atlas.py
  python -m pytest tools/saboteur_rip/test_world_atlas.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "world" / "saboteur2_world2.png"
CELLS = ROOT / "assets" / "world" / "s2_world_cells.json"
BUILD = ROOT / "tools" / "saboteur_rip" / "build_world_atlas.py"

CELL = 8
SKY_BLUE = (0, 0, 206)
FAN_SKY_CELLS = (
    (0, 0, 140, 112),
    (936, 0, 1024, 500),
)


def _paint_chrome(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    for cx0, cy0, cx1, cy1 in FAN_SKY_CELLS:
        draw.rectangle(
            [cx0 * CELL, cy0 * CELL, cx1 * CELL - 1, cy1 * CELL - 1],
            fill=SKY_BLUE,
        )


def _ensure_built() -> dict:
    # Scratch dir: a plain builder run writes draft/ and must not be
    # pointed at the hand-edited atlases.
    out = Path(tempfile.mkdtemp(prefix="s2-atlas-"))
    cells = out / "s2_world_cells.json"
    subprocess.run(
        [sys.executable, str(BUILD), "--tileset-dir", str(out), "--cells", str(cells)],
        check=True,
        cwd=ROOT,
    )
    return json.loads(cells.read_text(encoding="utf-8"))


def _load_atlas(layer: dict) -> Image.Image:
    path = Path(layer["tileset"].replace("res://", ""))
    if not path.is_absolute():
        path = ROOT / path
    return Image.open(path).convert("RGB")


def _rebuild(built: dict) -> Image.Image:
    cw, ch = built["grid"]
    width, height = built["size"]
    atlases = [_load_atlas(layer) for layer in built["layers"]]
    cells = built["cells"]
    rebuild = Image.new("RGB", (width, height), SKY_BLUE)
    for cy in range(ch):
        for cx in range(cw):
            li, tid = cells[cy * cw + cx]
            if li < 0:
                continue
            atlas = atlases[li]
            cols = atlas.width // CELL
            tx = (tid % cols) * CELL
            ty = (tid // cols) * CELL
            rebuild.paste(atlas.crop((tx, ty, tx + CELL, ty + CELL)), (cx * CELL, cy * CELL))
    return rebuild


def test_rebuild_matches_source_pixel_exact() -> None:
    built = _ensure_built()
    rebuild = _rebuild(built)
    expected = Image.open(SRC).convert("RGB")
    _paint_chrome(expected)
    assert rebuild.size == expected.size
    assert rebuild.tobytes() == expected.tobytes(), (
        "rebuild from atlases+grid differs from source outside fan chrome"
    )


def test_every_non_sky_cell_is_mapped() -> None:
    built = _ensure_built()
    counts: dict[int, int] = {}
    for li, _tid in built["cells"]:
        counts[li] = counts.get(li, 0) + 1
    assert counts.get(-1, 0) > 0, "expected some sky cells"
    for layer_index in range(len(built["layers"])):
        # fg may legitimately be empty on this map
        if built["layers"][layer_index]["name"] == "fg":
            continue
        assert counts.get(layer_index, 0) > 0


def test_atlas_tiles_cover_grid_ids() -> None:
    built = _ensure_built()
    layers = built["layers"]
    max_tid = [0] * len(layers)
    for li, tid in built["cells"]:
        if li >= 0:
            max_tid[li] = max(max_tid[li], tid)
    for li, layer in enumerate(layers):
        atlas = _load_atlas(layer)
        n_tiles = (atlas.width // CELL) * (atlas.height // CELL)
        assert max_tid[li] < n_tiles, (
            f"layer {layer['name']}: grid references tile {max_tid[li]}, "
            f"atlas has {n_tiles}"
        )


def main() -> int:
    tests = [
        test_rebuild_matches_source_pixel_exact,
        test_every_non_sky_cell_is_mapped,
        test_atlas_tiles_cover_grid_ids,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
        else:
            print(f"ok   {fn.__name__}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
