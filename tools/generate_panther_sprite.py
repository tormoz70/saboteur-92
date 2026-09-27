#!/usr/bin/env python3
"""Draw the Saboteur II panther sheet in one-colour ZX style.

The 1987 map has panthers baked into its screens (the ones
tools/saboteur_rip/fan_map_cleanup.py and the chunk edits erased): a black
cat about 56x24 px, long tail, low head. There is no sprite of it in the
game data we ripped, so this draws one from primitives, like
generate_saboteur85_assets.py draws its placeholder cast.

Output: assets/sprites/saboteur92_panther.png, 64x32 frames, feet on the
bottom row, facing right:
    0-3  gallop (extended, gather, collected, flight)
    4    crouch (stunned / waiting at a ledge)

Deterministic; run `python tools/generate_panther_sprite.py`, then import
once with `godot --headless --path . --import`.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sprites" / "saboteur92_panther.png"

FW, FH = 64, 32
GROUND = FH - 1
INK = (0, 0, 0, 255)
PAPER = (0, 0, 0, 0)

# (shoulder, paw) pairs for front and hind legs, plus a body lift, per frame.
# Coordinates are frame pixels; the leg is a 2 px limb with a bent knee.
GALLOP = [
    {  # extended: front reaching forward, hind pushing back
        "lift": 1,
        "front": [((42, 20), (48, 25), (53, GROUND)), ((40, 20), (45, 26), (49, GROUND))],
        "hind": [((18, 20), (12, 25), (7, GROUND)), ((20, 20), (15, 26), (11, GROUND))],
    },
    {  # gather: front sweeping back, hind swinging forward
        "lift": 0,
        "front": [((42, 20), (41, 26), (38, GROUND)), ((40, 20), (43, 26), (42, GROUND))],
        "hind": [((18, 20), (22, 26), (25, GROUND)), ((20, 20), (18, 26), (20, GROUND))],
    },
    {  # collected: legs bunched under the belly
        "lift": 0,
        "front": [((42, 20), (37, 26), (33, GROUND)), ((40, 20), (38, 25), (36, GROUND))],
        "hind": [((18, 20), (25, 25), (29, GROUND)), ((20, 20), (24, 26), (27, GROUND))],
    },
    {  # flight: all four paws off the ground, stretched
        "lift": 2,
        "front": [((42, 20), (49, 22), (55, 25)), ((40, 20), (47, 23), (52, 27))],
        "hind": [((18, 20), (11, 22), (5, 25)), ((20, 20), (13, 24), (8, 27))],
    },
]


def _limb(draw: ImageDraw.ImageDraw, pts, dy: int) -> None:
    shifted = [(x, y - dy if y < GROUND else y) for x, y in pts]
    draw.line(shifted, fill=1, width=2)
    px, py = shifted[-1]
    draw.rectangle([px, py - 1, px + 2, py], fill=1)


def _body(draw: ImageDraw.ImageDraw, dy: int, crouch: bool = False) -> None:
    top = 13 - dy + (3 if crouch else 0)
    # Haunch, a lean waist and a deep chest.
    draw.ellipse([12, top, 25, top + 9], fill=1)
    draw.rectangle([19, top + 1, 37, top + 6], fill=1)
    draw.ellipse([31, top - 1, 45, top + 9], fill=1)
    # Neck and a small head carried low, level with the shoulder.
    hy = top - 1 + (2 if crouch else 0)
    draw.polygon([(40, top), (46, hy - 1), (49, hy + 5), (42, top + 6)], fill=1)
    draw.ellipse([45, hy - 2, 54, hy + 5], fill=1)
    draw.rectangle([53, hy + 1, 56, hy + 4], fill=1)
    draw.point((47, hy - 3), fill=1)
    draw.point((50, hy - 3), fill=1)
    draw.point((52, hy + 1), fill=0)
    # Long tail sweeping down off the rump, tip turned up.
    draw.line(
        [(13, top + 2), (8, top + 4), (4, top + 7), (2, top + 10)],
        fill=1,
        width=2,
    )
    draw.line([(2, top + 10), (0, top + 8)], fill=1, width=1)


def gallop_frame(i: int) -> Image.Image:
    spec = GALLOP[i]
    mask = Image.new("1", (FW, FH), 0)
    draw = ImageDraw.Draw(mask)
    dy = spec["lift"]
    _body(draw, dy)
    for pts in spec["front"] + spec["hind"]:
        _limb(draw, pts, dy)
    return _ink(mask)


def crouch_frame() -> Image.Image:
    mask = Image.new("1", (FW, FH), 0)
    draw = ImageDraw.Draw(mask)
    _body(draw, 0, crouch=True)
    for pts in (
        ((42, 23), (47, 28), (50, GROUND)),
        ((40, 23), (44, 28), (46, GROUND)),
        ((18, 23), (13, 28), (12, GROUND)),
        ((20, 23), (17, 28), (16, GROUND)),
    ):
        _limb(draw, pts, 0)
    return _ink(mask)


def _ink(mask: Image.Image) -> Image.Image:
    out = Image.new("RGBA", mask.size, PAPER)
    out.paste(INK, mask=mask)
    return out


def build_sheet() -> Image.Image:
    frames = [gallop_frame(i) for i in range(len(GALLOP))] + [crouch_frame()]
    sheet = Image.new("RGBA", (FW * len(frames), FH), PAPER)
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * FW, 0))
    return sheet


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    build_sheet().save(OUT)
    print(f"Wrote {OUT.relative_to(ROOT)} ({FW}x{FH} frames)")


if __name__ == "__main__":
    main()
