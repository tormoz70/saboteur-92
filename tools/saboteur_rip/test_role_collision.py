#!/usr/bin/env python3
"""Object bounds → collision stamp (no mosaic required)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from object_types import (
    TYPE_COLLISION,
    collision_for_type,
    stamp_collision,
    type_grid_from_placements,
)


def test_type_table() -> None:
    assert collision_for_type("floor_brick") == "floor"
    assert collision_for_type("earth") == "solid"
    assert collision_for_type("floor_diamond") == "floor"
    assert collision_for_type("ladder") == "climb"
    assert collision_for_type("furniture") == "none"
    assert collision_for_type("crate") == "none"
    assert collision_for_type("unknown") == "none"


def test_stamp_from_rects() -> None:
    cw, ch = 4, 5
    placements = [
        {"type": "earth", "x": 0, "y": 4, "w": 1, "h": 1},
        {"type": "floor_brick", "x": 1, "y": 4, "w": 1, "h": 1},
        {"type": "floor_diamond", "x": 2, "y": 4, "w": 1, "h": 1},
        {"type": "ladder", "x": 1, "y": 1, "w": 1, "h": 3},
    ]
    solid, ladders = stamp_collision(placements, cw, ch)
    assert solid[4][0] == 1
    assert solid[4][1] == 1, "brick floor is one cell thick"
    assert solid[4][2] == 1
    assert solid[3][1] == 0, "floor does not grow down"
    assert ladders[1][1] == 1
    assert ladders[2][1] == 1
    assert ladders[3][1] == 1


def test_hatch_is_floor_intersect_climb() -> None:
    # Floor strip beside a ladder on the same row = lid; shaft stays climb.
    cw, ch = 3, 4
    placements = [
        {"type": "floor_brick", "x": 2, "y": 1, "w": 1, "h": 1},
        {"type": "ladder", "x": 1, "y": 1, "w": 1, "h": 3},
    ]
    solid, ladders = stamp_collision(placements, cw, ch)
    assert solid[1][1] == 1, "hatch lid"
    assert solid[1][2] == 1, "office floor"
    assert solid[2][1] == 0, "shaft is not solid"
    assert ladders[1][1] == 1, "lid stays in the climb zone"
    assert ladders[2][1] == 1
    assert ladders[3][1] == 1


def test_floor_aabb_only_top_row() -> None:
    # Even if a floor object were taller, only the top is walkable.
    solid, _ = stamp_collision(
        [{"type": "floor_brick", "x": 0, "y": 1, "w": 3, "h": 4}], 3, 6
    )
    assert solid[1] == [1, 1, 1]
    assert solid[2] == [0, 0, 0]
    assert solid[3] == [0, 0, 0]


def test_earth_stamps_cells_not_aabb() -> None:
    # L-shape must not fill the missing corner.
    placements = [
        {
            "type": "earth",
            "x": 0,
            "y": 0,
            "w": 2,
            "h": 2,
            "_cells": [(0, 0), (0, 1), (1, 1)],
        }
    ]
    solid, _ = stamp_collision(placements, 2, 2)
    assert solid[0][0] == 1
    assert solid[0][1] == 0
    assert solid[1][0] == 1
    assert solid[1][1] == 1


def test_rasterize_and_catalog() -> None:
    placements = [{"type": "floor_brick", "x": 1, "y": 0, "w": 2, "h": 1}]
    grid = type_grid_from_placements(placements, 4, 1)
    assert grid[0] == ["", "floor_brick", "floor_brick", ""]
    assert "floor_brick" in TYPE_COLLISION
    assert "ladder" in TYPE_COLLISION


def test_earth_is_not_blue_brick() -> None:
    from object_types import is_blue_brick_char, is_earth_char, is_girder_char

    speckle = [list(r) for r in (
        "kkkkkkkk",
        "kkkkkkkk",
        "kkkkkkbk",
        "kkkkkkkk",
        "kkkkkkkk",
        "kkkkkkkk",
        "kkkkkkkk",
        "kbkkkkkk",
    )]
    paper = [list(r) for r in (
        "kkkkkkkk",
        "bkbbbbbb",
        "bkbbbbbb",
        "bkbbbbbb",
        "kkkkkkkk",
        "bbbbbkbb",
        "bbbbbkbb",
        "bbbbbkbb",
    )]
    girder = [list(r) for r in (
        "bbbbbwww",
        "bbbwwwww",
        "bbwwwwwb",
        "bwwwwwww",
        "bwwwwwwb",
        "wwwwwwbw",
        "wwwwwwwb",
        "wwwwwwbw",
    )]
    night = [list(r) for r in (
        "bbbbbbbb",
        "bbkbbbbb",
        "bbbbbbbb",
        "bbbbkbbb",
        "bbbbbbbb",
        "bbbbbbkb",
        "bbbbbbbb",
        "bbbbbbbb",
    )]
    assert is_earth_char(speckle)
    assert not is_blue_brick_char(speckle)
    assert is_blue_brick_char(paper)
    assert not is_earth_char(paper)
    assert is_girder_char(girder)
    assert not is_earth_char(night)


def test_earth_next_to_sky_stays_solid() -> None:
    from object_types import stamp_collision

    placements = [
        {
            "type": "earth",
            "x": 0,
            "y": 0,
            "w": 2,
            "h": 1,
            "_cells": [(0, 0), (1, 0)],
        },
        {"type": "sky", "x": 2, "y": 0, "w": 1, "h": 1},
    ]
    solid, _ = stamp_collision(placements, 3, 1)
    assert solid[0] == [1, 1, 0]


def main() -> None:
    test_type_table()
    test_stamp_from_rects()
    test_hatch_is_floor_intersect_climb()
    test_floor_aabb_only_top_row()
    test_earth_stamps_cells_not_aabb()
    test_rasterize_and_catalog()
    test_earth_is_not_blue_brick()
    test_earth_next_to_sky_stays_solid()
    print("test_role_collision: OK")


if __name__ == "__main__":
    main()
