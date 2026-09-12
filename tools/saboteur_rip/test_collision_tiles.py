#!/usr/bin/env python3
"""Collision tile RLE round-trip vs s2_collision.json rectangles."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collision_tiles import (
    greedy_rects,
    ladder_rects,
    payload_from_collision_json,
    rle_decode,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "world"


def test_roundtrip_counts() -> None:
    data = json.loads((OUT / "s2_collision.json").read_text(encoding="utf-8"))
    payload = payload_from_collision_json(data)
    cw, ch = payload["grid"]
    ids = rle_decode(payload["rle"])
    climb = rle_decode(payload["ladder_rle"])
    assert len(ids) == cw * ch
    assert len(climb) == cw * ch
    solid_grid = []
    climb_grid = []
    for y in range(ch):
        srow = []
        lrow = []
        for x in range(cw):
            i = y * cw + x
            srow.append(1 if ids[i] in (1, 3) else 0)
            lrow.append(1 if climb[i] else 0)
        solid_grid.append(srow)
        climb_grid.append(lrow)
    solids = greedy_rects(solid_grid)
    ladders = ladder_rects(climb_grid)
    assert len(solids) == len(data["solids"]), (len(solids), len(data["solids"]))
    assert len(ladders) == len(data["ladders"]), (len(ladders), len(data["ladders"]))
    assert solids == data["solids"]
    assert ladders == data["ladders"]


def test_committed_file_matches() -> None:
    path = OUT / "s2_collision_tiles.json"
    assert path.exists(), "run collision_tiles.py"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload.get("collision_source") == "collision_tiles"
    assert payload["tiles"]["solid"] == 1
    assert payload["tiles"]["ladder"] == 2
    data = json.loads((OUT / "s2_collision.json").read_text(encoding="utf-8"))
    fresh = payload_from_collision_json(data)
    assert payload["rle"] == fresh["rle"]


def main() -> None:
    test_roundtrip_counts()
    test_committed_file_matches()
    print("test_collision_tiles: OK")


if __name__ == "__main__":
    main()
