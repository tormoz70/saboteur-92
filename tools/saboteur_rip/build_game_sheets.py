#!/usr/bin/env python3
"""Build in-game sprite sheets from ripped original Saboteur frames."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RIPPED = ROOT / "assets" / "reference" / "original" / "ripped"
OUT = ROOT / "assets" / "sprites"

# Original Saboteur character: 48x56 px (ripped PNGs are 2x at 96x112).
FW, FH = 48, 56


def load_frame(prefix: str, name: str) -> Image.Image:
    path = RIPPED / f"{prefix}_{name}.png"
    if not path.exists():
        raise FileNotFoundError(path)
    img = Image.open(path).convert("RGBA")
    if img.size != (FW, FH):
        img = img.resize((FW, FH), Image.NEAREST)
    return img


def build_sheet(prefix: str, names: list[str]) -> Image.Image:
    frames = [load_frame(prefix, n) for n in names]
    sheet = Image.new("RGBA", (FW * len(frames), FH), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * FW, 0), frame)
    return sheet


def main() -> None:
    if not RIPPED.exists():
        raise SystemExit(f"Missing ripped sprites: {RIPPED}")

    player_names = [
        "standing",
        "standing",
        "walk_1",
        "walk_2",
        "walk_3",
        "walk_4",
        "jump",
        "punch",
        "jump_kick",
        "ladder",
        "ladder",
        "dead",
    ]
    guard_names = [
        "standing",
        "standing",
        "walk_1",
        "walk_2",
        "walk_3",
        "walk_4",
        "punch",
    ]

    player = build_sheet("ninja", player_names)
    guard = build_sheet("guard", guard_names)

    OUT.mkdir(parents=True, exist_ok=True)
    player_path = OUT / "saboteur85_player.png"
    guard_path = OUT / "saboteur85_guard.png"
    player.save(player_path)
    guard.save(guard_path)
    print(f"Wrote {player_path} ({player.size[0]}x{player.size[1]})")
    print(f"Wrote {guard_path} ({guard.size[0]}x{guard.size[1]})")


if __name__ == "__main__":
    main()
