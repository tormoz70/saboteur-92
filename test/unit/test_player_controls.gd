extends GutTest
## Drive a real Player on a floor and check the inlay chords stick.

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")

var _lid: StaticBody2D


func after_each() -> void:
	_lid = null
	_release_all()
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func test_still_up_starts_stand_kick() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_up")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.KICK)
	assert_eq(player.velocity.x, 0.0)


func test_space_while_still_is_also_a_kick() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("jump")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.KICK)


func test_run_plus_up_starts_long_jump() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.SOMERSAULT)
	assert_gt(player.velocity.x, 0.0)
	assert_lt(player.velocity.y, 0.0)


func test_held_run_and_up_jumps_again_after_landing() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	Input.action_press("move_up")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.SOMERSAULT)
	var saw_air := false
	for _i in 90:
		await wait_physics_frames(1)
		if not player.is_on_floor():
			saw_air = true
		elif saw_air:
			await wait_physics_frames(3)
			assert_eq(player.current_state, Player.State.SOMERSAULT, "held MOVE+UP flips again")
			assert_lt(player.velocity.y, 0.0)
			return
	assert_true(saw_air, "should have left the slab")
	fail_test("should have jumped again after landing")


func test_still_fire_starts_punch() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("punch")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.PUNCH)
	assert_eq(player.velocity.x, 0.0)


func test_run_plus_fire_starts_flying_kick() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("punch")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.JUMP_KICK)
	assert_gt(player.velocity.x, 0.0)
	assert_lt(player.velocity.y, 0.0)


func test_running_jump_does_not_grab_ladder_in_air() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(4)
	assert_false(player.is_on_floor(), "jump should have left the slab")
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	await wait_physics_frames(4)
	assert_false(player.on_ladder, "held UP must not mount a shaft mid-jump")
	assert_eq(player.current_state, Player.State.SOMERSAULT)


func test_move_plus_up_on_ladder_climbs() -> void:
	# NW/NE on the rungs is climb, not a long jump that leaves Nina at the foot.
	var player := await _spawn_on_floor()
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	await wait_physics_frames(1)
	assert_true(player.can_climb)
	Input.action_press("move_right")
	Input.action_press("move_up")
	await wait_physics_frames(3)
	assert_true(player.on_ladder)
	assert_eq(player.current_state, Player.State.CLIMB)


func test_still_up_on_ladder_still_climbs() -> void:
	var player := await _spawn_on_floor()
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	await wait_physics_frames(1)
	assert_true(player.can_climb)
	Input.action_press("move_up")
	await wait_physics_frames(2)
	assert_true(player.on_ladder)
	assert_eq(player.current_state, Player.State.CLIMB)


func test_held_up_after_jump_does_not_mount_on_landing() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(4)
	assert_false(player.is_on_floor())
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	Input.action_release("move_right")
	var saw_air := false
	for _i in 40:
		await wait_physics_frames(1)
		if not player.is_on_floor():
			saw_air = true
		elif saw_air:
			break
	assert_true(saw_air, "should have left the slab")
	assert_true(player.is_on_floor(), "should have landed")
	assert_false(player.on_ladder, "held UP from the jump must not mount")


func test_fresh_up_after_jump_still_climbs() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(4)
	assert_false(player.is_on_floor())
	Input.action_release("move_right")
	var saw_air := false
	for _i in 80:
		await wait_physics_frames(1)
		if not player.is_on_floor():
			saw_air = true
		elif saw_air:
			break
	assert_true(player.is_on_floor())
	_add_ladder(Vector2(player.global_position.x + 24.0, 20.0), Vector2(160, 200))
	await wait_physics_frames(1)
	Input.action_release("move_up")
	await wait_physics_frames(1)
	Input.action_press("move_up")
	await wait_physics_frames(2)
	assert_true(player.on_ladder)
	assert_eq(player.current_state, Player.State.CLIMB)


func test_held_up_after_flying_kick_does_not_mount() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_up")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.KICK)
	await wait_physics_frames(30)
	Input.action_press("move_right")
	Input.action_press("punch")
	await wait_physics_frames(4)
	assert_eq(player.current_state, Player.State.JUMP_KICK)
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	Input.action_release("move_right")
	Input.action_release("punch")
	var saw_air := false
	for _i in 40:
		await wait_physics_frames(1)
		if not player.is_on_floor() and not player.on_ladder:
			saw_air = true
		elif saw_air:
			break
	assert_true(saw_air, "flying kick should leave the slab")
	assert_false(player.on_ladder, "UP held through a flying kick must not mount")


