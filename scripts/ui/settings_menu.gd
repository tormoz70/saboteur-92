extends CanvasLayer
## Settings overlay shared by the title screen and the pause menu. Values go
## straight to GameSettings, which applies and saves them.

signal closed

@onready var sfx_row: StepperRow = %SfxRow
@onready var music_row: StepperRow = %MusicRow
@onready var tilt_toggle: Button = %TiltToggle
@onready var tilt_note: Label = %TiltNote
@onready var sensitivity_row: StepperRow = %SensitivityRow
@onready var pad_size_row: StepperRow = %PadSizeRow
@onready var pad_opacity_row: StepperRow = %PadOpacityRow
@onready var back_button: Button = %BackButton


func _ready() -> void:
	sfx_row.value_changed.connect(func(v: float) -> void: GameSettings.sfx_volume = v)
	music_row.value_changed.connect(func(v: float) -> void: GameSettings.music_volume = v)
	sensitivity_row.value_changed.connect(func(v: float) -> void: GameSettings.tilt_sensitivity = v)
	pad_size_row.value_changed.connect(func(v: float) -> void: GameSettings.pad_scale = v)
	pad_opacity_row.value_changed.connect(func(v: float) -> void: GameSettings.pad_opacity = v)
	tilt_toggle.toggled.connect(func(is_on: bool) -> void: GameSettings.tilt_enabled = is_on)
	back_button.pressed.connect(close)
	GameSettings.changed.connect(_sync)
	TiltSteer.sensor_missing_changed.connect(_on_sensor_missing_changed)
	_sync()


func open() -> void:
	_sync()
	visible = true
	var first := sfx_row.minus_button
	if first.disabled:
		first = sfx_row.plus_button
	first.grab_focus()


func close() -> void:
	if not visible:
		return
	visible = false
	closed.emit()


func is_open() -> bool:
	return visible


func _sync() -> void:
	sfx_row.set_value_no_signal(GameSettings.sfx_volume)
	music_row.set_value_no_signal(GameSettings.music_volume)
	sensitivity_row.set_value_no_signal(GameSettings.tilt_sensitivity)
	pad_size_row.set_value_no_signal(GameSettings.pad_scale)
	pad_opacity_row.set_value_no_signal(GameSettings.pad_opacity)
	tilt_toggle.set_pressed_no_signal(GameSettings.tilt_enabled)
	tilt_toggle.text = "ON" if GameSettings.tilt_enabled else "OFF"
	tilt_note.text = "NO SENSOR" if GameSettings.tilt_enabled and TiltSteer.sensor_missing else ""
	sensitivity_row.modulate.a = 1.0 if GameSettings.tilt_enabled else 0.5


func _on_sensor_missing_changed(_is_missing: bool) -> void:
	_sync()
