extends GutTest
## Counts come from s2_collision.json / s2_objects.json, not mosaic pixels.


func after_each() -> void:
	if Input.is_action_pressed("move_left"):
		Input.action_release("move_left")
	if Input.is_action_pressed("move_down"):
		Input.action_release("move_down")
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _collision_data() -> Dictionary:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	return parsed


func _objects_catalog() -> Dictionary:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_objects.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	return parsed


func test_collision_json_has_solids_ladders_and_lifts() -> void:
	var data := _collision_data()
	assert_eq(str(data.get("collision_source", "")), "object_bounds")
	assert_gt(data.get("solids", []).size(), 0, "solids array")
	assert_gt(data.get("ladders", []).size(), 0, "ladders array")
	assert_gt(data.get("lifts", []).size(), 0, "lifts array")
	for rect in data["solids"]:
		assert_eq(rect.size(), 4, "solid is [x, y, w, h]")
	for rect in data["ladders"]:
		assert_eq(rect.size(), 4, "ladder is [x, y, w, h]")
	for spec in data["lifts"]:
		assert_true(spec.has("x") and spec.has("y") and spec.has("w") and spec.has("h"))
		assert_true(spec.has("top") and spec.has("bottom"))


func test_registry_climb_types_are_not_solid() -> void:
	var catalog := _objects_catalog()
	var types: Dictionary = catalog.get("types", {})
	var climb_ids: Array[String] = []
	for tid in types:
		if str(types[tid].get("collision", "")) == "climb":
			climb_ids.append(str(tid))
	assert_gt(climb_ids.size(), 0, "climb types in registry")
	for tid in climb_ids:
		assert_eq(str(types[tid].get("collision", "")), "climb")
		if str(types[tid].get("mode", "")) != "module_repeat":
			continue
		var module: Array = types[tid].get("module", [])
		assert_eq(module.size(), 2)
		assert_eq(int(module[0]), 16, "%s rung width" % tid)
		assert_eq(int(module[1]), 8, "%s rung height" % tid)


func test_windows_and_furniture_have_no_collision() -> void:
	var catalog := _objects_catalog()
	var types: Dictionary = catalog.get("types", {})
	for tid in types:
		var spec: Dictionary = types[tid]
		var name := str(tid)
		if (
			name.begins_with("window")
			or name.begins_with("furniture")
			or name.begins_with("bookcase")
			or name == "desk"
		):
			assert_eq(str(spec.get("collision", "")), "none", "%s must be walk-behind" % tid)
		if name.begins_with("chr_") and str(spec.get("layer", "")) == "sky":
			assert_eq(str(spec.get("collision", "")), "none", "sky fill %s" % tid)


func test_player_walks_on_a_bytecode_floor() -> void:
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	var data := _collision_data()
	var floor_rect: Array = []
	for rect in data["solids"]:
		if int(rect[3]) == 8 and int(rect[2]) >= 256 and int(rect[0]) > 64:
			floor_rect = rect
			break
	assert_gt(floor_rect.size(), 0, "need a one-cell floor strip")
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var player: Player = level.get_node("Player")
	var scale := float(data.get("scale", 2))
	var stand_x := float(floor_rect[0]) + float(floor_rect[2]) * 0.5
	player.global_position = Vector2(stand_x, float(floor_rect[1]) - 56.0) * scale
	player.velocity = Vector2.ZERO
	await wait_physics_frames(10)
	assert_true(player.is_on_floor(), "should stand on a bytecode solid")
	var start_x := player.global_position.x
	Input.action_press("move_left")
	for _i in 80:
		await wait_physics_frames(1)
	Input.action_release("move_left")
	assert_lt(player.global_position.x, start_x - 16.0, "should have walked left")
	assert_gt(player.global_position.x, float(floor_rect[0]) * scale)


func test_level_builds_one_shape_per_json_entry() -> void:
	var data := _collision_data()
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var solids: Node = level.get_node("World/Solids")
	var ladders: Node = level.get_node("World/Ladders")
	var lifts: Node = level.get_node("World/Lifts")
	assert_eq(solids.get_child_count(), data["solids"].size())
	assert_eq(ladders.get_child_count(), data["ladders"].size())
	assert_eq(lifts.get_child_count(), data["lifts"].size())
	assert_null(
		level.get_node_or_null("Letterbox"),
		"side letterbox bars hide playable width the D-pad should sit in"
	)
