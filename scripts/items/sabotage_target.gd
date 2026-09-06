extends Area2D

@export var requires_key: bool = false
@export var requires_document: bool = true
@export var requires_bomb: bool = true


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("player"):
		return
	if body.get("is_dead"):
		return
	if requires_key and not GameManager.has_key:
		return
	if requires_document and not GameManager.has_document:
		return
	if requires_bomb and not GameManager.has_bomb:
		return
	if GameManager.bomb_planted:
		return
	EventBus.bomb_planted.emit()


func _process(_delta: float) -> void:
	if GameManager.bomb_planted:
		modulate = Color(1.0, 0.3, 0.3)
	else:
		modulate = Color(1.0, 1.0, 1.0, 0.7)
