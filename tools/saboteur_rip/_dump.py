"""Dump an image region as Spectrum ink letters: _dump.py img x y w h."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_s2_world import CELL, _col  # noqa: E402


def main() -> None:
    path = sys.argv[1]
    x0, y0, w, h = (int(v) for v in sys.argv[2:6])
    im = Image.open(path).convert("RGB")
    px = im.load()
    head = "".join(str((x0 + i) % 10) for i in range(w))
    print(f"      {head}")
    for y in range(y0, y0 + h):
        row = "".join(_col(*px[x, y]) for x in range(x0, x0 + w))
        print(f"{y:5d}{'|' if y % CELL == 0 else ' '}{row}")


if __name__ == "__main__":
    main()
