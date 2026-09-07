class_name Player
extends CharacterBody2D

enum State {
	IDLE,
	RUN,
	JUMP,
	JUMP_KICK,
	KICK,
	CLIMB,
	CROUCH,
	CRAWL,
	CROUCH_PUNCH,
	PUNCH,
	SOMERSAULT,
	DEAD,
}

# Tuned to Saboteur II feel, still using CharacterBody2D physics.
# Original logic is ~5.5 ticks/s and 1 tile/tick; our tiles are 16px.
# Combat/jump chords match the 1987 inlay (see SaboteurControls).
const BODY_STAND_SIZE := Vector2(14, 42)
const BODY_STAND_POS := Vector2(24, 35)
const BODY_CROUCH_SIZE := Vector2(14, 24)
const BODY_CROUCH_POS := Vector2(24, 44)
# Strike hitboxes, as reach in front of the body centre and height in the
# 48x56 sprite cell. PunchArea's own shape sits on its origin, so these are the
# whole placement: mirroring x around BODY_STAND_POS.x is what makes a punch to
# the left reach as far as the same punch to the right.
const PUNCH_HIT := Vector2(19.0, 19.0)
const KICK_HIT := Vector2(21.0, 11.0)
const JUMP_KICK_HIT := Vector2(22.0, 20.0)
const CROUCH_PUNCH_HIT := Vector2(19.0, 36.0)
# Touchscreen taps never land on the same frame, and JMP and HIT sit far
# enough apart that a thumb needs a moment to roll between them, so UP and
# FIRE count as one chord while they are this close together.
const COMBO_WINDOW := 0.25

@export var speed: float = 110.0
@export var crawl_speed: float = 55.0
@export var jump_velocity: float = -270.0
@export var gravity: float = 820.0
@export var climb_speed: float = 56.0
@export var punch_duration: float = 0.32
@export var kick_duration: float = 0.42
## Long jump with a somersault: MOVE + UP + FIRE.
@export var somersault_speed_scale: float = 1.7
@export var somersault_jump_scale: float = 1.0
@export var max_energy: int = 100
@export var iframe_time: float = 0.55
@export var regen_delay: float = 1.25
@export var regen_per_second: float = 20.0
@export var spawn_point: Vector2 = Vector2(48, 184)
@export var max_fall_speed: float = 420.0

var current_state: State = State.IDLE
var facing: int = 1
var punch_timer: float = 0.0
var on_ladder: bool = false
var on_lift: bool = false
var can_climb: bool = false
var is_dead: bool = false
var energy: int = 100
var _kick_left_ground: bool = false
var _flip_left_ground: bool = false
var _air_time: float = 0.0
var _strike_age: float = 0.0
# Seconds each chord button has been held, or INF while it is up. A button
# left held from an earlier move is not part of the next gesture.
var _up_hold: float = INF
var _fire_hold: float = INF
var _iframe: float = 0.0
var _time_since_hit: float = 10.0
var _regen_accum: float = 0.0
var _world_mask: int = CollisionLayers.LAYER_WORLD
var _ladder := LadderController.new()
var _lifts := LiftRider.new()

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var body_collision: CollisionShape2D = $CollisionShape2D
@onready var punch_area: Area2D = $PunchArea
@onready var ladder_detector: Area2D = $LadderDetector


func _ready() -> void:
	punch_area.monitoring = false
	energy = max_energy
	floor_snap_length = 16.0
	safe_margin = 0.25
	_world_mask = collision_mask
	_ladder.setup(self)
	_lifts.setup(self)
	EventBus.player_died.connect(_on_player_died)
	EventBus.energy_changed.emit(energy, max_energy)


