class_name RopeController
extends RefCounted

## Tightrope: Nina runs along the top. Stopping or reversing mid-span drops
## her straight down. Enter from a crossbar while moving horizontally; step
## off onto a solid/oneway floor at either end.

var _p: Player
var _dir: float = 0.0
var _stop_timer: float = 0.0
var _rope_y: float = 0.0
var _mount_x: float = 0.0
var _lost_overlap: float = 0.0


func setup(player: Player) -> void:
	_p = player


func reset() -> void:
	_dir = 0.0
	_stop_timer = 0.0
	_rope_y = 0.0
	_mount_x = 0.0
	_lost_overlap = 0.0
	if _p.on_rope:
		_p.on_rope = false
		_p.apply_world_mask()


func overlaps() -> bool:
	return _rope_area() != null


func update_state() -> void:
	if _p.on_ladder or _p.on_lift:
		if _p.on_rope:
			_fall()
		return
	if _p.on_rope:
		return
	if not _may_mount():
		return
	_enter()


func process_rope(delta: float) -> void:
	if not _p.on_rope:
		return
	# Overlap can blink for a frame after teleports / snaps; only fall after
	# a short gap, or when a real floor catches the soles past the mount.
	if overlaps():
		_lost_overlap = 0.0
	else:
		_lost_overlap += delta
		if _lost_overlap > 0.2:
			if _p.is_on_floor() or _floor_under_feet():
				_leave_to_floor()
			else:
				_fall()
			return
	var axis := TiltSteer.move_axis()
	if absf(axis) > 0.1 and signf(axis) != signf(_dir):
		_fall()
		return
	if absf(axis) < 0.1:
		_stop_timer += delta
		if _stop_timer >= _p.rope_stop_grace:
			_fall()
		else:
			_p.velocity = Vector2(_dir * _p.rope_speed * 0.15, 0.0)
			_snap_y()
			_p.current_state = Player.State.RUN
		return
	_stop_timer = 0.0
	_dir = signf(axis)
	_p.facing = int(_dir)
	_p.velocity = Vector2(_dir * _p.rope_speed, 0.0)
	_snap_y()
	_p.current_state = Player.State.RUN
	if absf(_p.global_position.x - _mount_x) > 48.0 and _floor_under_feet():
		_leave_to_floor()


func _may_mount() -> bool:
	if _p.on_ladder or _p.on_lift or not overlaps():
		return false
	if absf(TiltSteer.move_axis()) < 0.1:
		return false
	# From a crossbar on the floor, or grabbing mid-air after a run-up jump.
	if not _p.is_on_floor() and absf(_p.velocity.x) < 20.0:
		return false
	var area := _rope_area()
	var col := area.get_child(0) as CollisionShape2D if area else null
	if col == null or col.shape == null:
		return false
	var half_h: float = (col.shape as RectangleShape2D).size.y * 0.5
	return absf(_feet_y() - col.global_position.y) <= half_h + 16.0


func _enter() -> void:
	_p.on_rope = true
	_p.on_ladder = false
	_p.collision_mask = 0
	_p.floor_snap_length = 0.0
	_dir = signf(TiltSteer.move_axis())
	if _dir == 0.0:
		_dir = float(_p.facing)
	_stop_timer = 0.0
	_mount_x = _p.global_position.x
	_p.facing = int(_dir)
	var area := _rope_area()
	if area != null:
		var col := area.get_child(0) as CollisionShape2D
		if col != null:
			_rope_y = area.get_meta("rope_y", col.global_position.y)
	_snap_y()
	_p.velocity = Vector2(_dir * _p.rope_speed, 0.0)
	_p.current_state = Player.State.RUN
	AudioManager.play_sfx("rope_mount")


func _fall() -> void:
	_p.on_rope = false
	_p.apply_world_mask()
	_p.floor_snap_length = 16.0
	_p.velocity = Vector2.ZERO
	_p.current_state = Player.State.JUMP
	_dir = 0.0
	_stop_timer = 0.0
	AudioManager.play_sfx("rope_fall")


func _leave_to_floor() -> void:
	_p.on_rope = false
	_p.apply_world_mask()
	_p.floor_snap_length = 16.0
	_p.velocity.y = 0.0
	_p.current_state = (
		Player.State.RUN if absf(TiltSteer.move_axis()) > 0.1 else Player.State.IDLE
	)
	_dir = 0.0
	_stop_timer = 0.0


func _snap_y() -> void:
	if _rope_y == 0.0:
		return
	var feet_off := (Player.BODY_STAND_POS.y + Player.BODY_STAND_SIZE.y * 0.5) * _p.scale.y
	_p.global_position.y = _rope_y - feet_off


func _feet_y() -> float:
	return (
		_p.global_position.y
		+ (Player.BODY_STAND_POS.y + Player.BODY_STAND_SIZE.y * 0.5) * _p.scale.y
	)


func _floor_under_feet() -> bool:
	var space := _p.get_world_2d().direct_space_state
	var cx := _p.global_position.x + Player.BODY_STAND_POS.x * _p.scale.x
	var feet := _feet_y()
	var q := PhysicsRayQueryParameters2D.create(
		Vector2(cx, feet - 2.0), Vector2(cx, feet + 10.0)
	)
	# World mask is 0 while on the rope — probe LAYER_WORLD directly.
	q.collision_mask = CollisionLayers.LAYER_WORLD
	q.exclude = [_p.get_rid()]
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return false
	var n: Vector2 = hit.normal
	return n.y <= -0.5


func _rope_area() -> Area2D:
	if _p.ladder_detector == null:
		return null
	for area in _p.ladder_detector.get_overlapping_areas():
		if area is Area2D and area.get_meta("rope", false):
			return area
	return null
