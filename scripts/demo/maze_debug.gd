extends Node
## `--demo-maze` — debug playthrough of the collision maze.
## Turns on collision shapes + CollisionLayer overlay, then walks / jumps /
## climbs as far as the solids allow. Does not quit: watch the window.

const ARG := "--demo-maze"
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
const COLLISION_PATH := "res://assets/world/s2_collision.json"

enum Mode { LAND, WALK, JUMP, CLIMB_UP, CLIMB_DOWN }

var _player: CharacterBody2D
var _mode: Mode = Mode.LAND
var _dir := 1
var _elapsed := 0.0
var _stuck := 0.0
var _last_pos := Vector2.ZERO
var _driving := false
var _log_wait := 0.0
var _jump_left := 0.0
var _scale := 2.0
var _min := Vector2(INF, INF)
var _max := Vector2(-INF, -INF)
var _status: Label
var _ladders: Array = []
var _climbed: Dictionary = {}
var _reversals := 0
var _jumps := 0
var _climbs := 0


func _ready() -> void:
	if not OS.get_cmdline_user_args().has(ARG):
		queue_free()
		return
	var level := get_parent()
	_player = level.get_node_or_null("Player")
	if _player == null:
		push_error("[Maze] player missing")
		return
	GameManager.demo_mode = true
	get_tree().debug_collisions_hint = true
	# Don't fill CollisionLayer (100k+ cells) — debug shapes on Solids/Ladders are enough.
	for name in ["Guards"]:
		var node: Node = level.get_node_or_null(name)
		if node:
			node.process_mode = Node.PROCESS_MODE_DISABLED
	_load_ladders()
	_add_hud()
	print("[Maze] debug run: collision overlay on, driving Nina")
	await get_tree().create_timer(0.8).timeout
	if not is_instance_valid(_player):
		return
	_last_pos = _player.global_position
	_driving = true
	_mode = Mode.WALK


func _load_ladders() -> void:
	if not FileAccess.file_exists(COLLISION_PATH):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(COLLISION_PATH))
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	_scale = float(parsed.get("scale", 2))
	_ladders = parsed.get("ladders", [])


func _add_hud() -> void:
	var layer := CanvasLayer.new()
	layer.name = "MazeDebugHud"
	layer.layer = 20
	_status = Label.new()
	_status.position = Vector2(12, 8)
	_status.add_theme_font_size_override("font_size", 16)
	_status.modulate = Color(1, 1, 0.4)
	layer.add_child(_status)
	add_child(layer)


func _physics_process(delta: float) -> void:
	if not _driving or not is_instance_valid(_player):
		return
	_elapsed += delta
	_note_bounds()
	if _player.global_position.distance_to(_last_pos) > 6.0:
		_stuck = 0.0
		_last_pos = _player.global_position
	else:
		_stuck += delta
	_drive(delta)
	_log_wait += delta
	if _log_wait >= 1.0:
		_log_wait = 0.0
		_log()
	_refresh_hud()


func _drive(delta: float) -> void:
	if _jump_left > 0.0:
		_jump_left -= delta
		if _jump_left <= 0.0 and Input.is_action_pressed("jump"):
			Input.action_release("jump")
	match _mode:
		Mode.WALK:
			_walk()
		Mode.JUMP:
			_hold_run()
		Mode.CLIMB_UP:
			_press_only("move_up")
			if _stuck > 0.45 or _player.global_position.y < _last_pos.y - 200.0:
				_climbed[_ladder_key()] = true
				_mode = Mode.CLIMB_DOWN
				_stuck = 0.0
		Mode.CLIMB_DOWN:
			_press_only("move_down")
			if _player.is_on_floor() and not _player.on_ladder:
				_mode = Mode.WALK
				_stuck = 0.0


func _walk() -> void:
	if _player.can_climb and not _climbed.has(_ladder_key()):
		_climbs += 1
		_mode = Mode.CLIMB_UP
		_stuck = 0.0
		print("[Maze] climb at (%.0f, %.0f)" % [_player.global_position.x, _player.global_position.y])
		return
	_hold_run()
	if _stuck < 0.4:
		return
	if _player.is_on_floor():
		_jumps += 1
		_jump_left = 0.22
		if not Input.is_action_pressed("jump"):
			Input.action_press("jump")
		_mode = Mode.JUMP
		_stuck = 0.0
		print("[Maze] jump at (%.0f, %.0f)" % [_player.global_position.x, _player.global_position.y])
		return
	_reverse()


func _hold_run() -> void:
	if _dir > 0:
		_press_only("move_right")
	else:
		_press_only("move_left")
	if _mode == Mode.JUMP and _stuck > 0.55:
		if Input.is_action_pressed("jump"):
			Input.action_release("jump")
		_reverse()
		_mode = Mode.WALK


func _reverse() -> void:
	_dir *= -1
	_reversals += 1
	_stuck = 0.0
	print(
		"[Maze] blocked, turn %s at (%.0f, %.0f) floor=%s wall=%s climb=%s"
		% [
			"right" if _dir > 0 else "left",
			_player.global_position.x,
			_player.global_position.y,
			_player.is_on_floor(),
			_player.is_on_wall(),
			_player.can_climb,
		]
	)


func _ladder_key() -> int:
	return int(round(_player.global_position.x / 32.0))


func _press_only(action: String) -> void:
	for candidate in ACTIONS:
		if candidate == action:
			if not Input.is_action_pressed(candidate):
				Input.action_press(candidate)
		elif candidate != "jump" and Input.is_action_pressed(candidate):
			Input.action_release(candidate)


func _note_bounds() -> void:
	var p := _player.global_position
	_min.x = minf(_min.x, p.x)
	_min.y = minf(_min.y, p.y)
	_max.x = maxf(_max.x, p.x)
	_max.y = maxf(_max.y, p.y)


func _log() -> void:
	print(
		"[Maze] t=%.0fs pos=(%.0f, %.0f) floor=%s wall=%s climb=%s dir=%s span=(%.0f,%.0f)-(%.0f,%.0f) rev=%d jumps=%d climbs=%d"
		% [
			_elapsed,
			_player.global_position.x,
			_player.global_position.y,
			_player.is_on_floor(),
			_player.is_on_wall(),
			_player.can_climb,
			"R" if _dir > 0 else "L",
			_min.x,
			_min.y,
			_max.x,
			_max.y,
			_reversals,
			_jumps,
			_climbs,
		]
	)


func _refresh_hud() -> void:
	if _status == null:
		return
	_status.text = (
		"MAZE DEBUG  t=%.0f  pos=%.0f,%.0f  %s  floor=%s wall=%s climb=%s  span %.0fx%.0f  rev=%d"
		% [
			_elapsed,
			_player.global_position.x,
			_player.global_position.y,
			"R" if _dir > 0 else "L",
			_player.is_on_floor(),
			_player.is_on_wall(),
			_player.can_climb,
			_max.x - _min.x,
			_max.y - _min.y,
			_reversals,
		]
	)


func _exit_tree() -> void:
	for action in ACTIONS:
		if Input.is_action_pressed(action):
			Input.action_release(action)
	print(
		"[Maze] done elapsed=%.1f span=(%.0f,%.0f)-(%.0f,%.0f) reversals=%d jumps=%d climbs=%d"
		% [_elapsed, _min.x, _min.y, _max.x, _max.y, _reversals, _jumps, _climbs]
	)
