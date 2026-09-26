#!/usr/bin/env python3
"""CI check: white metal beams follow the collision rule.

User's rule: a white metal beam is solid only when it lies horizontally —
heroes and guards walk on it. Vertical and diagonal beams are background;
heroes pass through them.

Beams are drawn on the `interior1` / `interior2` layers with the tiles listed
below (atlas coords in `s2_interior_tileset`). For every chunk cell:

- a horizontal-beam tile must sit on `solid` collision;
- a vertical / diagonal beam tile must not sit on `solid` or `oneway`.

Reads `assets/world/chunks_json`, so run `tools/export_chunks_to_json.py`
after editing the `.tscn` chunks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_JSON = ROOT / "assets" / "world" / "chunks_json"
ID_MAP = ROOT / "assets" / "tilesets" / "tile_id_map.json"
CELL = 8
CHUNK_W, CHUNK_H = 128, 72
BEAM_LAYERS = ("interior1", "interior2")
TRANSPOSE = 16384

HORIZONTAL_BEAMS = {(13, 0)}
BACKGROUND_BEAMS = {
	(21, 0),  # vertical lattice
	(9, 2),  # mast top joint
	(25, 2),
	(27, 2),
	(3, 3),
	(6, 3),
	(12, 3),
	(15, 3),
	(16, 3),
}
VERTICAL_BEAMS = {(21, 0)}


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


def _beam_kind(tile: list[int]) -> str | None:
	_src, ax, ay, alt = tile
	key = (ax, ay)
	transposed = bool(alt & TRANSPOSE)
	if key in HORIZONTAL_BEAMS:
		return "background" if transposed else "horizontal"
	if key in BACKGROUND_BEAMS:
		if transposed and key in VERTICAL_BEAMS:
			return "horizontal"
		return "background"
	return None


def main() -> int:
	id_map = json.loads(ID_MAP.read_text(encoding="utf-8"))
	interior = id_map["palettes"]["s2_interior_tileset"]["tiles"]
	col_pal = id_map["palettes"]["s2_collision_tileset"]
	col_types = col_pal["collision_types"]
	kinds = {i: _beam_kind(t) for i, t in enumerate(interior)}

	errors: list[str] = []
	counts = {"horizontal": 0, "background": 0}
	for path in sorted(CHUNKS_JSON.glob("chunk_*.json")):
		chunk = json.loads(path.read_text(encoding="utf-8"))
		w, h = chunk["grid_size"]
		layers = chunk["layers"]
		cx, cy = int(path.stem[6:8]), int(path.stem[9:11])
		col = _decode(layers["collision"], w, h) if "collision" in layers else [-1] * (w * h)
		for name in BEAM_LAYERS:
			if name not in layers:
				continue
			for i, tid in enumerate(_decode(layers[name], w, h)):
				kind = kinds.get(tid) if tid >= 0 else None
				if kind is None:
					continue
				counts[kind] += 1
				c = col[i]
				ctype = col_types[c] if c >= 0 else "empty"
				x = (cx * CHUNK_W + i % w) * CELL
				y = (cy * CHUNK_H + i // w) * CELL
				if kind == "horizontal" and ctype != "solid":
					errors.append(
						f"{path.stem} {name}: horizontal beam at png ({x}, {y}) "
						f"has '{ctype}' collision, expected 'solid'"
					)
				elif kind == "background" and ctype in ("solid", "oneway"):
					errors.append(
						f"{path.stem} {name}: vertical/diagonal beam at png ({x}, {y}) "
						f"has '{ctype}' collision, expected none"
					)

	print(
		f"beams: horizontal={counts['horizontal']} vertical/diagonal={counts['background']}"
	)
	if errors:
		print(f"check_beams: {len(errors)} error(s)")
		for e in errors[:50]:
			print(f"  {e}")
		return 1
	print("check_beams: OK")
	return 0


if __name__ == "__main__":
	sys.exit(main())
