extends Node
## `--demo-tilt` fakes a phone's tilt sensor with Input.set_gravity and checks
## that Nina walks the way the screen leans, with no key or button held.
##
## Sensor hardware is the one part of tilt steering a desktop cannot exercise.
## Everything after it is covered here: the project settings that let readings
## through, TiltSteer's smoothing and walk axis, and the player acting on it.

const ARG := "--demo-tilt"
## Roll well past TiltSteer.ENGAGE_TILT, with gravity still mostly down-screen.
const LEAN := 6.0
const DOWN := -7.5
const HOLD := 1.1
const SETTLE := 0.8
const MIN_WALK := 40.0
## Levelling off still coasts a few frames while the low-passed reading falls
## back through the hold angle, so "stopped" is checked on the velocity too.
const MAX_DRIFT := 24.0
const STEPS: Array[Dictionary] = [
	{"name": "lean right", "roll": LEAN, "want": 1},
	{"name": "lean left", "roll": -LEAN, "want": -1},
	{"name": "hold level", "roll": 0.0, "want": 0},
]

var _player: CharacterBody2D
var _step: int = -1
var _elapsed: float = 0.0
var _mark_x: float = 0.0
var _finished: bool = false
var _quit_ok: bool = false
var _quit_in: float = -1.0


func _ready() -> void:
	if not OS.get_cmdline_user_args().has(ARG):
		queue_free()
		return
	_player = get_parent().get_node_or_null("Player")
	if _player == null:
		_fail("player missing")
		return
	_lean(0.0)
	TiltSteer.enabled = true
	if not TiltSteer.enabled:
		_fail("tilt steering refused to switch on")
		return
	print("[Demo] Tilt probe started: no keys held, gravity faked")
	await get_tree().create_timer(SETTLE).timeout
	if not is_instance_valid(_player):
		_fail("player vanished during the settle delay")
		return
	_begin_step(0)


func _physics_process(delta: float) -> void:
	if _finished:
		_quit_in -= delta
		if _quit_in <= 0.0:
			get_tree().quit(0 if _quit_ok else 1)
		return
	if _step < 0 or _step >= STEPS.size():
		return
	_elapsed += delta
	if _elapsed < HOLD:
		return
	var spec := STEPS[_step]
	var walked := _player.global_position.x - _mark_x
	print("[Demo] %s -> walked %.0f px" % [spec["name"], walked])
	if not _walk_matches(int(spec["want"]), walked):
		_fail("%s moved %.0f px" % [spec["name"], walked])
		return
	if _step + 1 >= STEPS.size():
		_succeed()
		return
	_begin_step(_step + 1)


func _walk_matches(want: int, walked: float) -> bool:
	if want > 0:
		return walked > MIN_WALK
	if want < 0:
		return walked < -MIN_WALK
	return absf(walked) < MAX_DRIFT and absf(_player.velocity.x) < 1.0


func _begin_step(index: int) -> void:
	_step = index
	_elapsed = 0.0
	_mark_x = _player.global_position.x
	_lean(float(STEPS[index]["roll"]))
	print("[Demo] Step: %s" % STEPS[index]["name"])


func _lean(roll: float) -> void:
	# Godot hands over gravity in screen space: +x is the right screen edge.
	Input.set_gravity(Vector3(roll, DOWN, 0.0))


func _succeed() -> void:
	_finish(true)
	print("[Demo] Tilt steering OK")


func _fail(reason: String) -> void:
	_finish(false)
	push_error("[Demo] FAIL: %s" % reason)


func _finish(ok: bool) -> void:
	_step = STEPS.size()
	_lean(0.0)
	TiltSteer.enabled = false
	_finished = true
	_quit_ok = ok
	_quit_in = 0.4 if ok else 0.2