func test_held_up_after_stand_kick_still_climbs() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_up")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.KICK)
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_release("move_right")
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	await wait_physics_frames(30)
	assert_true(player.on_ladder, "UP after a kick is still a climb, not a spent jump")
	assert_eq(player.current_state, Player.State.CLIMB)


func test_dead_end_lift_up_is_a_kick() -> void:
	var player := await _spawn_on_dead_end_lift()
	Input.action_press("move_up")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.KICK)
	assert_true(player.punch_area.monitoring)


func test_dead_end_lift_down_ducks() -> void:
	var player := await _spawn_on_dead_end_lift()
	Input.action_press("move_down")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.CROUCH)


func test_airborne_fire_does_not_start_a_kick() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(6)
	assert_false(player.is_on_floor())
	Input.action_release("move_up")
	Input.action_release("move_right")
	Input.action_press("punch")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.SOMERSAULT)
	assert_ne(player.current_state, Player.State.JUMP_KICK)


func test_down_while_still_ducks() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_down")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.CROUCH)
	assert_eq(player.velocity.x, 0.0)


func test_down_plus_move_rolls() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_down")
	await wait_physics_frames(2)
	Input.action_press("move_right")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.CRAWL)
	assert_eq(player.anim.animation, &"roll")
	assert_eq(player.anim.sprite_frames.get_frame_count(&"roll"), 4)
	assert_gt(player.velocity.x, 0.0)
	assert_lt(player.velocity.x, player.speed)
	var shape := player.body_collision.shape as RectangleShape2D
	assert_eq(shape.size, Player.BODY_CROUCH_SIZE)


func test_walks_up_a_one_cell_step() -> void:
	var player := await _spawn_on_floor()
	_add_step(200.0, 16.0)
	var start_y := player.global_position.y
	Input.action_press("move_right")
	for _i in 80:
		await wait_physics_frames(1)
		if player.global_position.x >= 200.0:
			break
	assert_gt(player.global_position.x, 190.0, "should have reached the step")
	assert_lt(player.global_position.y, start_y - 8.0, "feet should rise onto the step")


func test_climb_stops_under_a_dead_end_ceiling() -> void:
	# JMP/UP on a ladder is climb. Ghosting through the lid used to plant the
	# feet on its underside, restore world collision, and freeze the body inside
	# the brick. Stop at head height instead.
	var player := await _spawn_under_ceiling()
	_add_ladder(Vector2(140, 24), Vector2(160, 112))
	await wait_physics_frames(1)
	Input.action_press("move_up")
	for _i in 90:
		await wait_physics_frames(1)
		if player.global_position.y <= -48.0:
			fail_test("climbed through the lid to y=%.1f" % player.global_position.y)
			return
	assert_true(player.on_ladder, "still on the rungs under the lid")
	assert_gt(player.global_position.y, -48.0, "head stays below the red brick")
	assert_false(_overlaps_ceiling(player), "body must not sit inside the lid")
	Input.action_release("move_up")
	Input.action_press("move_down")
	var y_at_lid := player.global_position.y
	await wait_physics_frames(20)
	assert_gt(player.global_position.y, y_at_lid + 8.0, "DOWN still climbs away from the lid")


func test_climb_through_hatch_still_emerges() -> void:
	# Rungs continue above the lid, so this is a hatch, not a dead-end.
	# Stopping at head height would leave Nina stuck under every floor.
	var player := await _spawn_on_floor()
	_add_solid(Vector2(240, 0), Vector2(480, 8))
	_add_ladder(Vector2(140, -40), Vector2(160, 280))
	await wait_physics_frames(1)
	Input.action_press("move_up")
	for _i in 120:
		await wait_physics_frames(1)
		if player.global_position.y < -20.0:
			break
	assert_lt(player.global_position.y, -8.0, "should climb through the hatch")


func test_climb_through_hatch_when_rungs_end_at_the_floor() -> void:
	# Document hatch: the floor slab covers the shaft and the Area2D stops
	# at the lid. Climb through until the feet reach the TOP, not the
	# underside (that embedded the body and froze the pose).
	var player := await _spawn_on_floor()
	_lid = _add_solid(Vector2(240, 0), Vector2(480, 8))
	_add_ladder(Vector2(140, 44), Vector2(160, 80))
	await wait_physics_frames(1)
	Input.action_press("move_up")
	for _i in 120:
		await wait_physics_frames(1)
		if not player.on_ladder and player.global_position.y < 20.0:
			break
	assert_false(player.on_ladder)
	assert_true(player.is_on_floor(), "stands on the hatch")
	assert_lt(player.global_position.y, 8.0, "feet should reach the hatch floor")
	assert_lt(
		player.body_collision.global_position.y,
		-4.0,
		"body centre sits above the slab, not inside it"
	)