func _physics_process(delta: float) -> void:
	if is_dead or GameManager.state != GameManager.GameState.PLAYING:
		velocity = Vector2.ZERO
		move_and_slide()
		return

	_iframe = maxf(_iframe - delta, 0.0)
	if _iframe <= 0.0:
		anim.modulate = Color.WHITE
	_time_since_hit += delta
	_air_time = 0.0 if is_on_floor() else _air_time + delta
	_tick_chord(delta)
	_tick_regen(delta)

	can_climb = _ladder.overlaps()
	var climb_axis := get_climb_axis()
	_ladder.update_state(climb_axis)
	_lifts.update_state()
	floor_snap_length = 0.0 if on_ladder else 16.0
	collision_mask = 0 if on_ladder else _world_mask

	_tick_attack(delta)
	if not _lifts.is_riding():
		_handle_attack_input()

	var lift_holds := false
	if on_lift:
		lift_holds = _lifts.process()

	if on_ladder:
		_ladder.process_climb(delta, climb_axis)
	elif lift_holds:
		# Cabin is moving or just started; process() already zeroed velocity.
		pass
	elif _is_planted_strike():
		velocity.x = 0.0
		if not is_on_floor():
			velocity.y += gravity * delta
	elif current_state == State.JUMP_KICK:
		if not is_on_floor():
			_kick_left_ground = true
			velocity.y += gravity * delta
		velocity.x = float(facing) * speed
		if _kick_left_ground and is_on_floor():
			punch_area.monitoring = false
			current_state = State.IDLE
	elif current_state == State.SOMERSAULT:
		_process_somersault(delta)
	else:
		_process_platformer(delta)

	if not on_ladder:
		velocity.y = minf(velocity.y, max_fall_speed)
	_update_animation()
	if on_lift and _lifts.is_riding():
		return
	move_and_slide()
	_try_unstuck()


func _tick_attack(delta: float) -> void:
	if not _is_striking():
		return
	_strike_age += delta
	punch_timer -= delta
	if punch_timer > 0.0:
		return
	punch_area.monitoring = false
	if current_state == State.JUMP_KICK:
		# Keep the yoko-geri pose until landing; only the hitbox turns off.
		return
	if not is_on_floor():
		current_state = State.JUMP
	elif current_state == State.CROUCH_PUNCH and _wants_low_stance():
		# Stay small: standing up under a hatch or lift would wedge the body.
		current_state = State.CRAWL if absf(TiltSteer.move_axis()) > 0.0 else State.CROUCH
	else:
		current_state = State.IDLE


func _handle_attack_input() -> void:
	if on_ladder:
		return
	if _is_striking() or current_state == State.SOMERSAULT:
		# FIRE went in first; UP finishing the chord still means the flip.
		if _flip_upgrade_wanted():
			_start_somersault()
		return
	if not is_on_floor():
		# UP went in first; FIRE finishing the chord still means the flip.
		if _late_flip_wanted():
			_start_somersault()
		return

	var direction := TiltSteer.move_axis()
	var moving := absf(direction) > 0.0
	if moving:
		apply_facing(int(sign(direction)))

	match SaboteurControls.resolve_ground(
		moving,
		SaboteurControls.just_up(),
		Input.is_action_just_pressed("punch"),
		can_climb,
		_lifts.can_ride_up(),
		_chord_is_fresh(),
		_wants_low_stance()
	):
		SaboteurControls.GroundAction.STAND_KICK:
			_start_stand_kick()
		SaboteurControls.GroundAction.RUNNING_JUMP:
			_start_running_jump(direction)
		SaboteurControls.GroundAction.FLYING_KICK:
			_start_jump_kick()
		SaboteurControls.GroundAction.CROUCH_PUNCH:
			_start_crouch_punch()
		SaboteurControls.GroundAction.SOMERSAULT:
			_start_somersault()
		SaboteurControls.GroundAction.PUNCH:
			_start_punch()
		_:
			pass


func _process_somersault(delta: float) -> void:
	velocity.x = float(facing) * speed * somersault_speed_scale
	if not is_on_floor():
		_flip_left_ground = true
		velocity.y += gravity * delta
		return
	if _flip_left_ground:
		current_state = State.IDLE


func _process_platformer(delta: float) -> void:
	if not is_on_floor():
		velocity.y += gravity * delta
		if current_state != State.JUMP:
			current_state = State.JUMP
		return

	# Takeoff frame is still on the floor; keep JUMP until vertical speed falls.
	if current_state == State.JUMP:
		if velocity.y < 0.0:
			return
		current_state = State.IDLE

	var direction := TiltSteer.move_axis()
	var moving := absf(direction) > 0.0
	var down := SaboteurControls.wants_down()
	var lift_down := _lifts.can_ride_down()
	if SaboteurControls.should_crouch(moving, down, lift_down):
		velocity.x = 0.0
		current_state = State.CROUCH
	elif SaboteurControls.should_crawl(moving, down, lift_down):
		velocity.x = direction * crawl_speed
		apply_facing(int(sign(direction)))
		current_state = State.CRAWL
	elif direction:
		velocity.x = direction * speed
		apply_facing(int(sign(direction)))
		if current_state != State.PUNCH and current_state != State.KICK:
			current_state = State.RUN
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		current_state = State.IDLE


