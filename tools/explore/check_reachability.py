#!/usr/bin/env python3
"""CI reachability checks for the Saboteur II maze.

Builds the nav graph into a temporary directory (not .mcp/) and verifies:

  1. Mission chain spawn → key → orders → card → dump console → exit is
     reachable, including lift edges.
  2. Every connected blue-tunnel region (Wallpaper layer, underground) that
     has walkable floors (solid/oneway support) contains at least one nav
     node reachable from spawn. Shaft-only wallpaper pockets are ignored —
     lifts stop at shaft ends only, so mid-shaft stands are not real floors.

    python tools/explore/check_reachability.py
"""
from __future__ import annotations

import base64
import json
import re
import struct
import sys
import tempfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "explore"))

from build_nav import (  # noqa: E402
	CELL,
	CHUNK_H,
	CHUNK_W,
	CHUNKS,
	ONEWAY,
	SHAFT,
	SOLID,
	WORLD,
	build,
	load_grid,
)
from nav_reach import reach  # noqa: E402

# Underground starts around chunk row 2 (below the surface buildings).
UG_ROW = 144
# Ignore tiny wallpaper crumbs (single props / seams).
MIN_REGION = 40
# Feet-to-wallpaper body overlap: Nina is ~6 cells tall above the feet.
BODY_ROWS = range(-8, 1)


