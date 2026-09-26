extends GutTest
## ChunkValidator: structural checks and the body-sized reachability model.

# '.' empty (no tile), '#' solid, 'H' ladder, '-' oneway, '~' rope.
const GLYPH_IDS := {".": -1, "#": 1, "H": 2, "-": 3, "~": 4}
const ID_MAP := {
	"empty_id": -1,
	"layers": {"collision": {"palette": "c"}},
	"palettes": {"c": {
		"tiles": [[0, 0, 0, 0], [0, 1, 0, 0], [0, 2, 0, 0], [0, 3, 0, 0], [0, 4, 0, 0]],
		"collision_types": ["empty", "solid", "ladder", "oneway", "rope"],
	}},
}


func _chunk(rows: Array) -> Dictionary:
	var grid := []
	for line: String in rows:
		var row := []
		for ch in line:
			row.append(GLYPH_IDS[ch])
		grid.append(row)
	return {
		"grid_size": [rows[0].length(), rows.size()],
		"empty_id": -1,
		"layers": {"collision": {"encoding": "grid", "data": grid}},
	}


func _validate(rows: Array, entries: Array, exits: Array, options := {}) -> Dictionary:
	return ChunkValidator.validate_chunk_connectivity(_chunk(rows), ID_MAP, entries, exits, options)


func _two_rooms(hatch: String = "#") -> Array:
	var rows := []
	for y in 16:
		rows.append("............")
	rows[7] = "#####%s######" % hatch
	if hatch == "H":
		for y in range(8, 16):
			rows[y] = ".....H......"
	return rows


func test_sealed_room_is_unreachable() -> void:
	var r := _validate(_two_rooms(), [[2, 15]], [[2, 3]])
	assert_false(r.reachable, "exit above a solid floor must not count as reached")
	assert_false(r.ok)


func test_ladder_through_hatch_connects_rooms() -> void:
	var r := _validate(_two_rooms("H"), [[2, 15]], [[9, 3]])
	assert_true(r.reachable, str(r.errors))


func test_entry_in_floor_does_not_tunnel_down() -> void:
	var r := _validate(_two_rooms(), [[2, 7]], [[9, 14]])
	assert_false(r.reachable)


func _hatch(lid: int) -> Array:
	var rows := []
	for y in 18:
		rows.append("............")
	for y in lid:
		rows[7 - y] = "############"
	for y in range(8, 18):
		rows[y] = ".....H......"
	return rows


func test_climbs_through_thin_hatch_lid() -> void:
	var r := _validate(_hatch(2), [[2, 17]], [[9, 3]])
	assert_true(r.reachable, str(r.errors))


func test_drops_down_through_hatch_onto_ladder() -> void:
	var r := _validate(_hatch(2), [[9, 5]], [[2, 17]])
	assert_true(r.reachable, str(r.errors))


func test_thick_lid_is_a_dead_end() -> void:
	assert_false(_validate(_hatch(3), [[2, 17]], [[9, 3]]).reachable)


func test_link_connects_sealed_rooms() -> void:
	var r := _validate(_two_rooms(), [[2, 15]], [[9, 3]], {"links": [[[2, 15], [2, 6]]]})
	assert_true(r.reachable, str(r.errors))


func _tunnel(headroom: int) -> Array:
	var rows := []
	for y in 10:
		var block := "####" if y < 10 - headroom else "...."
		rows.append("........" + block + "........")
	return rows


func test_body_does_not_fit_low_gap() -> void:
	assert_false(_validate(_tunnel(2), [[2, 9]], [[16, 9]]).reachable)


func test_crawls_through_crouch_high_gap() -> void:
	var r := _validate(_tunnel(3), [[2, 9]], [[16, 9]])
	assert_true(r.reachable, str(r.errors))


func _pit(gap: int) -> Array:
	var rows := []
	for y in 12:
		rows.append("........................")
	rows[6] = "########" + ".".repeat(gap) + "#".repeat(16 - gap)
	return rows


func test_jumps_short_gap() -> void:
	var r := _validate(_pit(3), [[2, 5]], [[20, 5]])
	assert_true(r.reachable, str(r.errors))


func test_long_gap_is_not_jumpable() -> void:
	assert_false(_validate(_pit(7), [[2, 5]], [[20, 5]]).reachable)


func _ledge(height: int) -> Array:
	var rows := []
	for y in 10:
		rows.append("........" + ("########" if y >= 10 - height else "........"))
	return rows


