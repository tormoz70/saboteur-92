extends Node
## Headless mission autotest for CI.
## `--demo` — quiet lab route: key, orders, crate codes, service lift, interlock,
## card, dump console, west tunnel exit (coords from s2_entities.json).
## `--demo-fuse` — teleports to the console, plants, stands still, expects LOST.

enum Step {
	KEY,
	TO_DOC_LADDER,
	CLIMB_TO_DOC,
	GET_DOC,
	CLIMB_FROM_DOC,
	ARM_QUIET_ROUTE,
	TO_SERVICE_LIFT,
	RIDE_SERVICE_DOWN,
	TO_INTERLOCK,
	TO_CARD,
	TO_PLANT,
	ESCAPE,
	WAIT_FUSE,
	DONE,
}

const ENTITIES_PATH := "res://assets/world/s2_entities.json"
const COLLISION_PATH := "res://assets/world/s2_collision.json"
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
const STUCK_LIMIT := 45.0
const TIME_LIMIT := 300.0
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
var _ladders: Array = []
var _marker_world: Dictionary = {}
var _service_lift_x := 0.0
var _service_lift_top_y := 0.0
var _service_lift_bottom_y := 0.0
var _interlock_world := Vector2.ZERO
var _card_world := Vector2.ZERO
var _plant_world := Vector2.ZERO
var _exit_world := Vector2.ZERO


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
	GameManager.demo_mode = true
	if _fuse_only:
		GameManager.bomb_fuse_time = FUSE_TEST_TIME
		GameManager.has_key = true
		GameManager.has_document = true
		GameManager.has_bomb = true
		_player.global_position = _plant_world - Vector2(80.0, 0.0)
		_player.velocity = Vector2.ZERO
		_step = Step.TO_PLANT
		print("[Demo] Fuse-loss probe started (fuse=%.1fs)" % GameManager.bomb_fuse_time)
	else:
		print("[Demo] Lab mission playthrough started (quiet route)")
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
	_ladders = collision.get("ladders", [])
	var spawn: Array = entities.get("spawn", [])
	if spawn.size() < 2:
		_fail("entities JSON missing spawn")
		return false
	_ground_player_y = float(spawn[1]) * _scale
	var doc := _item_png(entities, "document")
	if doc == Vector2.INF:
		_fail("entities JSON missing document")
		return false
	_upper_player_y = (doc.y - 48.0) * _scale
	_ladder_doc_x = _ladder_center_near(doc, _ladders)
	if _ladder_doc_x <= 0.0:
		_fail("no ladder covers the document")
		return false
	var lifts: Array = collision.get("lifts", [])
	var lock: Dictionary = entities.get("locked_lift", {})
	if not lock.has("x"):
		_fail("entities JSON missing locked_lift")
		return false
	var lift_spec := _lift_spec_near(float(lock["x"]), lifts)
	if lift_spec.is_empty():
		_fail("no lift matches locked_lift x=%s" % lock["x"])
		return false
	for spec in entities.get("markers", []):
		var label := str(spec.get("label", ""))
		if label.is_empty() or not spec.has("x") or not spec.has("y"):
			continue
		_marker_world[label] = _png_to_world(float(spec["x"]), float(spec["y"]))
	if _marker_world.size() < 3:
		_fail("entities JSON missing crate code markers")
		return false
	_service_lift_x = (float(lift_spec["x"]) + float(lift_spec["w"]) * 0.5) * _scale
	_service_lift_top_y = float(lift_spec["top"]) * _scale
	_service_lift_bottom_y = float(lift_spec["bottom"]) * _scale
	var interlock: Dictionary = entities.get("interlock", {})
	if interlock.is_empty():
		_fail("entities JSON missing interlock")
		return false
	_interlock_world = _png_to_world(float(interlock["x"]), float(interlock["y"]))
	var bomb := _item_png(entities, "bomb")
	if bomb == Vector2.INF:
		_fail("entities JSON missing bomb/card")
		return false
	_card_world = _png_to_world(bomb.x, bomb.y)
	var sab: Dictionary = entities.get("sabotage", {})
	if sab.is_empty():
		_fail("entities JSON missing sabotage console")
		return false
	_plant_world = _png_to_world(float(sab["x"]), float(sab["y"]))
	var ex: Dictionary = entities.get("exit", {})
	if ex.is_empty():
		_fail("entities JSON missing exit")
		return false
	_exit_world = _png_to_world(float(ex["x"]), float(ex["y"]))
	return true


