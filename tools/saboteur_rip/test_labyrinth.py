#!/usr/bin/env python3
"""Whole-maze passability: floors/ground hold, ladders exist, spawn is not a void.

Global spawn→exit connectivity is reported but not required: object-bound
AABBs still isolate pockets (see docs/audit_baseline.md). Falling through a
floor or a missing ladder mask is a hard fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labyrinth import Labyrinth, feet_cell


def test_spawn_lands_on_a_floor() -> None:
    maze = Labyrinth()
    sx, sy = feet_cell(*maze.entities["spawn"])
    land = maze._drop(sx, sy)
    assert land is not None, "spawn drops into the void"
    assert land in maze.stand, land
    # Must actually meet a solid, not fall off the map.
    cx, cy = land
    assert maze.solid[cy + 1][cx], "landed without a floor cell"


def test_every_ladder_has_climb_cells() -> None:
    maze = Labyrinth()
    missing = [r for r in maze.collision["ladders"] if not maze.ladder_has_climb(r)]
    assert missing == [], missing[:8]


def test_every_ladder_is_tall_enough_to_mount() -> None:
    maze = Labyrinth()
    short = [r for r in maze.collision["ladders"] if int(r[3]) < 24]
    assert short == [], short


def test_thin_floors_exist_in_the_solid_grid() -> None:
    maze = Labyrinth()
    holes = maze.floor_top_holes()
    assert holes == [], holes[:8]


def test_standable_cells_have_solid_or_lift_under_feet() -> None:
    maze = Labyrinth()
    bad: list[tuple[int, int]] = []
    lift_cells: set[tuple[int, int]] = set()
    for spec in maze.collision.get("lifts", []):
        x, y, w, h = int(spec["x"]), int(spec["y"]), int(spec["w"]), int(spec["h"])
        for stop in (y, int(spec["top"]), int(spec["bottom"])):
            fy = stop // 8 - 1
            for cx in range(x // 8, (x + max(w, 1) - 1) // 8 + 1):
                lift_cells.add((cx, fy))
    for cx, cy in maze.stand:
        if cy + 1 >= maze.ch:
            bad.append((cx, cy))
            continue
        if maze.solid[cy + 1][cx]:
            continue
        if (cx, cy) in lift_cells:
            continue
        bad.append((cx, cy))
    assert bad == [], bad[:12]


def test_every_lift_has_a_platform() -> None:
    maze = Labyrinth()
    for spec in maze.collision["lifts"]:
        assert int(spec["w"]) >= 8 and int(spec["h"]) >= 1, spec


def test_report_prints_reachability() -> None:
    """Not a passability gate — documents how much of the maze BFS can see."""
    maze = Labyrinth()
    r = maze.report()
    assert r["reached"] > 0
    assert r["standable"] > 1000
    print(
        "labyrinth reachability: reached %s / standable %s, ladders %s/%s, "
        "points %s, blocked screens %s"
        % (
            r["reached"],
            r["standable"],
            r["ladders"] - len(r["unreachable_ladders"]),
            r["ladders"],
            r["unreachable_points"],
            r["blocked_screens"],
        )
    )


def main() -> None:
    test_spawn_lands_on_a_floor()
    test_every_ladder_has_climb_cells()
    test_every_ladder_is_tall_enough_to_mount()
    test_thin_floors_exist_in_the_solid_grid()
    test_standable_cells_have_solid_or_lift_under_feet()
    test_every_lift_has_a_platform()
    test_report_prints_reachability()
    print("test_labyrinth: OK")


if __name__ == "__main__":
    main()
