extends GutTest


func test_world_tiles_has_authoring_layers() -> void:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_world_tiles.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	var layers: Dictionary = parsed.get("layers", {})
	for name in ["sky", "earth", "structure", "wallpaper", "interior", "fg"]:
		assert_true(layers.has(name), "layer %s" % name)
		var spec: Dictionary = layers[name]
		assert_gt(spec.get("tile_count", 0), 0, "%s tile_count" % name)
		assert_gt(spec.get("rle", []).size(), 0, "%s rle" % name)


func test_objects_catalog_present() -> void:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_objects.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	assert_gt(parsed.get("defs", {}).size(), 0, "object defs")
	assert_gt(parsed.get("placements", []).size(), 0, "placements")
	assert_gt(parsed.get("types", {}).size(), 0, "object types")
	assert_true(parsed["types"].has("floor_brick"), "floor_brick type")


func test_level_has_tile_layers() -> void:
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	for name in ["Sky", "Earth", "Structure", "Wallpaper", "Interior", "Foreground"]:
		assert_not_null(level.get_node_or_null(name), "TileMapLayer %s" % name)


func test_collision_notes_layer_source() -> void:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	var layers: Array = parsed.get("collision_layers", [])
	if not layers.is_empty():
		assert_has(layers, "earth")
		assert_has(layers, "structure")
	assert_eq(str(parsed.get("collision_source", "")), "object_bounds")
