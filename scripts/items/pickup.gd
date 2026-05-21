extends Area2D

@export var item_type: String = "key"
@export var required_item: String = ""

const ITEM_COLORS := {
	"key": Color(1.0, 0.85, 0.2, 1.0),
	"document": Color(0.85, 0.95, 1.0, 1.0),
	"bomb": Color(0.9, 0.3, 0.2, 1.0),
}


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	if has_node("Sprite") and ITEM_COLORS.has(item_type):
		$Sprite.color = ITEM_COLORS[item_type]


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("player"):
		return
	if required_item != "" and not _player_has(required_item):
		return
	EventBus.item_collected.emit(item_type)
	queue_free()


func _player_has(item: String) -> bool:
	match item:
		"key":
			return GameManager.has_key
		"document":
			return GameManager.has_document
		"bomb":
			return GameManager.has_bomb
	return false
