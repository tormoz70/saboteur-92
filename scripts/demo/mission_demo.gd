extends Node
## Headless mission autotest for CI. `--demo` walks spawn → exit with live
## guards. `--demo-fuse` plants, stands still, and expects LOST not WON.
## Layout is read from s2_entities.json / s2_collision.json, not hardcoded.

enum Step {
	KEY,
	TO_DOC_LADDER,
	CLIMB_TO_DOC,
	GET_DOC,
	CLIMB_FROM_DOC,
	BOMB,
	PLANT,
	ESCAPE,
	WAIT_FUSE,
	DONE,
}

const ENTITIES_PATH := "res://assets/world/s2_entities.json"
const COLLISION_PATH := "res://assets/world/s2_collision.json"
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
const STUCK_LIMIT := 25.0
const TIME_LIMIT := 120.0
const FUSE_TEST_TIME := 1.0

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
var _fuse_only := false
var _scale := 2.0
var _ladder_doc_x := 0.0
var _ground_player_y := 0.0
var _upper_player_y := 0.0


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	_fuse_only = args.has("--demo-fuse")
	if not args.has("--demo") and not _fuse_only:
		queue_free()
		return
	_player = get_parent().get_node("Player")
	if GameManager.lives != 3 or GameManager.state != GameManager.GameState.PLAYING:
		_fail(
			"GameManager not in a clean start (lives=%d state=%d)"
			% [GameManager.lives, int(GameManager.state)]
		)
		return
	if not _load_layout():
		return
	if _fuse_only:
		GameManager.bomb_fuse_time = FUSE_TEST_TIME
		GameManager.has_key = true
		GameManager.has_document = true
		GameManager.has_bomb = true
		_step = Step.PLANT
		print("[Demo] Fuse-loss probe started (fuse=%.1fs)" % GameManager.bomb_fuse_time)
	else:
		print("[Demo] Mission playthrough started (live guards)")
	await get_tree().create_timer(0.6).timeout
	if not is_instance_valid(_player):
		_fail("player missing after start delay")
		return
	_last_pos = _player.global_position
	_ready_to_drive = true
	_log_step()


func _load_layout() -> bool:
	var entities := _parse_json(ENTITIES_PATH)
	var collision := _parse_json(COLLISION_PATH)
	if entities.is_empty() or collision.is_empty():
		_fail("could not read layout JSON")
		return false
	_scale = float(collision.get("scale", 2))
	var spawn: Array = entities.get("spawn", [])
	if spawn.size() < 2:
		_fail("entities JSON missing spawn")
		return false
	_ground_player_y = float(spawn[1]) * _scale
	var doc := _item_xy(entities, "document")
	if doc == Vector2.INF:
		_fail("entities JSON missing document")
		return false
	_upper_player_y = (doc.y - 48.0) * _scale
	_ladder_doc_x = _ladder_center_near(doc, collision.get("ladders", []))
	if _ladder_doc_x <= 0.0:
		_fail("no ladder covers the document")
		return false
	return true


func _item_xy(entities: Dictionary, item_id: String) -> Vector2:
	for spec in entities.get("items", []):
		if str(spec.get("id", "")) == item_id:
			if not spec.has("x") or not spec.has("y"):
				return Vector2.INF
			return Vector2(float(spec["x"]), float(spec["y"]))
	return Vector2.INF


func _ladder_center_near(doc_png: Vector2, ladders: Array) -> float:
	var best := INF
	var best_cx := 0.0
	for rect in ladders:
		var x := float(rect[0])
		var y := float(rect[1])
		var w := float(rect[2])
		var h := float(rect[3])
		# Pickups sit on the floor just above the Area2D top, so allow a
		# hatch-sized band above the rectangle.
		if doc_png.y < y - 32.0 or doc_png.y > y + h:
			continue
		var cx := x + w * 0.5
		var d := absf(cx - doc_png.x)
		if d < best:
			best = d
			best_cx = cx
	if best == INF:
		return 0.0
	return best_cx * _scale