func _item_png(entities: Dictionary, item_id: String) -> Vector2:
	for spec in entities.get("items", []):
		if str(spec.get("id", "")) == item_id:
			if not spec.has("x") or not spec.has("y"):
				return Vector2.INF
			return Vector2(float(spec["x"]), float(spec["y"]))
	return Vector2.INF


func _lift_spec_near(png_x: float, lifts: Array) -> Dictionary:
	for spec in lifts:
		if absf(float(spec.get("x", -1.0)) - png_x) < 1.0:
			return spec
	return {}


func _ladder_center_near(doc_png: Vector2, ladders: Array) -> float:
	var best := INF
	var best_cx := 0.0
	for rect in ladders:
		var x := float(rect[0])
		var y := float(rect[1])
		var w := float(rect[2])
		var h := float(rect[3])
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


func _ladder_x_near(world_x: float, world_y: float) -> float:
	var png_y := world_y / _scale
	var best := INF
	var best_cx := _ladder_doc_x
	for rect in _ladders:
		var x := float(rect[0])
		var y := float(rect[1])
		var w := float(rect[2])
		var h := float(rect[3])
		if png_y < y - 64.0 or png_y > y + h + 64.0:
			continue
		var cx := (x + w * 0.5) * _scale
		var d := absf(cx - world_x)
		if d < best:
			best = d
			best_cx = cx
	return best_cx


func _png_to_world(x: float, y: float) -> Vector2:
	return Vector2(x, y) * _scale


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
	if _check_mission_state():
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


func _check_mission_state() -> bool:
	if GameManager.state == GameManager.GameState.WON:
		if _fuse_only:
			_fail("fuse test won instead of losing")
		else:
			_succeed()
		return true
	if GameManager.state == GameManager.GameState.LOST:
		if _fuse_only:
			_succeed_fuse_loss()
		else:
			_fail("mission lost during %s" % Step.keys()[_step])
		return true
	if GameManager.state != GameManager.GameState.PLAYING:
		_fail("unexpected state %d during %s" % [int(GameManager.state), Step.keys()[_step]])
		return true
	return false


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
			if _player.global_position.y <= _marker_world["06"].y + 48.0:
				GameManager.note_code("06")
			if _player.global_position.y <= _upper_player_y + 24.0:
				if _player.is_on_floor():
					_go(Step.GET_DOC)
				elif _player.on_ladder:
					_press_only("move_right")
		Step.GET_DOC:
			_press_only("move_right")
			if GameManager.has_document:
				_go(Step.CLIMB_FROM_DOC)
		Step.CLIMB_FROM_DOC:
			_climb_to_y(_ladder_doc_x, _ground_player_y - 12.0, true)
			if _player.global_position.y >= _ground_player_y - 12.0 and _player.is_on_floor():
				_go(Step.ARM_QUIET_ROUTE)
		Step.ARM_QUIET_ROUTE:
			_arm_quiet_route()
			_go(Step.TO_SERVICE_LIFT)
		Step.TO_SERVICE_LIFT:
			_approach_lift_top()
			if _player.on_lift and absf(_body_x() - _service_lift_x) <= 32.0:
				_go(Step.RIDE_SERVICE_DOWN)
		Step.RIDE_SERVICE_DOWN:
			_ride_service_down()
			if _player.global_position.y >= _service_lift_bottom_y - 200.0:
				_arm_lab_route()
				_go(Step.TO_INTERLOCK)
		Step.TO_INTERLOCK:
			if GameManager.interlock_cut:
				_player.global_position = _card_world - Vector2(64.0, 0.0)
				_player.velocity = Vector2.ZERO
				_go(Step.TO_CARD)
			else:
				_navigate_to(_interlock_world)
		Step.TO_CARD:
			if not GameManager.has_bomb:
				_player.global_position = _card_world - Vector2(24.0, 40.0)
				_player.velocity = Vector2.ZERO
			if GameManager.has_bomb:
				_go(Step.TO_PLANT)
		Step.TO_PLANT:
			if not GameManager.bomb_planted:
				_player.global_position = _plant_world - Vector2(24.0, 40.0)
				_player.velocity = Vector2.ZERO
			if GameManager.bomb_planted:
				if _fuse_only:
					_go(Step.WAIT_FUSE)
				else:
					_player.global_position = _exit_world - Vector2(120.0, 0.0)
					_player.velocity = Vector2.ZERO
					_go(Step.ESCAPE)
		Step.ESCAPE:
			_player.global_position = _exit_world - Vector2(24.0, 40.0)
			_player.velocity = Vector2.ZERO
			_press_only("move_left")
		Step.WAIT_FUSE:
			_release_all()
		Step.DONE:
			_release_all()


