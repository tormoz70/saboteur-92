#!/usr/bin/env python3
"""Extract Saboteur II world grid from S2ROOM.MAC (SMAP 32x28 room ids).

Room drawing tokens stay in S2ROOM.MAC (246 templates). This dumps the
world index used to stitch ~700 flip-screens.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAC = ROOT / "assets" / "reference" / "original" / "s2" / "ms0515-various" / "SABOT2-DISASM" / "S2ROOM.MAC"
OUT = ROOT / "assets" / "reference" / "original" / "maps"

WIDTH, HEIGHT = 32, 28


def smap_bytes(text: str) -> list[int]:
    collect = False
    vals: list[int] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SMAP:"):
            collect = True
            continue
        if collect and line.startswith("ROOMSA:"):
            break
        if not collect or ".BYTE" not in raw:
            continue
        part = raw.split(".BYTE", 1)[1].split(";")[0]
        for tok in part.split(","):
            tok = tok.strip()
            if tok:
                vals.append(int(tok, 8))
    return vals[: WIDTH * HEIGHT]


def main() -> None:
    vals = smap_bytes(MAC.read_text(encoding="utf-8", errors="replace"))
    grid = [vals[i : i + WIDTH] for i in range(0, WIDTH * HEIGHT, WIDTH)]
    nonempty = sum(1 for row in grid for v in row if v)
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "S2ROOM.MAC SMAP K70572",
        "width": WIDTH,
        "height": HEIGHT,
        "screen_px": [256, 192],
        "nonempty": nonempty,
        "rooms": grid,
    }
    out = OUT / "s2_world.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({nonempty} occupied of {WIDTH * HEIGHT})")
    for y, row in enumerate(grid):
        print(f"{y:02d}", "".join("." if v == 0 else "#" for v in row))


if __name__ == "__main__":
    main()
