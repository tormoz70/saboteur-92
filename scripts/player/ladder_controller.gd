class_name LadderController
extends RefCounted

const CLIMB_STEP_PX := 16.0

var climb_frame: int = 0

var _p: Player
var _step_timer: float = 0.0
# UP held at the moment the player leaves the floor is spent until release.
var _up_spent_on_jump: bool = false
var _was_on_floor: bool = false
var _probe_shape := RectangleShape2D.new()
var _probe_query := PhysicsShapeQueryParameters2D.new()


func setup(player: Player) -> void:
	_p = player


func reset() -> void:
	_step_timer = 0.0
	climb_frame = 0
	_up_spent_on_jump = false
	_was_on_floor = false


func overlaps() -> bool:
	var col := _detector_shape()
	if col == null:
		return false
	return _query(col.shape, col.global_transform)


func update_state(climb_axis: float) -> void:
	var h_axis := TiltSteer.move_axis()
	var want_climb := absf(climb_axis) > 0.0
	var on_floor := _p.is_on_floor()
	if not SaboteurControls.wants_up():
		_up_spent_on_jump = false
	elif _was_on_floor and not on_floor:
		_up_spent_on_jump = true
	_was_on_floor = on_floor
	if _p.on_ladder:
		if not _p.can_climb:
			_leave()
			return
		if absf(h_axis) > 0.0 and not want_climb:
			_leave()
			return
		# Touch pads send left+down together. That must walk across a hatch,
		# not trap Nina in the shaft (02 office). MOVE+UP still climbs.
		if climb_axis > 0.0 and absf(h_axis) >= climb_axis:
			_leave()
			return
		return
	# Mount only from the floor. Airborne grab is off on purpose: a jump,
	# fall, or hatch fly-through must not become a climb. Overlapping a
	# shaft still mounts even with MOVE held: NW/NE on the rungs is climb,
	# not a running jump that leaves Nina stuck at the foot of the ladder.
	if not _p.is_on_floor():
		return
	if not _p.can_climb or not want_climb:
		return
	# Leftover UP after a jump is not a new climb press.
	if climb_axis < 0.0 and _up_spent_on_jump:
		return
	# Same hatch rule: a mostly-horizontal pad walks, pure DOWN drops.
	if climb_axis > 0.0 and absf(h_axis) >= climb_axis:
		return
	# Hatch: Down only if rungs continue under the floor. Up only if rungs continue above.
	if climb_axis > 0.0 and _below_feet():
		_enter()
		_take_step(climb_axis)
	elif climb_axis < 0.0 and _above_feet():
		_enter()
		_take_step(climb_axis)


func process_climb(delta: float, axis: float) -> void:
	_p.velocity = Vector2.ZERO
	_p.current_state = Player.State.CLIMB
	_snap_to_ladder()
	if absf(axis) < 0.1:
		_step_timer = 0.0
		return
	var step_time := CLIMB_STEP_PX / maxf(_p.climb_speed, 1.0)
	_step_timer += delta
	while _step_timer >= step_time and _p.on_ladder:
		if not _take_step(axis):
			_step_timer = 0.0
			break
		_step_timer -= step_time


func sync_pose() -> void:
	# Original flips the same sprite every tile; lock the pose to world Y so
	# up and down stay on the same rungs instead of skipping every other frame.
	climb_frame = int(floor(_p.global_position.y / CLIMB_STEP_PX)) & 1


func _enter() -> void:
	_p.on_ladder = true
	_p.collision_mask = 0
	_p.floor_snap_length = 0.0
	_p.velocity = Vector2.ZERO
	_step_timer = 0.0
	_snap_to_ladder()


func _leave() -> void:
	_p.on_ladder = false
	_p.apply_world_mask()
	_p.floor_snap_length = 16.0
	_p.velocity = Vector2.ZERO
	if _head_in_world_solid():
		_unstick_from_solids()
	_snap_onto_support()


func _snap_to_ladder() -> void:
	var areas := _p.ladder_detector.get_overlapping_areas()
	if areas.is_empty():
		return
	var col := areas[0].get_child(0) as CollisionShape2D
	if col == null:
		return
	_p.global_position.x = col.global_position.x - Player.BODY_STAND_POS.x * _p.scale.x


