#!/usr/bin/env python3
"""Fingerprint checks for floors / earth — collision is stamped from object bounds."""
from __future__ import annotations

from object_types import (
    is_diamond_floor_tile,
    is_earth_char,
    is_blue_brick_char,
    is_girder_char,
    is_x_lattice_tile,
    is_sky_rail_tile,
    stamp_collision,
)
from test_ladder_classify import SKY_LEFT, X_LATTICE, FakePx
from build_s2_world import cell_is_diamond_floor, _is_diamond_floor_tile

DIAMOND_FLOOR = [
    list("wwwwwwww"),
    list("wwwwwwww"),
    list("wbbbbbbw"),
    list("bwbbbbwb"),
    list("bbwbbwbb"),
    list("bbbwwbbb"),
    list("wwwwwwww"),
    list("wwwwwwww"),
]
SKY_BAR = [list("wwwwwwww"), list("wwwwwwww")] + [list("bbbbbbbb") for _ in range(6)]
WINDOW = [
    list("wwwwwwww"),
    list("wbbbbbbw"),
    list("wbwwwwbw"),
    list("wbwwwwbw"),
    list("wbwwwbbw"),
    list("wbwwwbbw"),
    list("wbbbbbbw"),
    list("wwwwwwww"),
]
GIRDER_LIP = [
    list("bbbbbwww"),
    list("bbbwwwww"),
    list("bbwwwwwb"),
    list("bwwwwwww"),
    list("bwwwwwwb"),
    list("wwwwwwbw"),
    list("wwwwwwwb"),
    list("wwwwwwbw"),
]
SPECKLE = [
    list("kkkkkkkk"),
    list("kkkkkkkk"),
    list("kkkkkkbk"),
    list("kkkkkkkk"),
    list("kkkkkkkk"),
    list("kkkkkkkk"),
    list("kkkkkkkk"),
    list("kbkkkkkk"),
]
PAPER = [
    list("kkkkkkkk"),
    list("bkbbbbbb"),
    list("bkbbbbbb"),
    list("bkbbbbbb"),
    list("kkkkkkkk"),
    list("bbbbbkbb"),
    list("bbbbbkbb"),
    list("bbbbbkbb"),
]


def test_diamond_slab_is_floor() -> None:
    assert is_diamond_floor_tile(DIAMOND_FLOOR)
    assert _is_diamond_floor_tile(DIAMOND_FLOOR)
    assert cell_is_diamond_floor(FakePx(DIAMOND_FLOOR), 0, 0)


def test_diamond_rejects_rails_windows_and_bars() -> None:
    assert not is_diamond_floor_tile(SKY_LEFT)
    assert not is_diamond_floor_tile(X_LATTICE)
    assert not is_diamond_floor_tile(SKY_BAR)
    assert not is_diamond_floor_tile(WINDOW)
    assert not is_sky_rail_tile(DIAMOND_FLOOR)
    assert not is_x_lattice_tile(DIAMOND_FLOOR)


def test_girder_is_not_lattice() -> None:
    assert is_girder_char(GIRDER_LIP)
    assert not is_girder_char(X_LATTICE)
    assert is_x_lattice_tile(X_LATTICE)


def test_earth_vs_wallpaper() -> None:
    assert is_earth_char(SPECKLE)
    assert not is_blue_brick_char(SPECKLE)
    assert is_blue_brick_char(PAPER)
    assert not is_earth_char(PAPER)


def test_stamp_does_not_thicken() -> None:
    solid, _ = stamp_collision(
        [{"type": "floor_brick", "x": 0, "y": 1, "w": 4, "h": 1}], 4, 5
    )
    assert solid[1] == [1, 1, 1, 1]
    assert solid[2] == [0, 0, 0, 0]


def main() -> None:
    test_diamond_slab_is_floor()
    test_diamond_rejects_rails_windows_and_bars()
    test_girder_is_not_lattice()
    test_earth_vs_wallpaper()
    test_stamp_does_not_thicken()
    print("test_floor_classify: OK")


if __name__ == "__main__":
    main()
