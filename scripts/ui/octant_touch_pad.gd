class_name OctantTouchPad
extends Control
## 8-way movement pad: one finger, pie slices from the center.
##
## The previous pad stacked eight rotated TouchScreenButton wedges with a
## hollow hub. Taps in the middle and in the gaps between wedges did nothing,
## so this Control maps the touch angle itself and reuses ChordTouchButton's
## hold counts so sliding from Left onto Jump-Left does not drop `move_left`.

const DEAD_ZONE := 12.0
const IDLE := Color(1.0, 1.0, 1.0, 0.88)
const ACTIVE := Color(1.0, 0.92, 0.28, 0.98)
const HUB := Color(0.08, 0.07, 0.08, 0.55)

var _finger: int = -1
var _octant: int = -1


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)
	tree_exiting.connect(release_finger)


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_on_touch(event)
	elif event is InputEventScreenDrag:
		_on_drag(event)


func octant_from_vec(delta: Vector2) -> int:
	var i := int(round(delta.angle() / (PI * 0.25)))
	return posmod(i, 8)


static func chord_for(oct: int) -> PackedStringArray:
	match oct:
		0:
			return PackedStringArray(["move_right"])
		1:
			return PackedStringArray(["move_right", "move_down"])
		2:
			return PackedStringArray(["move_down"])
		3:
			return PackedStringArray(["move_left", "move_down"])
		4:
			return PackedStringArray(["move_left"])
		5:
			return PackedStringArray(["move_left", "move_up"])
		6:
			return PackedStringArray(["move_up"])
		7:
			return PackedStringArray(["move_right", "move_up"])
		_:
			return PackedStringArray()


func octant_at(local_pos: Vector2) -> int:
	var delta := local_pos - size * 0.5
	if delta.length() > _radius():
		return -1
	if delta.length() < DEAD_ZONE:
		return _octant if _finger != -1 else -1
	return octant_from_vec(delta)


func release_finger() -> void:
	_finger = -1
	_set_octant(-1)


func _on_touch(event: InputEventScreenTouch) -> void:
	if event.pressed:
		if _finger != -1:
			return
		var oct := octant_at(_event_local(event.position))
		if oct < 0:
			return
		_finger = event.index
		_set_octant(oct)
		return
	if event.index == _finger:
		release_finger()


func _on_drag(event: InputEventScreenDrag) -> void:
	var oct := octant_at(_event_local(event.position))
	if _finger == event.index:
		_set_octant(oct)
		return
	if _finger != -1 or oct < 0:
		return
	_finger = event.index
	_set_octant(oct)


func _event_local(screen_pos: Vector2) -> Vector2:
	return get_global_transform_with_canvas().affine_inverse() * screen_pos


func _set_octant(next: int) -> void:
	if next == _octant:
		return
	_release_octant(_octant)
	_octant = next
	_hold_octant(_octant)
	queue_redraw()


func _hold_octant(oct: int) -> void:
	if oct < 0:
		return
	for action in chord_for(oct):
		ChordTouchButton.retain(StringName(action))


func _release_octant(oct: int) -> void:
	if oct < 0:
		return
	for action in chord_for(oct):
		ChordTouchButton.drop(StringName(action))


func _radius() -> float:
	return minf(size.x, size.y) * 0.5 - 8.0


func _draw() -> void:
	var center := size * 0.5
	var outer := _radius()
	if outer <= 8.0:
		return
	var inner := outer * 0.28
	draw_circle(center, outer + 3.0, Color(0.05, 0.04, 0.05, 0.42))
	for oct in 8:
		var fill := ACTIVE if oct == _octant else IDLE
		if oct % 2 == 1 and oct != _octant:
			fill = Color(fill.r, fill.g, fill.b, 0.72)
		draw_colored_polygon(_sector_points(oct, inner, outer), fill)
	draw_circle(center, inner - 2.0, HUB)
	_draw_cardinal_arrows(center, outer)


func _sector_points(oct: int, inner: float, outer: float) -> PackedVector2Array:
	var center := size * 0.5
	var a0 := (float(oct) - 0.5) * PI * 0.25
	var a1 := (float(oct) + 0.5) * PI * 0.25
	var pts := PackedVector2Array()
	const STEPS := 4
	for i in range(STEPS + 1):
		var a := lerpf(a0, a1, float(i) / float(STEPS))
		pts.append(center + Vector2.from_angle(a) * outer)
	for i in range(STEPS, -1, -1):
		var a := lerpf(a0, a1, float(i) / float(STEPS))
		pts.append(center + Vector2.from_angle(a) * inner)
	return pts


func _draw_cardinal_arrows(center: Vector2, outer: float) -> void:
	var reach := outer * 0.68
	_draw_arrow(center, Vector2.RIGHT, reach, 0)
	_draw_arrow(center, Vector2.DOWN, reach, 2)
	_draw_arrow(center, Vector2.LEFT, reach, 4)
	_draw_arrow(center, Vector2.UP, reach, 6)


func _draw_arrow(center: Vector2, along: Vector2, reach: float, oct: int) -> void:
	var tip := center + along * reach
	var side := Vector2(-along.y, along.x)
	var pts := PackedVector2Array([
		tip,
		tip - along * 22.0 + side * 11.0,
		tip - along * 22.0 - side * 11.0,
	])
	var color := Color(0.12, 0.1, 0.1, 0.95) if oct == _octant else Color(0.12, 0.1, 0.1, 0.8)
	draw_colored_polygon(pts, color)
