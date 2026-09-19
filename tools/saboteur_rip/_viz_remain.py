"""Show remaining unreached floors and wide context crops for open blocks."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw
from labyrinth import Labyrinth, CELL

OUT = ROOT / "docs" / "audit_views" / "playability"


def clusters(cells: set[tuple[int, int]], gap: int = 8) -> list[list[tuple[int, int]]]:
    """Group nearby unreached standable cells into bbox-clusters."""
    remaining = set(cells)
    groups: list[list[tuple[int, int]]] = []
    while remaining:
        seed = remaining.pop()
        box = [seed]
        qx = [seed]
        while qx:
            x, y = qx.pop()
            for p in list(remaining):
                if abs(p[0] - x) <= gap and abs(p[1] - y) <= gap:
                    remaining.remove(p)
                    box.append(p)
                    qx.append(p)
        groups.append(box)
    groups.sort(key=len, reverse=True)
    return groups


def crop_overlay(
    fan: Image.Image,
    lab: Labyrinth,
    unreached: set[tuple[int, int]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    path: Path,
    scale: int = 3,
    title: str | None = None,
) -> None:
    crop = fan.crop((x0 * CELL, y0 * CELL, x1 * CELL, y1 * CELL)).convert("RGBA")
    ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    for cy in range(y0, y1):
        for cx in range(x0, x1):
            rx, ry = (cx - x0) * CELL, (cy - y0) * CELL
            if (cx, cy) in lab.reached:
                dr.rectangle([rx, ry, rx + 7, ry + 7], fill=(0, 255, 0, 60))
            if lab.solid[cy][cx]:
                dr.rectangle([rx, ry, rx + 7, ry + 7], outline=(255, 0, 0, 140))
            elif (cx, cy) in unreached:
                dr.rectangle(
                    [rx, ry, rx + 7, ry + 7],
                    fill=(255, 0, 220, 170),
                    outline=(0, 220, 255, 255),
                )
            elif lab.rope[cy][cx]:
                dr.rectangle([rx, ry, rx + 7, ry + 7], fill=(255, 140, 0, 120))
    if title:
        dr.text((4, 4), title, fill=(255, 255, 0, 255))
    out = Image.alpha_composite(crop, ov).convert("RGB")
    out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)
    print("wrote", path, out.size)


def _write_problem_views(fan: Image.Image, lab: Labyrinth, unreached: set[tuple[int, int]]) -> None:
    """Crops a human can actually read: magenta = floor BFS still cannot stand on."""
    problems = [
        ("remain_here.png", 70, 170, 180, 270, 3, "west warehouse — isolated"),
        ("remain_cave_gap.png", 95, 228, 130, 290, 4, "shaft under warehouse"),
        ("remain_east.png", 790, 115, 860, 190, 3, "east rooms"),
    ]
    climb_miss = {p for p in lab.climb_cells if p not in lab.reached}
    for name, x0, y0, x1, y1, scale, _title in problems:
        crop = fan.crop((x0 * CELL, y0 * CELL, x1 * CELL, y1 * CELL)).convert("RGBA")
        ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                rx, ry = (cx - x0) * CELL, (cy - y0) * CELL
                if (cx, cy) in unreached:
                    dr.rectangle([rx, ry, rx + 7, ry + 7], fill=(255, 0, 220, 160))
                elif (cx, cy) in climb_miss:
                    dr.rectangle([rx, ry, rx + 7, ry + 7], fill=(255, 180, 0, 150))
        out = Image.alpha_composite(crop, ov).convert("RGB")
        out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
        path = OUT / name
        out.save(path)
        print("wrote", path, out.size)

    q = 4
    overview = fan.resize((fan.width // q, fan.height // q), Image.NEAREST).convert("RGB")
    dr = ImageDraw.Draw(overview)
    groups = clusters(unreached, gap=12)
    for n, g in enumerate(groups[:8]):
        xs = [p[0] for p in g]
        ys = [p[1] for p in g]
        pad = 8
        x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
        x1, y1 = min(lab.cw, max(xs) + pad + 1), min(lab.ch, max(ys) + pad + 1)
        box = [x0 * CELL // q, y0 * CELL // q, x1 * CELL // q, y1 * CELL // q]
        dr.rectangle(box, outline=(255, 255, 0), width=3)
        dr.text((box[0] + 4, box[1] + 4), str(n), fill=(255, 255, 0))
    path = OUT / "remain_map.png"
    overview.save(path)
    print("wrote", path, overview.size)


def main() -> None:
    lab = Labyrinth()
    unreached = {p for p in lab.stand if p not in lab.reached}
    print("unreached standable", len(unreached))
    groups = clusters(unreached, gap=12)
    print("clusters", len(groups), "top sizes", [len(g) for g in groups[:8]])

    fan = Image.open(ROOT / "assets" / "world" / "saboteur2_world2.png").convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("remain_cluster_*.png"):
        stale.unlink()

    ov = Image.new("RGBA", (lab.cw, lab.ch), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    for x, y in lab.reached:
        dr.point((x, y), fill=(0, 255, 0, 255))
    for x, y in unreached:
        dr.point((x, y), fill=(0, 220, 255, 255))
    base = fan.resize((lab.cw, lab.ch), Image.NEAREST).convert("RGBA")
    comp = Image.alpha_composite(base, ov).convert("RGB")
    comp = comp.resize((lab.cw * 2, lab.ch * 2), Image.NEAREST)
    comp.save(OUT / "remain_fullmap.png")
    print("wrote", OUT / "remain_fullmap.png")

    named = [
        ("remain_block2.png", 470, 8, 610, 88, 2, "2 roof towers"),
        ("remain_block3.png", 478, 88, 620, 230, 2, "3 east facade"),
    ]
    for name, x0, y0, x1, y1, scale, title in named:
        crop_overlay(fan, lab, unreached, x0, y0, x1, y1, OUT / name, scale, title)

    for i, g in enumerate(groups[:8]):
        xs = [p[0] for p in g]
        ys = [p[1] for p in g]
        tiny = len(g) <= 2
        pad = 6 if tiny else 14
        x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
        x1, y1 = min(lab.cw, max(xs) + pad + 1), min(lab.ch, max(ys) + pad + 1)
        sc = 8 if tiny else (4 if (x1 - x0) < 50 else 3)
        crop_overlay(
            fan,
            lab,
            unreached,
            x0,
            y0,
            x1,
            y1,
            OUT / f"remain_cluster_{i}.png",
            sc,
            f"cluster {i} n={len(g)}",
        )

    _write_problem_views(fan.convert("RGB"), lab, unreached)


if __name__ == "__main__":
    main()
