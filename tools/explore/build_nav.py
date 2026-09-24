#!/usr/bin/env python3
"""Navigation graph of the Saboteur II maze for scripts/demo/explore_demo.gd.

Reads the CollisionLayer of every world chunk, finds every spot where Nina can
stand or crawl, and links them with the moves the player controller really
has: walk (1-cell steps), crawl, ladders, running somersault, walking off a
ledge, lift cabins and bookcase passages. Jumps and drops are simulated with
the numbers from player.gd, so the explorer only tries arcs that should land.

Units are native px (world = native x 2). Node X is the body centre (always a
cell boundary), node F is the feet line (top of the floor row).

    python tools/explore/build_nav.py [out.json]
"""
from __future__ import annotations

import base64
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "scenes" / "world" / "chunks"
WORLD = ROOT / "assets" / "world"
OUT = ROOT / ".mcp" / "explore" / "nav_graph.json"

CELL = 8
CHUNK_W, CHUNK_H = 128, 72
EMPTY, SOLID, LADDER, ONEWAY, ROPE, SHAFT = range(6)

# player.gd numbers are world px at scale 2; halve them.
WALK = 55.0
CRAWL = 50.0
FLIP_VX = 110.0 * 1.7 / 2.0
FLIP_VY = -270.0 * 1.4 / 2.0
GRAVITY = 410.0
MAX_FALL = 210.0
CLIMB = 28.0
LIFT_SPEED = 44.0
DT = 1.0 / 60.0
# Body: 14 px wide around X, 42 px standing / 24 px crouched above the feet.
HALF_W = 7
STAND_ROWS = 6
CROUCH_ROWS = 3
# Coverage waypoint every N cells along a floor, plus both ends.
WP_STEP = 4
MAX_AIR_STEPS = 300
MAX_WALKOFF_STEPS = 40

WALK_EDGE, CLIMB_EDGE, JUMP_EDGE, DROP_EDGE, LIFT_EDGE, PASSAGE_EDGE = range(6)


