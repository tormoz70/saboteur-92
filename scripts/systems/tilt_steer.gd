extends Node
## Optional phone-tilt left/right. Off by default; D-pad and keys win.
##
## Sensors only reach the game when input_devices/sensors/enable_accelerometer
## (and enable_gravity) are on in project.godot: the Android backend registers
## its SensorEventListener from those settings, so with them off every read is
## Vector3.ZERO and tilt silently does nothing.

signal enabled_changed(is_on: bool)
signal sensor_missing_changed(is_missing: bool)

const CONFIG_PATH := "user://settings.cfg"
const CONFIG_SECTION := "controls"
const CONFIG_KEY := "tilt_steer"
## m/s^2 of roll past the calibrated rest angle: ~12° to start walking and ~7°
## to keep walking, so a hand wobbling on the threshold does not stutter.
const ENGAGE_TILT := 2.0
const HOLD_TILT := 1.2
## Gravity is ~9.8 m/s^2, so anything this short means "no sensor reading".
const SENSOR_EPSILON := 0.5
## Rest angle is captured when tilt is switched on; cap it so enabling the
## option on a phone lying on its side still leaves both directions reachable.
const NEUTRAL_LIMIT := 4.0
const SMOOTHING := 12.0
## Report a missing sensor only after a full second of silence: readings arrive
## on the sensor's own clock, not once per frame.
const SENSOR_GRACE := 1.0

var enabled: bool = false:
	set(value):
		if enabled == value:
			return
		enabled = value
		if enabled:
			calibrate()
		else:
			_clear_tilt()
		_save()
		enabled_changed.emit(enabled)

var sensor_missing: bool = false

var _tilt: float = 0.0
var _axis: float = 0.0
var _neutral: float = 0.0
var _silence: float = 0.0


func _ready() -> void:
	_load()


func _physics_process(delta: float) -> void:
	if not enabled or GameManager.demo_mode:
		_clear_tilt()
		return
	var sensor := read_sensor()
	if sensor == Vector3.ZERO:
		_silence += delta
		_axis = 0.0
		_set_sensor_missing(_silence >= SENSOR_GRACE)
		return
	_silence = 0.0
	_set_sensor_missing(false)
	_tilt = lerpf(_tilt, screen_tilt(sensor) - _neutral, minf(SMOOTHING * delta, 1.0))
	_axis = axis_from_tilt(_tilt, _axis)


func move_axis() -> float:
	var buttons := Input.get_axis("move_left", "move_right")
	if absf(buttons) > 0.01:
		return buttons
	if not enabled or GameManager.demo_mode:
		return 0.0
	return _axis


func calibrate() -> void:
	# Whatever angle the phone is held at right now becomes "walk nowhere".
	var sensor := read_sensor()
	_neutral = 0.0
	if sensor != Vector3.ZERO:
		_neutral = clampf(screen_tilt(sensor), -NEUTRAL_LIMIT, NEUTRAL_LIMIT)
	_tilt = 0.0
	_axis = 0.0
	_silence = 0.0


func read_sensor() -> Vector3:
	# Gravity is the low-passed sensor and is what a tilt reading wants, but
	# not every phone reports it, so fall back to the raw accelerometer.
	var gravity := Input.get_gravity()
	if gravity.length() >= SENSOR_EPSILON:
		return gravity
	var acceleration := Input.get_accelerometer()
	if acceleration.length() >= SENSOR_EPSILON:
		return acceleration
	return Vector3.ZERO


static func screen_tilt(sensor: Vector3) -> float:
	# Android rotates sensor values into screen space before handing them to
	# Godot (GodotInputHandler.onSensorChanged) and negates them, so the vector
	# follows gravity with +x at the right edge of the screen no matter how the
	# device is rotated. Screen-left edge down -> negative x -> walk left.
	return sensor.x


static func axis_from_tilt(tilt: float, current_axis: float) -> float:
	var direction := signf(tilt)
	if direction == current_axis and absf(tilt) >= HOLD_TILT:
		return current_axis
	if absf(tilt) >= ENGAGE_TILT:
		return direction
	return 0.0


func _set_sensor_missing(is_missing: bool) -> void:
	if sensor_missing == is_missing:
		return
	sensor_missing = is_missing
	sensor_missing_changed.emit(sensor_missing)


func _clear_tilt() -> void:
	_tilt = 0.0
	_axis = 0.0
	_silence = 0.0
	_set_sensor_missing(false)


func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) != OK:
		return
	enabled = bool(cfg.get_value(CONFIG_SECTION, CONFIG_KEY, false))


func _save() -> void:
	var cfg := ConfigFile.new()
	cfg.load(CONFIG_PATH)
	cfg.set_value(CONFIG_SECTION, CONFIG_KEY, enabled)
	cfg.save(CONFIG_PATH)
