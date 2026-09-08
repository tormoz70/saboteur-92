#!/usr/bin/env python3
"""Build saboteur93_player_moves.png — crouch punch plus somersault spin.

Both poses are derived from saboteur93_player.png so they keep the exact
silhouette, palette and 48x56 cell of the sheet the player scene already uses:

- crouch punch: the crouch pose with the standing punch's arm grafted on at
  crouch shoulder height.
- somersault / floor roll: original crouch (K47212) is the tucked embryo
  pose. Rotate that ball in 45 degree steps for a right-facing flip (the
  scene mirrors it for left) and for SW/SE rolls on the floor.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "sprites" / "saboteur93_player.png"
OUT = ROOT / "assets" / "sprites" / "saboteur93_player_moves.png"

FW, FH = 48, 56

IDLE_FRAME = 0
PUNCH_FRAME = 6
CROUCH_FRAME = 12

# Punch arm inside the standing frame, and how far down the crouch drops the
# shoulders (crouch head top 25 vs idle head top 9).
PUNCH_ARM_BOX = (24, 17, 45, 21)
CROUCH_DROP = 16

SPIN_STEPS = 8
# Sprites are drawn from the cell's top-left corner, and the standing body box
# spans y 14..56 of the cell, so the tumbling ball spins about its middle.
SPIN_CENTER = (24, 34)


def cell(sheet: Image.Image, index: int) -> Image.Image:
    return sheet.crop((index * FW, 0, (index + 1) * FW, FH))


def crouch_punch(sheet: Image.Image) -> Image.Image:
    frame = cell(sheet, CROUCH_FRAME)
    arm = cell(sheet, PUNCH_FRAME).crop(PUNCH_ARM_BOX)
    out = frame.copy()
    out.paste(arm, (PUNCH_ARM_BOX[0], PUNCH_ARM_BOX[1] + CROUCH_DROP), arm)
    return out


def somersault(sheet: Image.Image, step: int) -> Image.Image:
    tuck = cell(sheet, CROUCH_FRAME)
    bbox = tuck.getbbox()
    if bbox is None:
        raise SystemExit("crouch frame is empty — is the sheet built?")
    ball = tuck.crop(bbox)
    # Negative angle so the tumble runs head-forward for a right-facing flip.
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


def build(sheet: Image.Image) -> Image.Image:
    frames = [crouch_punch(sheet)]
    frames += [somersault(sheet, step) for step in range(SPIN_STEPS)]
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
    print(f"Wrote {OUT} ({out.width}x{out.height}, {out.width // FW} frames)")


if __name__ == "__main__":
    main()
