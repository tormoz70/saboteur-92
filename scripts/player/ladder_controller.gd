class_name LadderController
extends RefCounted

const CLIMB_STEP_PX := 16.0

var climb_frame: int = 0

var _p: Player
var _step_timer: float = 0.0
var _probe_shape := RectangleShape2D.new()
var _probe_query := PhysicsShapeQueryParameters2D.new()


func setup(player: Player) -> void:
	_p = player


func reset() -> void:
	_step_timer = 0.0
	climb_frame = 0


func overlaps() -> bool:
	var col := _detector_shape()
	if col == null:
		return false
	return _query(col.shape, col.global_transform)


func update_state(climb_axis: float) -> void:
	var h_axis := TiltSteer.move_axis()
	var want_climb := absf(climb_axis) > 0.0
	var running_jump := (
		not _p.on_ladder
		and _p.is_on_floor()
		and absf(h_axis) > 0.0
		and SaboteurControls.wants_up()
	)
	if _p.on_ladder:
		if not _p.can_climb:
			_leave()
			return
		if absf(h_axis) > 0.0 and not want_climb:
			_leave()
			return
		return
	# MOVE+UP is a jump for the whole arc. After takeoff, held UP still
	# drives climb_axis, so a shaft/hatch must not grab mid-air.
	if not _p.is_on_floor():
		return
	if running_jump or not _p.can_climb or not want_climb:
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
	_p.global_position.y = hit.position.y - feet_off


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
		var ceil_y := _blocking_ceiling_y(step.y)
		if ceil_y < INF:
			# Climbing up: y decreases. Dismount when feet rise to the lid.
			if _feet_y() + step.y <= ceil_y + 2.0:
				_dismount_to_y(ceil_y)
			else:
				_dismount_if_landing()
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
	# Reused query keeps leftover fields. Set every field the four old
	# functions wrote, every call, or a prior detector/probe leaks in.
	_probe_query.shape = shape
	_probe_query.transform = xf
	_probe_query.collision_mask = _p.ladder_detector.collision_mask
	_probe_query.collide_with_areas = true
	_probe_query.collide_with_bodies = false
	_probe_query.exclude = [_p.get_rid()]
	return _p.get_world_2d().direct_space_state.intersect_shape(_probe_query, 1).size() > 0


func _blocking_floor_y(dy: float) -> float:
	var hit := _vertical_solid(_feet_y() - 1.0, _feet_y() + dy + 2.0)
	if hit.is_empty():
		return INF
	var fy: float = hit.position.y
	# Hatch: rungs continue under the lid, so the floor is walkable but climbable-through.
	if _at_world(Vector2(_body_cx(), fy + 32.0)):
		return INF
	return fy


func _blocking_ceiling_y(dy: float) -> float:
	var head := _p.global_position.y + 2.0
	var hit := _vertical_solid(head, head + dy - 2.0)
	if hit.is_empty():
		return INF
	var cy: float = hit.position.y
	# Shaft continues through the lid — keep climbing.
	if _at_world(Vector2(_body_cx(), cy - 32.0)):
		return INF
	# Landing lid (ladder ends here): keep climbing through until feet reach it.
	if _at_world(Vector2(_body_cx(), cy + 2.0)) and _feet_y() + dy > cy + 2.0:
		return INF
	return cy


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


func _detector_shape() -> CollisionShape2D:
	var col := _p.ladder_detector.get_child(0) as CollisionShape2D
	if col == null or col.shape == null:
		return null
	return col
