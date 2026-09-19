"""Connected-component markup of the pure-black cells in the fan map.

Pure-black 8x8 cells are ambiguous: solid rock (earth fill) and passable air
(room / tunnel interiors) look identical pixel-for-pixel. The brick lining
around rooms physically separates the two, so each 4-connected component of
black cells is entirely rock or entirely air. This script finds those
components, proposes a classification, and writes a check-in table that a
human verifies once — instead of 25 morphological passes.

Output: assets/world/s2_air_regions.json
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "assets" / "world" / "saboteur2_world2.png"
OUT = ROOT / "assets" / "world" / "s2_air_regions.json"

CELL = 8
BLACK = (0, 0, 0)
SKY = (0, 0, 206)


def cell_classes(img: np.ndarray) -> tuple[np.ndarray, int, int]:
    """0 = structure/other, 1 = pure black, 2 = sky. Per 8x8 cell."""
    h, w, _ = img.shape
    cw, ch = w // CELL, h // CELL
    cls = np.zeros((ch, cw), dtype=np.uint8)
    for cy in range(ch):
        for cx in range(cw):
            block = img[cy * CELL : (cy + 1) * CELL, cx * CELL : (cx + 1) * CELL]
            flat = block.reshape(-1, 3)
            if (flat == SKY).all(axis=1).all():
                cls[cy, cx] = 2
            elif (flat == BLACK).all(axis=1).all():
                cls[cy, cx] = 1
    return cls, cw, ch


def components(cls: np.ndarray, cw: int, ch: int) -> list[dict]:
    """4-connected components over the pure-black cells."""
    seen = np.zeros((ch, cw), dtype=bool)
    regions: list[dict] = []
    for sy in range(ch):
        for sx in range(cw):
            if cls[sy, sx] != 1 or seen[sy, sx]:
                continue
            cells: list[tuple[int, int]] = []
            q = deque([(sx, sy)])
            seen[sy, sx] = True
            minx = maxx = sx
            miny = maxy = sy
            touches_border = False
            while q:
                x, y = q.popleft()
                cells.append((x, y))
                minx = min(minx, x)
                maxx = max(maxx, x)
                miny = min(miny, y)
                maxy = max(maxy, y)
                if x == 0 or y == 0 or x == cw - 1 or y == ch - 1:
                    touches_border = True
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < cw and 0 <= ny < ch and not seen[ny, nx] and cls[ny, nx] == 1:
                        seen[ny, nx] = True
                        q.append((nx, ny))
            regions.append(
                {
                    "cells": cells,
                    "count": len(cells),
                    "bbox": [minx, miny, maxx - minx + 1, maxy - miny + 1],
                    "touches_border": touches_border,
                }
            )
    return regions


def classify(region: dict, cw: int, ch: int) -> str:
    """Heuristic draft, verified by eye once.

    The ground mass is the large black body that reaches the map edge below
    the sky; room / tunnel air is enclosed by brick and never touches the
    outer border. Large interior voids are air; tiny sealed pockets are rock.
    """
    if region["touches_border"]:
        return "rock"
    if region["count"] >= 40:
        return "air"
    return "rock"


def main() -> None:
    img = np.array(Image.open(WORLD).convert("RGB"))
    cls, cw, ch = cell_classes(img)
    regions = components(cls, cw, ch)
    regions.sort(key=lambda r: -r["count"])
    black_total = sum(r["count"] for r in regions)
    out_regions = []
    for i, r in enumerate(regions):
        out_regions.append(
            {
                "id": i,
                "kind": classify(r, cw, ch),
                "count": r["count"],
                "bbox": r["bbox"],
                "touches_border": r["touches_border"],
                "cells": [[x, y] for x, y in r["cells"]],
            }
        )
    doc = {
        "source": "connected components of pure-black cells in saboteur2_world2.png",
        "cell": CELL,
        "grid": [cw, ch],
        "black_cells": black_total,
        "region_count": len(out_regions),
        "regions": out_regions,
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    big = [r for r in out_regions if r["count"] >= 40]
    big_cells = sum(r["count"] for r in big)
    air = [r for r in out_regions if r["kind"] == "air"]
    print(f"grid={cw}x{ch} black_cells={black_total} regions={len(out_regions)}")
    print(
        f"large(>=40)={len(big)} holding {big_cells} cells "
        f"({100.0 * big_cells / max(1, black_total):.1f}%)"
    )
    print(f"air={len(air)} rock={len(out_regions) - len(air)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
