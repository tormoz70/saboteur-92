extends GutTest
## Panther on hand-built collision tiles at the game's x2 scale: touch
## damage, clearing it with the somersault (worked out from Nina's jump
## numbers and then flown for real), staying on its floor, and the low punch
## that stuns and kills it.

const Arena := preload("res://test/enemy_arena.gd")
const Panther := preload("res://scripts/enemies/panther.gd")
const PANTHER_SCENE := preload("res://scenes/enemies/panther.tscn")
const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
const FLOOR_ROW := 20
const NINA_FEET := 56.0
const NINA_BODY_X := 24.0
const PANTHER_FEET := 32.0
const PANTHER_MID := 32.0

var _root: Node2D
var _tiles: TileMapLayer


func before_each() -> void:
	GameManager.reset_run_state()
	_root = Node2D.new()
	add_child_autofree(_root)
	_tiles = Arena.make_layer()
	_root.add_child(_tiles)


func after_each() -> void:
	_release_all()
	GameManager.reset_run_state()


func test_somersault_arc_clears_the_hurt_box() -> void:
	var nina: Player = autofree(PLAYER_SCENE.instantiate())
	var panther: CharacterBody2D = autofree(PANTHER_SCENE.instantiate())
	var hurt_col := panther.get_node("HurtBox/CollisionShape2D") as CollisionShape2D
	var hurt := (hurt_col.shape as RectangleShape2D).size
	# Height of the hurt box's top above the floor the panther stands on.
	var hurt_h := (PANTHER_FEET - (hurt_col.position.y - hurt.y * 0.5)) * Arena.SCALE
	var hurt_w := hurt.x * Arena.SCALE
	var nina_w := Player.BODY_STAND_SIZE.x * Arena.SCALE
	var v := -nina.jump_velocity * nina.somersault_jump_scale
	var g := nina.gravity
	var apex := v * v / (2.0 * g)
	assert_gt(apex, hurt_h * 2.0, "the flip rises well above the panther's back")
	# Time the feet spend above the hurt box, and the ground covered meanwhile.
	var above := 2.0 * sqrt(v * v - 2.0 * g * hurt_h) / g
	var travel := nina.speed * nina.somersault_speed_scale * above
	assert_gt(
		travel,
		hurt_w + nina_w,
		"even over a standing panther the feet stay high for the whole overlap"
	)


func test_somersault_over_a_charging_panther_takes_no_damage() -> void:
	_floor(0, 79)
	var nina := _nina(200.0)
	var panther := _panther(760.0, -1)
	await _step(4)
	Input.action_press("move_right")
	var flipped := false
	var in_flip := false
	var frames := 0
	while frames < 240:
		await _step(1)
		frames += 1
		in_flip = in_flip or nina.current_state == Player.State.SOMERSAULT
		var gap := _panther_x(panther) - _nina_x(nina)
		if not flipped and gap <= 170.0:
			Input.action_press("jump")
			flipped = true
			await _step(3)
			Input.action_release("jump")
		if flipped and nina.is_on_floor() and nina.current_state != Player.State.SOMERSAULT:
			break
	await _step(6)
	assert_true(in_flip, "she met the panther with a somersault")
	assert_eq(panther.ai_state, Panther.AiState.CHARGE, "it was charging at her")
	assert_gt(_nina_x(nina), _panther_x(panther), "she landed beyond it")
	assert_eq(nina.energy, nina.max_energy, "the flip took her clean over")


func test_touch_hurts_nina() -> void:
	_floor(0, 49)
	var nina := _nina(200.0)
	var panther := _panther(560.0, -1)
	await _until(func() -> bool: return nina.energy < nina.max_energy, 180)
	assert_eq(nina.energy, nina.max_energy - panther.contact_damage, "one touch, one bite")


func test_turns_at_a_ledge_and_a_wall_without_falling() -> void:
	_floor(10, 29)
	Arena.fill(_tiles, 10, FLOOR_ROW - 3, 10, FLOOR_ROW - 1, Arena.SOLID)
	var panther := _panther(320.0, 1)
	await _step(4)
	var floor_y := panther.global_position.y
	var flips := 0
	var facing: int = panther.facing
	var min_x := INF
	var max_x := -INF
	for _i in 360:
		await _step(1)
		min_x = minf(min_x, _panther_x(panther))
		max_x = maxf(max_x, _panther_x(panther))
		if panther.facing != facing:
			facing = panther.facing
			flips += 1
	assert_gte(flips, 3, "it paces between the wall and the ledge")
	assert_almost_eq(panther.global_position.y, floor_y, 1.0, "it never drops off")
	assert_gt(min_x, 176.0, "it stops at the wall")
	assert_lte(max_x, 480.0, "it stops at the ledge")
	assert_true(panther.is_on_floor())


func test_low_punch_stuns_then_kills() -> void:
	_floor(0, 49)
	var nina := _nina(200.0)
	var panther := _panther(250.0, -1)
	panther.prowl_speed = 0.0
	panther.charge_speed = 0.0
	nina.punch_area.body_entered.connect(
		func(body: Node2D) -> void:
			if body.is_in_group("enemies"):
				body.take_damage()
	)
	watch_signals(EventBus)
	await _step(4)
	await _press("move_down")
	await _press("punch")
	await _step(2)
	assert_eq(panther.ai_state, Panther.AiState.STUNNED, "the low punch lands and stuns it")
	Input.action_release("punch")
	await _step(int(nina.punch_duration * 60.0) + 4)
	await _press("punch")
	await _step(2)
	assert_eq(panther.ai_state, Panther.AiState.DEAD, "the second punch kills it")
	assert_signal_emitted(EventBus, "enemy_killed")
	var body: WeakRef = weakref(panther)
	await _until(func() -> bool: return body.get_ref() == null, 60)
	assert_null(body.get_ref(), "the body is cleared away")


func _floor(x0: int, x1: int) -> void:
	Arena.fill(_tiles, x0, FLOOR_ROW, x1, FLOOR_ROW + 1, Arena.SOLID)


func _panther(centre_x: float, facing: int) -> CharacterBody2D:
	var panther: CharacterBody2D = PANTHER_SCENE.instantiate()
	panther.scale = Vector2(Arena.SCALE, Arena.SCALE)
	panther.position = Vector2(
		centre_x - PANTHER_MID * Arena.SCALE,
		Arena.origin_on_floor(Arena.row_top(FLOOR_ROW), PANTHER_FEET)
	)
	_root.add_child(panther)
	panther.facing = facing
	return panther


func _nina(centre_x: float) -> Player:
	var nina: Player = PLAYER_SCENE.instantiate()
	nina.scale = Vector2(Arena.SCALE, Arena.SCALE)
	nina.position = Vector2(
		centre_x - NINA_BODY_X * Arena.SCALE,
		Arena.origin_on_floor(Arena.row_top(FLOOR_ROW), NINA_FEET)
	)
	_root.add_child(nina)
	return nina


func _panther_x(panther: CharacterBody2D) -> float:
	return panther.global_position.x + PANTHER_MID * Arena.SCALE


func _nina_x(nina: Player) -> float:
	return nina.global_position.x + NINA_BODY_X * Arena.SCALE


func _press(action: String) -> void:
	Input.action_press(action)
	await _step(2)


func _until(done: Callable, max_frames: int) -> void:
	for _i in max_frames:
		if done.call():
			return
		await _step(1)


func _step(n: int) -> void:
	for _i in n:
		await get_tree().physics_frame


func _release_all() -> void:
	for a in ACTIONS:
		if Input.is_action_pressed(a):
			Input.action_release(a)
