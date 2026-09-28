extends CanvasLayer

const ControlChrome := preload("res://scripts/ui/control_chrome.gd")

@onready var tilt_toggle: Button = $Root/TiltToggle
@onready var left_pad: OctantTouchPad = $Root/LeftPad
@onready var right_pad: Control = $Root/RightPad


func _ready() -> void:
	tilt_toggle.button_pressed = TiltSteer.enabled
	_refresh_tilt_label()
	tilt_toggle.toggled.connect(_on_tilt_toggled)
	TiltSteer.enabled_changed.connect(_on_tilt_enabled_changed)
	TiltSteer.sensor_missing_changed.connect(_on_tilt_sensor_missing_changed)
	GameSettings.changed.connect(apply_settings)
	ControlChrome.apply(tilt_toggle)
	apply_settings()


func apply_settings() -> void:
	# Scale around the screen corner each pad is anchored to, so a bigger pad
	# grows inward instead of off the edge.
	left_pad.pivot_offset = Vector2(0.0, left_pad.size.y)
	right_pad.pivot_offset = right_pad.size
	var s := Vector2.ONE * GameSettings.pad_scale
	left_pad.scale = s
	right_pad.scale = s
	left_pad.modulate.a = GameSettings.pad_opacity
	right_pad.modulate.a = GameSettings.pad_opacity


## Drops every finger and held action, e.g. when a pause hides the pad
## mid-touch and the release would never arrive.
func release_all() -> void:
	left_pad.release_finger()
	ChordTouchButton.reset_holds()


func _on_tilt_toggled(is_on: bool) -> void:
	TiltSteer.enabled = is_on
	_refresh_tilt_label()


func _on_tilt_enabled_changed(is_on: bool) -> void:
	if tilt_toggle.button_pressed != is_on:
		tilt_toggle.button_pressed = is_on
	_refresh_tilt_label()


func _on_tilt_sensor_missing_changed(_is_missing: bool) -> void:
	_refresh_tilt_label()


func _refresh_tilt_label() -> void:
	if not TiltSteer.enabled:
		tilt_toggle.text = "TILT"
	elif TiltSteer.sensor_missing:
		# Otherwise a phone without a usable sensor looks like a broken game.
		tilt_toggle.text = "NO SENSOR"
	else:
		tilt_toggle.text = "TILT ON"
