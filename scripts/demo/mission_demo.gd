extends Node

enum Step {
	GET_KEY,
	TO_LADDER,
	CLIMB_UP,
	GET_DOCUMENT,
	CLIMB_DOWN,
	GET_BOMB,
	PLANT_BOMB,
	ESCAPE,
	DONE,
}

const LADDER_X := 592.0
const UPPER_Y := 72.0
const GROUND_Y := 184.0

var _step: Step = Step.GET_KEY
var _after_climb_up: Step = Step.GET_DOCUMENT
var _after_climb_down: Step = Step.GET_BOMB
var _player: CharacterBody2D
var _wait := 0.0


func _ready() -> void:
	if not OS.get_cmdline_user_args().has("--demo"):
		queue_free()
		return
	_player = get_parent().get_node("Player")
	GameManager.demo_mode = true
	_freeze_guards()
	print("[Demo] Mission autopilot started")
	await get_tree().create_timer(0.6).timeout
	_log_step()


func _physics_process(delta: float) -> void:
	if _step == Step.DONE:
		return
	if GameManager.state == GameManager.GameState.WON:
		_finish()
		return
	if GameManager.state != GameManager.GameState.PLAYING:
		_release_all()
		return

	match _step:
		Step.GET_KEY:
			_hold("move_right")
			if GameManager.has_key or _player.global_position.x >= 112.0:
				_go(Step.TO_LADDER)

		Step.TO_LADDER:
			_after_climb_up = Step.PLANT_BOMB if GameManager.has_bomb else Step.GET_DOCUMENT
			_hold("move_right")
			if _player.global_position.x >= LADDER_X - 8.0:
				_go(Step.CLIMB_UP)

		Step.CLIMB_UP:
			if _player.global_position.x < LADDER_X - 4.0:
				_hold("move_right")
			else:
				_hold("move_up")
			if _player.global_position.y <= UPPER_Y:
				_go(_after_climb_up)

		Step.GET_DOCUMENT:
			_hold("move_left")
			if GameManager.has_document or _player.global_position.x <= 362.0:
				_after_climb_down = Step.GET_BOMB
				_go(Step.CLIMB_DOWN)

		Step.CLIMB_DOWN:
			if _player.global_position.x < LADDER_X - 4.0:
				_hold("move_right")
			elif not _player.is_on_floor() or _player.global_position.y < GROUND_Y - 4.0:
				_hold("move_down")
			else:
				_release_all()
				_go(_after_climb_down)

		Step.GET_BOMB:
			_hold("move_left")
			if GameManager.has_bomb or _player.global_position.x <= 388.0:
				_go(Step.TO_LADDER)

		Step.PLANT_BOMB:
			_hold("move_left")
			if GameManager.bomb_planted or _player.global_position.x <= 428.0:
				_after_climb_down = Step.ESCAPE
				_go(Step.CLIMB_DOWN)

		Step.ESCAPE:
			_hold("move_left")
			if _player.global_position.x <= 60.0:
				_release_all()

	_wait += delta
	if _wait >= 0.75:
		_wait = 0.0
		_log_progress()


func _go(next: Step) -> void:
	_step = next
	_release_all()
	_log_step()


func _finish() -> void:
	_release_all()
	_step = Step.DONE
	print("[Demo] Mission complete! Score=%d Lives=%d" % [GameManager.score, GameManager.lives])


func _freeze_guards() -> void:
	for guard in get_tree().get_nodes_in_group("enemies"):
		guard.set_physics_process(false)
		guard.collision_layer = 0
		guard.collision_mask = 0


func _hold(action: String) -> void:
	Input.action_press(action)


func _release_all() -> void:
	for action in ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]:
		if Input.is_action_pressed(action):
			Input.action_release(action)


func _log_step() -> void:
	print("[Demo] Step: %s" % Step.keys()[_step])


func _log_progress() -> void:
	print(
		"[Demo] pos=(%.0f, %.0f) key=%s doc=%s bomb=%s planted=%s timer=%.1f"
		% [
			_player.global_position.x,
			_player.global_position.y,
			GameManager.has_key,
			GameManager.has_document,
			GameManager.has_bomb,
			GameManager.bomb_planted,
			GameManager.bomb_timer,
		]
	)