func is_riding_lift() -> bool:
	return _lifts.is_riding()


func _try_unstuck() -> void:
	if (
		not is_on_floor()
		or _is_striking()
		or current_state == State.CROUCH
		or current_state == State.CRAWL
		or current_state == State.SOMERSAULT
		or on_ladder
		or on_lift
	):
		return
	var direction := TiltSteer.move_axis()
	if direction == 0.0 or absf(velocity.x) > 8.0:
		return
	var escape := Vector2(direction * 6.0, -10.0)
	if not test_move(global_transform, escape):
		global_position += escape


func get_climb_axis() -> float:
	return SaboteurControls.climb_axis()


func _start_running_jump(direction: float) -> void:
	if direction != 0.0:
		velocity.x = direction * speed
		apply_facing(int(sign(direction)))
	else:
		velocity.x = float(facing) * speed
	velocity.y = jump_velocity
	current_state = State.JUMP


func get_world_mask() -> int:
	return _world_mask


func apply_world_mask() -> void:
	collision_mask = _world_mask


func apply_facing(direction: int) -> void:
	facing = direction
	anim.flip_h = facing < 0


func _start_punch() -> void:
	current_state = State.PUNCH
	punch_timer = punch_duration
	_aim_strike(PUNCH_HIT)


func _start_stand_kick() -> void:
	current_state = State.KICK
	punch_timer = kick_duration
	_aim_strike(KICK_HIT)


func _start_crouch_punch() -> void:
	current_state = State.CROUCH_PUNCH
	punch_timer = punch_duration
	_aim_strike(CROUCH_PUNCH_HIT)


func _start_jump_kick() -> void:
	current_state = State.JUMP_KICK
	_kick_left_ground = false
	velocity.y = jump_velocity
	velocity.x = float(facing) * speed
	punch_timer = kick_duration
	_aim_strike(JUMP_KICK_HIT)


func _start_somersault() -> void:
	current_state = State.SOMERSAULT
	_flip_left_ground = not is_on_floor()
	punch_area.monitoring = false
	velocity = Vector2(
		float(facing) * speed * somersault_speed_scale,
		jump_velocity * somersault_jump_scale
	)


func _aim_strike(hit: Vector2) -> void:
	_strike_age = 0.0
	punch_area.monitoring = true
	punch_area.position = Vector2(BODY_STAND_POS.x + hit.x * float(facing), hit.y)


func _flip_upgrade_wanted() -> bool:
	# MOVE + FIRE already started the flying kick and UP arrived a frame or two
	# later. Those are the flip's own two buttons, so finish the gesture rather
	# than leaving the player in a kick they did not ask for.
	return (
		current_state == State.JUMP_KICK
		and _strike_age <= COMBO_WINDOW
		and SaboteurControls.just_up()
		and absf(TiltSteer.move_axis()) > 0.0
	)


func _late_flip_wanted() -> bool:
	# The mirror case: MOVE + UP already started the running jump and FIRE
	# arrived a frame or two later. Rising, and only just, so FIRE after
	# walking off a ledge stays the no-op the inlay says it is.
	return (
		current_state == State.JUMP
		and velocity.y < 0.0
		and _air_time <= COMBO_WINDOW
		and Input.is_action_just_pressed("punch")
		and absf(TiltSteer.move_axis()) > 0.0
	)


func _is_striking() -> bool:
	return (
		current_state == State.PUNCH
		or current_state == State.KICK
		or current_state == State.CROUCH_PUNCH
		or current_state == State.JUMP_KICK
	)


func _is_planted_strike() -> bool:
	return (
		current_state == State.PUNCH
		or current_state == State.KICK
		or current_state == State.CROUCH_PUNCH
	)


func _tick_chord(delta: float) -> void:
	_up_hold = _advance_hold(_up_hold, delta, SaboteurControls.just_up(), SaboteurControls.wants_up())
	_fire_hold = _advance_hold(
		_fire_hold,
		delta,
		Input.is_action_just_pressed("punch"),
		Input.is_action_pressed("punch")
	)


