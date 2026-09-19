#!/usr/bin/env python3
"""Walkability graph of the Saboteur II maze from collision tiles.

Cells are mosaic 8×8. Player origin is sprite top-left; feet sit 56px below
and 24px to the right (see s2_entities.json / player.tscn). Movement models
walk, 1-cell step-up, a short jump, gravity, ladders, tightropes, lifts and
bookcase passages — enough to ask “can Nina reach this room / ladder / corridor?”
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "assets" / "world"
CELL = 8
# Hang-glider intro (START): Nina flies R→L, jumps off, falls straight down.
GLIDER_FLIGHT_Y = range(10, 22)
GLIDER_FLIGHT_X = range(470, 611)
# Sprite 48×56 in PNG; body is 14×42 with origin at top-left.
FEET_DX = 24
FEET_DY = 56
# Standing body ~42px → 5 cells; crawl ~24px → 3 cells.
STAND_CELLS = 5
CRAWL_CELLS = 3
STEP_CELLS = 1
# player.gd: jump_velocity=270, gravity=820 → h = v²/2g ≈ 5.5 cells.
# Horizontal: speed 110 × hang 2v/g ≈ 9 cells. Rounded up so the gate
# does not undershoot the real character.
JUMP_CELLS = 6
JUMP_HORIZ = 10
SCREEN_W, SCREEN_H = 256, 192
SCREEN_CW, SCREEN_CH = SCREEN_W // CELL, SCREEN_H // CELL


def load_grids() -> tuple[
    list[list[int]], list[list[int]], list[list[int]], list[list[int]], int, int
]:
    """Solid + climb + rope grids from the native collision grid (build_collision.py).

    collision_type ids: 0 empty, 1 solid, 2 ladder, 3 oneway, 4 rope. Oneway
    floors are standable, so they count as solid for walkability. Nina can
    also drop through a oneway grate (hold down).
    """
    doc = json.loads((WORLD / "s2_collision_grid.json").read_text(encoding="utf-8"))
    cw, ch = doc["grid"]
    ids = doc["cells"]
    solid = [[0] * cw for _ in range(ch)]
    climb = [[0] * cw for _ in range(ch)]
    rope = [[0] * cw for _ in range(ch)]
    oneway = [[0] * cw for _ in range(ch)]
    for i, v in enumerate(ids):
        y, x = i // cw, i % cw
        if v == 1 or v == 3:
            solid[y][x] = 1
            if v == 3:
                oneway[y][x] = 1
        elif v == 2:
            climb[y][x] = 1
        elif v == 4:
            rope[y][x] = 1
    return solid, climb, rope, oneway, cw, ch


def png_to_cell(x: float, y: float) -> tuple[int, int]:
    return int(x) // CELL, int(y) // CELL


def feet_cell(origin_x: float, origin_y: float) -> tuple[int, int]:
    return png_to_cell(origin_x + FEET_DX, origin_y + FEET_DY)


def _empty_column(
    solid: list[list[int]], cx: int, y0: int, y1: int, cw: int, ch: int
) -> bool:
    """True if [y0, y1] inclusive is in-bounds and not solid."""
    if cx < 0 or cx >= cw:
        return False
    if y0 > y1:
        y0, y1 = y1, y0
    if y0 < 0 or y1 >= ch:
        return False
    for y in range(y0, y1 + 1):
        if solid[y][cx]:
            return False
    return True


def clearance(
    solid: list[list[int]], cx: int, fy: int, cells: int, cw: int, ch: int
) -> bool:
    top = fy - cells + 1
    return _empty_column(solid, cx, top, fy, cw, ch)


class Labyrinth:
    def __init__(self) -> None:
        self.solid, self.climb, self.rope, self.oneway, self.cw, self.ch = load_grids()
        self.collision = json.loads((WORLD / "s2_collision.json").read_text(encoding="utf-8"))
        self.entities = json.loads((WORLD / "s2_entities.json").read_text(encoding="utf-8"))
        self.stand: set[tuple[int, int]] = set()
        self.climb_cells: set[tuple[int, int]] = set()
        self.rope_cells: set[tuple[int, int]] = set()
        self._index_cells()
        self.reached: set[tuple[int, int]] = set()
        self._bfs()

    def _index_cells(self) -> None:
        solid, climb, rope, cw, ch = self.solid, self.climb, self.rope, self.cw, self.ch
        for y in range(ch):
            for x in range(cw):
                if climb[y][x]:
                    self.climb_cells.add((x, y))
                if rope[y][x]:
                    self.rope_cells.add((x, y))
                if y + 1 < ch and not solid[y][x] and solid[y + 1][x]:
                    if clearance(solid, x, y, CRAWL_CELLS, cw, ch):
                        self.stand.add((x, y))
        # Lift cars are extra floors (AnimatableBody2D), not in the tile grid.
        # A stop exists at every shaft row that neighbours a real floor, so
        # Nina can board at each LEVEL, not only at decoder top/bottom.
        for spec in self.collision.get("lifts", []):
            x, y, w = int(spec["x"]), int(spec["y"]), int(spec["w"])
            top, bottom = int(spec["top"]), int(spec["bottom"])
            x0, x1 = x // CELL, (x + max(w, 1) - 1) // CELL
            y0, y1 = min(top, bottom) // CELL, max(top, bottom) // CELL
            for fy in range(max(0, y0 - 1), min(ch, y1 + 1)):
                adj_floor = any(
                    (ax, fy) in self.stand for ax in (x0 - 1, x1 + 1) if 0 <= ax < cw
                )
                car_stop = fy in {y // CELL - 1, top // CELL - 1, bottom // CELL - 1}
                if not (adj_floor or car_stop):
                    continue
                for cx in range(x0, x1 + 1):
                    if 0 <= cx < cw and not solid[fy][cx]:
                        if clearance(solid, cx, fy, CRAWL_CELLS, cw, ch):
                            self.stand.add((cx, fy))

    def _drop(self, cx: int, cy: int) -> tuple[int, int] | None:
        solid, climb, ch = self.solid, self.climb, self.ch
        y = cy
        while y + 1 < ch and not solid[y + 1][cx] and (cx, y) not in self.climb_cells:
            y += 1
            if (cx, y) in self.stand:
                return (cx, y)
        if (cx, y) in self.stand or (cx, y) in self.climb_cells:
            return (cx, y)
        if y + 1 < ch and (solid[y + 1][cx] or climb[y + 1][cx]):
            if (cx, y) in self.stand or (cx, y) in self.climb_cells:
                return (cx, y)
        return None

    def _stand_run_width(self, cx: int, cy: int) -> int:
        """How many consecutive stand cells share this floor row."""
        n = 0
        x = cx
        while x >= 0 and (x, cy) in self.stand:
            n += 1
            x -= 1
        x = cx + 1
        while x < self.cw and (x, cy) in self.stand:
            n += 1
            x += 1
        return n

    def _oneway_run_width(self, cx: int, cy: int) -> int:
        """How many consecutive oneway cells share this grate row."""
        n = 0
        x = cx
        while x >= 0 and self.oneway[cy][x]:
            n += 1
            x -= 1
        x = cx + 1
        while x < self.cw and self.oneway[cy][x]:
            n += 1
            x += 1
        return n

    def _fall_from_rope(self, cx: int, cy: int) -> tuple[int, int] | None:
        """Stopping on a tightrope: Nina drops straight down to the next floor."""
        y = cy
        while y + 1 < self.ch:
            ny = y + 1
            if (cx, ny) in self.stand or (cx, ny) in self.climb_cells:
                return (cx, ny)
            if (cx, ny) in self.rope_cells:
                y = ny
                continue
            if self.solid[ny][cx]:
                break
            y = ny
        return None

    def _neighbors(self, cx: int, cy: int) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        solid, cw, ch = self.solid, self.cw, self.ch
        on_climb = (cx, cy) in self.climb_cells
        on_stand = (cx, cy) in self.stand
        on_rope = (cx, cy) in self.rope_cells

        def add(nx: int, ny: int) -> None:
            if 0 <= nx < cw and 0 <= ny < ch:
                if (
                    (nx, ny) in self.stand
                    or (nx, ny) in self.climb_cells
                    or (nx, ny) in self.rope_cells
                ):
                    out.append((nx, ny))

        def try_land(nx: int, ny: int) -> None:
            if (nx, ny) in self.rope_cells:
                add(nx, ny)
                return
            if (nx, ny) in self.stand or (nx, ny) in self.climb_cells:
                add(nx, ny)
                return
            if ny < 0 or ny >= ch or nx < 0 or nx >= cw:
                return
            if solid[ny][nx]:
                return
            landed = self._drop(nx, ny)
            if landed:
                out.append(landed)

        # Walk, step-up, short hop, run-jump, walk off a ledge. Same from a rope
        # (jump off at range, then fall onto a facade shelf).
        if on_stand or on_climb or on_rope:
            for dx in (-1, 1):
                if (cx + dx, cy) in self.rope_cells:
                    add(cx + dx, cy)
            for dx in range(-JUMP_HORIZ, JUMP_HORIZ + 1):
                if dx == 0:
                    continue
                nx = cx + dx
                if nx < 0 or nx >= cw:
                    continue
                for dy in range(-JUMP_CELLS, STEP_CELLS + 1):
                    ny = cy + dy
                    if ny < 0 or ny >= ch:
                        continue
                    # Arc over short obstacles: flight height is the apex of a
                    # JUMP_CELLS hop, not the standing row. Full-height room
                    # walls still block because they occupy the apex row too.
                    if ny < cy:
                        flight_top = ny
                    else:
                        flight_top = max(0, cy - JUMP_CELLS)
                    if not _empty_column(solid, cx, flight_top, cy, cw, ch):
                        continue
                    clear = True
                    step = 1 if dx > 0 else -1
                    for mx in range(cx + step, nx, step):
                        if not _empty_column(solid, mx, flight_top, flight_top, cw, ch):
                            clear = False
                            break
                    if not clear:
                        continue
                    # Landing cell needs room for Nina's body (crawl height);
                    # the floor below may be solid — that is the ledge she
                    # lands on. Checking the whole cy..ny column would forbid
                    # jumping onto any ledge whose top is between the two rows.
                    if not _empty_column(solid, nx, ny - CRAWL_CELLS + 1, ny, cw, ch):
                        continue
                    try_land(nx, ny)
        if on_stand and cy + 2 < ch and self.oneway[cy + 1][cx]:
            # Drop through a grate onto the next floor. Skip 1–2 cell nubs
            # under a wide roof (tower teeth); keep narrow facade shelves
            # under a short balcony.
            landed = self._drop(cx, cy + 2)
            roof_w = self._oneway_run_width(cx, cy + 1)
            while (
                landed
                and self._stand_run_width(landed[0], landed[1]) < 3
                and roof_w >= 12
            ):
                y = landed[1] + 1
                while y < ch and self.solid[y][cx]:
                    y += 1
                nxt = self._drop(cx, y) if y < ch else None
                if not nxt or nxt[1] <= landed[1]:
                    landed = None
                    break
                landed = nxt
            if landed:
                out.append(landed)
        if on_rope:
            for dx in (-1, 1):
                nx = cx + dx
                if (nx, cy) in self.rope_cells:
                    add(nx, cy)
            landed = self._fall_from_rope(cx, cy)
            if landed:
                out.append(landed)
        if on_climb:
            for dy in (-1, 1):
                add(cx, cy + dy)
            # Emerge through a 1–2 cell hatch lid onto the floor above.
            for depth in (1, 2):
                lid0 = cy - depth
                stand_y = lid0 - 1
                if lid0 < 0 or stand_y < 0:
                    break
                if not all(solid[lid0 + d][cx] for d in range(depth)):
                    continue
                if (cx, stand_y) in self.stand:
                    add(cx, stand_y)
                    break
        # Hatch: walkable lid with a shaft under the feet (lid is solid, not climb).
        if on_stand:
            for depth in (1, 2):
                shaft_y = cy + 1 + depth
                if shaft_y >= ch:
                    break
                if not all(solid[cy + 1 + d][cx] for d in range(depth)):
                    continue
                if (cx, shaft_y) in self.climb_cells:
                    add(cx, shaft_y)
                    break
            if cy + 1 < ch and self.climb[cy + 1][cx]:
                add(cx, cy + 1)
        return out

    def _bfs(self) -> None:
        spawn = self.entities["spawn"]
        sx, sy = feet_cell(float(spawn[0]), float(spawn[1]))
        start = self._drop(sx, sy)
        if start is None:
            start = (sx, sy)
        q: deque[tuple[int, int]] = deque()
        if 0 <= start[0] < self.cw and 0 <= start[1] < self.ch:
            q.append(start)
            self.reached.add(start)
        for gy in GLIDER_FLIGHT_Y:
            for gx in GLIDER_FLIGHT_X:
                land = self._drop(gx, gy)
                if land and land not in self.reached:
                    self.reached.add(land)
                    q.append(land)
        # Bookcase warps (crouch).
        passages = [
            (
                feet_cell(float(p["x"]), float(p["y"])),
                feet_cell(float(p["to_x"]), float(p["to_y"])),
            )
            for p in self.entities.get("passages", [])
        ]
        lift_of: dict[tuple[int, int], int] = {}
        lift_groups: list[set[tuple[int, int]]] = []
        for spec in self.collision.get("lifts", []):
            x, w = int(spec["x"]), int(spec["w"])
            top, bottom = int(spec["top"]), int(spec["bottom"])
            x0, x1 = x // CELL, (x + max(w, 1) - 1) // CELL
            y0, y1 = min(top, bottom) // CELL, max(top, bottom) // CELL
            group = {
                (px, py)
                for px, py in self.stand | self.climb_cells
                if x0 <= px <= x1 and y0 - 2 <= py <= y1 + 2
            }
            if not group:
                continue
            idx = len(lift_groups)
            lift_groups.append(group)
            for cell in group:
                lift_of[cell] = idx
        used_lifts: set[int] = set()

        while q:
            cx, cy = q.popleft()
            for nb in self._neighbors(cx, cy):
                if nb not in self.reached:
                    self.reached.add(nb)
                    q.append(nb)
            for a, b in passages:
                here = (cx, cy)
                other = b if here == a else a if here == b else None
                if other is None:
                    dest = self._nearest_stand(cx, cy, 2)
                    if dest == a:
                        other = b
                    elif dest == b:
                        other = a
                if other:
                    dest = self._nearest_stand(*other) or other
                    if dest not in self.reached:
                        self.reached.add(dest)
                        q.append(dest)
            li = lift_of.get((cx, cy))
            if li is not None and li not in used_lifts:
                used_lifts.add(li)
                for nb in lift_groups[li]:
                    if nb not in self.reached:
                        self.reached.add(nb)
                        q.append(nb)

    def _nearest_stand(self, cx: int, cy: int, radius: int = 6) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        best_d = radius + 1
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                p = (cx + dx, cy + dy)
                if p in self.stand or p in self.climb_cells:
                    d = abs(dx) + abs(dy)
                    if d < best_d:
                        best_d = d
                        best = p
        return best

    def _geometry_flood(self) -> set[tuple[int, int]]:
        """Body-aware connectivity ignoring gravity/jumps: Nina's crouch box
        (2 wide x 3 tall) fits a passage iff every cell of the box is non-solid.

        This is the fair "is the geometry there" gate. The strict BFS
        (`self.reached`) models realistic platformer moves and is conservative;
        a room that is geometry-reachable but not BFS-reached needs a specific
        route, while a room that is not geometry-reachable is genuinely sealed.
        """
        solid, cw, ch = self.solid, self.cw, self.ch

        def fits(x: int, y: int) -> bool:
            for dx in (0, 1):
                for dy in (0, 1, 2):
                    xx, yy = x + dx, y - dy
                    if not (0 <= xx < cw and 0 <= yy < ch) or solid[yy][xx]:
                        return False
            return True

        spawn = self.entities["spawn"]
        sx, sy = feet_cell(float(spawn[0]), float(spawn[1]))
        seen: set[tuple[int, int]] = set()
        if fits(sx, sy):
            seen.add((sx, sy))
        q: deque[tuple[int, int]] = deque(seen)
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) not in seen and fits(nx, ny):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def _geometry_reachable(
        self, x: float, y: float, geo: set[tuple[int, int]], radius: int = 6
    ) -> bool:
        cx, cy = feet_cell(x, y)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if (cx + dx, cy + dy) in geo:
                    return True
        return False

    def reachable_png(self, x: float, y: float, radius: int = 8) -> bool:
        cx, cy = feet_cell(x, y)
        got = self._nearest_stand(cx, cy, radius)
        if got is not None and got in self.reached:
            return True
        # Sprite origins hang in the air (spawn, airborne pickups); the feet
        # drop onto the floor below.
        dropped = self._drop(cx, cy)
        return dropped is not None and dropped in self.reached

    def origin_reachable(self, x: float, y: float, radius: int = 8) -> bool:
        """True if a sprite-top-left origin can stand / land at this PNG point."""
        return self.reachable_png(x, y, radius)

    def ladder_reachable(self, rect: list[int]) -> bool:
        x, y, w, h = (int(v) for v in rect[:4])
        x0, x1 = x // CELL, (x + w - 1) // CELL
        y0, y1 = y // CELL, (y + h - 1) // CELL
        for cy in range(max(0, y0), min(self.ch, y1 + 1)):
            for cx in range(max(0, x0), min(self.cw, x1 + 1)):
                if (cx, cy) in self.reached:
                    return True
        return False

    def floor_run_holes(self) -> list[dict]:
        """Gaps in a reachable floor run (corridor missing a cell)."""
        holes: list[dict] = []
        by_y: dict[int, list[int]] = {}
        for cx, cy in self.stand:
            by_y.setdefault(cy, []).append(cx)
        for cy, xs in by_y.items():
            xs.sort()
            run: list[int] = []
            for x in xs:
                if not run or x == run[-1] + 1:
                    run.append(x)
                else:
                    holes.extend(self._holes_in_run(cy, run))
                    run = [x]
            holes.extend(self._holes_in_run(cy, run))
        return holes

    def _holes_in_run(self, cy: int, run: list[int]) -> list[dict]:
        if len(run) < 4:
            return []
        reached_n = sum(1 for x in run if (x, cy) in self.reached)
        if reached_n == 0 or reached_n == len(run):
            return []
        # Touches the reachable component but some cells in the same strip are not.
        holes = []
        for x in run:
            if (x, cy) not in self.reached:
                holes.append({"x": x * CELL, "y": cy * CELL, "cell": [x, cy]})
        return holes

    def screens_with_floor(self) -> list[tuple[int, int, int]]:
        """(sx, sy, standable_count) for Spectrum screens that have a floor."""
        counts: dict[tuple[int, int], int] = {}
        for cx, cy in self.stand:
            sx, sy = cx // SCREEN_CW, cy // SCREEN_CH
            counts[sx, sy] = counts.get((sx, sy), 0) + 1
        return sorted((sx, sy, n) for (sx, sy), n in counts.items() if n >= 8)

    def unreachable_screens(self) -> list[tuple[int, int]]:
        """Playable screens that neighbour a reached screen but have no reached cell."""
        reached_screens: set[tuple[int, int]] = set()
        floor_screens = {(sx, sy) for sx, sy, _n in self.screens_with_floor()}
        for cx, cy in self.reached:
            reached_screens.add((cx // SCREEN_CW, cy // SCREEN_CH))
        blocked: list[tuple[int, int]] = []
        for sx, sy in floor_screens:
            if (sx, sy) in reached_screens:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (sx + dx, sy + dy) in reached_screens:
                    blocked.append((sx, sy))
                    break
        return blocked

    def ladder_has_climb(self, rect: list[int]) -> bool:
        x, y, w, h = (int(v) for v in rect[:4])
        x0, x1 = x // CELL, (x + max(w, 1) - 1) // CELL
        y0, y1 = y // CELL, (y + max(h, 1) - 1) // CELL
        for cy in range(max(0, y0), min(self.ch, y1 + 1)):
            for cx in range(max(0, x0), min(self.cw, x1 + 1)):
                if self.climb[cy][cx]:
                    return True
        return False

    def thin_floors(self) -> list[list[int]]:
        return [r for r in self.collision["solids"] if int(r[3]) <= 16]

    def floor_top_holes(self) -> list[list[int]]:
        """Thin solids whose top cell is missing from the solid grid."""
        holes: list[list[int]] = []
        solid, cw, ch = self.solid, self.cw, self.ch
        for r in self.thin_floors():
            x, y, w, h = (int(v) for v in r[:4])
            cy = y // CELL
            if cy < 0 or cy >= ch:
                holes.append(r)
                continue
            x0, x1 = x // CELL, (x + max(w, 1) - 1) // CELL
            for cx in range(max(0, x0), min(cw, x1 + 1)):
                if not solid[cy][cx]:
                    holes.append(r)
                    break
        return holes

    def _climb_runs(self) -> list[list[int]]:
        """Ladder rects as vertical runs of climb cells in the native grid."""
        runs: list[list[int]] = []
        for cx in range(self.cw):
            y = 0
            while y < self.ch:
                if self.climb[y][cx]:
                    y0 = y
                    while y < self.ch and self.climb[y][cx]:
                        y += 1
                    if y - y0 >= 3:
                        runs.append([cx * CELL, y0 * CELL, CELL, (y - y0) * CELL])
                else:
                    y += 1
        return runs

    def report(self) -> dict:
        ladders = self._climb_runs()
        miss_ladders = [r for r in ladders if not self.ladder_reachable(r)]
        lifts_ok = []
        lifts_bad = []
        for spec in self.collision.get("lifts", []):
            ok = self.origin_reachable(float(spec["x"]), float(spec["y"]) - FEET_DY, 10)
            (lifts_ok if ok else lifts_bad).append(spec)
        points: dict[str, tuple[float, float]] = {
            "spawn": tuple(self.entities["spawn"]),
            "sabotage": (self.entities["sabotage"]["x"], self.entities["sabotage"]["y"]),
        }
        ex = self.entities.get("exit")
        if isinstance(ex, dict) and "x" in ex and "y" in ex:
            points["exit"] = (ex["x"], ex["y"])
        for item in self.entities.get("items", []):
            points[str(item.get("id", item.get("type", "item")))] = (item["x"], item["y"])
        for m in self.entities.get("markers", []):
            points[str(m.get("id", m.get("label", "m")))] = (m["x"], m["y"])
        miss_points = {
            name: xy for name, xy in points.items() if not self.origin_reachable(xy[0], xy[1])
        }
        geo = self._geometry_flood()
        geo_miss = {
            name: xy
            for name, xy in points.items()
            if not self._geometry_reachable(xy[0], xy[1], geo)
        }
        holes = self.floor_run_holes()
        return {
            "standable": len(self.stand),
            "climb_cells": len(self.climb_cells),
            "rope_cells": len(self.rope_cells),
            "reached": len(self.reached),
            "geometry_reached": len(geo),
            "geometry_unreachable_points": geo_miss,
            "ladders": len(ladders),
            "unreachable_ladders": miss_ladders,
            "unreachable_lifts": lifts_bad,
            "unreachable_points": miss_points,
            "corridor_holes": holes[:40],
            "corridor_hole_count": len(holes),
            "blocked_screens": self.unreachable_screens(),
            "floor_screens": len(self.screens_with_floor()),
        }


def main() -> None:
    maze = Labyrinth()
    r = maze.report()
    print("standable", r["standable"], "climb", r["climb_cells"], "reached", r["reached"])
    print(
        "geometry reached",
        r["geometry_reached"],
        "geometry-unreachable points",
        r["geometry_unreachable_points"],
    )
    print("floor screens", r["floor_screens"], "blocked screens", r["blocked_screens"])
    print("unreachable ladders", len(r["unreachable_ladders"]), "of", r["ladders"])
    if r["unreachable_ladders"][:8]:
        print("  sample", r["unreachable_ladders"][:8])
    print("unreachable lifts", r["unreachable_lifts"])
    print("unreachable points", r["unreachable_points"])
    print("corridor holes", r["corridor_hole_count"])


if __name__ == "__main__":
    main()
