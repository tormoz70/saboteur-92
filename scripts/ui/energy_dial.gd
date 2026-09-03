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
	var r := minf(size.x, size.y) * 0.5 - 2.0
	draw_circle(center, r, Color(0.07, 0.06, 0.07, 0.82))
	draw_arc(center, r - 1.0, 0.0, TAU, 40, Color(0.45, 0.16, 0.16, 0.95), 2.0, true)
	if _ratio <= 0.001:
		return
	var start := -PI * 0.5
	var sweep := TAU * _ratio
	var steps := maxi(4, int(ceili(36.0 * _ratio)))
	var pts := PackedVector2Array()
	pts.append(center)
	for i in range(steps + 1):
		var t := start + sweep * float(i) / float(steps)
		pts.append(center + Vector2(cos(t), sin(t)) * (r - 3.5))
	var fill := Color(0.86, 0.14, 0.14) if _ratio > 0.28 else Color(0.95, 0.42, 0.12)
	draw_colored_polygon(pts, fill)