func test_jump_off_ladder_into_ceiling_does_not_wedge() -> void:
	# Climb to the lid, then MOVE without UP to hop off. Restoring world
	# collision while the head is in the brick used to freeze the pose.
	var player := await _spawn_under_ceiling()
	_add_ladder(Vector2(140, 24), Vector2(160, 112))
	await wait_physics_frames(1)
	Input.action_press("move_up")
	for _i in 40:
		await wait_physics_frames(1)
		if player.on_ladder:
			break
	assert_true(player.on_ladder)
	await wait_physics_frames(20)
	Input.action_release("move_up")
	Input.action_press("move_right")
	await wait_physics_frames(2)
	assert_false(player.on_ladder, "MOVE without UP leaves the rungs")
	assert_false(_overlaps_ceiling(player), "leave must not plant the head in the lid")
	for _i in 80:
		await wait_physics_frames(1)
		if player.is_on_floor() and not player.on_ladder:
			break
	assert_false(_overlaps_ceiling(player), "bonking the lid must not embed the body")
	assert_true(player.is_on_floor() or player.velocity.y > 0.0, "falls or stands after the hop")
	assert_ne(player.current_state, Player.State.SOMERSAULT, "ceiling is not a flip landing")


func test_somersault_into_ceiling_does_not_wedge() -> void:
	var player := await _spawn_under_ceiling()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.SOMERSAULT)
	for _i in 80:
		await wait_physics_frames(1)
		if player.is_on_floor() and player.current_state != Player.State.SOMERSAULT:
			break
	assert_false(_overlaps_ceiling(player), "a lid bonk must not embed the body")
	assert_true(player.is_on_floor() or player.velocity.y >= 0.0)


func _spawn_on_floor() -> Player:
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	_add_solid(Vector2(240, 80), Vector2(480, 16))

	var player: Player = PLAYER_SCENE.instantiate()
	add_child_autofree(player)
	# Collider bottom is 56px below origin; sit just above the slab.
	player.global_position = Vector2(80, 20)
	await wait_physics_frames(8)
	assert_true(player.is_on_floor(), "player should land on the test slab")
	return player


func _spawn_under_ceiling() -> Player:
	var player := await _spawn_on_floor()
	# Thick mass, underside at y=-32. Empty space above a thin bar would
	# make this a hatch; a deep brick block is a real dead-end lid.
	_lid = _add_solid(Vector2(240, -72), Vector2(480, 80))
	return player


func _overlaps_ceiling(player: Player) -> bool:
	if _lid == null:
		return false
	var col := player.body_collision
	var q := PhysicsShapeQueryParameters2D.new()
	q.shape = col.shape
	q.transform = col.global_transform
	q.collision_mask = player.get_world_mask()
	q.collide_with_bodies = true
	q.exclude = [player.get_rid()]
	for hit in player.get_world_2d().direct_space_state.intersect_shape(q, 8):
		if hit.get("collider") == _lid:
			return true
	return false


func _spawn_on_dead_end_lift() -> Player:
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	var lift := Lift.new()
	var col := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(96, 8)
	col.shape = rect
	col.position = Vector2(48, 4)
	lift.add_child(col)
	add_child_autofree(lift)
	lift.global_position = Vector2(80, 80)
	lift.setup(80.0, 80.0, 96.0)

	var player: Player = PLAYER_SCENE.instantiate()
	add_child_autofree(player)
	# is_centered uses origin.x + 48; feet sit 56px below origin.
	player.global_position = Vector2(80, 24)
	await wait_physics_frames(8)
	assert_true(player.is_on_floor(), "player should stand on the cabin")
	assert_true(player.on_lift)
	return player


func _add_step(left_x: float, height: float) -> void:
	# _spawn_on_floor slab: center (240, 80), size 480x16, top at y=72.
	_add_solid(Vector2(left_x + 80.0, 72.0 - height * 0.5), Vector2(160.0, height))


func _add_solid(center: Vector2, size: Vector2) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.collision_layer = CollisionLayers.LAYER_WORLD
	body.collision_mask = 0
	var col := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = size
	col.shape = rect
	col.position = center
	body.add_child(col)
	add_child_autofree(body)
	return body


func _add_ladder(center: Vector2, size: Vector2) -> void:
	var area := Area2D.new()
	area.collision_layer = CollisionLayers.LAYER_TRIGGERS
	area.collision_mask = 0
	area.monitorable = true
	area.monitoring = false
	var col := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = size
	col.shape = shape
	col.position = center
	area.add_child(col)
	add_child_autofree(area)


func _release_all() -> void:
	for action in ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]:
		if Input.is_action_pressed(action):
			Input.action_release(action)
