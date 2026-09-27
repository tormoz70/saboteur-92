extends CharacterBody2D

## Saboteur II panther. Faster than Nina, hurts her on touch, never leaves
## its floor: it prowls between walls, ledges and optional patrol bounds and
## charges once it sees her. Its HurtBox is low enough for Nina's somersault
## to clear (test_panther.gd checks the numbers). A low punch (crouch + FIRE)
## reaches its body; the first hit stuns it, the second kills it.

enum AiState { PROWL, CHARGE, STUNNED, DEAD }

const GRAVITY := 600.0
const MAX_FALL := 420.0
# Sprite px in the 64x32 cell facing right; flip_h mirrors about FRAME_MID.
const EYE := Vector2(52.0, 12.0)
const FRAME_MID := 32.0
const LEDGE_MARGIN := 2.0
const LEDGE_DEPTH := 10.0
const WALL_REACH := 3.0
## Seconds without seeing Nina before a charge winds down to a prowl.
const LOSE_SIGHT_SEC := 0.8

@export var prowl_speed: float = 140.0
@export var charge_speed: float = 175.0
@export var contact_damage: int = 15
@export var contact_cooldown: float = 0.6
@export var max_health: int = 2
@export var stun_time: float = 0.6
## Seconds a charging panther keeps running once Nina is behind it.
@export var turn_delay: float = 0.5
## World px either side of the spawn; 0 roams the whole floor.
@export var patrol_distance: float = 0.0

var health: int
var ai_state: AiState = AiState.PROWL
var facing: int = 1
var patrol_origin: float
var target: Node2D = null
var _state_time: float = 0.0
var _unseen_time: float = 0.0
var _behind_time: float = 0.0
var _contact_left: float = 0.0
var _body_width: float = 32.0

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var sight: Area2D = $SightArea
@onready var hurt_box: Area2D = $HurtBox
@onready var body_shape: CollisionShape2D = $CollisionShape2D


func _ready() -> void:
	health = max_health
	patrol_origin = global_position.x
	add_to_group("enemies")
	add_to_group("panthers")
	var rect := body_shape.shape as RectangleShape2D
	if rect:
		_body_width = rect.size.x


func _physics_process(delta: float) -> void:
	if ai_state == AiState.DEAD:
		return
	_state_time += delta
	_contact_left = maxf(_contact_left - delta, 0.0)
	var seen := _visible_player()
	if seen:
		target = seen
		_unseen_time = 0.0
	else:
		_unseen_time += delta

	match ai_state:
		AiState.PROWL:
			_prowl()
			if seen:
				_set_state(AiState.CHARGE)
		AiState.CHARGE:
			_charge(delta)
		AiState.STUNNED:
			velocity.x = 0.0
			if _state_time >= stun_time:
				_set_state(AiState.PROWL)

	if not is_on_floor():
		velocity.y = minf(velocity.y + GRAVITY * delta, MAX_FALL)
	move_and_slide()
	_touch_player()
	_update_anim()


func blocked_ahead(dir: int) -> bool:
	return (
		EnemySenses.wall_ahead(self, dir, WALL_REACH)
		or EnemySenses.ledge_ahead(self, dir, _body_width + LEDGE_MARGIN, LEDGE_DEPTH)
	)


func _visible_player() -> Node2D:
	var eye := global_transform * Vector2(FRAME_MID + (EYE.x - FRAME_MID) * facing, EYE.y)
	for body in sight.get_overlapping_bodies():
		if not body.is_in_group("player") or body.get("is_dead"):
			continue
		if EnemySenses.can_see(self, eye, body):
			return body
	return null


func _set_state(next: AiState) -> void:
	ai_state = next
	_state_time = 0.0
	_behind_time = 0.0


func _prowl() -> void:
	if patrol_distance > 0.0:
		if global_position.x <= patrol_origin - patrol_distance:
			facing = 1
		elif global_position.x >= patrol_origin + patrol_distance:
			facing = -1
	if is_on_floor() and blocked_ahead(facing):
		facing = -facing
	velocity.x = facing * prowl_speed


func _charge(delta: float) -> void:
	if not is_instance_valid(target) or _unseen_time > LOSE_SIGHT_SEC:
		target = null
		_set_state(AiState.PROWL)
		return
	var dx := _centre_of(target).x - _centre_of(self).x
	if dx * facing < 0.0:
		_behind_time += delta
		if _behind_time >= turn_delay:
			facing = -facing
			_behind_time = 0.0
	else:
		_behind_time = 0.0
	if is_on_floor() and blocked_ahead(facing):
		velocity.x = 0.0
	else:
		velocity.x = facing * charge_speed


func _touch_player() -> void:
	if ai_state != AiState.PROWL and ai_state != AiState.CHARGE:
		return
	if _contact_left > 0.0:
		return
	for body in hurt_box.get_overlapping_bodies():
		if body.is_in_group("player") and body.has_method("take_damage"):
			body.take_damage(contact_damage)
			_contact_left = contact_cooldown
			return


func _centre_of(node: Node2D) -> Vector2:
	var col := node.get_node_or_null("CollisionShape2D") as Node2D
	return col.global_position if col else node.global_position


func take_damage(amount: int = 1) -> void:
	if ai_state == AiState.DEAD:
		return
	AudioManager.play_sfx("hit")
	health -= amount
	if health <= 0:
		_die()
		return
	_set_state(AiState.STUNNED)
	velocity.x = 0.0
	modulate = Color(1.5, 0.5, 0.5)
	await get_tree().create_timer(0.1, false).timeout
	modulate = Color.WHITE


func _die() -> void:
	_set_state(AiState.DEAD)
	velocity = Vector2.ZERO
	collision_layer = 0
	collision_mask = 0
	hurt_box.set_deferred("monitoring", false)
	EventBus.enemy_killed.emit(self)
	anim.play("crouch")
	anim.modulate = Color(0.4, 0.4, 0.4)
	await get_tree().create_timer(0.4, false).timeout
	queue_free()


func _update_anim() -> void:
	if ai_state == AiState.DEAD:
		return
	anim.flip_h = facing < 0
	if ai_state == AiState.STUNNED or absf(velocity.x) < 5.0:
		anim.play("crouch")
		return
	anim.play("run")
	anim.speed_scale = absf(velocity.x) / prowl_speed
