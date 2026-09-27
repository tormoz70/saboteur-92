class_name StepperRow
extends HBoxContainer
## One settings line: name, big "-" / "+" buttons and a bar you can also tap.

signal value_changed(value: float)

@export var title: String = ""
@export var min_value: float = 0.0
@export var max_value: float = 1.0
@export var step: float = 0.1

var value: float = 0.0

@onready var name_label: Label = $Name
@onready var minus_button: Button = $Minus
@onready var bar: ProgressBar = $Bar
@onready var plus_button: Button = $Plus
@onready var value_label: Label = $Value


func _ready() -> void:
	name_label.text = title
	bar.min_value = min_value
	bar.max_value = max_value
	bar.step = 0.0
	minus_button.pressed.connect(nudge.bind(-1))
	plus_button.pressed.connect(nudge.bind(1))
	bar.gui_input.connect(_on_bar_input)
	_refresh()


func set_value_no_signal(next: float) -> void:
	value = _snap(next)
	if is_node_ready():
		_refresh()


func nudge(direction: int) -> void:
	_commit(value + step * direction)


func _commit(next: float) -> void:
	var next_value := _snap(next)
	if is_equal_approx(next_value, value):
		return
	value = next_value
	_refresh()
	value_changed.emit(value)


func _snap(v: float) -> float:
	var steps := roundf((clampf(v, min_value, max_value) - min_value) / step)
	return clampf(min_value + steps * step, min_value, max_value)


func _refresh() -> void:
	bar.value = value
	value_label.text = "%d%%" % roundi(value * 100.0)
	minus_button.disabled = value <= min_value + 0.0001
	plus_button.disabled = value >= max_value - 0.0001


func _on_bar_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if mb == null or not mb.pressed or mb.button_index != MOUSE_BUTTON_LEFT:
		return
	var t := clampf(mb.position.x / maxf(bar.size.x, 1.0), 0.0, 1.0)
	_commit(lerpf(min_value, max_value, t))
	bar.accept_event()
