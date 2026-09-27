extends CharacterBody2D

## Saboteur II guard. Patrols its floor, turning at walls, ledges and the
## patrol bounds. Seeing Nina (SightArea plus a clear line of sight) makes
## it stop for `notice_time` with a "!" over its head, then chase. In reach
## it winds up a punch for `attack_windup`; the blow lands only if she is
## still in front of it when the wind-up ends.

enum AiState { PATROL, NOTICE, CHASE, WINDUP, RECOVER, DEAD }

## Seconds of engagement (chase and fight, not the notice pause) before the
## guard raises the alarm.
const ALARM_CHASE_SEC := 1.0
const GRAVITY := 600.0
# Same cap as Nina. An uncapped fall tunnels through one-cell floors and the
# sweep in move_and_slide freezes the game.
const MAX_FALL := 420.0
# Sprite px: head height in the 48x56 cell, and the footing probe.
const EYE := Vector2(24.0, 12.0)
const LEDGE_MARGIN := 2.0
const LEDGE_DEPTH := 10.0
const WALL_REACH := 3.0
const STRIKE_POSE_SEC := 0.2
const STAGGER_SEC := 0.35

@export var patrol_speed: float = 60.0
@export var chase_speed: float = 100.0
@export var max_health: int = 2
@export var patrol_distance: float = 120.0
## World px between body centres at which the guard starts a punch.
@export var attack_range: float = 45.0
## World px in front of the body centre the blow still lands at the end of
## the wind-up.
@export var attack_reach: float = 52.0
@export var attack_damage: int = 15
@export var notice_time: float = 0.4
@export var attack_windup: float = 0.4
@export var attack_recover: float = 0.45
## Seconds the guard keeps chasing towards where it last saw Nina.
@export var sight_memory: float = 0.5

var health: int
var ai_state: AiState = AiState.PATROL
var patrol_origin: float
var patrol_dir: int = 1
var facing: int = 1
var target: Node2D = null
var _state_time: float = 0.0
var _chase_time: float = 0.0
var _unseen_time: float = 0.0
var _last_seen_x: float = 0.0
var _recover_left: float = 0.0
var _strike_pose_left: float = 0.0
var _body_width: float = 14.0

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var sight: Area2D = $SightArea
@onready var alert_mark: CanvasItem = $AlertMark
@onready var body_shape: CollisionShape2D = $CollisionShape2D


func _ready() -> void:
	health = max_health
	patrol_origin = global_position.x
	add_to_group("enemies")
	var rect := body_shape.shape as RectangleShape2D
	if rect:
		_body_width = rect.size.x
	alert_mark.visible = false


func _physics_process(delta: float) -> void:
	if ai_state == AiState.DEAD:
		return
	_state_time += delta
	_strike_pose_left = maxf(_strike_pose_left - delta, 0.0)
	var seen := _visible_player()
	if seen:
		target = seen
		_unseen_time = 0.0
		_last_seen_x = _centre_of(seen).x
	else:
		_unseen_time += delta

	match ai_state:
		AiState.PATROL:
			_patrol()
			if seen:
				_start_notice()
		AiState.NOTICE:
			_notice()
		AiState.CHASE:
			_chase()
		AiState.WINDUP:
			_windup()
		AiState.RECOVER:
			_recover(delta)

	if is_engaged():
		_chase_time += delta
		if _chase_time >= ALARM_CHASE_SEC:
			GameManager.raise_alarm()
	else:
		_chase_time = 0.0

	if not is_on_floor():
		velocity.y = minf(velocity.y + GRAVITY * delta, MAX_FALL)
	move_and_slide()
	_update_anim()


func is_engaged() -> bool:
	return ai_state in [AiState.CHASE, AiState.WINDUP, AiState.RECOVER]


func blocked_ahead(dir: int) -> bool:
	return (
		EnemySenses.wall_ahead(self, dir, WALL_REACH)
		or EnemySenses.ledge_ahead(self, dir, _body_width + LEDGE_MARGIN, LEDGE_DEPTH)
	)


func _visible_player() -> Node2D:
	var eye := global_transform * EYE
	for body in sight.get_overlapping_bodies():
		if not body.is_in_group("player") or body.get("is_dead"):
			continue
		if EnemySenses.can_see(self, eye, body):
			return body
	return null


func _set_state(next: AiState) -> void:
	ai_state = next
	_state_time = 0.0
	alert_mark.visible = next == AiState.NOTICE


