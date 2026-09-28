extends Control

## Small circular energy pie, drawn clockwise from 12 o'clock.

@export var radius: float = 22.0

var _ratio: float = 1.0


func set_energy(current: int, max_energy: int) -> void:
	if max_energy <= 0:
		_ratio = 0.0
	else:
		_ratio = clampf(float(current) / float(max_energy), 0.0, 1.0)
	queue_redraw()


func _ready() -> void:
	custom_minimum_size = Vector2(radius * 2.0 + 4.0, radius * 2.0 + 4.0)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _draw() -> void:
	var center := size * 0.5
	var r := minf(size.x, size.y) * 0.5 - 3.0
	var width := 4.5
	draw_arc(center, r, 0.0, TAU, 48, Color(1, 1, 1, 0.16), width, true)
	if _ratio <= 0.001:
		return
	var start := -PI * 0.5
	var color := Color(0.45, 0.82, 1.0, 0.95) if _ratio > 0.28 else Color(0.96, 0.55, 0.42, 0.95)
	var steps := maxi(8, int(ceili(48.0 * _ratio)))
	draw_arc(center, r, start, start + TAU * _ratio, steps, color, width, true)
