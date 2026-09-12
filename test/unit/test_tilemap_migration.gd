extends GutTest
## Tile RLE and greedy merge match committed collision rectangles.


func test_rle_roundtrip_small() -> void:
	var ids := PackedInt32Array([1, 1, 1, 0, 2, 2])
	var runs := TileMapUtils.rle_encode(ids)
	var back := TileMapUtils.rle_decode(runs)
	assert_eq(back.size(), ids.size())
	for i in ids.size():
		assert_eq(back[i], ids[i])
	var again := TileMapUtils.rle_encode(back)
	assert_eq(again, runs)


func test_collision_tiles_file_present() -> void:
	assert_true(FileAccess.file_exists("res://assets/world/s2_collision_tiles.json"))
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision_tiles.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	assert_eq(str(parsed.get("collision_source", "")), "collision_tiles")
	assert_eq(int(parsed.get("tiles", {}).get("solid", -1)), 1)
	assert_eq(int(parsed.get("tiles", {}).get("ladder", -1)), 2)
	assert_true(parsed.has("ladder_rle"))


func test_greedy_matches_committed_rects() -> void:
	var tiles: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision_tiles.json")
	)
	var rects: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(tiles, TYPE_DICTIONARY)
	assert_typeof(rects, TYPE_DICTIONARY)
	var grid: Array = tiles.get("grid", [])
	var cw := int(grid[0])
	var ch := int(grid[1])
	var cell := int(tiles.get("cell", 8))
	var ids := TileMapUtils.rle_decode(tiles.get("rle", []))
	var climb := TileMapUtils.rle_decode(tiles.get("ladder_rle", []))
	var masks := TileMapUtils.ids_to_masks(ids, cw, ch, climb)
	var solids: Array = TileMapUtils.greedy_merge_rects(masks["solid"], cell)
	var ladders: Array = TileMapUtils.ladder_rects(masks["climb"], cell)
	assert_eq(solids.size(), rects["solids"].size())
	assert_eq(ladders.size(), rects["ladders"].size())


func test_spawn_fixture_is_one_spectrum_screen() -> void:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://test/fixtures/screen_spawn_tiles.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	var grid: Array = parsed.get("grid", [])
	assert_eq(int(grid[0]), 32)
	assert_eq(int(grid[1]), 24)
	assert_true(ResourceLoader.exists("res://scenes/levels/screen_spawn.tscn"))