static func _advance_hold(held_for: float, delta: float, tapped: bool, held: bool) -> float:
	if tapped:
		return 0.0
	return held_for + delta if held else INF


func _chord_is_fresh() -> bool:
	# Both buttons down, and both pressed recently enough to read as one roll
	# of the thumb. UP left held since an earlier kick is stale and does not
	# turn the next flying kick into a flip.
	return maxf(_up_hold, _fire_hold) <= COMBO_WINDOW


func _wants_low_stance() -> bool:
	var moving := absf(TiltSteer.move_axis()) > 0.0
	var down := SaboteurControls.wants_down()
	var lift_down := _lifts.can_ride_down()
	return (
		SaboteurControls.should_crouch(moving, down, lift_down)
		or SaboteurControls.should_crawl(moving, down, lift_down)
	)


func _update_animation() -> void:
	_set_body_crouch(
		current_state == State.CROUCH
		or current_state == State.CRAWL
		or current_state == State.CROUCH_PUNCH
	)
	match current_state:
		State.CLIMB:
			_ladder.sync_pose()
			anim.flip_h = false
			if anim.animation != &"climb":
				anim.play(&"climb")
			anim.speed_scale = 0.0
			anim.set_frame_and_progress(_ladder.climb_frame, 0.0)
		State.PUNCH:
			_play_anim(&"punch")
		State.KICK:
			_play_anim(&"kick")
		State.CROUCH_PUNCH:
			_play_anim(&"crouch_punch")
		State.SOMERSAULT:
			_play_anim(&"somersault")
		State.JUMP_KICK:
			_play_anim(&"jump_kick")
		State.JUMP:
			_play_anim(&"jump")
		State.RUN:
			_play_anim(&"run")
		State.CROUCH, State.CRAWL:
			_play_anim(&"crouch")
		State.DEAD:
			_play_anim(&"death")
		_:
			_play_anim(&"idle")


func _play_anim(anim_name: StringName) -> void:
	anim.speed_scale = 1.0
	if anim.animation != anim_name:
		anim.play(anim_name)


func _set_body_crouch(crouching: bool) -> void:
	var shape := body_collision.shape as RectangleShape2D
	if crouching:
		shape.size = BODY_CROUCH_SIZE
		body_collision.position = BODY_CROUCH_POS
	else:
		shape.size = BODY_STAND_SIZE
		body_collision.position = BODY_STAND_POS


func _tick_regen(delta: float) -> void:
	if on_ladder:
		_regen_accum = 0.0
		return
	if energy >= max_energy:
		_regen_accum = 0.0
		return
	if _time_since_hit < regen_delay:
		_regen_accum = 0.0
		return
	_regen_accum += regen_per_second * delta
	var recovered := int(_regen_accum)
	if recovered <= 0:
		return
	_regen_accum -= float(recovered)
	energy = mini(energy + recovered, max_energy)
	EventBus.energy_changed.emit(energy, max_energy)


func take_damage(amount: int = 12) -> void:
	if is_dead or GameManager.demo_mode or _iframe > 0.0:
		return
	energy = maxi(energy - amount, 0)
	_iframe = iframe_time
	_time_since_hit = 0.0
	_regen_accum = 0.0
	anim.modulate = Color(1.4, 0.45, 0.45)
	EventBus.energy_changed.emit(energy, max_energy)
	if energy > 0:
		return
	is_dead = true
	current_state = State.DEAD
	GameManager.lose_mission()


func respawn(to_position: Vector2) -> void:
	is_dead = false
	current_state = State.IDLE
	on_ladder = false
	on_lift = false
	_ladder.reset()
	_lifts.reset()
	can_climb = false
	apply_world_mask()
	_kick_left_ground = false
	_flip_left_ground = false
	_air_time = 0.0
	_strike_age = 0.0
	_up_hold = INF
	_fire_hold = INF
	_iframe = 0.0
	_time_since_hit = 10.0
	_regen_accum = 0.0
	energy = max_energy
	anim.modulate = Color.WHITE
	global_position = to_position
	velocity = Vector2.ZERO
	EventBus.energy_changed.emit(energy, max_energy)


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		return
	await get_tree().create_timer(0.5).timeout
	respawn(spawn_point)
