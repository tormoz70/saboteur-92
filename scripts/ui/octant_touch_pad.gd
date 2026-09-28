class_name OctantTouchPad
extends Control
## 8-way movement pad: one finger, pie slices from the center.
##
## The previous pad stacked eight rotated TouchScreenButton wedges with a
## hollow hub. Taps in the middle and in the gaps between wedges did nothing,
## so this Control maps the touch angle itself and reuses ChordTouchButton's
## hold counts so sliding from Left onto Jump-Left does not drop `move_left`.

const ChordPad := preload("res://scripts/ui/chord_touch_button.gd")
const DEAD_ZONE := 12.0
const DISC := Color(0.06, 0.08, 0.12, 0.55)
const RING := Color(1.0, 1.0, 1.0, 0.28)
const GLOW := Color(0.45, 0.82, 1.0, 0.42)
const MARK := Color(1.0, 1.0, 1.0, 0.72)

var _finger: int = -1
var _octant: int = -1


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)
	tree_exiting.connect(release_finger)


func _input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
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
		ChordPad.retain(StringName(action))


func _release_octant(oct: int) -> void:
	if oct < 0:
		return
	for action in chord_for(oct):
		ChordPad.drop(StringName(action))


func _radius() -> float:
	return minf(size.x, size.y) * 0.5 - 8.0


func _draw() -> void:
	var center := size * 0.5
	var outer := _radius()
	if outer <= 8.0:
		return
	var inner := outer * 0.28
	draw_circle(center, outer, DISC)
	draw_arc(center, outer - 1.5, 0.0, TAU, 64, RING, 2.5, true)
	if _octant >= 0:
		draw_colored_polygon(_sector_points(_octant, inner, outer * 0.92), GLOW)
	_draw_marks(center, outer)
	var knob := center
	if _octant >= 0:
		knob += Vector2.from_angle(float(_octant) * PI * 0.25) * outer * 0.46
	draw_circle(knob, outer * 0.22, Color(1.0, 1.0, 1.0, 0.92))
	draw_arc(knob, outer * 0.22, 0.0, TAU, 32, Color(0.45, 0.82, 1.0, 0.9), 2.0, true)


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


func _draw_marks(center: Vector2, outer: float) -> void:
	var reach := outer * 0.78
	for oct in [0, 2, 4, 6]:
		var along := Vector2.from_angle(float(oct) * PI * 0.25)
		var tip := center + along * reach
		var side := Vector2(-along.y, along.x)
		var color := Color(0.55, 0.9, 1.0, 1.0) if oct == _octant else MARK
		draw_polyline(
			PackedVector2Array([
				tip - along * 12.0 + side * 7.0,
				tip,
				tip - along * 12.0 - side * 7.0,
			]),
			color,
			3.0,
			true
		)