func test_jumps_onto_low_ledge() -> void:
	var r := _validate(_ledge(2), [[2, 9]], [[12, 7]])
	assert_true(r.reachable, str(r.errors))


func test_high_ledge_needs_a_ladder() -> void:
	assert_false(_validate(_ledge(4), [[2, 9]], [[12, 5]]).reachable)


func test_climbs_ladder_up_through_oneway_floor() -> void:
	var rows := []
	for y in 16:
		rows.append("................")
	rows[7] = "----------------"
	for y in range(8, 16):
		rows[y] = ".....H.........."
	var r := _validate(rows, [[2, 15]], [[12, 6]])
	assert_true(r.reachable, str(r.errors))


func test_reports_malformed_rle() -> void:
	var chunk := {
		"grid_size": [4, 2],
		"layers": {"collision": {"encoding": "rle", "data": [-1, 0, 1, 8]}},
	}
	var r := ChunkValidator.validate_chunk_connectivity(chunk, ID_MAP, [[0, 0]], [[1, 0]])
	assert_false(r.ok)
	assert_string_contains(" ".join(r.errors), "count 0")


func test_reports_short_rle() -> void:
	var errors := PackedStringArray()
	ChunkValidator.decode_layer({"encoding": "rle", "data": [1, 3]}, 4, 2, -1, errors)
	assert_eq(errors.size(), 1)
	assert_string_contains(errors[0], "3 of 8")


func test_reports_palette_id_out_of_range() -> void:
	var chunk := _chunk(["....", "...."])
	chunk.layers.collision.data[1][2] = 9
	var r := ChunkValidator.validate_chunk_connectivity(chunk, ID_MAP, [[0, 1]], [[3, 1]])
	assert_string_contains(" ".join(r.errors), "palette id 9")


func test_reports_unknown_layer() -> void:
	var chunk := _chunk(["....", "...."])
	chunk.layers["lava"] = {"encoding": "rle", "data": [-1, 8]}
	var r := ChunkValidator.validate_chunk_connectivity(chunk, ID_MAP, [[0, 1]], [[3, 1]])
	assert_string_contains(" ".join(r.errors), "unknown layer 'lava'")


func _real(chunk_id: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(
		"res://assets/world/chunks_json/%s.json" % chunk_id))


func _real_id_map() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://assets/tilesets/tile_id_map.json"))


func test_real_spawn_reaches_key() -> void:
	var chunk := _real("chunk_02_01")
	var key: Array = []
	for e in chunk.entities:
		if e.type == "key":
			key = [int(e.position[0]), int(e.position[1])]
	var r := ChunkValidator.validate_chunk_connectivity(chunk, _real_id_map(), [], [key])
	assert_true(r.reachable, str(r.errors))


func test_real_ladder_tops_are_reachable_from_bottoms() -> void:
	var id_map := _real_id_map()
	var types: Array = id_map.palettes.s2_collision_tileset.collision_types
	var shafts := 0
	var failed: Array = []
	for cy in 8:
		for cx in 8:
			var chunk := _real("chunk_%02d_%02d" % [cx, cy])
			if not chunk.layers.has("collision"):
				continue
			var ids := ChunkValidator.decode_layer(chunk.layers.collision, 128, 72, -1, PackedStringArray())
			for x in 128:
				var y := 0
				while y < 72:
					if ids[y * 128 + x] < 0 or types[ids[y * 128 + x]] != "ladder":
						y += 1
						continue
					var top := y
					while y < 72 and ids[y * 128 + x] >= 0 and types[ids[y * 128 + x]] == "ladder":
						y += 1
					if y - 1 - top < 6 or top < 4 or y >= 71:
						continue
					# Exit just above the top rung, or above a hatch lid over it.
					var exit_y := top - 1
					while exit_y > top - 4 and ids[exit_y * 128 + x] >= 0 \
							and types[ids[exit_y * 128 + x]] == "solid":
						exit_y -= 1
					if top - 1 - exit_y > 2:
						continue  # lid thicker than a hatch: a dead end in game too
					shafts += 1
					var r := ChunkValidator.validate_chunk_connectivity(
						chunk, id_map, [[x, y - 1]], [[x, exit_y]])
					if not r.reachable:
						failed.append([chunk.chunk_id, x, top])
	assert_gt(shafts, 100)
	assert_eq(failed, [], "ladder tops unreachable")
