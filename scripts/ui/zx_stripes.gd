extends Control
## The four slanted Spectrum rainbow bands from the case badge.

const COLORS: Array[Color] = [
	Color(1.0, 0.0, 0.0),
	Color(1.0, 1.0, 0.0),
	Color(0.0, 1.0, 0.0),
	Color(0.0, 1.0, 1.0),
]


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)


func _draw() -> void:
	var slant := size.y
	var band := (size.x - slant) / COLORS.size()
	if band <= 0.0:
		return
	for i in COLORS.size():
		var x0 := band * i
		var pts := PackedVector2Array([
			Vector2(x0, size.y),
			Vector2(x0 + band, size.y),
			Vector2(x0 + band + slant, 0.0),
			Vector2(x0 + slant, 0.0),
		])
		draw_colored_polygon(pts, COLORS[i])
