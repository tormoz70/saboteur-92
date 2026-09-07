class_name LiftRider
extends RefCounted

const LiftPlatform := preload("res://scripts/world/lift.gd")

var _p: Player
var _lift: LiftPlatform = null


func setup(player: Player) -> void:
	_p = player


func reset() -> void:
	# Player.respawn used to null _lift without stop_ride(). Dying mid-ride
	# left the cabin moving; calling _leave() here would halt it.
	_lift = null
	_p.on_lift = false


func is_riding() -> bool:
	return _p.on_lift and _lift != null and _lift.dir != 0


func is_centered() -> bool:
	return _p.on_lift and _lift != null and _lift.is_centered(_p)


func can_ride_up() -> bool:
	return is_centered() and _lift != null and not _lift.at_top()


func can_ride_down() -> bool:
	return is_centered() and _lift != null and not _lift.at_bottom()


func update_state() -> void:
	if _p.on_ladder:
		_leave()
		return
	var found: LiftPlatform = null
	for i in range(_p.get_slide_collision_count()):
		var col := _p.get_slide_collision(i)
		var n := col.get_collider() as LiftPlatform
		if n != null:
			found = n
			break
	if found == null:
		if _p.on_lift and _lift != null and _lift.dir != 0:
			return
		_leave()
		return
	_p.on_lift = true
	_lift = found


func process() -> bool:
	# True when the cabin is moving or just started. False: treat as a floor
	# so a dead-end lift can still kick, jump, or duck.
	if _lift == null:
		return false
	if _lift.dir != 0:
		if SaboteurControls.wants_up() and _lift.dir > 0:
			_lift.dir = -1
		elif SaboteurControls.wants_down() and _lift.dir < 0:
			_lift.dir = 1
		_p.velocity = Vector2.ZERO
		_p.current_state = Player.State.IDLE
		return true
	var want := 0
	if SaboteurControls.wants_up():
		want = -1
	elif SaboteurControls.wants_down():
		want = 1
	if want != 0 and _lift.start_ride(_p, want):
		_p.velocity = Vector2.ZERO
		_p.current_state = Player.State.IDLE
		return true
	return false


func _leave() -> void:
	if _lift != null and _lift.rider == _p:
		_lift.stop_ride()
	_p.on_lift = false
	_lift = null
