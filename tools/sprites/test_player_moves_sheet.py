#!/usr/bin/env python3
"""The moves sheet keeps crouch-punch plus original SOM1C–SOM4C (air + floor)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "assets" / "sprites" / "saboteur93_player_moves.png"
FW, FH = 48, 56
CELLS = 9


def _cell(img: Image.Image, i: int) -> Image.Image:
    return img.crop((i * FW, 0, (i + 1) * FW, FH))


def main() -> None:
    img = Image.open(SHEET).convert("RGBA")
    assert img.size == (FW * CELLS, FH), f"{SHEET} is {img.size}, want {FW * CELLS}x{FH}"
    bottoms: list[int] = []
    for i in range(CELLS):
        bbox = _cell(img, i).getbbox()
        assert bbox is not None, f"cell {i} is empty"
        bottoms.append(bbox[3])
    air = bottoms[1:5]
    floor = bottoms[5:9]
    assert max(air) < min(floor), f"floor SOM should sit below air SOM: air={air} floor={floor}"
    print(f"ok: {SHEET.name} {CELLS} cells, air bottoms={air}, floor bottoms={floor}")


if __name__ == "__main__":
    main()
