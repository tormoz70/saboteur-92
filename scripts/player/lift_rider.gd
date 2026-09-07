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


func process() -> void:
	_p.current_state = Player.State.IDLE
	if _lift == null:
		return
	if _lift.dir != 0:
		if Input.is_action_pressed("move_up") and _lift.dir > 0:
			_lift.dir = -1
		elif Input.is_action_pressed("move_down") and _lift.dir < 0:
			_lift.dir = 1
		_p.velocity = Vector2.ZERO
		return
	var want := 0
	if Input.is_action_pressed("move_up"):
		want = -1
	elif Input.is_action_pressed("move_down"):
		want = 1
	if want != 0 and _lift.start_ride(_p, want):
		_p.velocity = Vector2.ZERO
		return
	var direction := TiltSteer.move_axis()
	if direction:
		_p.velocity.x = direction * _p.speed
		_p.apply_facing(int(sign(direction)))
		_p.current_state = Player.State.RUN
	else:
		_p.velocity.x = move_toward(_p.velocity.x, 0.0, _p.speed)


func _leave() -> void:
	if _lift != null and _lift.rider == _p:
		_lift.stop_ride()
	_p.on_lift = false
	_lift = null