func _parse_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("[Demo] missing %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("[Demo] could not parse %s" % path)
		return {}
	return parsed


func _physics_process(delta: float) -> void:
	if _finished:
		_quit_in -= delta
		if _quit_in <= 0.0:
			get_tree().quit(0 if _quit_ok else 1)
		return
	if not _ready_to_drive:
		return

	if GameManager.state == GameManager.GameState.WON:
		if _fuse_only:
			_fail("fuse test won instead of losing")
			return
		_succeed()
		return
	if GameManager.state == GameManager.GameState.LOST:
		if _fuse_only:
			_succeed_fuse_loss()
			return
		_fail("mission lost during %s" % Step.keys()[_step])
		return
	if GameManager.state != GameManager.GameState.PLAYING:
		_fail("unexpected state %d during %s" % [int(GameManager.state), Step.keys()[_step]])
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
			_walk_to_x(_ladder_doc_x)
			if absf(_body_x() - _ladder_doc_x) <= 10.0:
				_go(Step.CLIMB_TO_DOC)
		Step.CLIMB_TO_DOC:
			_climb_to_y(_ladder_doc_x, _upper_player_y + 12.0, false)
			if _player.global_position.y <= _upper_player_y + 12.0 and _player.is_on_floor():
				_go(Step.GET_DOC)
		Step.GET_DOC:
			_press_only("move_right")
			if GameManager.has_document:
				_go(Step.CLIMB_FROM_DOC)
		Step.CLIMB_FROM_DOC:
			_climb_to_y(_ladder_doc_x, _ground_player_y - 12.0, true)
			if _player.global_position.y >= _ground_player_y - 12.0 and _player.is_on_floor():
				_go(Step.BOMB)
		Step.BOMB:
			_press_only("move_right")
			if GameManager.has_bomb:
				_go(Step.PLANT)
		Step.PLANT:
			_press_only("move_right")
			if GameManager.bomb_planted:
				if _fuse_only:
					_go(Step.WAIT_FUSE)
				else:
					_go(Step.ESCAPE)
		Step.ESCAPE:
			_press_only("move_left")
		Step.WAIT_FUSE:
			_release_all()
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
	for candidate in ACTIONS:
		if candidate == action:
			if not Input.is_action_pressed(candidate):
				Input.action_press(candidate)
		elif Input.is_action_pressed(candidate):
			Input.action_release(candidate)


func _body_x() -> float:
	return _player.global_position.x + 24.0 * _scale


func _go(next: Step) -> void:
	_step = next
	_stuck = 0.0
	_release_all()
	_log_step()


func _succeed() -> void:
	var expected := 150 + GameManager.ESCAPE_BONUS
	if GameManager.score != expected or GameManager.lives != 3 or GameManager.bomb_timer <= 0.0:
		_fail(
			"unexpected outcome: score=%d lives=%d timer=%.1f (want score=%d lives=3 timer>0)"
			% [GameManager.score, GameManager.lives, GameManager.bomb_timer, expected]
		)
		return
	_finish(true)
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


func _succeed_fuse_loss() -> void:
	if GameManager.lives != 0:
		_fail("fuse loss left lives=%d" % GameManager.lives)
		return
	_finish(true)
	print(
		"[Demo] Fuse loss OK reason=%s lives=%d score=%d elapsed=%.1f"
		% [GameManager.fail_reason, GameManager.lives, GameManager.score, _elapsed]
	)


func _fail(reason: String) -> void:
	_finish(false)
	push_error("[Demo] FAIL: %s" % reason)


func _finish(ok: bool) -> void:
	_release_all()
	_step = Step.DONE
	_finished = true
	_quit_ok = ok
	_quit_in = 0.4 if ok else 0.2


func _release_all() -> void:
	for action in ACTIONS:
		if Input.is_action_pressed(action):
			Input.action_release(action)


func _log_step() -> void:
	print("[Demo] Step: %s" % Step.keys()[_step])


func _log_progress() -> void:
	print(
		"[Demo] pos=(%.0f, %.0f) floor=%s ladder=%s key=%s doc=%s bomb=%s planted=%s timer=%.1f lives=%d energy=%s"
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
			GameManager.lives,
			_player.get("energy"),
		]
	)
