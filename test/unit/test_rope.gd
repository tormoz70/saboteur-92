extends GutTest
## Tightrope: run across, fall on stop. Uses a real Player plus hand-built
## floor / rope Area2Ds (same trigger layer as level_base ropes).

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const FLOOR_TOP := 200.0
const ROPE_Y := 200.0
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]

var _player: Player
var _root: Node2D


func before_each() -> void:
	GameManager.reset_run_state()
	_root = Node2D.new()
	add_child_autofree(_root)
	# Left pad overlaps the rope start so she mounts while still on floor.
	_root.add_child(_make_floor(0.0, 200.0))
	_root.add_child(_make_floor(440.0, 200.0))
	_root.add_child(_make_rope(120.0, 360.0))
	_player = PLAYER_SCENE.instantiate()
	_root.add_child(_player)
	_player.global_position = _spawn()
	_player.rope_stop_grace = 0.08
	await _step(6)


func after_each() -> void:
	_release_all()
	GameManager.reset_run_state()


func test_running_across_the_rope_reaches_the_far_crossbar() -> void:
	await _press("move_right")
	var saw_rope := false
	var frames := 0
	while frames < 240 and _player.global_position.x < 480.0:
		await _step(1)
		frames += 1
		if _player.on_rope:
			saw_rope = true
			assert_eq(_player.collision_mask, 0, "world collision is off on the rope")
	assert_true(saw_rope, "mounted the rope while running")
	assert_true(_player.global_position.x >= 440.0, "Nina reaches the far pad")
	assert_false(_player.on_rope, "she steps off the rope onto the pad")


func test_stopping_mid_rope_falls() -> void:
	await _press("move_right")
	var frames := 0
	# Reach the open span past the left pad (pad ends at x=200).
	while frames < 180 and _player.global_position.x < 260.0:
		await _step(1)
		frames += 1
	assert_true(_player.on_rope, "still on the rope in the open span")
	assert_gt(_player.global_position.x, 200.0, "past the left pad")
	var rope_y := _player.global_position.y
	Input.action_release("move_right")
	await _step(int(_player.rope_stop_grace * 60.0) + 20)
	assert_false(_player.on_rope, "stopping mid-span drops her")
	assert_gt(_player.global_position.y, rope_y + 8.0, "she falls below the rope")
	assert_false(_player.is_on_floor(), "no floor under the open span")


func _spawn() -> Vector2:
	return Vector2(40.0, FLOOR_TOP - Player.BODY_STAND_POS.y - Player.BODY_STAND_SIZE.y * 0.5)


func _make_floor(x: float, w: float) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.collision_layer = CollisionLayers.LAYER_WORLD
	body.collision_mask = 0
	var col := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(w, 24.0)
	col.shape = shape
	col.position = Vector2(x + w * 0.5, FLOOR_TOP + 12.0)
	body.add_child(col)
	return body


func _make_rope(x: float, w: float) -> Area2D:
	var area := Area2D.new()
	area.set_meta("rope", true)
	area.collision_layer = CollisionLayers.LAYER_TRIGGERS
	area.collision_mask = 0
	area.monitorable = true
	area.monitoring = false
	var col := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(w, 48.0)
	col.shape = shape
	col.position = Vector2(x + w * 0.5, ROPE_Y)
	area.add_child(col)
	return area


func _press(action: String) -> void:
	Input.action_press(action)
	await _step(2)


func _release_all() -> void:
	for a in ACTIONS:
		if Input.is_action_pressed(a):
			Input.action_release(a)


func _step(n: int) -> void:
	for _i in n:
		await get_tree().physics_frame
