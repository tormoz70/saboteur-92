extends GutTest


func test_objects_catalog_has_typed_layers() -> void:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_objects.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	var types: Dictionary = parsed.get("types", {})
	var instances: Array = parsed.get("instances", [])
	assert_gt(types.size(), 0, "object types")
	assert_gt(instances.size(), 0, "instances")
	for name in ["sky", "earth", "structure", "interior", "artifacts", "machines", "actors", "fg"]:
		assert_true(parsed.get("layer_z", {}).has(name), "layer_z %s" % name)
	var has_ladder := false
	for tid in types:
		var spec: Dictionary = types[tid]
		if str(tid).begins_with("ladder_") and str(spec.get("mode", "")) == "module_repeat":
			has_ladder = true
			assert_eq(str(spec.get("collision", "")), "climb")
			var module: Array = spec.get("module", [])
			assert_eq(module.size(), 2)
			assert_eq(int(module[0]), 16)
			assert_eq(int(module[1]), 8)
	assert_true(has_ladder, "at least one climb type")
	if types.has("window"):
		assert_eq(str(types["window"].get("collision", "")), "none")
	if types.has("bookcase"):
		assert_eq(str(types["bookcase"].get("collision", "")), "none")
	assert_true(types.has("desk"), "desk overlay type")
	assert_eq(str(types["desk"].get("layer", "")), "interior")
	assert_true(bool(types["desk"].get("overlay", false)))
	assert_gt(int(types["desk"].get("z", 0)), 0)


func test_level_has_object_layer_nodes() -> void:
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	for name in [
		"Sky", "Earth", "Structure", "Interior", "Artifacts", "Machines", "ActorsLayer", "Foreground"
	]:
		var node := level.get_node_or_null(name)
		assert_not_null(node, "layer %s" % name)
		assert_eq(node.get_class(), "Node2D", "%s is a Node2D container" % name)
	assert_null(level.get_node_or_null("Wallpaper"), "wallpaper merged into interior")
	assert_gt(level.get_node("Interior").get_child_count(), 0, "interior objects spawned")


func test_collision_notes_object_bounds() -> void:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	var layers: Array = parsed.get("collision_layers", [])
	if not layers.is_empty():
		assert_has(layers, "earth")
		assert_has(layers, "structure")
	assert_eq(str(parsed.get("collision_source", "")), "object_bounds")
