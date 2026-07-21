#!/usr/bin/env python3
"""Build 4-frame run sheet from reference ninja + ripped walk cycle."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RIPPED = ROOT / "assets" / "reference" / "original" / "ripped"
REF = (
    ROOT
    / "assets"
    / "sprites"
    / "ref"
    / "ninja_idle_ref.png"
)
OUT = ROOT / "assets" / "sprites" / "saboteur93_ninja_run4.png"

FW, FH = 48, 56
WALK = ["walk_1", "walk_2", "walk_3", "walk_4"]

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)


def load_ref(path: Path) -> Image.Image:
    if path.exists():
        return Image.open(path).convert("RGBA")
    raise FileNotFoundError(path)


def to_silhouette(img: Image.Image) -> Image.Image:
    """Map ripped frame to black body + white accents (eyes, belt, boots)."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    px = img.load()
    op = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 64:
                continue
            lum = (r + g + b) / 3
            # skin / belt / boot highlights in ripped art
            if lum > 150 or (r > 180 and g > 120):
                op[x, y] = WHITE
            else:
                op[x, y] = BLACK
    return out


def content_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    px = img.load()
    w, h = img.size
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 64:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        return 0, 0, w - 1, h - 1
    return min_x, min_y, max_x, max_y


def fit_frame(src: Image.Image, target_h: int = 54, baseline: int = 55) -> Image.Image:
    """Scale sprite to target height, align feet to baseline inside FW×FH cell."""
    cell = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    bbox = content_bbox(src)
    cropped = src.crop(bbox)
    cw, ch = cropped.size
    if ch == 0:
        return cell
    scale = target_h / ch
    nw = max(1, int(cw * scale))
    nh = max(1, int(ch * scale))
    scaled = cropped.resize((nw, nh), Image.NEAREST)
    # center horizontally, feet on baseline
    ox = (FW - nw) // 2
    oy = baseline - nh
    cell.paste(scaled, (ox, oy), scaled)
    return cell


def apply_ref_head_band(ref: Image.Image, frame: Image.Image) -> Image.Image:
    """Copy white accent pixels from reference upper body onto run frame."""
    ref_px = ref.load()
    fr = frame.copy()
    fp = fr.load()
    rw, rh = ref.size
    # reference white pixels in top 55% -> template for mask/eye/belt top
    ref_whites: list[tuple[int, int]] = []
    for y in range(int(rh * 0.55)):
        for x in range(rw):
            if ref_px[x, y] == WHITE:
                ref_whites.append((x, y))
    if not ref_whites:
        return frame

    fb = content_bbox(frame)
    fx0, fy0, fx1, fy1 = fb
    fh = fy1 - fy0 + 1
    fw = fx1 - fx0 + 1
    rb = content_bbox(ref)
    rx0, ry0, rx1, ry1 = rb
    rh_body = ry1 - ry0 + 1
    rw_body = rx1 - rx0 + 1

    for rx, ry in ref_whites:
        if ry < ry0 or ry > ry0 + int(rh_body * 0.45):
            continue
        nx = fx0 + int((rx - rx0) * fw / max(1, rw_body))
        ny = fy0 + int((ry - ry0) * min(fh, rh_body) / max(1, rh_body))
        if 0 <= nx < FW and 0 <= ny < FH and fp[nx, ny][3] > 64:
            fp[nx, ny] = WHITE
    return fr


def build_run_sheet(ref_path: Path, out_path: Path) -> Image.Image:
    ref_raw = load_ref(ref_path)
    ref_fit = fit_frame(to_silhouette(ref_raw.resize((FW, FH), Image.NEAREST)))

    frames: list[Image.Image] = []
    for name in WALK:
        path = RIPPED / f"ninja_{name}.png"
        if not path.exists():
            raise FileNotFoundError(path)
        walk = Image.open(path).convert("RGBA").resize((FW, FH), Image.NEAREST)
        sil = to_silhouette(walk)
        sil = fit_frame(sil, target_h=content_bbox(ref_fit)[3] - content_bbox(ref_fit)[1] + 1)
        sil = apply_ref_head_band(ref_fit, sil)
        frames.append(sil)

    sheet = Image.new("RGBA", (FW * len(frames), FH), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        sheet.paste(fr, (i * FW, 0), fr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return sheet


def main() -> None:
    sheet = build_run_sheet(REF, OUT)
    print(f"Wrote {OUT} ({sheet.size[0]}x{sheet.size[1]})")


if __name__ == "__main__":
    main()