func _snap_onto_support() -> void:
	var space := _p.get_world_2d().direct_space_state
	var cx := _p.global_position.x + Player.BODY_STAND_POS.x * _p.scale.x
	var from := Vector2(cx, _p.global_position.y + 4.0)
	var q := PhysicsRayQueryParameters2D.create(from, from + Vector2(0.0, 96.0))
	q.collision_mask = _p.get_world_mask()
	q.exclude = [_p.get_rid()]
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return
	var n: Vector2 = hit.normal
	if n.y > -0.5:
		return
	var feet_off := (Player.BODY_STAND_POS.y + Player.BODY_STAND_SIZE.y * 0.5) * _p.scale.y
	# A ray that starts in a lid can report the underside as a floor. Only
	# snap when the hit is actually under the soles, otherwise fall.
	if hit.position.y + 4.0 < _feet_y() - 8.0:
		return
	_p.global_position.y = hit.position.y - feet_off
	if _head_in_world_solid():
		_unstick_from_solids()


func _take_step(axis: float) -> bool:
	var step := Vector2(0.0, signf(axis) * CLIMB_STEP_PX)
	var dest := _p.global_position + step
	if not _overlaps_at(dest):
		# Ladder ended: stand on a close floor, otherwise hang on the last rung.
		if axis > 0.0:
			_dismount_if_close_floor()
		else:
			_dismount_if_landing()
		return false
	if axis > 0.0:
		var floor_y := _blocking_floor_y(step.y)
		if floor_y < INF:
			_dismount_to_y(floor_y)
			return false
	else:
		if not _try_climb_up_past_lid(step):
			return false
	_p.move_and_collide(step)
	sync_pose()
	return true


func _overlaps_at(origin: Vector2) -> bool:
	var col := _detector_shape()
	if col == null:
		return false
	var xf := col.global_transform
	xf.origin += origin - _p.global_position
	return _query(col.shape, xf)


func _feet_y() -> float:
	return (
		_p.global_position.y
		+ (Player.BODY_STAND_POS.y + Player.BODY_STAND_SIZE.y * 0.5) * _p.scale.y
	)


func _head_y() -> float:
	return (
		_p.global_position.y
		+ (Player.BODY_STAND_POS.y - Player.BODY_STAND_SIZE.y * 0.5) * _p.scale.y
	)


func _body_cx() -> float:
	return _p.global_position.x + Player.BODY_STAND_POS.x * _p.scale.x


func _at_world(point: Vector2) -> bool:
	return _hits(point, Vector2(8.0, 8.0))


func _above_feet() -> bool:
	return _probe(Vector2(Player.BODY_STAND_POS.x, 16.0) * _p.scale, Vector2(12.0, 20.0) * _p.scale)


func _below_feet() -> bool:
	# Entirely under the soles so a dead-end floor with rungs at foot height
	# does not count as a hatch.
	return _probe(
		Vector2(Player.BODY_STAND_POS.x * _p.scale.x, _feet_y() - _p.global_position.y + 24.0),
		Vector2(10.0, 16.0)
	)


func _probe(local_center: Vector2, size: Vector2) -> bool:
	return _hits(_p.global_position + local_center, size)


func _hits(center: Vector2, size: Vector2) -> bool:
	_probe_shape.size = size
	return _query(_probe_shape, Transform2D(0.0, center))


func _query(shape: Shape2D, xf: Transform2D) -> bool:
	return _shape_hits(
		shape, xf, _p.ladder_detector.collision_mask, true, false
	)


func _shape_hits(
	shape: Shape2D, xf: Transform2D, mask: int, areas: bool, bodies: bool
) -> bool:
	# Reused query keeps leftover fields. Set every field the four old
	# functions wrote, every call, or a prior detector/probe leaks in.
	_probe_query.shape = shape
	_probe_query.transform = xf
	_probe_query.collision_mask = mask
	_probe_query.collide_with_areas = areas
	_probe_query.collide_with_bodies = bodies
	_probe_query.exclude = [_p.get_rid()]
	return _p.get_world_2d().direct_space_state.intersect_shape(_probe_query, 1).size() > 0


func _blocking_floor_y(dy: float) -> float:
	var hit := _vertical_solid(_feet_y() - 1.0, _feet_y() + dy + 2.0)
	if hit.is_empty():
		return INF
	var fy: float = hit.position.y
	# Already on or inside this slab: keep climbing so a hatch mount from
	# the floor can pass the lid. Approaching a floor from above must land
	# even when rungs continue — another DOWN from the floor enters the
	# next shaft. Riding every hatch in one hold drops Nina through the
	# 02 office into the basement.
	if fy <= _feet_y() + 2.0:
		return INF
	return fy


func _try_climb_up_past_lid(step: Vector2) -> bool:
	# True: take the step. False: blocked or already dismounted.
	var head := _head_y()
	var hit := _vertical_solid(head + 1.0, head + step.y - 2.0)
	if hit.is_empty():
		return true
	var bottom: float = hit.position.y
	# Shaft continues through the lid.
	if _at_world(Vector2(_body_cx(), bottom - 32.0)):
		return true
	# Thin walkable floor (document hatch): rungs often stop at the slab.
	# Climb through until the feet reach the TOP, never the underside.
	var top := _walkable_top(bottom)
	if top < INF:
		if _feet_y() + step.y <= top + 2.0:
			_dismount_to_y(top)
			return false
		return true
	# Dead-end mass: stay on the last rung. Do not plant feet on the underside.
	_dismount_if_landing()
	return false


