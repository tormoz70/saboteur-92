extends GutTest
## Drive a real Player on a floor and check the inlay chords stick.


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


func test_down_while_still_ducks_and_does_not_crawl() -> void:
	var player := await _spawn_on_floor()
	Input.action_press("move_down")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.CROUCH)
	assert_eq(player.velocity.x, 0.0)
	Input.action_press("move_right")
	await wait_physics_frames(2)
	assert_eq(player.current_state, Player.State.RUN)


func _spawn_on_floor() -> Player:
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

	var player: Player = preload("res://scenes/player/player.tscn").instantiate()
	add_child_autofree(player)
	# Collider bottom is 56px below origin; sit just above the slab.
	player.global_position = Vector2(80, 20)
	await wait_physics_frames(8)
	assert_true(player.is_on_floor(), "player should land on the test slab")
	return player


func _release_all() -> void:
	for action in ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]:
		if Input.is_action_pressed(action):
			Input.action_release(action)
