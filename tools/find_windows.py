#!/usr/bin/env python3
"""Find the window holes in the world map for the skyline view behind them.

A window is a small pocket of cells that no visual layer covers, closed in
by the wall. Through it the level's backdrop shows; WorldLook hangs a slice
of the city skyline in each one. Open sky is one big region and is left to
the skyline strip.

Reads `assets/world/chunks_json`, so run `tools/export_chunks_to_json.py`
after editing the `.tscn` chunks.

    python tools/find_windows.py            # write assets/world/s2_windows.json
    python tools/find_windows.py --check    # exit 1 if the file is stale
"""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_JSON = ROOT / "assets" / "world" / "chunks_json"
OUT = ROOT / "assets" / "world" / "s2_windows.json"
CELL = 8
CHUNK_W, CHUNK_H = 128, 72
GRID_W, GRID_H = CHUNK_W * 8, CHUNK_H * 8
# Bigger pockets are rooms open to the sky or shafts, not windows.
MAX_CELLS = 16


def _decode(layer: dict, w: int, h: int) -> list[int]:
    data = layer["data"]
    if layer.get("encoding") == "grid":
        return [v for row in data for v in row]
    out: list[int] = []
    for i in range(0, len(data), 2):
        out.extend([data[i]] * data[i + 1])
    if len(out) != w * h:
        raise SystemExit(f"bad rle payload: {len(out)} cells, expected {w * h}")
    return out


def _covered() -> list[bytearray]:
    grid = [bytearray(GRID_W) for _ in range(GRID_H)]
    for path in sorted(CHUNKS_JSON.glob("chunk_*.json")):
        chunk = json.loads(path.read_text(encoding="utf-8"))
        cx, cy = (int(v) for v in path.stem.split("_")[1:3])
        w, h = chunk["grid_size"]
        empty = chunk.get("empty_id", -1)
        for name, layer in chunk["layers"].items():
            if name == "collision":
                continue
            ids = _decode(layer, w, h)
            for y in range(h):
                row = grid[cy * h + y]
                base = cx * w
                for x in range(w):
                    if ids[y * w + x] != empty:
                        row[base + x] = 1
    return grid


def find_windows() -> list[list[int]]:
    grid = _covered()
    seen = [bytearray(GRID_W) for _ in range(GRID_H)]
    windows: list[list[int]] = []
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] or seen[y][x]:
                continue
            seen[y][x] = 1
            queue = deque([(x, y)])
            x0 = x1 = x
            y0 = y1 = y
            edge = False
            while queue:
                px, py = queue.popleft()
                x0, x1, y0, y1 = min(x0, px), max(x1, px), min(y0, py), max(y1, py)
                edge |= px in (0, GRID_W - 1) or py in (0, GRID_H - 1)
                for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H and not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = 1
                        queue.append((nx, ny))
            w, h = x1 - x0 + 1, y1 - y0 + 1
            if not edge and w <= MAX_CELLS and h <= MAX_CELLS:
                windows.append([x0 * CELL, y0 * CELL, w * CELL, h * CELL])
    return windows


def main() -> int:
    windows = find_windows()
    text = json.dumps(
        {"note": "native px [x, y, w, h]; see tools/find_windows.py", "windows": windows},
        separators=(",", ":"),
    ) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT).as_posix()} is stale: run tools/find_windows.py")
            return 1
        print(f"OK: {len(windows)} windows")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(windows)} windows -> {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
