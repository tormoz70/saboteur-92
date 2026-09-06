"""Save a scaled crop of the mosaic (probe helper): _crop.py x y w h [scale]."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_s2_world import CELL, SCREEN_H, SCREEN_W, SRC  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / ".mcp" / "probe_crop.png"


def main() -> None:
    x, y, w, h = (int(v) for v in sys.argv[1:5])
    s = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    im = Image.open(SRC).convert("RGB")
    im.crop((x, y, x + w, y + h)).resize((w * s, h * s), Image.NEAREST).save(OUT)
    print(f"crop ({x},{y}) {w}x{h} cell ({x // CELL},{y // CELL}) screen ({x // SCREEN_W},{y // SCREEN_H}) -> {OUT}")


if __name__ == "__main__":
    main()
