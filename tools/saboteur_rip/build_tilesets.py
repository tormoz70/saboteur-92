#!/usr/bin/env python3
"""Generate native Godot TileSet .tres resources from the atlases.

Visual tilesets: one per layer, plain atlas, no physics.
Collision tileset: 4 semantic tiles with a physics layer and a
collision_type custom data layer, so TileMapLayer physics and ladder
detection both work from the same resource.

Run after build_world_atlas.py:
  python tools/saboteur_rip/build_tilesets.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT_TILESETS = ROOT / "assets" / "tilesets"
CELLS = ROOT / "assets" / "world" / "s2_world_cells.json"

CELL = 8

# Collision tile ids in the 4x1 collision atlas.
COLLISION_TILES = [
    ("empty", None),      # 0:0 transparent, no polygon
    ("solid", "solid"),   # 1:0 red, full square
    ("ladder", "ladder"), # 2:0 yellow, no polygon (climb is an Area2D)
    ("oneway", "oneway"), # 3:0 cyan, one-way platform
]

# Full-square polygon for an 8x8 tile, centred on the tile origin.
SQUARE = "PackedVector2Array(-4, -4, 4, -4, 4, 4, -4, 4)"


def _atlas_grid(png: Path) -> tuple[int, int]:
    img = Image.open(png)
    return img.width // CELL, img.height // CELL


def write_visual_tileset(layer: dict) -> Path:
    name = layer["name"]
    png = OUT_TILESETS / f"s2_{name}_tileset.png"
    cols, rows = _atlas_grid(png)
    n_tiles = cols * rows
    lines = [
        '[gd_resource type="TileSet" load_steps=2 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="res://assets/tilesets/s2_{name}_tileset.png" id="1"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]',
        'texture = ExtResource("1")',
        "texture_region_size = Vector2i(8, 8)",
        "use_texture_padding = true",
    ]
    for i in range(n_tiles):
        x = i % cols
        y = i // cols
        lines.append(f"{x}:{y}/0 = 0")
    lines.extend(
        [
            "",
            "[resource]",
            "tile_size = Vector2i(8, 8)",
            'sources/0 = SubResource("TileSetAtlasSource_1")',
            "",
        ]
    )
    out = OUT_TILESETS / f"s2_{name}_tileset.tres"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_collision_tileset() -> Path:
    png = OUT_TILESETS / "s2_collision_tileset.png"
    if not png.exists():
        _write_collision_png(png)
    lines = [
        '[gd_resource type="TileSet" load_steps=2 format=3]',
        "",
        '[ext_resource type="Texture2D" path="res://assets/tilesets/s2_collision_tileset.png" id="1"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]',
        'texture = ExtResource("1")',
        "texture_region_size = Vector2i(8, 8)",
        "use_texture_padding = true",
    ]
    for i, (kind, _physics) in enumerate(COLLISION_TILES):
        lines.append(f"{i}:0/0 = 0")
        lines.append(f'{i}:0/0/custom_data_0 = "{kind}"')
    # Physics polygons: only solid and oneway get a square; oneway is one-way.
    lines.append(f"1:0/0/physics_layer_0/polygon_0/points = {SQUARE}")
    lines.append(f"3:0/0/physics_layer_0/polygon_0/points = {SQUARE}")
    lines.append("3:0/0/physics_layer_0/polygon_0/one_way = true")
    lines.extend(
        [
            "",
            "[resource]",
            "tile_size = Vector2i(8, 8)",
            'custom_data_layer_0/name = "collision_type"',
            "custom_data_layer_0/type = 4",
            "physics_layer_0/collision_layer = 4",
            "physics_layer_0/collision_mask = 0",
            'sources/0 = SubResource("TileSetAtlasSource_1")',
            "",
        ]
    )
    out = OUT_TILESETS / "s2_collision_tileset.tres"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _write_collision_png(png: Path) -> None:
    from PIL import ImageDraw

    img = Image.new("RGBA", (CELL * 4, CELL), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [
        (0, 0, 0, 0),
        (200, 40, 40, 255),
        (220, 200, 40, 255),
        (40, 180, 220, 255),
    ]
    for i, color in enumerate(colors):
        if color[3] == 0:
            continue
        x0 = i * CELL
        draw.rectangle([x0, 0, x0 + CELL - 1, CELL - 1], fill=color)
    img.save(png)


def main() -> None:
    cells = json.loads(CELLS.read_text(encoding="utf-8"))
    written = []
    for layer in cells["layers"]:
        written.append(write_visual_tileset(layer))
    written.append(write_collision_tileset())
    print("build_tilesets:")
    for path in written:
        print("  wrote", path)


if __name__ == "__main__":
    main()
