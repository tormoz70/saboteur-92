"""Composite BG + a Nina stand-in + FG over a bookcase (probe helper)."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "assets" / "world" / "saboteur2_world.png"
FG = ROOT / "assets" / "world" / "saboteur2_fg.png"
OUT = ROOT / ".mcp" / "probe_comp.png"


def main() -> None:
    x, y, w, h = (int(v) for v in sys.argv[1:5])
    nina = [int(v) for v in sys.argv[5:9]] if len(sys.argv) > 8 else None
    bg = Image.open(WORLD).convert("RGBA").crop((x, y, x + w, y + h))
    fg = Image.open(FG).convert("RGBA").crop((x, y, x + w, y + h))
    if nina:
        draw = ImageDraw.Draw(bg)
        draw.rectangle((nina[0] - x, nina[1] - y, nina[0] - x + nina[2], nina[1] - y + nina[3]), fill=(255, 255, 255, 255))
    bg.alpha_composite(fg)
    bg.resize((w * 4, h * 4), Image.NEAREST).save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
