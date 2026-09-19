"""Reach report + overlay after the capability bump."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw
from labyrinth import Labyrinth, feet_cell

OUT = ROOT / "docs" / "audit_views" / "playability"


def main() -> None:
    lab = Labyrinth()
    sr = sum(1 for p in lab.stand if p in lab.reached)
    cr = sum(1 for p in lab.climb_cells if p in lab.reached)
    print(
        f"stand={len(lab.stand)} stand_reached={sr} ({100.0*sr/max(1,len(lab.stand)):.1f}%) "
        f"climb={len(lab.climb_cells)} climb_reached={cr} reached={len(lab.reached)}"
    )
    r = lab.report()
    print("geometry", r["geometry_reached"], "geo_miss", r["geometry_unreachable_points"])
    print("unreachable points", r["unreachable_points"])
    print("unreachable lifts", len(r["unreachable_lifts"]), "ladders", len(r["unreachable_ladders"]), "of", r["ladders"])
    print("blocked screens", r["blocked_screens"])

    points = {
        "spawn": tuple(lab.entities["spawn"]),
        "exit": (lab.entities["exit"]["x"], lab.entities["exit"]["y"]),
        "sabotage": (lab.entities["sabotage"]["x"], lab.entities["sabotage"]["y"]),
        **{str(i.get("id", i.get("type"))): (i["x"], i["y"]) for i in lab.entities.get("items", [])},
    }
    for name, xy in points.items():
        fx, fy = feet_cell(float(xy[0]), float(xy[1]))
        print(
            f"  {name:10} feet=({fx:4d},{fy:3d}) drop={lab._drop(fx, fy)} "
            f"ok={lab.origin_reachable(xy[0], xy[1])}"
        )

    fan = Image.open(ROOT / "assets" / "world" / "saboteur2_world2.png").convert("RGB")
    ov = Image.new("RGBA", (lab.cw, lab.ch), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    for x, y in lab.reached:
        dr.point((x, y), fill=(0, 255, 0, 255))
    base = fan.resize((lab.cw, lab.ch), Image.NEAREST).convert("RGBA")
    comp = Image.alpha_composite(base, ov).convert("RGB")
    comp = comp.resize((lab.cw * 2, lab.ch * 2), Image.NEAREST)
    OUT.mkdir(parents=True, exist_ok=True)
    comp.save(OUT / "reached_fullmap.png")
    print("wrote", OUT / "reached_fullmap.png")

    # exit crop
    ex, ey = feet_cell(640, 3092)
    x0, y0, x1, y1 = ex - 20, ey - 12, ex + 20, ey + 12
    crop = fan.crop((x0 * 8, y0 * 8, x1 * 8, y1 * 8)).convert("RGBA")
    ov2 = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    d2 = ImageDraw.Draw(ov2)
    for cy in range(y0, y1):
        for cx in range(x0, x1):
            rx, ry = (cx - x0) * 8, (cy - y0) * 8
            if (cx, cy) in lab.reached:
                d2.rectangle([rx, ry, rx + 7, ry + 7], fill=(0, 255, 0, 90))
            if lab.solid[cy][cx]:
                d2.rectangle([rx, ry, rx + 7, ry + 7], outline=(255, 0, 0, 180))
            elif (cx, cy) in lab.stand and (cx, cy) not in lab.reached:
                d2.rectangle([rx, ry, rx + 7, ry + 7], outline=(0, 255, 255, 255))
    d2.rectangle(
        [(ex - x0) * 8 - 2, (ey - y0) * 8 - 2, (ex - x0) * 8 + 9, (ey - y0) * 8 + 9],
        outline=(255, 255, 0, 255),
        width=2,
    )
    out = Image.alpha_composite(crop, ov2).convert("RGB")
    out = out.resize((out.width * 3, out.height * 3), Image.NEAREST)
    out.save(OUT / "exit_area.png")
    print("wrote", OUT / "exit_area.png")


if __name__ == "__main__":
    main()
