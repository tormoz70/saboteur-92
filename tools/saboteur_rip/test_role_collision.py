#!/usr/bin/env python3
"""Collision is a marker property, then stamped from object bounds."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opcode_catalog import MARKERS
from room_bytecode import RoomObject
from decompose_world import apply_hatches, stamp_world


def test_catalog_collision_table() -> None:
    assert MARKERS[0o00].collision == "floor"
    assert MARKERS[0o03].collision == "none"
    assert MARKERS[0o10].collision == "climb"
    assert MARKERS[0o21].collision == "machine"
    assert MARKERS[0o23].collision == "none"
    assert MARKERS[0o50].collision == "none"
    assert MARKERS[0o142].collision == "none"


def test_stamp_floor_is_one_cell_thick() -> None:
    floor = RoomObject("fill_h", "chr_001", 2, "floor", "module_repeat", 8, 32, 16, 8)
    solid, climb = stamp_world([floor], 1, 1)
    assert solid[4][1] == 1
    assert solid[4][2] == 1
    assert solid[5][1] == 0, "floor does not grow down"
    assert climb[4][1] == 0


def test_stamp_ladder_is_climb() -> None:
    ladder = RoomObject(
        "ladder", "ladder_green", 3, "climb", "module_repeat", 8, 8, 16, 32, tiles=(0o54, 0o55)
    )
    solid, climb = stamp_world([ladder], 1, 1)
    assert climb[1][1] == 1
    assert climb[2][1] == 1
    assert solid[1][1] == 0


def test_hatch_lid_from_climb_beside_floor() -> None:
    floor = RoomObject("fill_h", "chr_001", 2, "floor", "module_repeat", 16, 16, 8, 8)
    ladder = RoomObject(
        "ladder", "ladder_green", 3, "climb", "module_repeat", 0, 16, 16, 32, tiles=(0o54, 0o55)
    )
    solid, climb = stamp_world([floor, ladder], 1, 1)
    apply_hatches(solid, climb)
    assert climb[2][0] == 1
    assert solid[2][2] == 1, "adjacent floor cell"
    assert solid[2][1] == 1, "hatch lid over the climb cell beside the floor"


def main() -> None:
    test_catalog_collision_table()
    test_stamp_floor_is_one_cell_thick()
    test_stamp_ladder_is_climb()
    test_hatch_lid_from_climb_beside_floor()
    print("test_role_collision: OK")


if __name__ == "__main__":
    main()
