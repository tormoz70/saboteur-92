extends Area2D

@export var dest_x: float = 0.0
@export var dest_y: float = 0.0
@export var need_crouch: bool = true


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	collision_layer = CollisionLayers.LAYER_TRIGGERS
	collision_mask = CollisionLayers.LAYER_PLAYER


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("player"):
		return
	if body.get("is_dead"):
		return
	if need_crouch and body.has_method("is_low_stance") and not body.is_low_stance():
		return
	body.global_position = Vector2(dest_x, dest_y)
	body.velocity = Vector2.ZERO
