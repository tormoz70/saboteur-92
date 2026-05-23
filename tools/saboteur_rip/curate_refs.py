#!/usr/bin/env python3
"""Pick humanoid-looking monochrome sprites from extracted PNGs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "reference" / "original" / "extracted" / "split"
OUT = ROOT / "assets" / "reference" / "original" / "curated"


def row_widths(img: Image.Image) -> list[int]:
    px = img.load()
    w, h = img.size
    return [sum(1 for x in range(w) if px[x, y][3] > 0) for y in range(h)]


def humanoid_score(img: Image.Image) -> float:
    widths = row_widths(img)
    active = [w for w in widths if w > 0]
    if len(active) < 18 or len(active) > 46:
        return 0.0
    if max(widths) > 14 or max(widths) < 4:
        return 0.0
    top = sum(widths[:8])
    mid = sum(widths[8:28])
    bot = sum(widths[28:])
    if top == 0 or mid == 0 or bot == 0:
        return 0.0
    # Prefer head narrower than body, feet narrower than body
    head = max(widths[:10])
    body = max(widths[10:34])
    feet = max(widths[34:])
    if not (head <= body and feet <= body):
        return 0.0
    fill = sum(active) / (img.width * img.height)
    if fill < 0.12 or fill > 0.55:
        return 0.0
    return fill * (body / img.width)


def upscale(img: Image.Image, scale: int = 4) -> Image.Image:
    w, h = img.size
    out = Image.new("RGBA", (w * scale, h * scale), (32, 32, 48, 255))
    px = img.load()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if px[x, y][3]:
                for dy in range(scale):
                    for dx in range(scale):
                        op[x * scale + dx, y * scale + dy] = (0, 0, 0, 255)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ranked: list[tuple[float, Path, Image.Image]] = []
    for path in sorted(SRC.glob("*.png")):
        img = Image.open(path).convert("RGBA")
        s = humanoid_score(img)
        if s > 0:
            ranked.append((s, path, img))
    ranked.sort(key=lambda t: t[0], reverse=True)
    lines = ["# Curated humanoid candidates", ""]
    for i, (score, path, img) in enumerate(ranked[:16]):
        up = upscale(img)
        dst = OUT / f"ref_{i:02d}_{path.stem}.png"
        up.save(dst)
        lines.append(f"- score={score:.3f} from {path.name} -> {dst.name}")
        ascii_lines = []
        px = img.load()
        for y in range(img.height):
            if any(px[x, y][3] for x in range(img.width)):
                ascii_lines.append("".join("#" if px[x, y][3] else "." for x in range(img.width)))
        lines.append("```")
        lines.extend(ascii_lines[:24])
        lines.append("```")
        lines.append("")
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Curated {min(len(ranked), 16)} refs into {OUT}")


if __name__ == "__main__":
    main()
