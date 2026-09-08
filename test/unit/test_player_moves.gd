extends GutTest
## Drives the real Player scene on a floor with real input, so the crouch
## punch and the somersault long jump are checked as the player feels them.

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const FLOOR_TOP := 200.0
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]

var _player: Player
var _root: Node2D


func before_each() -> void:
	GameManager.reset_run_state()
	_root = Node2D.new()
	add_child_autofree(_root)
	_root.add_child(_make_floor())
	_player = PLAYER_SCENE.instantiate()
	_root.add_child(_player)
	_player.global_position = _spawn()
	await _step(6)


func after_each() -> void:
	_release_all()
	GameManager.reset_run_state()


func test_punch_reaches_in_front_of_the_body_on_both_facings() -> void:
	# The hitbox used to be pinned to a sprite-width offset that only pointed
	# right, so punching left swung at the player's own chest.
	for facing in [1, -1]:
		_player.apply_facing(facing)
		_player._start_punch()
		var hit := _punch_rect()
		var body := _body_rect()
		if facing > 0:
			assert_gt(hit.position.x, body.position.x, "punch right starts ahead of the body")
			assert_lt(hit.position.x, body.end.x + 32.0, "punch right stays in arm's reach")
		else:
			assert_lt(hit.end.x, body.end.x, "punch left starts ahead of the body")
			assert_gt(hit.end.x, body.position.x - 32.0, "punch left stays in arm's reach")
		assert_true(
			hit.end.y > body.position.y and hit.position.y < body.end.y,
			"the punch covers part of the body's own height"
		)
		assert_lt(hit.get_center().y, body.get_center().y, "a standing punch aims high")


func test_crouch_then_punch_is_a_low_punch() -> void:
	await _press("move_down")
	assert_eq(_player.current_state, Player.State.CROUCH, "down crouches")
	var crouch_size := _body_shape().size
	await _press("punch")
	assert_eq(_player.current_state, Player.State.CROUCH_PUNCH, "DOWN + FIRE punches low")
	assert_eq(_body_shape().size, crouch_size, "the body stays crouched while punching")
	assert_true(_player.punch_area.monitoring, "the low punch can actually hit")
	assert_gt(
		_player.punch_area.position.y, Player.PUNCH_HIT.y, "it lands below a standing punch"
	)
	var low := _punch_rect()
	var crouched := _body_rect()
	assert_true(
		low.end.y > crouched.position.y and low.position.y < crouched.end.y,
		"the low punch is at the height of a crouching target"
	)


func test_crouch_punch_returns_to_the_crouch() -> void:
	await _press("move_down")
	await _press("punch")
	Input.action_release("punch")
	await _step(int(_player.punch_duration * 60.0) + 4)
	assert_eq(_player.current_state, Player.State.CROUCH, "still crouching after the punch")
	assert_false(_player.punch_area.monitoring, "the hitbox closes with the punch")


func test_crawl_then_punch_stays_low() -> void:
	await _press("move_down")
	await _press("move_right")
	assert_eq(_player.current_state, Player.State.CRAWL, "down plus move crawls")
	await _press("punch")
	assert_eq(_player.current_state, Player.State.CROUCH_PUNCH, "crawling FIRE is still a low punch")
	assert_eq(_body_shape().size, Player.BODY_CROUCH_SIZE)


func test_standing_punch_is_unchanged() -> void:
	await _press("punch")
	assert_eq(_player.current_state, Player.State.PUNCH)


func test_running_jump_plus_punch_somersaults() -> void:
	await _run_right()
	await _press("jump")
	assert_eq(_player.current_state, Player.State.SOMERSAULT, "MOVE + UP is the long jump")
	assert_gt(
		absf(_player.velocity.x), _player.speed, "the somersault carries more speed than a run"
	)


func test_running_punch_plus_jump_also_somersaults() -> void:
	# The other tap order has to work too: a thumb reaches FIRE before UP just
	# as often as the other way round.
	await _run_right()
	await _press("punch")
	assert_eq(_player.current_state, Player.State.JUMP_KICK, "MOVE + FIRE kicks first")
	await _press("jump")
	assert_eq(_player.current_state, Player.State.SOMERSAULT, "FIRE then UP while running")


func test_both_buttons_on_one_frame_somersaults() -> void:
	# Neither tap is "the second one" here, so the chord has to be caught in
	# resolve_ground rather than by either upgrade path.
	await _run_right()
	Input.action_press("jump")
	Input.action_press("punch")
	await _step(2)
	assert_eq(_player.current_state, Player.State.SOMERSAULT, "MOVE + UP + FIRE together")