func _start_notice() -> void:
	_set_state(AiState.NOTICE)
	velocity.x = 0.0
	_face_x(_last_seen_x)
	AudioManager.play_sfx("spotted")


func _patrol() -> void:
	if global_position.x <= patrol_origin - patrol_distance:
		patrol_dir = 1
	elif global_position.x >= patrol_origin + patrol_distance:
		patrol_dir = -1
	if is_on_floor() and blocked_ahead(patrol_dir):
		patrol_dir = -patrol_dir
	facing = patrol_dir
	velocity.x = patrol_dir * patrol_speed


func _notice() -> void:
	velocity.x = 0.0
	if _unseen_time == 0.0:
		_face_x(_last_seen_x)
	if _state_time < notice_time:
		return
	if _unseen_time <= sight_memory and is_instance_valid(target):
		_set_state(AiState.CHASE)
	else:
		_set_state(AiState.PATROL)


func _chase() -> void:
	if not is_instance_valid(target) or _unseen_time > sight_memory:
		target = null
		_set_state(AiState.PATROL)
		return
	if _unseen_time == 0.0 and _in_attack_range():
		velocity.x = 0.0
		_set_state(AiState.WINDUP)
		return
	var dx := _last_seen_x - _centre_of(self).x
	if absf(dx) < 4.0:
		velocity.x = 0.0
		return
	_face_x(_last_seen_x)
	if is_on_floor() and blocked_ahead(facing):
		velocity.x = 0.0
	else:
		velocity.x = facing * chase_speed


func _windup() -> void:
	velocity.x = 0.0
	if _state_time < attack_windup:
		return
	var hittable := is_instance_valid(target) and target.has_method("take_damage")
	if hittable and _target_in_reach():
		target.take_damage(attack_damage)
	AudioManager.play_sfx("punch")
	_strike_pose_left = STRIKE_POSE_SEC
	_start_recover(attack_recover)


func _start_recover(seconds: float) -> void:
	_set_state(AiState.RECOVER)
	_recover_left = seconds


func _recover(delta: float) -> void:
	velocity.x = 0.0
	_recover_left -= delta
	if _recover_left > 0.0:
		return
	_set_state(AiState.CHASE)


func _in_attack_range() -> bool:
	var d := _centre_of(target) - _centre_of(self)
	return absf(d.x) <= attack_range and absf(d.y) <= attack_range


func _target_in_reach() -> bool:
	var d := _centre_of(target) - _centre_of(self)
	var ahead := d.x * float(facing)
	return ahead >= -4.0 and ahead <= attack_reach and absf(d.y) <= attack_range


func _centre_of(node: Node2D) -> Vector2:
	var col := node.get_node_or_null("CollisionShape2D") as Node2D
	return col.global_position if col else node.global_position


func _face_x(world_x: float) -> void:
	var dx := world_x - _centre_of(self).x
	if absf(dx) >= 1.0:
		facing = 1 if dx > 0.0 else -1


func take_damage(amount: int = 1) -> void:
	if ai_state == AiState.DEAD:
		return
	AudioManager.play_sfx("hit")
	health -= amount
	if health <= 0:
		_die()
		return
	# A hit spoils the wind-up and turns a patrolling guard round to fight.
	if ai_state != AiState.RECOVER:
		_start_recover(STAGGER_SEC)
	modulate = Color(1.5, 0.5, 0.5)
	await get_tree().create_timer(0.1, false).timeout
	modulate = Color.WHITE


func _die() -> void:
	_set_state(AiState.DEAD)
	velocity = Vector2.ZERO
	collision_layer = 0
	collision_mask = 0
	EventBus.enemy_killed.emit(self)
	anim.modulate = Color(0.4, 0.4, 0.4)
	await get_tree().create_timer(0.4, false).timeout
	queue_free()


func _update_anim() -> void:
	if ai_state == AiState.DEAD:
		return
	anim.flip_h = facing < 0
	anim.offset.x = 0.0
	anim.self_modulate = Color.WHITE
	match ai_state:
		AiState.WINDUP:
			# Telegraph: lean back and flush red until the punch comes out.
			anim.play("idle")
			anim.pause()
			anim.offset.x = -2.0 * facing
			var t := _state_time / maxf(attack_windup, 0.01)
			anim.self_modulate = Color(1.0, 1.0 - 0.7 * t, 1.0 - 0.7 * t)
		AiState.RECOVER:
			anim.play("punch" if _strike_pose_left > 0.0 else "idle")
		_:
			if absf(velocity.x) > 5.0:
				anim.play("run")
			else:
				anim.play("idle")
