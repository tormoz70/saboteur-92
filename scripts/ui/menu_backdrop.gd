extends Control
## Quiet vertical wash behind the title screen.


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)


func _draw() -> void:
	var steps := 28
	var band := size.y / float(steps)
	var top := Color(0.07, 0.11, 0.16)
	var bottom := Color(0.025, 0.03, 0.045)
	for i in steps:
		var t := float(i) / float(steps - 1)
		draw_rect(Rect2(0.0, band * i, size.x, band + 1.0), top.lerp(bottom, t))
	draw_circle(Vector2(size.x * 0.18, size.y * 0.28), 320.0, Color(0.28, 0.55, 0.75, 0.09))
	draw_circle(Vector2(size.x * 0.82, size.y * 0.82), 260.0, Color(0.12, 0.28, 0.36, 0.16))