func test_stale_held_up_does_not_turn_a_flying_kick_into_a_flip() -> void:
	# UP left held from an earlier standing kick is not part of the next
	# gesture, so MOVE + FIRE after it stays the inlay's flying kick.
	Input.action_press("move_up")
	await _step(2)
	assert_eq(_player.current_state, Player.State.KICK, "UP while still is the standing kick")
	await _step(40)
	Input.action_press("move_right")
	await _press("punch")
	assert_eq(_player.current_state, Player.State.JUMP_KICK, "a stale UP is not the flip chord")


func test_somersault_needs_a_direction() -> void:
	Input.action_press("jump")
	Input.action_press("punch")
	await _step(2)
	assert_ne(_player.current_state, Player.State.SOMERSAULT, "standing still cannot long jump")


func test_somersault_clears_more_ground_than_a_run() -> void:
	var flip := await _measure_jump(true)
	assert_gt(flip, 80.0, "the long jump covers real distance")


func test_somersault_lands_back_on_its_feet() -> void:
	await _run_right()
	await _press("jump")
	_release_all()
	await _step(120)
	assert_true(_player.is_on_floor(), "the flip ends on the floor")
	assert_ne(_player.current_state, Player.State.SOMERSAULT, "and leaves the spin")


func test_standing_jump_plus_punch_still_kicks() -> void:
	Input.action_press("punch")
	await _press("jump")
	assert_eq(_player.current_state, Player.State.KICK, "UP while still is the standing kick")


func test_punching_after_walking_off_a_ledge_stays_a_fall() -> void:
	# The inlay makes FIRE in the air a no-op, and falling is not the rising
	# half of a long jump, so neither rule may fire here.
	_player.current_state = Player.State.JUMP
	_player.global_position.y -= 96.0
	_player.velocity = Vector2(_player.speed, 60.0)
	Input.action_press("move_right")
	await _press("punch")
	assert_eq(_player.current_state, Player.State.JUMP, "falling + FIRE does nothing")


func test_crawl_uses_the_embryo_roll() -> void:
	await _press("move_down")
	await _press("move_right")
	assert_eq(_player.current_state, Player.State.CRAWL, "down plus move rolls")
	assert_eq(_player.anim.animation, &"roll")


func _measure_jump(with_flip: bool) -> float:
	await _run_right()
	await _press("jump")
	if with_flip:
		await _press("punch")
		Input.action_release("punch")
	var start_x := _player.global_position.x
	for _i in 180:
		if _player.is_on_floor():
			break
		await _step(1)
	var travelled: float = _player.global_position.x - start_x
	_release_all()
	return travelled


func _run_right() -> void:
	Input.action_press("move_right")
	await _step(10)
	assert_eq(_player.current_state, Player.State.RUN, "running before the jump")


func _reset_player() -> void:
	_release_all()
	_player.respawn(_spawn())
	await _step(6)


func _press(action: String) -> void:
	Input.action_press(action)
	# Godot turns an injected press into "just pressed" on the frame after the
	# call, so a tap needs two frames to reach _handle_attack_input.
	await _step(2)


func _step(frames: int) -> void:
	for _i in frames:
		await get_tree().physics_frame


func _release_all() -> void:
	for action in ACTIONS:
		if Input.is_action_pressed(action):
			Input.action_release(action)


func _spawn() -> Vector2:
	# Feet sit BODY_STAND_POS.y plus half the body height below the origin.
	return Vector2(0.0, FLOOR_TOP - Player.BODY_STAND_POS.y - Player.BODY_STAND_SIZE.y * 0.5)


func _body_shape() -> RectangleShape2D:
	return _player.body_collision.shape as RectangleShape2D


func _body_rect() -> Rect2:
	var size: Vector2 = _body_shape().size * _player.scale
	return Rect2(_player.body_collision.global_position - size * 0.5, size)


func _punch_rect() -> Rect2:
	var col := _player.punch_area.get_child(0) as CollisionShape2D
	var size: Vector2 = (col.shape as RectangleShape2D).size * _player.scale
	return Rect2(col.global_position - size * 0.5, size)


func _make_floor() -> StaticBody2D:
	var body := StaticBody2D.new()
	body.collision_layer = CollisionLayers.LAYER_WORLD
	body.collision_mask = 0
	var col := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(4096.0, 64.0)
	col.shape = shape
	col.position = Vector2(0.0, FLOOR_TOP + 32.0)
	body.add_child(col)
	return body
