extends GutTest
## Guard AI on hand-built collision tiles at the game's x2 scale: sight
## through walls, one-way platforms and ladders, turning at ledges and
## walls, the "!" pause, and a wind-up punch Nina can step away from.

const Arena := preload("res://test/enemy_arena.gd")
const Guard := preload("res://scripts/enemies/guard.gd")
const GUARD_SCENE := preload("res://scenes/enemies/guard.tscn")
const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
const FLOOR_ROW := 20
# Sprite px from the origin down to the feet (guard and Nina share the cell).
const FEET := 56.0
const BODY_X := 24.0

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


func test_sees_nina_in_the_open_past_a_ladder() -> void:
	_floor(0, 49)
	Arena.fill(_tiles, 12, FLOOR_ROW - 8, 12, FLOOR_ROW - 1, Arena.LADDER)
	var guard := _guard(112.0, 0.0)
	_nina(348.0)
	await _until(func() -> bool: return guard.ai_state != Guard.AiState.PATROL, 30)
	assert_eq(guard.ai_state, Guard.AiState.NOTICE, "a ladder does not hide her")


func test_does_not_see_through_a_wall() -> void:
	_floor(0, 49)
	Arena.fill(_tiles, 12, FLOOR_ROW - 10, 12, FLOOR_ROW - 1, Arena.SOLID)
	var guard := _guard(112.0, 0.0)
	var nina := _nina(348.0)
	await _step(40)
	assert_true(guard.sight.overlaps_body(nina), "she is inside the sight box")
	assert_eq(guard.ai_state, Guard.AiState.PATROL, "the wall hides her")
	assert_false(guard.alert_mark.visible)
	for y in range(FLOOR_ROW - 10, FLOOR_ROW):
		_tiles.erase_cell(Vector2i(12, y))
	await _until(func() -> bool: return guard.ai_state != Guard.AiState.PATROL, 30)
	assert_eq(guard.ai_state, Guard.AiState.NOTICE, "with the wall gone he sees her")


func test_sees_up_through_a_one_way_platform() -> void:
	_floor(0, 49)
	Arena.fill(_tiles, 8, 12, 24, 12, Arena.ONEWAY)
	var guard := _guard(112.0, 0.0)
	_nina(328.0, 12)
	await _until(func() -> bool: return guard.ai_state != Guard.AiState.PATROL, 40)
	assert_eq(guard.ai_state, Guard.AiState.NOTICE, "a one-way floor is not a wall")


func test_a_solid_platform_blocks_the_same_view() -> void:
	_floor(0, 49)
	Arena.fill(_tiles, 8, 12, 24, 12, Arena.SOLID)
	var guard := _guard(112.0, 0.0)
	var nina := _nina(328.0, 12)
	await _step(40)
	assert_true(guard.sight.overlaps_body(nina), "she is inside the sight box")
	assert_eq(guard.ai_state, Guard.AiState.PATROL, "solid brick hides her")


func test_notice_pause_comes_before_the_chase() -> void:
	_floor(0, 49)
	var guard := _guard(112.0, 0.0)
	_nina(348.0)
	await _until(func() -> bool: return guard.ai_state == Guard.AiState.NOTICE, 30)
	assert_true(guard.alert_mark.visible, "the ! is up")
	var frames := 0
	while guard.ai_state == Guard.AiState.NOTICE and frames < 90:
		assert_eq(guard.velocity.x, 0.0, "he stands still while noticing")
		await _step(1)
		frames += 1
	assert_eq(guard.ai_state, Guard.AiState.CHASE, "then he gives chase")
	assert_false(guard.alert_mark.visible)
	var seconds := frames / float(Engine.physics_ticks_per_second)
	assert_between(seconds, 0.3, 0.5, "the pause lasts 0.3-0.5 s")
	assert_almost_eq(seconds, guard.notice_time, 0.05)


func test_turns_at_the_platform_edge() -> void:
	_floor(10, 19)
	var guard := _guard(240.0, 1000.0)
	await _step(4)
	var floor_y := guard.global_position.y
	var turns := await _watch_patrol(guard, 360)
	assert_gte(turns.flips, 2, "he walks the ledge both ways")
	assert_almost_eq(guard.global_position.y, floor_y, 1.0, "he never steps off")
	assert_gte(turns.min_x, 160.0, "body centre stays over the platform (left)")
	assert_lte(turns.max_x, 320.0, "body centre stays over the platform (right)")
	assert_true(guard.is_on_floor())


