#!/usr/bin/env python3
"""Pixel-pattern checks for diamond slabs, cave tunnels, and red posts."""
from __future__ import annotations

from build_s2_world import (
    _apply_cave_gaps,
    _apply_cave_ground,
    _apply_cave_tunnels,
    _band_is_hall_side_step,
    _clear_hall_bites,
    _clear_standing_stubs,
    _clear_red_pillars,
    _clear_walkable_decor,
    _floor_is_hall_step,
    _is_cave_paper,
    _is_cave_void,
    _is_diamond_floor_tile,
    _is_sky_rail_tile,
    _is_speckled_earth,
    _is_x_lattice_tile,
    _paper_on_row_mask,
    cell_is_crate,
    cell_is_diamond_floor,
    cell_is_red_brick,
    fill_cave_earth,
    find_cave_gaps,
    find_cave_tunnels,
    find_red_pillars,
)
from test_ladder_classify import SKY_LEFT, X_LATTICE, FakePx

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


def test_diamond_slab_is_floor() -> None:
    assert _is_diamond_floor_tile(DIAMOND_FLOOR)
    assert cell_is_diamond_floor(FakePx(DIAMOND_FLOOR), 0, 0)


def test_diamond_rejects_rails_windows_and_bars() -> None:
    assert not _is_diamond_floor_tile(SKY_LEFT)
    assert not _is_diamond_floor_tile(X_LATTICE)
    assert not _is_diamond_floor_tile(SKY_BAR)
    assert not _is_diamond_floor_tile(WINDOW)
    assert not _is_sky_rail_tile(DIAMOND_FLOOR)
    assert not _is_x_lattice_tile(DIAMOND_FLOOR)


def _counts(rows: list[list[str]]) -> dict[str, int]:
    out = {k: 0 for k in "kbgrcywmo"}
    for row in rows:
        for p in row:
            out[p] += 1
    return out


BRICK = [list("bbbbbbbb") for _ in range(7)] + [list("kkkkkkkk")]
VOID = [list("kkkkkkkk") for _ in range(8)]
# Speckled earth is also `_is_cave_void` (k>=24, b<20). Hall-bite punches
# must not treat it as empty cave air.
SPECKLED = [list("kkkkkkkk") for _ in range(7)] + [list("kbkkkkkk")]
CYAN = [list("cccccccc") for _ in range(8)]
GREEN = [list("gggggggg") for _ in range(5)] + [list("kkkkkkkk") for _ in range(3)]
INK_RGB = {
    "k": (0, 0, 0),
    "b": (0, 0, 255),
    "c": (0, 255, 255),
    "g": (0, 255, 0),
    "r": (255, 0, 0),
    "y": (255, 255, 0),
    "w": (255, 255, 255),
}


