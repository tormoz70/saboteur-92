#!/usr/bin/env python3
"""Extract Saboteur II world grid from S2ROOM.MAC.

32 columns × 32 levels: RMDN=0 is virtual sky (room 0); rows 1..31 are MAP
at K70632. Byte 0 is room 0, not empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opcode_catalog import MAP_W, PLAYFIELD_H, SCREEN_W, WORLD_ROWS
from room_bytecode import load_smap

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "reference" / "original" / "maps"


def main() -> None:
    grid = load_smap()
    nonempty = sum(1 for row in grid for v in row if v)
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "S2ROOM.MAC MAP K70632 + virtual RMDN=0",
        "width": MAP_W,
        "height": WORLD_ROWS,
        "screen_px": [SCREEN_W, PLAYFIELD_H],
        "nonempty": nonempty,
        "rooms": grid,
    }
    out = OUT / "s2_world.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({nonempty} occupied of {MAP_W * WORLD_ROWS})")
    for y, row in enumerate(grid):
        print(f"{y:02d}", "".join("." if v == 0 else "#" for v in row))


if __name__ == "__main__":
    main()
