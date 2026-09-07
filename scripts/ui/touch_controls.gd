extends CanvasLayer

@onready var tilt_toggle: Button = $Root/TiltToggle


func _ready() -> void:
	tilt_toggle.button_pressed = TiltSteer.enabled
	_refresh_tilt_label()
	tilt_toggle.toggled.connect(_on_tilt_toggled)
	TiltSteer.enabled_changed.connect(_on_tilt_enabled_changed)
	TiltSteer.sensor_missing_changed.connect(_on_tilt_sensor_missing_changed)


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
