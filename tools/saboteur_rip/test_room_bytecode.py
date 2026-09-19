#!/usr/bin/env python3
"""Bytecode interpreter tests — no mosaic, no colour heuristics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opcode_catalog import CELL, MARKERS, PLAYFIELD_H, SCREEN_W, START_RMAC, WALLPAPER_TYPE, dest_to_cell, type_id_ladder
from room_bytecode import (
    RoomObject,
    apply_room_paper,
    connect_ladders,
    indoor_force_mask,
    interpret_room,
    is_cave_room,
    is_generic_interior,
    is_indoor_room,
    is_outdoor_room,
    load_rooms,
    load_smap,
    load_stiles,
    place_world,
    reachable_indoor_mask,
    prepare,
    room_objects_for_world,
    snap_ladders,
    unique_world_objects,
)


def test_catalog_covers_jump_table() -> None:
    missing = [n for n in range(0o150) if n <= 0o147 and n not in MARKERS]
    assert not missing, f"missing markers {missing}"
    assert MARKERS[0o10].collision == "climb"
    assert MARKERS[0o23].prefab and MARKERS[0o23].prefab.name == "moon"
    assert MARKERS[0o34].prefab and MARKERS[0o34].prefab.name == "tree_left"
    assert MARKERS[0o40].prefab and MARKERS[0o40].prefab.name == "tree_right"
    assert MARKERS[0o22].layer == 0
    assert type_id_ladder(0o41) == "ladder_green"
    prepare()
    box = MARKERS[0o115].prefab
    assert box is not None
    assert len(box.tiles) == 11 * 7
    assert 0o377 in box.tiles


def test_dest_to_cell_moon() -> None:
    col, row = dest_to_cell(0o62245)
    assert 0 <= col < 32
    assert 0 <= row < 18


def test_room0_is_sky_and_moon() -> None:
    prepare()
    rooms = load_rooms()
    assert len(rooms) >= 200, len(rooms)
    objs, buf = interpret_room(rooms[0])
    kinds = [o.kind for o in objs]
    assert "fill_room" in kinds, kinds
    assert any(o.type_id == "moon" or o.kind == "moon" for o in objs), objs[:5]
    # Default fill tile 001 is sky paper.
    assert buf[0] in (0, 1, 0o10)


def test_ladders_are_module_pairs() -> None:
    prepare()
    rooms = load_rooms()
    found = None
    for seq in rooms:
        objs, _ = interpret_room(seq)
        for o in objs:
            if o.kind == "ladder":
                found = o
                break
        if found:
            break
    assert found is not None, "no ladder in 246 rooms"
    assert found.w == 16
    assert found.module[0] == 16
    assert found.collision == "climb"
    assert found.h >= 8


def test_smap_grid() -> None:
    smap = load_smap()
    assert len(smap) == 32, len(smap)
    assert all(len(r) == 32 for r in smap)
    # RMDN=0 is virtual sky: the engine never reads MAP and always uses room 0.
    assert smap[0] == [0] * 32
    # MAP row 0 (RMDN=1) starts at K70632, not the K70572 leftover row.
    assert smap[1][7] == 0o144, smap[1][:16]
    assert smap[1][8] == 0o145
    assert smap[1][0] == 0
    # Last MAP row (RMDN=31) is present; previously truncated at 24/28.
    assert any(v for v in smap[31]), smap[31]
    rooms_used = sum(1 for row in smap for v in row if v)
    assert rooms_used > 50, rooms_used


def test_place_world_uses_playfield_stride() -> None:
    prepare()
    rooms = load_rooms()
    objs, _ = interpret_room(rooms[0])
    placed = place_world(objs, 1, 2)
    assert placed
    assert placed[0].x == objs[0].x + SCREEN_W
    assert placed[0].y == objs[0].y + 2 * PLAYFIELD_H
    assert placed[0].y != objs[0].y + 2 * 192


def test_moon_is_unique_world_object() -> None:
    prepare()
    rooms = load_rooms()
    objs, _ = interpret_room(rooms[0])
    assert any(o.type_id == "moon" for o in objs)
    assert not any(o.type_id == "moon" for o in room_objects_for_world(objs))
    unique = unique_world_objects(rooms)
    moons = [o for o in unique if o.type_id == "moon"]
    assert len(moons) == 1
    moon = moons[0]
    local = next(o for o in objs if o.type_id == "moon")
    assert moon.x == local.x + START_RMAC * SCREEN_W
    assert moon.y == local.y


def test_indoor_wallpaper_is_pale_yellow_not_sky() -> None:
    prepare()
    rooms = load_rooms()
    sky = apply_room_paper(room_objects_for_world(interpret_room(rooms[0])[0]))
    assert all(o.type_id != WALLPAPER_TYPE for o in sky)
    assert any(o.kind == "fill_room" and o.type_id != WALLPAPER_TYPE for o in sky)

    indoor = apply_room_paper(room_objects_for_world(interpret_room(rooms[1])[0]))
    assert is_indoor_room(interpret_room(rooms[1])[0])
    papers = [o for o in indoor if o.type_id == WALLPAPER_TYPE]
    assert len(papers) == 1
    assert papers[0].w == SCREEN_W
    assert papers[0].h == PLAYFIELD_H
    assert papers[0].collision == "none"

    outdoor = apply_room_paper(room_objects_for_world(interpret_room(rooms[5])[0]))
    assert not is_indoor_room(interpret_room(rooms[5])[0])
    assert not is_cave_room(interpret_room(rooms[5])[0])
    assert all(o.type_id != WALLPAPER_TYPE for o in outdoor)
    assert any(o.kind == "fill_room" for o in outdoor)

    cave_seq = next(seq for seq in rooms if is_cave_room(interpret_room(seq)[0]))
    cave = apply_room_paper(room_objects_for_world(interpret_room(cave_seq)[0]))
    assert all(o.type_id != WALLPAPER_TYPE for o in cave)
    assert any(o.kind == "stile" for o in cave)

    tree_seq = next(
        seq
        for seq in rooms
        if any(o.type_id.startswith("tree_") for o in interpret_room(seq)[0])
    )
    tree_objs = interpret_room(tree_seq)[0]
    assert is_outdoor_room(tree_objs)
    assert not is_indoor_room(tree_objs)
    outdoor_tree = apply_room_paper(room_objects_for_world(tree_objs), force_indoor=True)
    assert all(o.type_id != WALLPAPER_TYPE for o in outdoor_tree)
    assert any(o.kind == "fill_room" for o in outdoor_tree)

    cliff = interpret_room(rooms[4])[0]
    assert is_outdoor_room(cliff)
    assert not is_indoor_room(cliff)
    cliff_paper = apply_room_paper(room_objects_for_world(cliff), force_indoor=True)
    assert all(o.type_id != WALLPAPER_TYPE for o in cliff_paper)
    smap = load_smap()
    force = indoor_force_mask(smap, rooms)
    assert not force[9][5], "cliff shaft at (5,9) is not interior paper"

    roof = interpret_room(rooms[8])[0]
    assert is_outdoor_room(roof)
    assert not is_indoor_room(roof)
    assert all(
        o.type_id != WALLPAPER_TYPE
        for o in apply_room_paper(room_objects_for_world(roof), force_indoor=True)
    )

    slope = interpret_room(rooms[68])[0]
    assert is_indoor_room(slope)
    assert not is_outdoor_room(slope)
    slope_paper = apply_room_paper(room_objects_for_world(slope))
    assert any(o.type_id == WALLPAPER_TYPE for o in slope_paper)

    # Floors/windows without furniture are still the green rooms, not sky.
    floors = interpret_room(rooms[80])[0]
    assert is_indoor_room(floors)
    assert not is_outdoor_room(floors)
    assert not is_generic_interior(floors)
    assert any(
        o.type_id == WALLPAPER_TYPE
        for o in apply_room_paper(room_objects_for_world(floors))
    )
    # Tall outer wall: sky outside, brick on the interior sliver.
    facade = interpret_room(rooms[102])[0]
    assert not is_indoor_room(facade)
    facade_paper = apply_room_paper(room_objects_for_world(facade))
    papers = [o for o in facade_paper if o.type_id == WALLPAPER_TYPE]
    assert len(papers) == 1
    assert papers[0].w < SCREEN_W
    assert papers[0].x >= 200
    windows = interpret_room(rooms[132])[0]
    assert is_indoor_room(windows)
    assert not is_outdoor_room(windows)
    assert any(
        o.type_id == WALLPAPER_TYPE
        for o in apply_room_paper(room_objects_for_world(windows))
    )
    # Sky-tile earth without windows is the courtyard cutout.
    courtyard = interpret_room(rooms[124])[0]
    assert is_outdoor_room(courtyard)
    assert not is_indoor_room(courtyard)
    assert all(
        o.type_id != WALLPAPER_TYPE
        for o in apply_room_paper(room_objects_for_world(courtyard))
    )


def test_cave_filler_room1_is_not_a_building_floor() -> None:
    prepare()
    rooms = load_rooms()
    smap = load_smap()
    assert is_generic_interior(interpret_room(rooms[1])[0])
    assert not is_generic_interior(interpret_room(rooms[71])[0])
    reached = reachable_indoor_mask(smap, rooms)
    assert reached[10][5], "crate warehouse (5,10) is part of the building"
    assert not reached[16][21], "cave MAP=1 island at (21,16) is not a walk-in office"


def test_fill_h_split_on_row_wrap() -> None:
    prepare()
    rooms = load_rooms()
    for seq in rooms:
        objs, _ = interpret_room(seq)
        for o in objs:
            if o.kind == "fill_h":
                assert o.h == CELL, (o.x, o.y, o.w, o.h)


def test_ladders_snap_to_playfield_seam() -> None:
    prepare()
    rooms = load_rooms()
    found = None
    for seq in rooms:
        objs, _ = interpret_room(seq)
        for o in objs:
            if o.kind == "ladder" and o.y <= CELL and o.h >= 96:
                found = o
                break
        if found:
            break
    assert found is not None
    snapped = snap_ladders([found])[0]
    assert snapped.y == 0
    assert snapped.y + snapped.h == PLAYFIELD_H

    cliff = snap_ladders(room_objects_for_world(interpret_room(rooms[4])[0]))
    white = next(o for o in cliff if o.kind == "ladder")
    assert white.y == 0
    assert white.h == 120, (white.y, white.h)


def test_connect_ladders_reaches_nearby_floors() -> None:
    ladder = RoomObject(
        "ladder",
        "ladder_green",
        3,
        "climb",
        "module_repeat",
        80,
        40,
        16,
        48,
        tile=0o054,
        tiles=(0o054, 0o055),
        module=(16, CELL),
        axis="y",
    )
    ceiling = RoomObject(
        "fill_h",
        "chr_372",
        2,
        "floor",
        "module_repeat",
        0,
        8,
        256,
        CELL,
        tile=0o372,
        module=(CELL, CELL),
        axis="x",
    )
    floor = RoomObject(
        "fill_h",
        "chr_372",
        2,
        "floor",
        "module_repeat",
        0,
        112,
        256,
        CELL,
        tile=0o372,
        module=(CELL, CELL),
        axis="x",
    )
    connected = connect_ladders([ceiling, ladder, floor])
    shaft = next(o for o in connected if o.kind == "ladder")
    assert shaft.y == ceiling.y + ceiling.h
    assert shaft.y + shaft.h == floor.y


def test_stiles_count() -> None:
    stiles = load_stiles()
    assert len(stiles) == 25, len(stiles)
    assert all(len(s) >= 48 for s in stiles)


def main() -> None:
    test_catalog_covers_jump_table()
    test_dest_to_cell_moon()
    test_room0_is_sky_and_moon()
    test_ladders_are_module_pairs()
    test_smap_grid()
    test_place_world_uses_playfield_stride()
    test_moon_is_unique_world_object()
    test_indoor_wallpaper_is_pale_yellow_not_sky()
    test_cave_filler_room1_is_not_a_building_floor()
    test_fill_h_split_on_row_wrap()
    test_ladders_snap_to_playfield_seam()
    test_connect_ladders_reaches_nearby_floors()
    test_stiles_count()
    print("test_room_bytecode: OK")


if __name__ == "__main__":
    main()
