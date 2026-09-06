extends Node
## Headless mission playthrough for CI. Started by `--demo` (see level_01.gd).
## Route matches assets/world/s2_entities.json: key → document → bomb → plant → exit.

enum Step {
	KEY,
	TO_DOC_LADDER,
	CLIMB_TO_DOC,
	GET_DOC,
	CLIMB_FROM_DOC,
	BOMB,
	PLANT,
	ESCAPE,
	DONE,
}

const SCALE := 2.0
# Ladder at PNG x=1860, w=24 → centre 1872, then × scale. Horizontal input
# while off-centre kicks the player off the shaft (player.gd hatch logic).
const LADDER_DOC_X := 1872.0 * SCALE
const GROUND_PLAYER_Y := 792.0 * SCALE
const UPPER_PLAYER_Y := 648.0 * SCALE
const STUCK_LIMIT := 25.0
const TIME_LIMIT := 180.0

var _step: Step = Step.KEY
var _player: CharacterBody2D
var _stuck := 0.0
var _elapsed := 0.0
var _last_pos := Vector2.ZERO
var _log_wait := 0.0
var _ready_to_drive := false
var _finished := false
var _quit_ok := false
var _quit_in := -1.0


func _ready() -> void:
	if not OS.get_cmdline_user_args().has("--demo"):
		queue_free()
		return
	_player = get_parent().get_node("Player")
	GameManager.demo_mode = true
	GameManager.reset_inventory()
	GameManager.state = GameManager.GameState.PLAYING
	GameManager.lives = 3
	_freeze_guards()
	print("[Demo] Mission playthrough started")
	await get_tree().create_timer(0.6).timeout
	if not is_instance_valid(_player):
		_fail("player missing after start delay")
		return
	_last_pos = _player.global_position
	_ready_to_drive = true
	_log_step()


func _physics_process(delta: float) -> void:
	if _finished:
		_quit_in -= delta
		if _quit_in <= 0.0:
			get_tree().quit(0 if _quit_ok else 1)
		return
	if not _ready_to_drive:
		return

	if GameManager.state == GameManager.GameState.WON:
		_succeed()
		return
	if GameManager.state != GameManager.GameState.PLAYING:
		_fail("mission lost during %s" % Step.keys()[_step])
		return

	_drive()
	_elapsed += delta
	_stuck += delta
	if _player.global_position.distance_to(_last_pos) > 8.0:
		_stuck = 0.0
		_last_pos = _player.global_position
	_log_wait += delta
	if _log_wait >= 1.0:
		_log_wait = 0.0
		_log_progress()
	if _stuck > STUCK_LIMIT:
		_fail(
			"stuck on %s at (%.0f, %.0f)"
			% [Step.keys()[_step], _player.global_position.x, _player.global_position.y]
		)
		return
	if _elapsed > TIME_LIMIT:
		_fail("global timeout at %.1fs" % _elapsed)


func _drive() -> void:
	match _step:
		Step.KEY:
			_press_only("move_right")
			if GameManager.has_key:
				_go(Step.TO_DOC_LADDER)
		Step.TO_DOC_LADDER:
			_walk_to_x(LADDER_DOC_X)
			if absf(_body_x() - LADDER_DOC_X) <= 10.0:
				_go(Step.CLIMB_TO_DOC)
		Step.CLIMB_TO_DOC:
			_climb_to_y(LADDER_DOC_X, UPPER_PLAYER_Y + 12.0, false)
			if _player.global_position.y <= UPPER_PLAYER_Y + 12.0 and _player.is_on_floor():
				_go(Step.GET_DOC)
		Step.GET_DOC:
			_press_only("move_right")
			if GameManager.has_document:
				_go(Step.CLIMB_FROM_DOC)
		Step.CLIMB_FROM_DOC:
			_climb_to_y(LADDER_DOC_X, GROUND_PLAYER_Y - 12.0, true)
			if _player.global_position.y >= GROUND_PLAYER_Y - 12.0 and _player.is_on_floor():
				_go(Step.BOMB)
		Step.BOMB:
			_press_only("move_right")
			if GameManager.has_bomb:
				_go(Step.PLANT)
		Step.PLANT:
			_press_only("move_right")
			if GameManager.bomb_planted:
				_go(Step.ESCAPE)
		Step.ESCAPE:
			_press_only("move_left")
		Step.DONE:
			_release_all()


func _climb_to_y(ladder_x: float, target_y: float, going_down: bool) -> void:
	if going_down:
		if _player.on_ladder:
			_press_only("move_down")
			return
		var dx_down := ladder_x - _body_x()
		if absf(dx_down) > 6.0:
			if dx_down > 0.0:
				_press_only("move_right")
			else:
				_press_only("move_left")
			return
		_press_only("move_down")
		return
	if _player.global_position.y <= target_y:
		_press_only("move_right")
		return
	if _player.on_ladder:
		_press_only("move_up")
		return
	var dx := ladder_x - _body_x()
	if absf(dx) > 6.0:
		if dx > 0.0:
			_press_only("move_right")
		else:
			_press_only("move_left")
		return
	_press_only("move_up")


func _walk_to_x(world_x: float) -> void:
	var dx := world_x - _body_x()
	if dx > 6.0:
		_press_only("move_right")
	elif dx < -6.0:
		_press_only("move_left")
	else:
		_release_all()


func _press_only(action: String) -> void:
	for name in ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]:
		if name == action:
			if not Input.is_action_pressed(name):
				Input.action_press(name)
		elif Input.is_action_pressed(name):
			Input.action_release(name)


func _body_x() -> float:
	return _player.global_position.x + 24.0 * SCALE


func _go(next: Step) -> void:
	_step = next
	_stuck = 0.0
	_release_all()
	_log_step()


func _succeed() -> void:
	_release_all()
	_step = Step.DONE
	_finished = true
	_quit_ok = true
	_quit_in = 0.4
	print(
		"[Demo] Mission complete! score=%d lives=%d pos=(%.0f, %.0f) timer=%.1f elapsed=%.1f"
		% [
			GameManager.score,
			GameManager.lives,
			_player.global_position.x,
			_player.global_position.y,
			GameManager.bomb_timer,
			_elapsed,
		]
	)


func _fail(reason: String) -> void:
	_release_all()
	_step = Step.DONE
	_finished = true
	_quit_ok = false
	_quit_in = 0.2
	push_error("[Demo] FAIL: %s" % reason)


func _freeze_guards() -> void:
	for guard in get_tree().get_nodes_in_group("enemies"):
		guard.set_physics_process(false)
		guard.collision_layer = 0
		guard.collision_mask = 0


func _release_all() -> void:
	for action in ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]:
		if Input.is_action_pressed(action):
			Input.action_release(action)


func _log_step() -> void:
	print("[Demo] Step: %s" % Step.keys()[_step])


func _log_progress() -> void:
	print(
		"[Demo] pos=(%.0f, %.0f) floor=%s ladder=%s key=%s doc=%s bomb=%s planted=%s timer=%.1f"
		% [
			_player.global_position.x,
			_player.global_position.y,
			_player.is_on_floor(),
			_player.on_ladder,
			GameManager.has_key,
			GameManager.has_document,
			GameManager.has_bomb,
			GameManager.bomb_planted,
			GameManager.bomb_timer,
		]
	)
