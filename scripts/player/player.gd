extends CharacterBody2D

enum State { IDLE, RUN, JUMP, CLIMB, PUNCH, DEAD }

@export var speed: float = 150.0
@export var jump_velocity: float = -300.0
@export var gravity: float = 600.0
@export var climb_speed: float = 120.0
@export var punch_duration: float = 0.35

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var punch_area: Area2D = $PunchArea
@onready var ladder_detector: Area2D = $LadderDetector

var current_state: State = State.IDLE
var facing: int = 1
var punch_timer: float = 0.0
var on_ladder: bool = false
var can_climb: bool = false
var is_dead: bool = false


func _ready() -> void:
	punch_area.monitoring = false
	EventBus.player_died.connect(_on_player_died)


func _physics_process(delta: float) -> void:
	if is_dead or GameManager.state != GameManager.GameState.PLAYING:
		velocity = Vector2.ZERO
		move_and_slide()
		return

	can_climb = ladder_detector.get_overlapping_areas().size() > 0
	on_ladder = can_climb and abs(Input.get_axis("move_up", "move_down")) > 0.0

	if current_state == State.PUNCH:
		punch_timer -= delta
		if punch_timer <= 0.0:
			punch_area.monitoring = false
			current_state = State.IDLE

	if current_state != State.PUNCH and Input.is_action_just_pressed("punch"):
		_start_punch()

	if on_ladder:
		_process_climb(delta)
	elif current_state != State.PUNCH:
		_process_platformer(delta)

	_update_animation()
	move_and_slide()
	_try_unstuck()


func _process_platformer(delta: float) -> void:
	if not is_on_floor():
		velocity.y += gravity * delta
		current_state = State.JUMP
	else:
		if current_state == State.JUMP:
			current_state = State.IDLE

	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_velocity
		current_state = State.JUMP

	var direction := Input.get_axis("move_left", "move_right")
	if direction:
		velocity.x = direction * speed
		facing = int(sign(direction))
		anim.flip_h = facing < 0
		if is_on_floor() and current_state != State.PUNCH:
			current_state = State.RUN
	elif is_on_floor() and current_state != State.PUNCH:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		current_state = State.IDLE


func _try_unstuck() -> void:
	if not is_on_floor() or current_state == State.PUNCH or on_ladder:
		return
	var direction := Input.get_axis("move_left", "move_right")
	if direction == 0.0 or absf(velocity.x) > 8.0:
		return
	# Nudge up and along input when wedged between colliders (e.g. door + crate).
	var escape := Vector2(direction * 6.0, -10.0)
	if not test_move(global_transform, escape):
		global_position += escape


func _process_climb(_delta: float) -> void:
	velocity.x = 0.0
	velocity.y = Input.get_axis("move_up", "move_down") * climb_speed
	current_state = State.CLIMB


func _start_punch() -> void:
	current_state = State.PUNCH
	punch_timer = punch_duration
	punch_area.monitoring = true
	punch_area.position.x = 24.0 * facing


func _update_animation() -> void:
	match current_state:
		State.CLIMB:
			anim.play("climb")
		State.PUNCH:
			anim.play("punch")
		State.JUMP:
			anim.play("jump")
		State.RUN:
			anim.play("run")
		State.DEAD:
			anim.play("death")
		_:
			anim.play("idle")


func take_damage() -> void:
	if is_dead or GameManager.demo_mode:
		return
	is_dead = true
	current_state = State.DEAD
	GameManager.lose_mission()


func respawn(spawn_point: Vector2) -> void:
	is_dead = false
	current_state = State.IDLE
	global_position = spawn_point
	velocity = Vector2.ZERO


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		return
	await get_tree().create_timer(0.5).timeout
	respawn(Vector2(48, 184))
