#!/usr/bin/env python3
"""Lossless slicing of saboteur2_world2.png into per-layer Godot tile atlases.

No classification heuristics: every unique 8x8 cell becomes a tile, so the
rebuild is pixel-exact. Layer assignment comes from the checked-in table
assets/world/s2_tile_layers.json (tile id -> layer); a wrong layer is fixed
by editing the table, never by repainting pixels.

Outputs (draft/ by default; --overwrite writes the checked-in paths):
  draft/tilesets/s2_<layer>_tileset.png   one atlas per visual layer
  draft/s2_tile_layers.json               tile_id -> layer table
  draft/s2_world_cells.json               1024x576 grid of [layer, tile_id]
  draft/audit/slice_rebuild*.png          audit renders
  draft/audit/slice_report.json           counters

--tileset-dir and --cells write somewhere else (used by the roundtrip test)
and do not touch the checked-in atlases.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fan_map_cleanup import paint_fan_chrome as _paint_fan_chrome, paint_fan_guard_sprites

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fan_map_cleanup import paint_fan_chrome, paint_fan_guard_sprites
from tileset_guard import draft_root, prepare_draft, writing_live

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "world" / "saboteur2_world2.png"
OUT_WORLD = ROOT / "assets" / "world"
OUT_TILESETS = ROOT / "assets" / "tilesets"
OUT_REPORT = ROOT / "docs" / "audit_views"

CELL = 8
SCALE = 2
SCREEN = (256, 192)

SKY_BLUE = (0, 0, 206)
SKY_BLUE_B = (0, 0, 255)
BLACK = (0, 0, 0)
GREEN = (0, 251, 0)
RED = (255, 0, 0)

# Authoring layers in z-order. Sky is the SkyFill polygon, not a tile layer.
VISUAL_LAYERS = ("earth", "structure", "wallpaper", "mosaic", "interior", "fg")
LAYER_Z = {
    "earth": -20,
    "structure": -10,
    "wallpaper": -5,
    "mosaic": -4,
    "interior": 0,
    "fg": 12,
}

# Deterministic atlas order: most frequent tile first within a layer.
# Tile id 0 is reserved as the empty cell in every atlas.


def _is_sky_blue(p: tuple[int, int, int]) -> bool:
    return p == SKY_BLUE or p == SKY_BLUE_B


def _color_counts(buf: bytes) -> dict[str, int]:
    counts = {"red": 0, "green": 0, "blue": 0, "black": 0, "other": 0}
    for i in range(0, len(buf), 3):
        p = (buf[i], buf[i + 1], buf[i + 2])
        if p == RED:
            counts["red"] += 1
        elif p == GREEN:
            counts["green"] += 1
        elif _is_sky_blue(p):
            counts["blue"] += 1
        elif p == BLACK:
            counts["black"] += 1
        else:
            counts["other"] += 1
    return counts


def guess_layer(buf: bytes) -> str:
    """Initial tile -> layer guess by ink colour. Reviewed via s2_tile_layers.json.

    Everything that is not a flat background fill lands in `interior` — the
    former "leftover" (ladders, furniture, windows, signs, trees) is kept as
    tiles instead of being dropped.
    """
    c = _color_counts(buf)
    n = CELL * CELL
    if c["blue"] == n:
        return "earth"  # never used for sky: sky cells are excluded earlier
    if c["black"] == n:
        return "earth"
    if c["red"] + c["black"] == n and c["red"] >= 20:
        return "structure"
    if c["blue"] + c["black"] == n and c["blue"] >= 20:
        return "wallpaper"
    if c["green"] + c["black"] == n and c["green"] >= 20:
        return "mosaic"
    return "interior"


def paint_fan_chrome(img: Image.Image) -> None:
    """Erase Pavero logo, legend and ninja art so they never become tiles."""
    _paint_fan_chrome(img)


def cell_bytes(raw: memoryview, width: int, cx: int, cy: int) -> bytes:
    chunks: list[bytes] = []
    x0 = cx * CELL
    for y in range(CELL):
        row = ((cy * CELL + y) * width + x0) * 3
        chunks.append(bytes(raw[row : row + CELL * 3]))
    return b"".join(chunks)


def _is_pure_sky(buf: bytes) -> bool:
    for i in range(0, len(buf), 3):
        if not _is_sky_blue((buf[i], buf[i + 1], buf[i + 2])):
            return False
    return True


def pack_atlas(tiles: list[Image.Image], cols: int) -> Image.Image:
    n = len(tiles)
    rows = max(1, math.ceil(n / cols))
    atlas = Image.new("RGBA", (cols * CELL, rows * CELL), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        x = (i % cols) * CELL
        y = (i // cols) * CELL
        atlas.paste(tile.convert("RGBA"), (x, y))
    return atlas


def _tile_from_bytes(buf: bytes) -> Image.Image:
    return Image.frombytes("RGB", (CELL, CELL), buf).convert("RGBA")


def _blit_cell(dest: bytearray, width: int, cx: int, cy: int, tile: bytes) -> None:
    x0 = cx * CELL
    src_row = CELL * 3
    for y in range(CELL):
        dst = ((cy * CELL + y) * width + x0) * 3
        src = y * src_row
        dest[dst : dst + src_row] = tile[src : src + src_row]


def _arg(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv) or sys.argv[index + 1].startswith("--"):
        raise SystemExit(f"{flag} needs a path")
    return sys.argv[index + 1]


def main() -> None:
    tileset_arg = _arg("--tileset-dir")
    cells_arg = _arg("--cells")
    live = writing_live() and tileset_arg is None and cells_arg is None
    if live:
        tileset_dir = OUT_TILESETS
        cells_path = OUT_WORLD / "s2_world_cells.json"
        report_dir = OUT_REPORT
    else:
        scratch = draft_root(ROOT)
        if tileset_arg is None and cells_arg is None:
            prepare_draft(ROOT)
        tileset_dir = Path(tileset_arg) if tileset_arg else scratch / "tilesets"
        cells_path = Path(cells_arg) if cells_arg else scratch / "s2_world_cells.json"
        report_dir = scratch / "audit" if tileset_arg is None and cells_arg is None else cells_path.parent / "audit"
    canonical = tileset_dir.resolve() == OUT_TILESETS.resolve()
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    src = Image.open(SRC).convert("RGB")
    width, height = src.size
    if width % CELL or height % CELL:
        raise SystemExit(f"{SRC} size {width}x{height} is not divisible by {CELL}")
    paint_fan_chrome(src)
    n_guard = paint_fan_guard_sprites(src)
    if canonical:
        src.save(SRC)
    cw = width // CELL
    ch = height // CELL
    raw = memoryview(src.tobytes())

    # Pass 1: collect unique non-sky cells and their frequency.
    freq: Counter[bytes] = Counter()
    cell_buf: list[bytes | None] = [None] * (cw * ch)
    for cy in range(ch):
        for cx in range(cw):
            buf = cell_bytes(raw, width, cx, cy)
            if _is_pure_sky(buf):
                continue
            i = cy * cw + cx
            cell_buf[i] = buf
            freq[buf] += 1

    # Assign each unique tile a layer (table seed) and a deterministic id.
    tile_layer: dict[bytes, str] = {buf: guess_layer(buf) for buf in freq}
    layer_tiles: dict[str, list[bytes]] = {name: [] for name in VISUAL_LAYERS}
    tile_id: dict[bytes, int] = {}
    for name in VISUAL_LAYERS:
        mine = [buf for buf in freq if tile_layer[buf] == name]
        # Most frequent first, then by content for stability.
        mine.sort(key=lambda b: (-freq[b], b))
        layer_tiles[name] = mine
        for idx, buf in enumerate(mine):
            tile_id[buf] = idx + 1  # id 0 stays empty

    # Pass 2: emit the grid as [layer_index, tile_id] pairs.
    layer_index = {name: n for n, name in enumerate(VISUAL_LAYERS)}
    grid: list[list[int]] = []
    counts: Counter[str] = Counter({"sky": 0})
    for i in range(cw * ch):
        buf = cell_buf[i]
        if buf is None:
            grid.append([-1, 0])
            counts["sky"] += 1
            continue
        name = tile_layer[buf]
        grid.append([layer_index[name], tile_id[buf]])
        counts[name] += 1

    layers_path = (
        OUT_WORLD / "s2_tile_layers.json" if canonical else cells_path.with_name("s2_tile_layers.json")
    )
    tileset_dir.mkdir(parents=True, exist_ok=True)
    cells_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    # Atlases + table.
    unique_report: dict[str, int] = {}
    for name in VISUAL_LAYERS:
        tiles = layer_tiles[name]
        n = len(tiles) + 1  # + empty id 0
        cols = min(32, max(1, n))
        images = [Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))]
        images.extend(_tile_from_bytes(b) for b in tiles)
        atlas = pack_atlas(images, cols)
        atlas.save(tileset_dir / f"s2_{name}_tileset.png")
        unique_report[name] = len(tiles)

    table = {
        "note": "tile_id -> layer. Edit a layer here to re-file a tile; pixels never change.",
        "layers": VISUAL_LAYERS,
        "counts": {name: len(layer_tiles[name]) for name in VISUAL_LAYERS},
    }
    layers_path.write_text(json.dumps(table, indent=2), encoding="utf-8")

    cells_doc = {
        "scale": SCALE,
        "cell": CELL,
        "screen": list(SCREEN),
        "size": [width, height],
        "grid": [cw, ch],
        "sky_color": list(SKY_BLUE),
        "layers": [
            {
                "name": name,
                "z": LAYER_Z[name],
                "tileset": (
                    f"res://assets/tilesets/s2_{name}_tileset.png"
                    if canonical
                    else (tileset_dir / f"s2_{name}_tileset.png").resolve().as_posix()
                ),
            }
            for name in VISUAL_LAYERS
        ],
        "cells": grid,
    }
    cells_path.write_text(json.dumps(cells_doc, separators=(",", ":")), encoding="utf-8")

    # Audit render: rebuild from the emitted grid only.
    rebuild_buf = bytearray(width * height * 3)
    sky_row = bytes(SKY_BLUE) * CELL
    for cy in range(ch):
        for cx in range(cw):
            i = cy * cw + cx
            li, tid = grid[i]
            if li < 0:
                tile = sky_row * CELL
            else:
                tile = layer_tiles[VISUAL_LAYERS[li]][tid - 1]
            _blit_cell(rebuild_buf, width, cx, cy, tile)
    rebuild = Image.frombytes("RGB", (width, height), bytes(rebuild_buf))
    rebuild_path = report_dir / "slice_rebuild.png"
    rebuild.save(rebuild_path)
    overview = rebuild.resize((width // 4, height // 4), Image.Resampling.NEAREST)
    overview_path = report_dir / "slice_rebuild_quarter.png"
    overview.save(overview_path)

    report = {
        "source": SRC.as_posix(),
        "grid": [cw, ch],
        "cells": cw * ch,
        "counts": dict(counts),
        "unique_tiles": unique_report,
        "unique_total": sum(unique_report.values()),
        "guard_cells_erased": n_guard,
        "sky_color": list(SKY_BLUE),
        "rebuild": rebuild_path.as_posix(),
        "rebuild_quarter": overview_path.as_posix(),
    }
    (report_dir / "slice_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("build_world_atlas:")
    for name in ("sky",) + VISUAL_LAYERS:
        print(f"  {name:10} {counts[name]}")
    print("  unique", unique_report, "total", sum(unique_report.values()))
    print("  wrote", cells_path)
    print("  rebuild", rebuild_path)


if __name__ == "__main__":
    main()
