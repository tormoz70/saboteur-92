extends Node
## Optional phone-tilt left/right. Off by default; D-pad and keys win.

signal enabled_changed(is_on: bool)

enum Orientation { LANDSCAPE, REVERSE_LANDSCAPE, PORTRAIT, REVERSE_PORTRAIT }

const CONFIG_PATH := "user://settings.cfg"
const CONFIG_SECTION := "controls"
const CONFIG_KEY := "tilt_steer"
const DEADZONE := 1.4 # m/s^2; about 8–10° of roll past rest.

var enabled: bool = false:
	set(value):
		if enabled == value:
			return
		enabled = value
		_save()
		enabled_changed.emit(enabled)


func _ready() -> void:
	_load()


func move_axis() -> float:
	var buttons := Input.get_axis("move_left", "move_right")
	if absf(buttons) > 0.01:
		return buttons
	if not enabled or GameManager.demo_mode:
		return 0.0
	return axis_from_accelerometer(Input.get_accelerometer(), current_orientation())


func current_orientation() -> Orientation:
	var orient := DisplayServer.screen_get_orientation()
	match orient:
		DisplayServer.SCREEN_REVERSE_LANDSCAPE:
			return Orientation.REVERSE_LANDSCAPE
		DisplayServer.SCREEN_PORTRAIT:
			return Orientation.PORTRAIT
		DisplayServer.SCREEN_REVERSE_PORTRAIT:
			return Orientation.REVERSE_PORTRAIT
		_:
			# SENSOR / LANDSCAPE / unknown: the game viewport is 16:9.
			if DisplayServer.window_get_size().y > DisplayServer.window_get_size().x:
				return Orientation.PORTRAIT
			return Orientation.LANDSCAPE


static func axis_from_accelerometer(acc: Vector3, orientation: Orientation) -> float:
	var raw := raw_tilt(acc, orientation)
	if raw > DEADZONE:
		return 1.0
	if raw < -DEADZONE:
		return -1.0
	return 0.0


static func raw_tilt(acc: Vector3, orientation: Orientation) -> float:
	## Device-space gravity. Left edge of the *screen* down → negative (walk left).
	match orientation:
		Orientation.LANDSCAPE:
			return -acc.y
		Orientation.REVERSE_LANDSCAPE:
			return acc.y
		Orientation.PORTRAIT:
			return acc.x
		Orientation.REVERSE_PORTRAIT:
			return -acc.x
	return -acc.y


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
