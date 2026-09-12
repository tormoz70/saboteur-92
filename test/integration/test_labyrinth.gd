extends GutTest
## Whole-maze physics: every floor/ground top holds, ladders are mountable,
## corridors can be walked without falling through.

const ORIGIN_TO_FEET_Y := 56.0


func after_each() -> void:
	if Input.is_action_pressed("move_left"):
		Input.action_release("move_left")
	if Input.is_action_pressed("move_right"):
		Input.action_release("move_right")
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _collision() -> Dictionary:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	return parsed


func _boot_level() -> Node2D:
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	for name in ["Guards", "Items"]:
		var node: Node = level.get_node_or_null(name)
		if node:
			node.process_mode = Node.PROCESS_MODE_DISABLED
	return level


func _origin_on_floor(rect: Array, scale: float) -> Vector2:
	# Sprite origin is top-left; the stand collider sits 24px to the right.
	# Put the feet on the rect, not the origin, or 8px posts miss entirely.
	var left := float(rect[0])
	var right := left + float(rect[2])
	var feet_x := clampf(left + float(rect[2]) * 0.5, left + 1.0, right - 1.0)
	var origin_x := feet_x - 24.0
	var origin_y := float(rect[1]) - ORIGIN_TO_FEET_Y - 2.0
	return Vector2(origin_x, origin_y) * scale


func _floor_probe_hits(space: PhysicsDirectSpaceState2D, rect: Array, scale: float) -> bool:
	var left := float(rect[0]) * scale
	var right := (float(rect[0]) + float(rect[2])) * scale
	var top := float(rect[1]) * scale
	var feet_x := clampf((left + right) * 0.5, left + 2.0 * scale, right - 2.0 * scale)
	var probe := RectangleShape2D.new()
	probe.size = Vector2(maxf(8.0 * scale, 8.0), 4.0 * scale)
	var params := PhysicsShapeQueryParameters2D.new()
	params.shape = probe
	params.collision_mask = CollisionLayers.LAYER_WORLD
	params.collide_with_bodies = true
	params.collide_with_areas = false
	params.transform = Transform2D(0.0, Vector2(feet_x, top + 1.0 * scale))
	return not space.intersect_shape(params, 1).is_empty()


func test_spawn_falls_onto_a_floor_not_the_void() -> void:
	var data := _collision()
	var level := _boot_level()
	await get_tree().physics_frame
	await get_tree().physics_frame
	var player: Player = level.get_node("Player")
	var spawn_y := player.global_position.y
	var scale := float(data.get("scale", 2))
	for _i in 45:
		await wait_physics_frames(1)
		if player.is_on_floor():
			break
	assert_true(player.is_on_floor(), "spawn must land on a floor")
	assert_lt(player.global_position.y, spawn_y + 400.0 * scale, "must not fall through the map")
	assert_false(player.is_dead)


func test_every_floor_and_ground_top_stops_a_fall() -> void:
	var data := _collision()
	var level := _boot_level()
	await get_tree().physics_frame
	await get_tree().physics_frame
	var player: Player = level.get_node("Player")
	var space := player.get_world_2d().direct_space_state
	var misses: Array = []
	for rect in data.get("solids", []):
		var h := int(rect[3])
		var w := int(rect[2])
		if w < 8:
			continue
		if h > 16 and w < 64:
			continue
		if not _floor_probe_hits(space, rect, float(data.get("scale", 2))):
			misses.append(rect)
			if misses.size() >= 12:
				break
	assert_eq(misses.size(), 0, "fall-through at %s" % str(misses))