func test_turns_at_a_wall() -> void:
	_floor(0, 39)
	Arena.fill(_tiles, 4, FLOOR_ROW - 4, 4, FLOOR_ROW - 1, Arena.SOLID)
	Arena.fill(_tiles, 20, FLOOR_ROW - 4, 20, FLOOR_ROW - 1, Arena.SOLID)
	var guard := _guard(200.0, 1000.0)
	await _step(4)
	var floor_y := guard.global_position.y
	var turns := await _watch_patrol(guard, 480)
	assert_gte(turns.flips, 2, "he paces between the walls")
	assert_almost_eq(guard.global_position.y, floor_y, 1.0, "he never climbs or falls")
	assert_gt(turns.min_x, 80.0, "stops short of the left wall")
	assert_lt(turns.max_x, 320.0, "stops short of the right wall")


func test_chase_stops_at_the_edge() -> void:
	_floor(0, 14)
	Arena.fill(_tiles, 15, FLOOR_ROW + 2, 49, FLOOR_ROW + 3, Arena.SOLID)
	var guard := _guard(112.0, 0.0)
	_nina(528.0, FLOOR_ROW + 2)
	await _step(4)
	var floor_y := guard.global_position.y
	await _until(func() -> bool: return guard.ai_state == Guard.AiState.CHASE, 60)
	await _step(180)
	assert_eq(guard.ai_state, Guard.AiState.CHASE, "still after her")
	assert_almost_eq(guard.global_position.y, floor_y, 1.0, "he does not jump down")
	assert_lte(_centre_x(guard), 240.0, "he waits at the edge")
	assert_gt(_centre_x(guard), 180.0, "right at the edge")


func test_stepping_back_from_the_wind_up_avoids_the_blow() -> void:
	_floor(0, 49)
	var guard := _guard(112.0, 0.0)
	var nina := _nina(172.0)
	await _until(func() -> bool: return guard.ai_state == Guard.AiState.WINDUP, 120)
	assert_eq(guard.ai_state, Guard.AiState.WINDUP, "he winds up a punch")
	Input.action_press("move_right")
	await _until(func() -> bool: return guard.ai_state != Guard.AiState.WINDUP, 60)
	assert_eq(guard.ai_state, Guard.AiState.RECOVER, "the punch went out")
	assert_eq(nina.energy, nina.max_energy, "she was out of reach when it landed")


func test_standing_in_reach_takes_the_blow() -> void:
	_floor(0, 49)
	var guard := _guard(112.0, 0.0)
	var nina := _nina(172.0)
	await _until(func() -> bool: return guard.ai_state == Guard.AiState.WINDUP, 120)
	var windup_frames := 0
	while guard.ai_state == Guard.AiState.WINDUP and windup_frames < 60:
		assert_eq(nina.energy, nina.max_energy, "no damage before the wind-up ends")
		await _step(1)
		windup_frames += 1
	assert_gt(windup_frames, 18, "the wind-up is a visible telegraph")
	assert_eq(nina.energy, nina.max_energy - guard.attack_damage, "the blow lands at the end")


func _floor(x0: int, x1: int) -> void:
	Arena.fill(_tiles, x0, FLOOR_ROW, x1, FLOOR_ROW + 1, Arena.SOLID)


func _guard(centre_x: float, patrol: float) -> CharacterBody2D:
	var guard: CharacterBody2D = GUARD_SCENE.instantiate()
	guard.scale = Vector2(Arena.SCALE, Arena.SCALE)
	guard.position = Vector2(
		centre_x - BODY_X * Arena.SCALE, Arena.origin_on_floor(Arena.row_top(FLOOR_ROW), FEET)
	)
	guard.patrol_distance = patrol
	if patrol <= 0.0:
		guard.patrol_speed = 0.0
	_root.add_child(guard)
	return guard


func _nina(centre_x: float, row: int = FLOOR_ROW) -> Player:
	var nina: Player = PLAYER_SCENE.instantiate()
	nina.scale = Vector2(Arena.SCALE, Arena.SCALE)
	nina.position = Vector2(
		centre_x - BODY_X * Arena.SCALE, Arena.origin_on_floor(Arena.row_top(row), FEET)
	)
	_root.add_child(nina)
	return nina


func _centre_x(guard: CharacterBody2D) -> float:
	return guard.global_position.x + BODY_X * Arena.SCALE


func _watch_patrol(guard: CharacterBody2D, frames: int) -> Dictionary:
	var out := {"flips": 0, "min_x": INF, "max_x": -INF}
	var dir: int = guard.patrol_dir
	for _i in frames:
		await _step(1)
		var cx := _centre_x(guard)
		out.min_x = minf(out.min_x, cx)
		out.max_x = maxf(out.max_x, cx)
		if guard.patrol_dir != dir:
			dir = guard.patrol_dir
			out.flips += 1
	return out


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
