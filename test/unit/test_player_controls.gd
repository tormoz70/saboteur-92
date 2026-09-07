extends GutTest
## Drive a real Player on a floor and check the inlay chords stick.

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")


func after_each() -> void:
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


func test_run_plus_up_starts_running_jump() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(1)
	assert_eq(player.current_state, Player.State.JUMP)
	assert_gt(player.velocity.x, 0.0)
	assert_lt(player.velocity.y, 0.0)


func test_held_run_and_up_jumps_again_after_landing() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_right")
	Input.action_press("move_up")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.JUMP)
	var saw_air := false
	for _i in 50:
		await wait_physics_frames(1)
		if not player.is_on_floor():
			saw_air = true
		elif saw_air:
			await wait_physics_frames(2)
			assert_eq(player.current_state, Player.State.JUMP, "held MOVE+UP jumps again")
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
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(8)
	assert_false(player.is_on_floor(), "jump should have left the slab")
	assert_false(player.on_ladder, "held UP must not mount a shaft mid-jump")
	assert_eq(player.current_state, Player.State.JUMP)


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
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(4)
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
	_add_ladder(Vector2(140, -40), Vector2(160, 200))
	Input.action_press("move_right")
	await wait_physics_frames(2)
	Input.action_press("move_up")
	await wait_physics_frames(4)
	Input.action_release("move_right")
	var saw_air := false
	for _i in 40:
		await wait_physics_frames(1)
		if not player.is_on_floor():
			saw_air = true
		elif saw_air:
			break
	assert_true(player.is_on_floor())
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
	assert_eq(player.current_state, Player.State.JUMP)
	assert_ne(player.current_state, Player.State.JUMP_KICK)


func test_down_while_still_ducks() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_down")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.CROUCH)
	assert_eq(player.velocity.x, 0.0)


func test_down_plus_move_crawls() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_down")
	await wait_physics_frames(2)
	Input.action_press("move_right")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.CRAWL)
	assert_gt(player.velocity.x, 0.0)
	assert_lt(player.velocity.x, player.speed)
	var shape := player.body_collision.shape as RectangleShape2D
	assert_eq(shape.size, Player.BODY_CROUCH_SIZE)


func _spawn_on_floor() -> Player:
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	var floor := StaticBody2D.new()
	floor.collision_layer = CollisionLayers.LAYER_WORLD
	floor.collision_mask = 0
	var col := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(480, 16)
	col.shape = rect
	col.position = Vector2(240, 80)
	floor.add_child(col)
	add_child_autofree(floor)

	var player: Player = PLAYER_SCENE.instantiate()
	add_child_autofree(player)
	# Collider bottom is 56px below origin; sit just above the slab.
	player.global_position = Vector2(80, 20)
	await wait_physics_frames(8)
	assert_true(player.is_on_floor(), "player should land on the test slab")
	return player


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
