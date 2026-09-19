"""Geometry gate for the S2ROOM bytecode decoder.

verify_mosaic()'s 0.58 is a *render* match — it counts every glyph and colour
difference. The plan only needs correct rectangles. This gate compares the
decoder's solid rectangles against a reference solid mask derived from the
pixel-perfect fan map (structure cells + rock black-regions), so we score
geometry, not pixels.

Reference model per 8x8 cell:
  solid     = structure (non-black, non-sky) OR black cell in a rock region
  walkable  = sky OR black cell in an air region

Reports precision / recall / F1 and the sky-violation rate (decoder solid on
sky is unambiguously wrong), then writes s2_decoder_geometry.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from build_air_regions import cell_classes

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "assets" / "world" / "saboteur2_world2.png"
AIR = ROOT / "assets" / "world" / "s2_air_regions.json"
COLLISION = ROOT / "assets" / "world" / "s2_collision.json"
OUT = ROOT / "assets" / "world" / "s2_decoder_geometry.json"

CELL = 8


def build_reference(cls: np.ndarray, air: dict) -> np.ndarray:
    """solid mask: structure cells + black cells that belong to rock regions."""
    ch, cw = cls.shape
    rock = np.zeros((ch, cw), dtype=bool)
    for region in air["regions"]:
        if region["kind"] != "rock":
            continue
        for x, y in region["cells"]:
            rock[y, x] = True
    structure = cls == 0
    return structure | rock


def rasterize_solids(collision: dict, cw: int, ch: int) -> np.ndarray:
    mask = np.zeros((ch, cw), dtype=bool)
    for x, y, w, h in collision["solids"]:
        x0 = max(0, x // CELL)
        y0 = max(0, y // CELL)
        x1 = min(cw, (x + w + CELL - 1) // CELL)
        y1 = min(ch, (y + h + CELL - 1) // CELL)
        mask[y0:y1, x0:x1] = True
    return mask


def main() -> None:
    img = np.array(Image.open(WORLD).convert("RGB"))
    cls, cw, ch = cell_classes(img)
    air = json.loads(AIR.read_text(encoding="utf-8"))
    collision = json.loads(COLLISION.read_text(encoding="utf-8"))

    ref_solid = build_reference(cls, air)
    dec_solid = rasterize_solids(collision, cw, ch)
    sky = cls == 2

    inter = int((dec_solid & ref_solid).sum())
    dec_n = int(dec_solid.sum())
    ref_n = int(ref_solid.sum())
    precision = inter / dec_n if dec_n else 0.0
    recall = inter / ref_n if ref_n else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    sky_violation = int((dec_solid & sky).sum())
    sky_rate = sky_violation / dec_n if dec_n else 0.0

    report = {
        "decoder_solid_cells": dec_n,
        "reference_solid_cells": ref_n,
        "intersection": inter,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "sky_violation_cells": sky_violation,
        "sky_violation_rate": round(sky_rate, 4),
        "note": (
            "recall is bounded above because the decoder marks structural "
            "floors/walls, not the bulk earth mass; the fan-map reference "
            "(structure + rock) is the complete solid source."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