func _walkable_top(bottom_y: float) -> float:
	# Probe up from just inside the solid. A hatch is a thin slab with empty
	# space on top. A thick ceiling mass never emerges.
	var y := bottom_y - 2.0
	var end := bottom_y - 64.0 * maxf(_p.scale.y, 1.0)
	var inside := false
	while y > end:
		if _point_is_world_solid(Vector2(_body_cx(), y)):
			inside = true
			y -= 4.0
			continue
		if not inside:
			y -= 4.0
			continue
		# First empty sample sits just above the slab. Planting feet on the
		# last solid pixel (y+4) embeds the collider in the brick.
		if _point_is_world_solid(Vector2(_body_cx(), y - 8.0)):
			return INF
		return y
	return INF


func _point_is_world_solid(point: Vector2) -> bool:
	_probe_shape.size = Vector2(6.0, 4.0)
	return _shape_hits(
		_probe_shape, Transform2D(0.0, point), _p.get_world_mask(), false, true
	)


func _vertical_solid(from_y: float, to_y: float) -> Dictionary:
	var space := _p.get_world_2d().direct_space_state
	var cx := _body_cx()
	var q := PhysicsRayQueryParameters2D.create(Vector2(cx, from_y), Vector2(cx, to_y))
	q.collision_mask = _p.get_world_mask()
	q.exclude = [_p.get_rid()]
	return space.intersect_ray(q)


func _dismount_to_y(floor_y: float) -> void:
	var feet_off := (Player.BODY_STAND_POS.y + Player.BODY_STAND_SIZE.y * 0.5) * _p.scale.y
	_p.on_ladder = false
	_p.apply_world_mask()
	_p.floor_snap_length = 16.0
	_p.velocity = Vector2.ZERO
	_p.global_position.y = floor_y - feet_off
	_p.current_state = Player.State.IDLE
	if _head_in_world_solid():
		_unstick_from_solids()


func _dismount_if_close_floor() -> void:
	var hit := _vertical_solid(_feet_y() - 2.0, _feet_y() + 24.0)
	if hit.is_empty():
		return
	var n: Vector2 = hit.normal
	if n.y > -0.5:
		return
	_dismount_to_y(hit.position.y)


func _dismount_if_landing() -> bool:
	var space := _p.get_world_2d().direct_space_state
	var feet := _feet_y()
	var cx := _body_cx()
	for side in [-48.0, 48.0, -72.0, 72.0]:
		var from := Vector2(cx + side, feet - 12.0)
		var q := PhysicsRayQueryParameters2D.create(from, from + Vector2(0.0, 28.0))
		q.collision_mask = _p.get_world_mask()
		q.exclude = [_p.get_rid()]
		var hit := space.intersect_ray(q)
		if hit.is_empty():
			continue
		var n: Vector2 = hit.normal
		if n.y > -0.5:
			continue
		var fy: float = hit.position.y
		if absf(fy - feet) > 20.0:
			continue
		_dismount_to_y(fy)
		return true
	return false


func _body_overlaps_world() -> bool:
	var col := _p.body_collision
	if col == null or col.shape == null:
		return false
	return _shape_hits(col.shape, col.global_transform, _p.get_world_mask(), false, true)


func _head_in_world_solid() -> bool:
	_probe_shape.size = Vector2(10.0, 8.0) * _p.scale
	var center := Vector2(_body_cx(), _head_y() + 4.0 * _p.scale.y)
	return _shape_hits(
		_probe_shape, Transform2D(0.0, center), _p.get_world_mask(), false, true
	)


func _unstick_from_solids() -> void:
	# Climbing has world collision off, so a leave under a lid can restore
	# the mask while the head is still inside the brick. Slide down until the
	# collider is free. Do not run this for a normal floor rest: soles overlap
	# the slab by a safe-margin and shoving down would drop through it.
	if not _head_in_world_solid():
		return
	var step := 4.0 * _p.scale.y
	for _i in 40:
		_p.global_position.y += step
		if not _body_overlaps_world():
			_p.velocity.y = maxf(_p.velocity.y, 0.0)
			return


func _detector_shape() -> CollisionShape2D:
	var col := _p.ladder_detector.get_child(0) as CollisionShape2D
	if col == null or col.shape == null:
		return null
	return col
