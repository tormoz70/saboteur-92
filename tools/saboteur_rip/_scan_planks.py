"""Scan the mosaic for bookcase plank tiles (probe helper)."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_s2_world import CELL, SCREEN_H, SCREEN_W, SRC, find_bookcases  # noqa: E402


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    cases = find_bookcases(im)
    print("bookcases", len(cases))
    print(Counter((w, h) for _, _, w, h in cases))
    for x, y, w, h in cases[:60]:
        print(f"  cell ({x},{y}) {w}x{h} px ({x*CELL},{y*CELL}) screen ({x*CELL//SCREEN_W},{y*CELL//SCREEN_H})")


if __name__ == "__main__":
    main()
