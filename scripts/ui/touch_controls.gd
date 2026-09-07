extends CanvasLayer

@onready var tilt_toggle: Button = $Root/TiltToggle


func _ready() -> void:
	tilt_toggle.button_pressed = TiltSteer.enabled
	_refresh_tilt_label()
	tilt_toggle.toggled.connect(_on_tilt_toggled)
	TiltSteer.enabled_changed.connect(_on_tilt_enabled_changed)


func _on_tilt_toggled(is_on: bool) -> void:
	TiltSteer.enabled = is_on
	_refresh_tilt_label()


func _on_tilt_enabled_changed(is_on: bool) -> void:
	if tilt_toggle.button_pressed != is_on:
		tilt_toggle.button_pressed = is_on
	_refresh_tilt_label()


func _refresh_tilt_label() -> void:
	tilt_toggle.text = "TILT ON" if TiltSteer.enabled else "TILT"