def load_grid() -> np.ndarray:
    man = json.loads((CHUNKS / "chunks.json").read_text(encoding="utf-8"))
    nx = int(man.get("chunks_x", 8))
    paths = man["paths"]
    ny = (len(paths) + nx - 1) // nx
    g = np.zeros((ny * CHUNK_H, nx * CHUNK_W), dtype=np.uint8)
    for i, rp in enumerate(paths):
        text = (CHUNKS / Path(rp).name).read_text(encoding="utf-8")
        cx, cy = (i % nx) * CHUNK_W, (i // nx) * CHUNK_H
        for part in re.split(r"\[node name=", text)[1:]:
            if part.split('"', 2)[1] != "CollisionLayer":
                continue
            m = re.search(r'tile_map_data = PackedByteArray\("([^"]+)"\)', part)
            if not m:
                continue
            raw = base64.b64decode(m.group(1))[2:]
            for k in range(len(raw) // 12):
                x, y, _src, ax, _ay, alt = struct.unpack_from("<hhHhhH", raw, k * 12)
                code = SHAFT if ax == SOLID and alt == 1 else ax
                if 0 <= x < CHUNK_W and 0 <= y < CHUNK_H:
                    g[cy + y, cx + x] = code
    return g


class Maze:
    def __init__(self, g: np.ndarray) -> None:
        self.g = g
        self.h, self.w = g.shape
        self.block = (g == SOLID) | (g == SHAFT)
        self.support = self.block | (g == ONEWAY)
        self.oneway = g == ONEWAY
        # Node (j, r): body centre X = (j + 1) * 8 over columns j, j + 1; feet on row r.
        bp = self.block[:, :-1] | self.block[:, 1:]
        sp = self.support[:, :-1] | self.support[:, 1:]
        free = ~bp
        # run[r] = consecutive free rows ending at r (inclusive), per column pair.
        run = np.zeros(free.shape, dtype=np.int32)
        for r in range(self.h):
            run[r] = np.where(free[r], (run[r - 1] if r else 0) + 1, 0)
        above = np.zeros(free.shape, dtype=np.int32)
        above[1:] = run[:-1]
        self.crouch_ok = sp & (above >= CROUCH_ROWS)
        self.stand_ok = sp & (above >= STAND_ROWS)
        self.crouch_ok[:CROUCH_ROWS] = False

    # --- geometry -------------------------------------------------------
    def _cols(self, x: float) -> range:
        return range(int(np.floor((x - HALF_W) / CELL)), int(np.floor((x + HALF_W - 1e-6) / CELL)) + 1)

    def overlaps(self, x: float, f: float, rows: int = STAND_ROWS) -> bool:
        top = f - (42 if rows == STAND_ROWS else 24)
        r0 = int(np.floor(top / CELL))
        r1 = int(np.floor((f - 1e-6) / CELL))
        for c in self._cols(x):
            if c < 0 or c >= self.w:
                return True
            for r in range(max(r0, 0), min(r1, self.h - 1) + 1):
                if self.block[r, c]:
                    return True
        return False

    def supported(self, x: float, r: int, from_above: bool = True) -> bool:
        if r < 0 or r >= self.h:
            return False
        for c in self._cols(x):
            if 0 <= c < self.w and (self.block[r, c] or (from_above and self.oneway[r, c])):
                return True
        return False

    def simulate(self, x: float, f: float, vx: float, vy: float, walk_first: bool):
        """Returns (x, f) of the landing, or None (wall, void, or never left the floor)."""
        airborne = not walk_first
        for step in range(MAX_AIR_STEPS):
            if not airborne:
                nx = x + vx * DT
                if self.overlaps(nx, f):
                    return None
                x = nx
                if not self.supported(x, int(f // CELL)):
                    airborne = True
                    vy = 0.0
                elif step > MAX_WALKOFF_STEPS:
                    return None
                continue
            nx = x + vx * DT
            if not self.overlaps(nx, f):
                x = nx
            nf = f + vy * DT
            if vy < 0.0:
                if self.overlaps(x, nf):
                    # Bump the ceiling: feet go back to the lowest clear line.
                    nf = (np.floor((nf - 42) / CELL) + 1) * CELL + 42
                    nf = max(nf, f) if self.overlaps(x, nf) else nf
                    vy = 0.0
                f = nf
            else:
                r0 = int(np.floor(f / CELL))
                if f % CELL == 0:
                    r0 = int(f // CELL)
                r1 = int(np.floor(nf / CELL))
                landed = None
                for r in range(r0, r1 + 1):
                    top = r * CELL
                    if top < f - 1e-6 or top > nf + 1e-6:
                        continue
                    if self.supported(x, r):
                        landed = top
                        break
                if landed is not None:
                    return x, float(landed)
                f = nf
            vy = min(vy + GRAVITY * DT, MAX_FALL)
            if f > self.h * CELL + 64:
                return None
        return None


def ladder_rects(g: np.ndarray) -> list[list[int]]:
    h, w = g.shape
    runs: dict[tuple[int, int], int] = {}
    for x in range(w):
        col = g[:, x] == LADDER
        y = 0
        while y < h:
            if col[y]:
                s = y
                while y < h and col[y]:
                    y += 1
                runs[(x, s)] = y
            else:
                y += 1
    rects, used = [], set()
    for (x, s), e in sorted(runs.items()):
        if (x, s) in used:
            continue
        x1 = x + 1
        while runs.get((x1, s)) == e:
            used.add((x1, s))
            x1 += 1
        if (e - s) * CELL >= 24:
            rects.append([x * CELL, s * CELL, (x1 - x) * CELL, (e - s) * CELL])
    return rects


def build(out: Path) -> dict:
    g = load_grid()
    maze = Maze(g)
    coll = json.loads((WORLD / "s2_collision.json").read_text(encoding="utf-8"))
    ents = json.loads((WORLD / "s2_entities.json").read_text(encoding="utf-8"))

    rs, js = np.nonzero(maze.crouch_ok)
    raw = {(int(j), int(r)): i for i, (r, j) in enumerate(zip(rs, js))}
    print("standable spots", len(raw))

    # Walk adjacency -> segments (union-find).
    parent = list(range(len(raw)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for (j, r), i in raw.items():
        for dr in (-1, 0, 1):
            k = raw.get((j + 1, r + dr))
            if k is not None:
                parent[find(i)] = find(k)
    seg_of = {key: find(i) for key, i in raw.items()}
    segs: dict[int, list[tuple[int, int]]] = {}
    for key, s in seg_of.items():
        segs.setdefault(s, []).append(key)
    for s in segs:
        segs[s].sort()
    print("floor segments", len(segs))

    special: set[tuple[int, int]] = set()
    edges: list[tuple[tuple[int, int], tuple[int, int], int, int]] = []

    def snap(x: float, f: float) -> tuple[int, int] | None:
        r = int(round(f / CELL))
        j0 = int(round(x / CELL)) - 1
        for dj in (0, -1, 1, -2, 2):
            if (j0 + dj, r) in raw:
                return (j0 + dj, r)
        return None

    # Ladders: consecutive floors along each shaft.
    ladders = ladder_rects(g)
    for lx, ly, lw, lh in ladders:
        cx = lx + lw / 2.0
        j = int(round(cx / CELL)) - 1
        floors = []
        for r in range((ly - 16) // CELL, (ly + lh + 16) // CELL + 1):
            for dj in (0, -1, 1):
                if (j + dj, r) in raw:
                    floors.append((j + dj, r))
                    break
        floors.sort(key=lambda k: k[1])
        # A floor one row under another is the same landing (stair nub).
        dedup = []
        for k in floors:
            if dedup and k[1] - dedup[-1][1] <= 2:
                continue
            dedup.append(k)
        for a, b in zip(dedup, dedup[1:]):
            special.update((a, b))
            edges.append((a, b, CLIMB_EDGE, int(cx)))
            edges.append((b, a, CLIMB_EDGE, int(cx)))

    # Walking off ledges.
    for s, keys in segs.items():
        for key, d in ((keys[0], -1), (keys[-1], 1)):
            j, r = key
            land = maze.simulate((j + 1) * CELL, r * CELL, d * WALK, 0.0, True)
            if land is None:
                continue
            dst = snap(*land)
            if dst is None or seg_of[dst] == s:
                continue
            special.update((key, dst))
            edges.append((key, dst, DROP_EDGE, d))

    # Running somersaults: keep the safest takeoff per (from, to, dir).
    best: dict[tuple[int, int, int], tuple[float, tuple[int, int], tuple[int, int]]] = {}
    seg_span = {s: (keys[0][0], keys[-1][0]) for s, keys in segs.items()}
    n = 0
    for (j, r), i in raw.items():
        if not maze.stand_ok[r, j]:
            continue
        s = seg_of[(j, r)]
        lo, hi = seg_span[s]
        for d in (-1, 1):
            behind = any((j - d, r + dr) in raw for dr in (-1, 0, 1))
            if not behind:
                continue
            n += 1
            land = maze.simulate((j + 1) * CELL, r * CELL, d * FLIP_VX, FLIP_VY, False)
            if land is None:
                continue
            dst = snap(*land)
            if dst is None:
                continue
            ds = seg_of[dst]
            if ds == s:
                continue
            dlo, dhi = seg_span[ds]
            room_to = min(dst[0] - dlo, dhi - dst[0], 4)
            room_from = min((hi - j) if d > 0 else (j - lo), 4)
            score = room_to * 2 + room_from
            k = (s, ds, d)
            if k not in best or score > best[k][0]:
                best[k] = (score, (j, r), dst)
    print("somersaults simulated", n, "useful", len(best))
    for (_s, _ds, d), (_score, a, b) in best.items():
        special.update((a, b))
        edges.append((a, b, JUMP_EDGE, d))

    # Lifts: one shaft per x; the cabin runs end to end.
    shafts: list[dict] = []
    for spec in coll.get("lifts", []):
        x, w = int(spec["x"]), int(spec["w"])
        key = (x, int(spec["top"]), int(spec["bottom"]))
        if any((sh["x"], sh["top"], sh["bottom"]) == key for sh in shafts):
            continue
        cx = x + w / 2.0
        a = snap(cx, float(spec["top"]))
        b = snap(cx, float(spec["bottom"]))
        sh = {"x": x, "w": w, "top": key[1], "bottom": key[2], "center": cx}
        idx = len(shafts)
        shafts.append(sh)
        if not (a and b):
            print("lift shaft without end floors", sh, a, b)
        # A cabin resting on any shaft floor rides to either end; the explorer
        # only takes the edge while a cabin actually waits there.
        stops = []
        for r in range(key[1] // CELL, key[2] // CELL + 1):
            k = snap(cx, float(r * CELL))
            if k and k[1] == r and (not stops or stops[-1] != k):
                stops.append(k)
        for k in stops:
            for end in (a, b):
                if end and end != k:
                    special.update((k, end))
                    edges.append((k, end, LIFT_EDGE, idx))

    # Bookcase passages (crouch in the area, land at the destination).
    for p in ents.get("passages", []):
        a = snap(float(p["x"]) + 24.0, float(p["y"]) + 40.0)
        dest = maze.simulate(float(p["to_x"]) + 24.0, float(p["to_y"]) + 56.0, 0.0, 0.0, False)
        b = snap(*dest) if dest else None
        if a and b:
            special.update((a, b))
            edges.append((a, b, PASSAGE_EDGE, 0))

    # Graph nodes: waypoints along each floor + every special spot.
    chosen: set[tuple[int, int]] = set(special)
    for keys in segs.values():
        chosen.add(keys[0])
        chosen.add(keys[-1])
        for idx in range(0, len(keys), WP_STEP):
            chosen.add(keys[idx])
    order = sorted(chosen, key=lambda k: (seg_of[k], k[0], k[1]))
    node_id = {k: i for i, k in enumerate(order)}
    nodes = [
        [(j + 1) * CELL, r * CELL, 0 if maze.stand_ok[r, j] else 1, seg_of[(j, r)]]
        for j, r in order
    ]
    out_edges: list[list[int]] = []
    for s, keys in segs.items():
        pts = [k for k in keys if k in chosen]
        for a, b in zip(pts, pts[1:]):
            out_edges.append([node_id[a], node_id[b], WALK_EDGE, 0])
            out_edges.append([node_id[b], node_id[a], WALK_EDGE, 0])
    for a, b, t, extra in edges:
        out_edges.append([node_id[a], node_id[b], t, extra])

    spawn = ents["spawn"]
    start = maze.simulate(float(spawn[0]) + 24.0, float(spawn[1]) + 56.0, 0.0, 0.0, False)
    start_node = None
    start_key = snap(*start) if start else None
    if start_key:
        same = [k for k in chosen if seg_of[k] == seg_of[start_key]]
        start_node = node_id[min(same, key=lambda k: abs(k[0] - start_key[0]))]
    data = {
        "units": "native px; world = native x scale",
        "scale": 2,
        "nodes": nodes,
        "edges": out_edges,
        "lifts": shafts,
        "start": start_node,
        "segments": [[k[0][0], k[-1][0], k[0][1]] for k in segs.values()],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    kinds = [0] * 6
    for e in out_edges:
        kinds[e[2]] += 1
    print(
        f"wrote {out}: nodes={len(nodes)} edges={len(out_edges)} "
        f"walk={kinds[0]} climb={kinds[1]} jump={kinds[2]} drop={kinds[3]} "
        f"lift={kinds[4]} passage={kinds[5]} start={start_node}"
    )
    return data


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
