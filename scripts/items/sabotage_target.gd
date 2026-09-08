extends Area2D

@export var requires_key: bool = false
@export var requires_document: bool = true
@export var requires_bomb: bool = true


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	EventBus.bomb_planted.connect(_sync_modulate)
	# lose_mission() with lives left resets bomb_planted without emitting
	# bomb_planted; player_died fires after that reset.
	EventBus.player_died.connect(_sync_modulate)
	_sync_modulate()


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("player"):
		return
	if body.get("is_dead"):
		return
	if requires_key and not GameManager.has_key:
		return
	if requires_document and not GameManager.has_document and not GameManager.interlock_cut:
		return
	if requires_bomb and not GameManager.has_bomb:
		return
	if GameManager.bomb_planted:
		return
	EventBus.bomb_planted.emit()


func _sync_modulate() -> void:
	if GameManager.bomb_planted:
		modulate = Color(1.0, 0.3, 0.3)
	else:
		modulate = Color(1.0, 1.0, 1.0, 0.7)
