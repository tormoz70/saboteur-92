extends Area2D

@export var label: String = ""


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	collision_layer = CollisionLayers.LAYER_TRIGGERS
	collision_mask = CollisionLayers.LAYER_PLAYER


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("player"):
		return
	if body.get("is_dead"):
		return
	GameManager.note_code(label)
