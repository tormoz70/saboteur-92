#!/usr/bin/env python3
"""Build saboteur93_player_moves.png — crouch punch plus original somersaults.

Both poses keep the 48x56 cell of saboteur93_player.png:

- crouch punch: the crouch pose with the standing punch's arm grafted on at
  crouch shoulder height.
- somersault / floor roll: original SOM1C–SOM4C maps (K46352, K46413,
  K46455, K46517) — four tucked rotations, not a PIL spin of the crouch.
  Air cells keep the Spectrum placement; floor-roll cells are the same
  four frames dropped so the ball sits on the standing baseline.
  If the ripped SOM frames are missing, fall back to rotating crouch
  (K47212) in 45° steps.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "sprites" / "saboteur93_player.png"
RIPPED_S2 = ROOT / "assets" / "reference" / "original" / "ripped_s2"
OUT = ROOT / "assets" / "sprites" / "saboteur93_player_moves.png"

FW, FH = 48, 56

PUNCH_FRAME = 6
CROUCH_FRAME = 12

PUNCH_ARM_BOX = (24, 17, 45, 21)
CROUCH_DROP = 16

SPIN_STEPS = 8
SPIN_CENTER = (24, 34)
# Crouch feet sit on y=56; original SOM balls end around y=36.
FLOOR_DROP = 20


def cell(sheet: Image.Image, index: int) -> Image.Image:
    return sheet.crop((index * FW, 0, (index + 1) * FW, FH))


def crouch_punch(sheet: Image.Image) -> Image.Image:
    frame = cell(sheet, CROUCH_FRAME)
    arm = cell(sheet, PUNCH_FRAME).crop(PUNCH_ARM_BOX)
    out = frame.copy()
    out.paste(arm, (PUNCH_ARM_BOX[0], PUNCH_ARM_BOX[1] + CROUCH_DROP), arm)
    return out


def rotate_crouch(sheet: Image.Image, step: int) -> Image.Image:
    tuck = cell(sheet, CROUCH_FRAME)
    bbox = tuck.getbbox()
    if bbox is None:
        raise SystemExit("crouch frame is empty — is the sheet built?")
    ball = tuck.crop(bbox)
    spun = ball.rotate(
        -360.0 * step / SPIN_STEPS, resample=Image.NEAREST, expand=True
    )
    out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    out.paste(
        spun,
        (SPIN_CENTER[0] - spun.width // 2, SPIN_CENTER[1] - spun.height // 2),
        spun,
    )
    return out


def shift_down(frame: Image.Image, dy: int) -> Image.Image:
    out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    out.paste(frame, (0, dy), frame)
    return out


def load_original_somersaults() -> list[Image.Image] | None:
    frames: list[Image.Image] = []
    for i in range(1, 5):
        path = RIPPED_S2 / f"nina_somersault_{i}.png"
        if not path.exists():
            return None
        img = Image.open(path).convert("RGBA")
        if img.size != (FW, FH):
            img = img.resize((FW, FH), Image.NEAREST)
        frames.append(img)
    return frames


def build(sheet: Image.Image) -> Image.Image:
    frames = [crouch_punch(sheet)]
    original = load_original_somersaults()
    if original is not None:
        frames += original
        frames += [shift_down(f, FLOOR_DROP) for f in original]
    else:
        spun = [rotate_crouch(sheet, step) for step in range(SPIN_STEPS)]
        frames += spun
    out = Image.new("RGBA", (FW * len(frames), FH), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        out.paste(frame, (i * FW, 0), frame)
    return out


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Need {SRC} — run build_saboteur93_player.py first")
    sheet = Image.open(SRC).convert("RGBA")
    if sheet.height != FH or sheet.width < (CROUCH_FRAME + 1) * FW:
        raise SystemExit(f"{SRC} is not a {FW}x{FH} sheet with a crouch frame")
    out = build(sheet)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT)
    src = "original SOM1C–SOM4C" if load_original_somersaults() else "rotated crouch fallback"
    print(f"Wrote {OUT} ({out.width}x{out.height}, {out.width // FW} frames, {src})")


if __name__ == "__main__":
    main()