func test_every_ladder_overlaps_the_climb_detector() -> void:
	var data := _collision()
	var level := _boot_level()
	await get_tree().physics_frame
	await get_tree().physics_frame
	var player: Player = level.get_node("Player")
	player.set_physics_process(false)
	var scale := float(data.get("scale", 2))
	var space := player.get_world_2d().direct_space_state
	var params := PhysicsShapeQueryParameters2D.new()
	params.shape = player.get_node("LadderDetector/CollisionShape2D").shape
	params.collision_mask = CollisionLayers.LAYER_TRIGGERS
	params.collide_with_areas = true
	params.collide_with_bodies = false
	var misses: Array = []
	for rect in data.get("ladders", []):
		var origin := Vector2(
			float(rect[0]) + float(rect[2]) * 0.5 - 24.0,
			float(rect[1]) + minf(float(rect[3]) * 0.5, 40.0) - 40.0
		) * scale
		player.global_position = origin
		player.force_update_transform()
		var det: CollisionShape2D = player.get_node("LadderDetector/CollisionShape2D")
		params.transform = det.global_transform
		if space.intersect_shape(params, 1).is_empty():
			misses.append(rect)
			if misses.size() >= 8:
				break
	assert_eq(misses.size(), 0, "ladders with no detector hit %s" % str(misses))


func _standing_clearance(space: PhysicsDirectSpaceState2D, rect: Array, scale: float) -> bool:
	var left := float(rect[0]) * scale
	var right := (float(rect[0]) + float(rect[2])) * scale
	var top := float(rect[1]) * scale
	var feet_x := clampf((left + right) * 0.5, left + 2.0 * scale, right - 2.0 * scale)
	var probe := RectangleShape2D.new()
	probe.size = Vector2(8.0 * scale, 36.0 * scale)
	var params := PhysicsShapeQueryParameters2D.new()
	params.shape = probe
	params.collision_mask = CollisionLayers.LAYER_WORLD
	params.collide_with_bodies = true
	params.collide_with_areas = false
	# 40px body minus a little skin, sitting just above the floor lip.
	params.transform = Transform2D(0.0, Vector2(feet_x, top - 22.0 * scale))
	return space.intersect_shape(params, 1).is_empty()


func test_sample_floors_support_the_player_body() -> void:
	var data := _collision()
	var level := _boot_level()
	await get_tree().physics_frame
	var player: Player = level.get_node("Player")
	var scale := float(data.get("scale", 2))
	var space := player.get_world_2d().direct_space_state
	var checked := 0
	var n := 0
	for rect in data["solids"]:
		if int(rect[3]) != 8 or int(rect[2]) < 128:
			continue
		if not _standing_clearance(space, rect, scale):
			continue
		n += 1
		if n % 4 != 1:
			continue
		player.global_position = _origin_on_floor(rect, scale)
		player.velocity = Vector2.ZERO
		await wait_physics_frames(8)
		assert_true(
			player.is_on_floor(),
			"player fell through floor %s" % str(rect)
		)
		checked += 1
		if checked >= 12:
			break
	assert_gt(checked, 4, "need several corridor samples")


func test_long_corridor_walk_stays_on_the_floor() -> void:
	var data := _collision()
	var floor_rect: Array = []
	for rect in data["solids"]:
		if int(rect[3]) == 8 and int(rect[2]) >= 256:
			floor_rect = rect
			break
	assert_gt(floor_rect.size(), 0, "need a long floor strip")
	var level := _boot_level()
	await get_tree().physics_frame
	var player: Player = level.get_node("Player")
	var scale := float(data.get("scale", 2))
	player.global_position = _origin_on_floor(floor_rect, scale)
	player.velocity = Vector2.ZERO
	await wait_physics_frames(8)
	assert_true(player.is_on_floor())
	var y0 := player.global_position.y
	var x0 := player.global_position.x
	Input.action_press("move_right")
	for _i in 50:
		await wait_physics_frames(1)
	Input.action_release("move_right")
	assert_true(player.is_on_floor(), "walked off / through the corridor")
	assert_gt(player.global_position.x, x0 + 16.0, "should have walked")
	assert_lt(absf(player.global_position.y - y0), 24.0 * scale, "must not drop through")
