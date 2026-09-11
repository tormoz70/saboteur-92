#!/usr/bin/env python3
"""Layer export round-trip and composite checks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_s2_world as b

OUT = ROOT / "assets" / "world"
TILESET = ROOT / "assets" / "tilesets"


def test_tiles_json_has_layers() -> None:
    spec = json.loads((OUT / "s2_world_tiles.json").read_text(encoding="utf-8"))
    layers = spec.get("layers", {})
    for name in ("sky", "earth", "structure", "wallpaper", "interior", "fg"):
        assert name in layers, f"missing layer {name}"
        assert layers[name].get("rle"), f"empty rle for {name}"
        assert Path(layers[name]["atlas"].replace("res://", str(ROOT) + "/")).exists()


def test_objects_catalog() -> None:
    catalog = json.loads((OUT / "s2_objects.json").read_text(encoding="utf-8"))
    assert catalog.get("defs"), "object defs"
    assert catalog.get("placements"), "placements"
    assert (OUT / "objects" / "fg").is_dir()


def test_layer_atlas_roundtrip() -> None:
    spec = json.loads((OUT / "s2_world_tiles.json").read_text(encoding="utf-8"))
    cw, ch = spec["grid"]
    for name, layer in spec["layers"].items():
        mode = "RGBA" if name == "fg" else "RGB"
        ids = b.rle_decode(layer["rle"])
        atlas_cols = layer["atlas_tiles"][0]
        atlas_path = TILESET / Path(layer["atlas"]).name
        atlas = Image.open(atlas_path).convert(mode)
        rebuilt = b.reconstruct_from_atlas(atlas, ids, cw, ch, atlas_cols, mode)
        assert len(ids) == cw * ch, name


def test_world_composite_if_mosaic() -> None:
    if not b.SRC.exists():
        return
    im = Image.open(b.SRC).convert("RGB")
    solid, _lad, fg, bookcase, cases, biomes = b.classify_cells(im)
    world = im.copy()
    b.paint_cabinet_backs(world, bookcase)
    lifts, _car, car_rows = b.find_lifts(im, solid)
    b.paint_lift_cars(world, car_rows)
    b.punch_fg_cells(world, fg)
    fg_img = b.crate_overlay(im, fg, bookcase, cases)
    sx_n = im.width // b.SCREEN_W
    b.export_layered_world(
        world, fg_img, solid, fg, bookcase, biomes, im.load(), sx_n
    )
    spec = json.loads((OUT / "s2_world_tiles.json").read_text(encoding="utf-8"))
    rebuilt_world = b.reconstruct_world_from_tiles()
    assert rebuilt_world.tobytes() == world.tobytes()


def main() -> None:
    test_tiles_json_has_layers()
    test_objects_catalog()
    test_layer_atlas_roundtrip()
    test_world_composite_if_mosaic()
    print("test_world_layers: OK")


if __name__ == "__main__":
    main()
