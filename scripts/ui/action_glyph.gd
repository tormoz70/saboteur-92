extends TouchScreenButton
## Round glass button drawn on top of the touch shape. `kind` picks the icon.

const RADIUS := 40.0

@export var kind: String = "hit"


func _ready() -> void:
	pressed.connect(queue_redraw)
	released.connect(queue_redraw)


func _draw() -> void:
	var down := is_pressed()
	var fill := Color(0.45, 0.82, 1.0, 0.4) if down else Color(0.06, 0.08, 0.12, 0.62)
	draw_circle(Vector2.ZERO, RADIUS, fill)
	draw_arc(Vector2.ZERO, RADIUS - 1.0, 0.0, TAU, 40, Color(1, 1, 1, 0.4), 2.5, true)
	var ink := Color(1, 1, 1, 0.95)
	if kind == "jump":
		_draw_jump(ink)
	else:
		_draw_hit(ink)


func _draw_jump(ink: Color) -> void:
	draw_polyline(
		PackedVector2Array([Vector2(-13, 4), Vector2(0, -14), Vector2(13, 4)]),
		ink,
		4.0,
		true
	)
	draw_line(Vector2(-12, 16), Vector2(12, 16), ink, 3.0, true)


func _draw_hit(ink: Color) -> void:
	draw_circle(Vector2.ZERO, 5.0, ink)
	for i in 4:
		var dir := Vector2.from_angle(float(i) * TAU / 4.0 + PI * 0.25)
		draw_line(dir * 10.0, dir * 18.0, ink, 4.0, true)
