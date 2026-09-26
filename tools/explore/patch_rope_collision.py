#!/usr/bin/env python3
"""Paint the tightropes on CollisionLayer and erase false rooftop ropes.

Each rope is the red dotted line on the fan map, painted only between the
crossbars at its ends; the crossbars and the rock around them stay as they
are, because Nina walks there.

- Radio tower: y = 672 (row 84), x 4472–5943, from the central-complex
  crossbar to the radio-tower crossbar (chunk_04_01, chunk_05_01).
- Left antenna: y = 960 (row 120), x 1240–1695, from the antenna crossbar
  to the crossbar on the central complex's west wall (chunk_01_01).

False ropes: barrels/bottles at y 384–392, x 2968–3176 (chunk_02_00).
"""
from __future__ import annotations

import base64
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "scenes" / "world" / "chunks"
CELL = 8
CHUNK_W, CHUNK_H = 128, 72
ROPE_AX = 4

# (row, first px, last px) of each rope span, crossbars excluded.
ROPES = [
	(672 // CELL, 4472, 5943),
	(960 // CELL, 1240, 1695),
]

# False rope cells on rooftop barrels (erase → empty).
FALSE_ROPE = [
	(x, y)
	for y in (384 // CELL, 392 // CELL)
	for x in range(2968 // CELL, 3176 // CELL + 1)
]


def _chunk_xy(wx: int, wy: int) -> tuple[str, int, int]:
	cx, cy = wx // CHUNK_W, wy // CHUNK_H
	return f"chunk_{cx:02d}_{cy:02d}", wx - cx * CHUNK_W, wy - cy * CHUNK_H


def _decode(raw: bytes) -> dict[tuple[int, int], tuple[int, int, int, int]]:
	cells: dict[tuple[int, int], tuple[int, int, int, int]] = {}
	body = raw[2:]
	for k in range(len(body) // 12):
		x, y, src, ax, ay, alt = struct.unpack_from("<hhHhhH", body, k * 12)
		cells[(x, y)] = (src, ax, ay, alt)
	return cells


def _encode(cells: dict[tuple[int, int], tuple[int, int, int, int]]) -> str:
	parts = [struct.pack("<H", 0)]
	for (x, y), (src, ax, ay, alt) in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
		parts.append(struct.pack("<hhHhhH", x, y, src, ax, ay, alt))
	return base64.b64encode(b"".join(parts)).decode("ascii")


def _patch_chunk(path: Path, edits: dict[tuple[int, int], int | None]) -> tuple[int, int]:
	"""edits: (lx, ly) -> atlas_x, or None to erase. Returns (set, erased)."""
	text = path.read_text(encoding="utf-8")
	parts = re.split(r"(\[node name=\"[^\"]+\"[^\]]*\]\n)", text)
	out: list[str] = [parts[0]]
	set_n = erase_n = 0
	i = 1
	while i < len(parts):
		header = parts[i]
		body = parts[i + 1] if i + 1 < len(parts) else ""
		name_m = re.match(r'\[node name="([^"]+)"', header)
		if name_m and name_m.group(1) == "CollisionLayer":
			m = re.search(r'tile_map_data = PackedByteArray\("([^"]+)"\)', body)
			if not m:
				out.extend([header, body])
				i += 2
				continue
			cells = _decode(base64.b64decode(m.group(1)))
			for (lx, ly), ax in edits.items():
				if ax is None:
					if (lx, ly) in cells:
						del cells[(lx, ly)]
						erase_n += 1
				else:
					prev = cells.get((lx, ly))
					if prev is None or prev[1] != ax or prev[3] != 0:
						cells[(lx, ly)] = (0, ax, 0, 0)
						set_n += 1
			new_b64 = _encode(cells)
			body = body[: m.start(1)] + new_b64 + body[m.end(1) :]
		out.extend([header, body])
		i += 2
	path.write_text("".join(out), encoding="utf-8", newline="\n")
	return set_n, erase_n


def main() -> None:
	by_chunk: dict[str, dict[tuple[int, int], int | None]] = {}

	for row, px0, px1 in ROPES:
		for wx in range(px0 // CELL, px1 // CELL + 1):
			name, lx, ly = _chunk_xy(wx, row)
			by_chunk.setdefault(name, {})[(lx, ly)] = ROPE_AX

	for wx, wy in FALSE_ROPE:
		name, lx, ly = _chunk_xy(wx, wy)
		by_chunk.setdefault(name, {})[(lx, ly)] = None

	total_set = total_erase = 0
	for name, edits in sorted(by_chunk.items()):
		path = CHUNKS / f"{name}.tscn"
		if not path.exists():
			raise SystemExit(f"missing {path}")
		s, e = _patch_chunk(path, edits)
		total_set += s
		total_erase += e
		print(f"{name}: set={s} erase={e} edits={len(edits)}")
	print(f"done: rope cells written~{total_set}, false ropes erased={total_erase}")


if __name__ == "__main__":
	main()