class CellGridPx:
    """Each letter is an 8x8 block; `tiles` maps letter -> 8x8 ink rows."""

    def __init__(self, layout: list[str], tiles: dict[str, list[list[str]]]) -> None:
        self.layout = layout
        self.tiles = tiles

    def __getitem__(self, xy: tuple[int, int]) -> tuple[int, int, int]:
        x, y = xy
        letter = self.layout[y // 8][x // 8]
        ink = self.tiles[letter][y % 8][x % 8]
        return INK_RGB[ink]


def test_cave_paper_and_void_counts() -> None:
    assert _is_cave_paper(_counts(BRICK))
    assert _is_cave_void(_counts(VOID))
    assert _is_speckled_earth(_counts(SPECKLED))
    assert _is_cave_void(_counts(SPECKLED))
    assert not _is_cave_paper(_counts(VOID))
    assert not _is_cave_paper(_counts(CYAN))
    assert not _is_cave_void(_counts(BRICK))


def test_cave_tunnel_floor_and_ceiling() -> None:
    # 10-wide corridor: void, 6-cell blue brick, void. Interior stays air.
    layout = [
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK}
    px = CellGridPx(layout, tiles)
    biomes = ["cave"]
    hits = find_cave_tunnels(px, 12, 10, biomes, 1)
    cols = sorted({cx for cx, _y0, _y1 in hits})
    assert cols == list(range(1, 11))
    assert all(y0 == 2 and y1 == 7 for _cx, y0, y1 in hits)

    solid = [[1] * 12 for _ in range(10)]
    ceil_n, floor_n, punched = _apply_cave_tunnels(px, solid, biomes)
    assert ceil_n == 0
    assert floor_n == 0
    assert punched > 0
    for cx in range(1, 11):
        assert solid[2][cx] == 1
        assert solid[7][cx] == 0, "old paper lip is no longer the floor"
        assert solid[9][cx] == 1, "floor is two cells below the last brick"
        assert all(solid[cy][cx] == 0 for cy in range(3, 9))


def test_cave_tunnel_rejects_wallpaper_beside_green_room() -> None:
    # Basement far-wall: blue paper over void, green interior to the right.
    # That is not a cave corridor; painting y1 as a floor makes a chest-high wall.
    layout = [
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbg",
        "kbbbbbbbbbbg",
        "kbbbbbbbbbbg",
        "kbbbbbbbbbbg",
        "kbbbbbbbbbbg",
        "kbbbbbbbbbbg",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK, "g": GREEN}
    px = CellGridPx(layout, tiles)
    assert find_cave_tunnels(px, 12, 10, ["cave"], 1) == []


def test_cave_tunnel_rejects_cyan_and_short_runs() -> None:
    layout = [
        "kkkkkkkk",
        "cccccccc",
        "cccccccc",
        "cccccccc",
        "cccccccc",
        "cccccccc",
        "cccccccc",
        "kkkkkkkk",
        "kbbbbbkk",
        "kbbbbbkk",
        "kbbbbbkk",
        "kbbbbbkk",
        "kbbbbbkk",
        "kbbbbbkk",
        "kkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK, "c": CYAN}
    px = CellGridPx(layout, tiles)
    hits = find_cave_tunnels(px, 8, 15, ["cave"], 1)
    assert hits == []


def test_speckled_under_paper_is_not_a_floor_lip() -> None:
    """Gap finding climbs through hall earth; the lid must not be wallpaper."""
    layout = [
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kssssssssssk",
        "kssssssssssk",
        "kssssssssssk",
        "kssssssssssk",
        "kssssssssssk",
        "kssssssssssk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK, "s": SPECKLED}
    px = CellGridPx(layout, tiles)
    solid = [[0] * 12 for _ in range(16)]
    _apply_cave_ground(px, solid, ["cave"])
    _apply_cave_gaps(px, solid, ["cave"])
    for cx in range(1, 11):
        assert solid[6][cx] == 0, "last wallpaper cell must stay walkable %s" % cx
        assert solid[7][cx] == 1, "speckled earth is the hall floor %s" % cx


def test_flooded_gap_has_floor_and_ceiling() -> None:
    # Brick masses sandwich a black gap (air over water). Ceiling is the
    # underside of the upper mass; floor is the top of the lower mass.
    layout = [
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK}
    px = CellGridPx(layout, tiles)
    biomes = ["cave"]
    hits = find_cave_gaps(px, 12, 12, biomes, 1)
    cols = sorted({cx for cx, _y0, _y1 in hits})
    assert cols == list(range(1, 11))
    assert all(y0 == 2 and y1 == 9 for _cx, y0, y1 in hits)

    solid = [[1] * 12 for _ in range(12)]
    ceil_n, floor_n, punched = _apply_cave_gaps(px, solid, biomes)
    assert ceil_n == 0
    assert floor_n == 0
    assert punched > 0
    for cx in range(1, 11):
        assert solid[2][cx] == 1
        assert solid[9][cx] == 1
        assert all(solid[cy][cx] == 0 for cy in range(3, 9))


def test_stacked_tunnels_keep_dropped_floor_after_gaps() -> None:
    """Void between two brick bands looks like a flooded gap.

    Applying gaps first paints the upper paper lip as a floor. Tunnels must
    still drop that lip two cells so Nina fits under the ceiling.
    """
    layout = [
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK}
    px = CellGridPx(layout, tiles)
    biomes = ["cave"]
    solid = [[1] * 12 for _ in range(15)]
    _apply_cave_gaps(px, solid, biomes)
    _apply_cave_tunnels(px, solid, biomes)
    for cx in range(1, 11):
        assert solid[1][cx] == 1, "ceiling"
        assert solid[6][cx] == 0, "paper lip must not stay the floor"
        assert solid[8][cx] == 1, "floor two cells below the last brick"


RED_POST = [list("kkkrrkrk") for _ in range(8)]
RED_FLOOR = [
    list("rrrrkrrr"),
    list("rrrrkrrr"),
    list("rrrrkrrr"),
    list("kkkkkkkk"),
    list("krrrrrrr"),
    list("krrrrrrr"),
    list("krrrrrrr"),
    list("kkkkkkkk"),
]


def test_red_post_is_brick_but_not_a_floor() -> None:
    assert cell_is_red_brick(_counts(RED_POST))
    assert cell_is_red_brick(_counts(RED_FLOOR))


def test_red_pillars_are_passable() -> None:
    layout = [
        "k" * 12,
        "k" * 5 + "p" + "k" * 6,
        "k" * 5 + "p" + "k" * 6,
        "k" * 5 + "p" + "k" * 6,
        "k" * 5 + "p" + "k" * 6,
        "k" * 5 + "p" + "k" * 6,
        "F" * 12,
        "F" * 12,
        "k" * 12,
    ]
    tiles = {"k": VOID, "p": RED_POST, "F": RED_FLOOR}
    px = CellGridPx(layout, tiles)
    hits = find_red_pillars(px, 12, 9)
    assert hits == [(5, 1, 5)]
    solid = [[1] * 12 for _ in range(9)]
    cleared = _clear_red_pillars(px, solid)
    assert cleared > 0
    for cy in range(1, 6):
        assert solid[cy][5] == 0
    assert all(solid[6][cx] == 1 for cx in range(12))


CRATE = [
    list("yyyykkyk"),
    list("ykkyyyyy"),
    list("yyyykkyk"),
    list("kkkkkkkk"),
    list("yyyykkyk"),
    list("ykkyyyyy"),
    list("yyyykkyk"),
    list("kkkkkkkk"),
]


def test_crate_counts_as_furniture() -> None:
    assert cell_is_crate(_counts(CRATE))
    assert not _is_cave_paper(_counts(CRATE))


def test_blue_brick_and_crates_are_not_cave_rock() -> None:
    layout = [
        "kkkkkkkkkk",
        "kbbbbbbkk",
        "kbbccbbkk",
        "kbbccbbkk",
        "kbbbbbbkk",
        "kkkkkkkkkk",
    ]
    # pad rows to equal width
    layout = [row.ljust(10, "k") for row in layout]
    tiles = {"k": VOID, "b": BRICK, "c": CRATE}
    px = CellGridPx(layout, tiles)
    solid = [[0] * 10 for _ in range(6)]
    fill_cave_earth(solid, ["cave"], 1, px)
    for cy in range(1, 5):
        for cx in range(1, 7):
            letter = layout[cy][cx]
            if letter in "bc":
                assert solid[cy][cx] == 0, (cx, cy, letter)
    assert solid[0][1] == 1


def test_clear_paper_then_tunnel_keeps_lining() -> None:
    layout = [
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kbbbbbbbbbbk",
        "kkkkkkkkkkkk",
        "kkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK}
    px = CellGridPx(layout, tiles)
    solid = [[1] * 12 for _ in range(10)]
    cleared = _clear_walkable_decor(px, solid)
    assert cleared > 0
    for cx in range(1, 11):
        assert all(solid[cy][cx] == 0 for cy in range(2, 8))
    _apply_cave_tunnels(px, solid, ["cave"])
    for cx in range(1, 11):
        assert solid[2][cx] == 1
        assert solid[7][cx] == 0, "old paper lip is no longer the floor"
        assert solid[9][cx] == 1, "floor is two cells below the last brick"
        assert all(solid[cy][cx] == 0 for cy in range(3, 9))


def test_cave_hall_black_is_ground() -> None:
    # Taller than a thin tunnel: blue brick hall, black ceiling on the right,
    # black floor below. Void must be rock so the jagged edges are walkable
    # surfaces; wallpaper stays air.
    layout = [
        "kkkkkkkkkkkkkkkk",
        "kkkkkkkkkkkkkkkk",
        "bbbbbbbbkkkkkkkk",
        "bbbbbbbbbbkkkkkk",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "kkkkkkkkkkkkkkkk",
        "kkkkkkkkkkkkkkkk",
        "kkkkkkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK}
    px = CellGridPx(layout, tiles)
    w, h = 16, 16
    solid = [[0] * w for _ in range(h)]
    added = _apply_cave_ground(px, solid, ["cave"])
    assert added > 0
    assert solid[0][8] == 1
    assert solid[2][12] == 1, "ceiling mass on the right"
    assert solid[14][8] == 1, "floor mass"
    assert solid[6][4] == 0, "blue brick hall stays walkable"
    assert solid[3][2] == 0


def test_hall_side_step_is_not_a_tunnel_floor() -> None:
    """Shorter paper column next to a taller hall is an edge, not a floor."""
    paper = [[False] * 8 for _ in range(12)]
    for cy in range(2, 10):
        paper[cy][3] = True
        paper[cy][4] = True
    for cy in range(2, 7):
        paper[cy][2] = True
    assert _band_is_hall_side_step(paper, 2, 2, 6, 8, 12)
    assert not _band_is_hall_side_step(paper, 3, 2, 9, 8, 12)
    # One-cell lining noise is a real corridor, not a hall.
    jag = [[False] * 8 for _ in range(12)]
    for cy in range(2, 9):
        jag[cy][3] = True
        jag[cy][4] = True
    for cy in range(2, 8):
        jag[cy][2] = True
    assert not _band_is_hall_side_step(jag, 2, 2, 7, 8, 12)


def test_wide_tunnel_beside_hall_is_not_a_hall_step() -> None:
    """A real corridor keeps its floor even when a taller hall is next door."""
    paper = [[False] * 16 for _ in range(14)]
    for cy in range(2, 8):
        for cx in range(1, 9):
            paper[cy][cx] = True
    for cy in range(2, 13):
        for cx in range(9, 14):
            paper[cy][cx] = True
    assert not _floor_is_hall_step(paper, 8, 2, 7, 16, 14)
    assert not _band_is_hall_side_step(paper, 8, 2, 7, 16, 14)
    # Two short columns on the hall's own edge are still a step.
    jag = [[False] * 16 for _ in range(14)]
    for cy in range(2, 13):
        for cx in range(1, 11):
            jag[cy][cx] = True
    for cy in range(2, 8):
        jag[cy][11] = True
        jag[cy][12] = True
    assert _floor_is_hall_step(jag, 11, 2, 7, 16, 14)


def test_tunnel_beside_hall_keeps_lining() -> None:
    layout = [
        "kkkkkkkkkkkkkkkk",
        "kkkkkkkkkkkkkkkk",
        "kbbbbbbbbbbbbbbk",
        "kbbbbbbbbbbbbbbk",
        "kbbbbbbbbbbbbbbk",
        "kbbbbbbbbbbbbbbk",
        "kbbbbbbbbbbbbbbk",
        "kbbbbbbbbbbbbbbk",
        "kkkkkkkkkkbbbbbk",
        "kkkkkkkkkkbbbbbk",
        "kkkkkkkkkkbbbbbk",
        "kkkkkkkkkkbbbbbk",
        "kkkkkkkkkkkkkkkk",
        "kkkkkkkkkkkkkkkk",
    ]
    tiles = {"k": VOID, "b": BRICK}
    px = CellGridPx(layout, tiles)
    solid = [[0] * 16 for _ in range(14)]
    _apply_cave_tunnels(px, solid, ["cave"])
    for cx in range(1, 9):
        assert solid[2][cx] == 1, cx
        assert solid[7][cx] == 0, "paper lip is walkable %s" % cx
        assert solid[9][cx] == 1, "dropped floor %s" % cx
    _clear_hall_bites(px, solid, ["cave"])
    for cx in range(1, 9):
        assert solid[9][cx] == 1, "tunnel floor beside hall must stay %s" % cx


def test_interior_speckled_next_to_paper_stays_solid() -> None:
    """Interior earth is also `_is_cave_void`; hall-bite punch must skip it."""
    layout = [
        "kkkkkkkkkk",
        "bbbbbbbbkk",
        "bbbbbbbbkk",
        "bbbbbbbbkk",
        "ssssssssss",
        "ssssssssss",
    ]
    tiles = {"k": VOID, "b": BRICK, "s": SPECKLED}
    px = CellGridPx(layout, tiles)
    solid = [[1] * 10 for _ in range(6)]
    _clear_hall_bites(px, solid, ["interior"])
    for cx in range(10):
        assert solid[4][cx] == 1, cx
        assert solid[5][cx] == 1, cx


def test_standing_stub_above_hall_floor_is_cleared() -> None:
    """Lone cell two rows above a floor, with air beside it, is not a wall."""
    h, w = 8, 8
    solid = [[0] * w for _ in range(h)]
    for cx in range(w):
        solid[6][cx] = 1
    solid[3][3] = 1
    biomes = ["cave"]
    cleared = _clear_standing_stubs(solid, biomes)
    assert cleared == 1
    assert solid[3][3] == 0
    assert solid[6][3] == 1
    # A real 2-cell step stays: connected down into the floor stack.
    solid[5][4] = 1
    solid[6][4] = 1
    assert _clear_standing_stubs(solid, biomes) == 0
    assert solid[5][4] == 1


def test_paper_on_row_mask_reach() -> None:
    paper = [[False] * 10 for _ in range(3)]
    paper[1][2] = True
    assert _paper_on_row_mask(paper, 5, 1, 10, reach=4)
    assert not _paper_on_row_mask(paper, 8, 1, 10, reach=4)
    assert not _paper_on_row_mask(paper, 5, 0, 10, reach=4)


if __name__ == "__main__":
    test_diamond_slab_is_floor()
    test_diamond_rejects_rails_windows_and_bars()
    test_cave_paper_and_void_counts()
    test_cave_tunnel_floor_and_ceiling()
    test_cave_tunnel_rejects_wallpaper_beside_green_room()
    test_cave_tunnel_rejects_cyan_and_short_runs()
    test_speckled_under_paper_is_not_a_floor_lip()
    test_flooded_gap_has_floor_and_ceiling()
    test_stacked_tunnels_keep_dropped_floor_after_gaps()
    test_red_post_is_brick_but_not_a_floor()
    test_red_pillars_are_passable()
    test_crate_counts_as_furniture()
    test_blue_brick_and_crates_are_not_cave_rock()
    test_clear_paper_then_tunnel_keeps_lining()
    test_cave_hall_black_is_ground()
    test_hall_side_step_is_not_a_tunnel_floor()
    test_wide_tunnel_beside_hall_is_not_a_hall_step()
    test_tunnel_beside_hall_keeps_lining()
    test_interior_speckled_next_to_paper_stays_solid()
    test_paper_on_row_mask_reach()
    test_standing_stub_above_hall_floor_is_cleared()
    print("test_floor_classify: ok")
