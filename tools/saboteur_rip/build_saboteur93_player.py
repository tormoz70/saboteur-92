#!/usr/bin/env python3
"""Build saboteur93_player.png — ninja sheet with six animation groups."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RIPPED = ROOT / "assets" / "reference" / "original" / "ripped"
SRC85 = ROOT / "assets" / "sprites" / "saboteur85_player.png"
OUT = ROOT / "assets" / "sprites" / "saboteur93_player.png"

FW, FH = 48, 56

# Frame order: idle×2, run×4, punch×2, jump_kick×2, climb×2, crouch×2
FRAME_NAMES: list[str] = [
    "standing",
    "standing",
    "walk_1",
    "walk_2",
    "walk_3",
    "walk_4",
    "standing",
    "punch",
    "jump",
    "jump_kick",
    "ladder",
    "ladder",
    "sitting",
    "sitting",
]


def load_frame(name: str) -> Image.Image:
    path = RIPPED / f"ninja_{name}.png"
    if path.exists():
        img = Image.open(path).convert("RGBA")
        if img.size != (FW, FH):
            img = img.resize((FW, FH), Image.NEAREST)
        return img
    raise FileNotFoundError(path)


def load_from_85(index: int) -> Image.Image:
    sheet = Image.open(SRC85).convert("RGBA")
    return sheet.crop((index * FW, 0, (index + 1) * FW, FH))


def nudge_frame(frame: Image.Image, dx: int = 0, dy: int = 0) -> Image.Image:
    """Shift opaque pixels for a subtle second idle/crouch frame."""
    out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    out.paste(frame, (dx, dy), frame)
    return out


def build() -> Image.Image:
    frames: list[Image.Image] = []
    for name in FRAME_NAMES:
        try:
            frames.append(load_frame(name))
        except FileNotFoundError:
            # Fallback: map legacy 85 indices when ripped folder is absent
            fallback = {
                "standing": 0,
                "walk_1": 2,
                "walk_2": 3,
                "walk_3": 4,
                "walk_4": 5,
                "jump": 6,
                "punch": 7,
                "jump_kick": 8,
                "ladder": 9,
                "sitting": 0,
            }
            frames.append(load_from_85(fallback[name]))

    # Second idle: one-pixel bob; second crouch: tiny shift
    frames[1] = nudge_frame(frames[0], dy=1)
    frames[13] = nudge_frame(frames[12], dy=1)

    sheet = Image.new("RGBA", (FW * len(frames), FH), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * FW, 0), frame)
    return sheet


def main() -> None:
    if not RIPPED.exists() and not SRC85.exists():
        raise SystemExit("Need ripped frames or saboteur85_player.png")

    sheet = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"Wrote {OUT} ({sheet.size[0]}x{sheet.size[1]}, {sheet.size[0] // FW} frames)")


if __name__ == "__main__":
    main()
