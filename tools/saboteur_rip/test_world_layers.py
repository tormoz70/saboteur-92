#!/usr/bin/env python3
"""Object-registry layer checks — no TileMap RLE, no colour heuristics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from opcode_catalog import LAYER_NAMES, LAYER_Z
from PIL import Image

OUT = ROOT / "assets" / "world"


def test_objects_catalog() -> None:
    catalog = json.loads((OUT / "s2_objects.json").read_text(encoding="utf-8"))
    types = catalog.get("types") or {}
    instances = catalog.get("instances") or []
    assert types, "object types"
    assert instances, "instances"
    assert catalog.get("playfield") == [256, 144], catalog.get("playfield")
    assert catalog.get("map") == [32, 32], catalog.get("map")
    assert catalog.get("size") == [8192, 4608], catalog.get("size")
    layers = {spec["layer"] for spec in types.values()}
    for name in LAYER_NAMES.values():
        assert name in catalog.get("layer_z", {}), name
    assert "interior" in layers or "structure" in layers
    sprites = 0
    for tid, spec in types.items():
        rel = spec["sprite"].replace("res://", "")
        if (ROOT / rel).exists():
            sprites += 1
        base_z = LAYER_Z[[k for k, n in LAYER_NAMES.items() if n == spec["layer"]][0]]
        if spec.get("overlay"):
            assert spec["z"] > base_z, spec
        elif tid == "wallpaper_green":
            assert spec["z"] < base_z, spec
        else:
            assert spec["z"] == base_z
    assert sprites > 0, "type sprites on disk"
    assert "desk" in types, "desk overlay type"
    desk = types["desk"]
    assert desk["layer"] == "interior"
    assert desk.get("overlay")
    assert (ROOT / "assets/world/objects/interior/desk.png").exists()
    px = Image.open(ROOT / "assets/world/objects/interior/desk.png")
    assert px.mode == "RGBA"
    assert any(p[3] == 0 for p in px.getdata()), "desk sprite keeps wallpaper holes"
    moons = [i for i in instances if i.get("type") == "moon"]
    assert len(moons) == 1, len(moons)
    assert "moon" in types
    assert "wallpaper_green" in types
    paper = types["wallpaper_green"]
    assert paper["layer"] == "interior"
    assert paper["z"] == -15
    assert paper["collision"] == "none"
    papers = [i for i in instances if i.get("type") == "wallpaper_green"]
    assert papers, "indoor rooms have wallpaper"
    trees = [i for i in instances if str(i.get("type", "")).startswith("tree_")]
    assert trees, "tree stamps exist"
    assert "tree_left" in types and "tree_right" in types and "tree_leaves" in types
    assert types["tree_left"]["layer"] == "sky"
    crate = Image.open(ROOT / "assets/world/objects/interior/furniture_115.png")
    assert crate.mode == "RGBA"
    assert any(p[:3] == (255, 255, 0) for p in crate.getdata()), "BOX5P is bright yellow OCHRS crates"
    px = Image.open(ROOT / "assets/world/objects/interior/wallpaper_green.png")
    assert any(p[:3] in ((0, 255, 0), (0, 251, 0)) for p in px.getdata()), "indoor paper is ZX green brick"


def test_collision_from_objects() -> None:
    data = json.loads((OUT / "s2_collision.json").read_text(encoding="utf-8"))
    assert data.get("collision_source") == "object_bounds"
    assert data.get("solids")
    assert data.get("ladders")


def main() -> None:
    test_objects_catalog()
    test_collision_from_objects()
    print("test_world_layers: OK")


if __name__ == "__main__":
    main()
