#!/usr/bin/env python3
"""Rebuild the CollisionLayer around the three lift tubes of the fan map.

The fan map has three lifts: a tube between two cyan rails, a floor station at
the top where the rails start and one at the bottom. The rip read the rails as
ladders, left the tube open to fall into, and marked "lift shaft" cells
(alt 1) along columns shifted 256 px from the real tubes. This script:

- turns every alt 1 cell back into plain rock;
- turns the rail ladder cells of each tube into rock (the tube walls);
- clears the tube cells on each top station row: the parked cabin is the
  floor there, and with the cabin away Nina drops down the shaft.

Lift positions come from `lifts` in assets/world/s2_collision.json.

    python tools/explore/patch_lift_collision.py
"""
from __future__ import annotations

import base64
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "scenes" / "world" / "chunks"
COLLISION = ROOT / "assets" / "world" / "s2_collision.json"
CELL = 8
CHUNK_W, CHUNK_H = 128, 72
SOLID, LADDER = 1, 2
SHAFT_ALT = 1


def _decode(raw: bytes) -> dict[tuple[int, int], list[int]]:
	cells: dict[tuple[int, int], list[int]] = {}
	body = raw[2:]
	for k in range(len(body) // 12):
		x, y, src, ax, ay, alt = struct.unpack_from("<hhHhhH", body, k * 12)
		cells[(x, y)] = [src, ax, ay, alt]
	return cells


def _encode(cells: dict[tuple[int, int], list[int]]) -> str:
	parts = [struct.pack("<H", 0)]
	for (x, y), (src, ax, ay, alt) in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
		parts.append(struct.pack("<hhHhhH", x, y, src, ax, ay, alt))
	return base64.b64encode(b"".join(parts)).decode("ascii")


def _world_edits(lifts: list[dict]) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
	"""(rails -> rock, top station tube cells -> empty), keyed by world cell."""
	rails: dict[tuple[int, int], int] = {}
	tops: dict[tuple[int, int], int] = {}
	for spec in lifts:
		x0 = int(spec["x"]) // CELL
		x1 = (int(spec["x"]) + int(spec["w"])) // CELL
		top, bottom = int(spec["top"]) // CELL, int(spec["bottom"]) // CELL
		for row in range(top, bottom):
			rails[(x0 - 1, row)] = SOLID
			rails[(x1, row)] = SOLID
		for col in range(x0, x1):
			tops[(col, top)] = 0
	return rails, tops


def _patch(path: Path, cx: int, cy: int, rails: dict, tops: dict) -> tuple[int, int, int]:
	text = path.read_text(encoding="utf-8")
	parts = re.split(r"(\[node name=\"[^\"]+\"[^\]]*\]\n)", text)
	out: list[str] = [parts[0]]
	n_alt = n_rail = n_top = 0
	for i in range(1, len(parts), 2):
		header, body = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
		name = re.match(r'\[node name="([^"]+)"', header)
		m = re.search(r'tile_map_data = PackedByteArray\("([^"]+)"\)', body)
		if name and name.group(1) == "CollisionLayer" and m:
			cells = _decode(base64.b64decode(m.group(1)))
			for c in cells.values():
				if c[1] == SOLID and c[3] == SHAFT_ALT:
					c[3] = 0
					n_alt += 1
			for (wx, wy), _ax in rails.items():
				key = (wx - cx, wy - cy)
				if key in cells and cells[key][1] == LADDER:
					cells[key] = [0, SOLID, 0, 0]
					n_rail += 1
			for wx, wy in tops:
				if cells.pop((wx - cx, wy - cy), None) is not None:
					n_top += 1
			body = body[: m.start(1)] + _encode(cells) + body[m.end(1) :]
		out.extend([header, body])
	if n_alt or n_rail or n_top:
		path.write_text("".join(out), encoding="utf-8", newline="\n")
	return n_alt, n_rail, n_top


def main() -> None:
	lifts = json.loads(COLLISION.read_text(encoding="utf-8"))["lifts"]
	rails, tops = _world_edits(lifts)
	man = json.loads((CHUNKS / "chunks.json").read_text(encoding="utf-8"))
	nx = int(man.get("chunks_x", 8))
	for i, rp in enumerate(man["paths"]):
		path = CHUNKS / Path(rp).name
		cx, cy = (i % nx) * CHUNK_W, (i // nx) * CHUNK_H
		n_alt, n_rail, n_top = _patch(path, cx, cy, rails, tops)
		if n_alt or n_rail or n_top:
			print(f"{path.name}: shaft->rock={n_alt} rails->rock={n_rail} tops opened={n_top}")


if __name__ == "__main__":
	main()