def _load_wallpaper() -> "object":
	import numpy as np

	man = json.loads((CHUNKS / "chunks.json").read_text(encoding="utf-8"))
	nx = int(man.get("chunks_x", 8))
	paths = man["paths"]
	ny = (len(paths) + nx - 1) // nx
	g = np.zeros((ny * CHUNK_H, nx * CHUNK_W), dtype=np.uint8)
	for i, rp in enumerate(paths):
		text = (CHUNKS / Path(rp).name).read_text(encoding="utf-8")
		cx, cy = (i % nx) * CHUNK_W, (i // nx) * CHUNK_H
		for part in re.split(r"\[node name=", text)[1:]:
			if part.split('"', 2)[1] != "Wallpaper":
				continue
			m = re.search(r'tile_map_data = PackedByteArray\("([^"]+)"\)', part)
			if not m:
				continue
			raw = base64.b64decode(m.group(1))[2:]
			for k in range(len(raw) // 12):
				x, y, *_rest = struct.unpack_from("<hhHhhH", raw, k * 12)
				if 0 <= x < CHUNK_W and 0 <= y < CHUNK_H:
					g[cy + y, cx + x] = 1
	return g


def _components(mask, min_cells: int) -> list[dict]:
	h, w = mask.shape
	seen = __import__("numpy").zeros_like(mask)
	out: list[dict] = []
	for y in range(h):
		for x in range(w):
			if not mask[y, x] or seen[y, x]:
				continue
			q = deque([(x, y)])
			seen[y, x] = 1
			cells: list[tuple[int, int]] = []
			while q:
				cx, cy = q.popleft()
				cells.append((cx, cy))
				for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
					nx, ny = cx + dx, cy + dy
					if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
						seen[ny, nx] = 1
						q.append((nx, ny))
			if len(cells) < min_cells:
				continue
			xs = [c[0] for c in cells]
			ys = [c[1] for c in cells]
			out.append(
				{
					"n": len(cells),
					"x0": min(xs) * CELL,
					"x1": max(xs) * CELL,
					"y0": min(ys) * CELL,
					"y1": max(ys) * CELL,
					"cells": set(cells),
				}
			)
	return out


def _bfs_ok(adj: dict[int, list[int]], src: int, dst: int) -> bool:
	if src == dst:
		return True
	seen = {src}
	q = deque([src])
	while q:
		a = q.popleft()
		for b in adj.get(a, []):
			if b == dst:
				return True
			if b not in seen:
				seen.add(b)
				q.append(b)
	return False


def _nearest(nodes: list, px: float, py: float) -> tuple[int, float]:
	best_i = 0
	best_d = abs(nodes[0][0] - px) + abs(nodes[0][1] - py)
	for i, (x, f, *_rest) in enumerate(nodes):
		d = abs(x - px) + abs(f - py)
		if d < best_d:
			best_d = d
			best_i = i
	return best_i, best_d


def _support_code(grid, j: int, r: int) -> int:
	"""Collision under a nav body centred on columns j, j+1 with feet on row r.

	Returns SHAFT if either column is a lift shaft — mid-shaft stands are not
	real floors (cabins only stop at shaft ends).
	"""
	h, w = grid.shape
	if r < 0 or r >= h:
		return SOLID
	codes = []
	for c in (j, j + 1):
		if 0 <= c < w:
			codes.append(int(grid[r, c]))
	if not codes:
		return SOLID
	if SHAFT in codes:
		return SHAFT
	for prefer in (SOLID, ONEWAY):
		if prefer in codes:
			return prefer
	return codes[0]


def check_mission(data: dict) -> list[str]:
	ents = json.loads((WORLD / "s2_entities.json").read_text(encoding="utf-8"))
	nodes = data["nodes"]
	got = reach(data)
	adj: dict[int, list[int]] = {}
	for a, b, _t, _x in data["edges"]:
		adj.setdefault(a, []).append(b)

	spawn = ents["spawn"]
	items = {it["id"]: it for it in ents["items"]}
	chain = [
		("spawn", float(spawn[0]) + 24.0, float(spawn[1]) + 56.0),
		("key", float(items["key"]["x"]), float(items["key"]["y"]) + 28.0),
		("orders", float(items["document"]["x"]), float(items["document"]["y"]) + 28.0),
		("card", float(items["bomb"]["x"]), float(items["bomb"]["y"])),
		("console", float(ents["sabotage"]["x"]), float(ents["sabotage"]["y"])),
		("exit", float(ents["exit"]["x"]), float(ents["exit"]["y"])),
	]
	errors: list[str] = []
	prev = data["start"]
	if prev is None or prev not in got:
		errors.append("spawn start node missing or unreachable")
		return errors
	for name, px, py in chain:
		ni, dist = _nearest(nodes, px, py)
		if dist > 96:
			errors.append(f"{name}: no nav node within 96 px (nearest dist={dist:.0f})")
			continue
		if ni not in got:
			errors.append(
				f"{name}: node {ni} at ({nodes[ni][0]}, {nodes[ni][1]}) unreachable from spawn"
			)
			continue
		if not _bfs_ok(adj, prev, ni):
			errors.append(f"{name}: not reachable from previous mission step")
			continue
		prev = ni
	return errors


def check_blue_tunnels(data: dict, grid) -> list[str]:
	import numpy as np

	wp = _load_wallpaper()
	mask = wp.copy()
	mask[:UG_ROW] = 0
	regs = _components(mask, MIN_REGION)
	got = reach(data)
	nodes = data["nodes"]
	errors: list[str] = []

	for reg in regs:
		walk_nodes: list[int] = []
		for i, (x, f, *_rest) in enumerate(nodes):
			j = int(x) // CELL - 1
			r = int(f) // CELL
			hit = False
			for dj in (0, 1):
				for dry in BODY_ROWS:
					if (j + dj, r + dry) in reg["cells"]:
						hit = True
						break
				if hit:
					break
			if not hit:
				continue
			sup = _support_code(grid, j, r)
			if sup == SHAFT:
				continue
			if sup in (SOLID, ONEWAY):
				walk_nodes.append(i)
		if not walk_nodes:
			continue
		if any(i in got for i in walk_nodes):
			continue
		# Lift-shaft wallpaper pockets: the only "floors" sit on a row that is
		# mostly SHAFT (cabins stop at ends only). Not a walkable tunnel.
		if _shaft_pocket(reg, grid, walk_nodes, nodes):
			continue
		errors.append(
			"blue tunnel unreachable: "
			f"x={reg['x0']}-{reg['x1']} y={reg['y0']}-{reg['y1']} "
			f"(wallpaper cells={reg['n']}, walk floors={len(walk_nodes)})"
		)
	return errors


def _shaft_pocket(reg: dict, grid, walk_nodes: list[int], nodes: list) -> bool:
	rows = {int(nodes[i][1]) // CELL for i in walk_nodes}
	x0 = reg["x0"] // CELL
	x1 = reg["x1"] // CELL
	for r in rows:
		if r < 0 or r >= grid.shape[0]:
			continue
		span = grid[r, x0 : x1 + 1]
		if span.size == 0:
			continue
		if int((span == SHAFT).sum()) >= max(3, span.size // 3):
			return True
	return False


def main() -> int:
	tmpdir = Path(tempfile.mkdtemp(prefix="s2_nav_"))
	graph_path = tmpdir / "nav_graph.json"
	print(f"building nav graph -> {graph_path}")
	data = build(graph_path)
	got = reach(data)
	n = len(data["nodes"])
	print(f"nodes={n} reachable={len(got)} ({100.0 * len(got) / max(n, 1):.1f}%)")

	errors = check_mission(data)
	if errors:
		print("MISSION FAIL")
		for e in errors:
			print(f"  {e}")
	else:
		print("MISSION OK: spawn -> key -> orders -> card -> console -> exit")

	grid = load_grid()
	blue_errors = check_blue_tunnels(data, grid)
	if blue_errors:
		print(f"BLUE TUNNELS FAIL ({len(blue_errors)} region(s))")
		for e in blue_errors:
			print(f"  {e}")
	else:
		print("BLUE TUNNELS OK")

	errors.extend(blue_errors)
	if errors:
		print(f"check_reachability: {len(errors)} error(s)")
		return 1
	print("check_reachability: OK")
	return 0


if __name__ == "__main__":
	sys.exit(main())
