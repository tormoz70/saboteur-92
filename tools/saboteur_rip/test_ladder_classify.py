#!/usr/bin/env python3
"""Pixel-pattern checks for Saboteur II ladder tiles."""
from __future__ import annotations

from build_s2_world import (
    _is_green_rail_tile,
    _is_sky_rail_tile,
    _is_x_lattice_tile,
    cell_is_ladder,
)

SKY_LEFT = [
    list("wwwbwwww"),
    list("wwwbwbbb"),
    list("wwwbbbbb"),
    list("wwwbbbbb"),
    list("wwwbwwww"),
    list("wwwbwbbb"),
    list("wwwbbbbb"),
    list("wwwbbbbb"),
]
SKY_RIGHT = [
    list("wwwwbwww"),
    list("bbbwbwww"),
    list("bbbbbwww"),
    list("bbbbbwww"),
    list("wwwwbwww"),
    list("bbbwbwww"),
    list("bbbbbwww"),
    list("bbbbbwww"),
]
GREEN_LEFT = [
    list("gkkgkkkk"),
    list("gkkgkkkk"),
    list("gkkgkggg"),
    list("gkkgggkg"),
    list("gkkgkgkg"),
    list("gkkgggkg"),
    list("gkkgkkkg"),
    list("gkkggggg"),
]
X_LATTICE = [
    list("wwbbbwww"),
    list("wwbbwbww"),
    list("wwbwbbww"),
    list("wwwbbbww"),
    list("wwwbbbww"),
    list("wwbwbbww"),
    list("wwbbwbww"),
    list("wwbbbwww"),
]
SKY_NO_RUNGS = [list("wwwbbbbb") for _ in range(8)]
WHITE_WALL = [list("wwwwwwww") for _ in range(8)]


class FakePx:
    """8×8 ink grid exposed through the mosaic pixel callback."""

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows

    def __getitem__(self, xy: tuple[int, int]) -> tuple[int, int, int]:
        x, y = xy
        ink = self.rows[y][x]
        return {
            "k": (0, 0, 0),
            "b": (0, 0, 255),
            "g": (0, 255, 0),
            "c": (0, 255, 255),
            "w": (255, 255, 255),
        }[ink]


def test_sky_rail_pair_is_ladder() -> None:
    assert _is_sky_rail_tile(SKY_LEFT)
    assert _is_sky_rail_tile(SKY_RIGHT)
    assert not _is_green_rail_tile(SKY_LEFT)
    assert not _is_x_lattice_tile(SKY_LEFT)
    assert cell_is_ladder(FakePx(SKY_LEFT), 0, 0)
    assert cell_is_ladder(FakePx(SKY_RIGHT), 0, 0)


def test_green_and_lattice_still_match() -> None:
    assert _is_green_rail_tile(GREEN_LEFT)
    assert _is_x_lattice_tile(X_LATTICE)
    assert not _is_sky_rail_tile(GREEN_LEFT)
    assert not _is_sky_rail_tile(X_LATTICE)


def test_sky_rail_rejects_walls_and_bare_posts() -> None:
    assert not _is_sky_rail_tile(SKY_NO_RUNGS)
    assert not _is_sky_rail_tile(WHITE_WALL)
    assert not cell_is_ladder(FakePx(SKY_NO_RUNGS), 0, 0)


if __name__ == "__main__":
    test_sky_rail_pair_is_ladder()
    test_green_and_lattice_still_match()
    test_sky_rail_rejects_walls_and_bare_posts()
    print("test_ladder_classify: ok")