func _arm_lab_route() -> void:
	_player.global_position = _interlock_world - Vector2(64.0, 0.0)
	_player.velocity = Vector2.ZERO
	GameManager.cut_interlock()


func _arm_quiet_route() -> void:
	for label in GameManager.LIFT_CODE_LABELS:
		GameManager.note_code(label)
	_player.global_position = Vector2(_service_lift_x, _service_lift_top_y + 56.0)
	_player.velocity = Vector2.ZERO


func _visit_marker(label: String, target: Vector2) -> void:
	if label in GameManager.seen_codes:
		return
	_navigate_to(target)
	# Crate codes sit above floor lip; allow extra vertical slack.
	if _near(target, 48.0, 72.0):
		GameManager.note_code(label)


func _approach_lift_top() -> void:
	var top := Vector2(_service_lift_x, _service_lift_top_y)
	if absf(_body_x() - top.x) > 24.0:
		_walk_to_x(top.x)
		return
	if _player.global_position.y > top.y + 48.0:
		_climb_to_y(_service_lift_x, top.y, false)
		return
	if _player.global_position.y < top.y - 24.0:
		if _player.on_ladder:
			_press_only("move_down")
		else:
			_press_only("move_right")
		return
	_release_all()


func _ride_service_down() -> void:
	_walk_to_x(_service_lift_x)
	if _player.on_lift:
		_press_only("move_down")
	elif _player.global_position.y < _service_lift_bottom_y - 120.0:
		_press_only("move_down")


func _navigate_to(target: Vector2) -> void:
	if _near(target, 32.0, 48.0):
		_release_all()
		return
	var pos := _player.global_position
	var cx := _body_x()
	if absf(cx - target.x) > 20.0:
		_walk_to_x(target.x)
		return
	var dy := target.y - pos.y
	if dy < -24.0:
		var ladder_x := _ladder_x_near(target.x, pos.y)
		if absf(cx - ladder_x) > 16.0:
			_walk_to_x(ladder_x)
			return
		_climb_to_y(ladder_x, target.y, false)
	elif dy > 24.0:
		if absf(cx - _service_lift_x) <= 40.0 and _player.on_lift:
			_press_only("move_down")
			return
		var ladder_x := _ladder_x_near(target.x, pos.y)
		if absf(cx - ladder_x) > 16.0:
			_walk_to_x(ladder_x)
			return
		_climb_to_y(ladder_x, target.y, true)
	else:
		_release_all()


func _near(target: Vector2, slack_x: float, slack_y: float) -> bool:
	return (
		absf(_body_x() - target.x) <= slack_x
		and absf(_player.global_position.y - target.y) <= slack_y
	)


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
	if _player.global_position.y <= target_y + 8.0:
		_release_all()
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
	var min_score := 150 + GameManager.ESCAPE_BONUS
	if GameManager.score < min_score or GameManager.lives != 3 or GameManager.bomb_timer <= 0.0:
		_fail(
			"unexpected outcome: score=%d lives=%d timer=%.1f (want score>=%d lives=3 timer>0)"
			% [GameManager.score, GameManager.lives, GameManager.bomb_timer, min_score]
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
	if GameManager.fail_reason != "The complex collapsed":
		_fail("fuse loss reason=%s" % GameManager.fail_reason)
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
		(
			"[Demo] pos=(%.0f, %.0f) floor=%s ladder=%s lift=%s codes=%s interlock=%s key=%s doc=%s bomb=%s planted=%s"
			% [
				_player.global_position.x,
				_player.global_position.y,
				_player.is_on_floor(),
				_player.on_ladder,
				_player.on_lift,
				GameManager.seen_codes,
				GameManager.interlock_cut,
				GameManager.has_key,
				GameManager.has_document,
				GameManager.has_bomb,
				GameManager.bomb_planted,
			]
		)
		+ (
			" timer=%.1f lives=%d energy=%s"
			% [GameManager.bomb_timer, GameManager.lives, _player.get("energy")]
		)
	)
