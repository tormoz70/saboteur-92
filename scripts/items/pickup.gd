extends Area2D

@export var item_type: String = "key"
@export var required_item: String = ""

const ITEM_REGIONS := {
	"key": Rect2(0, 0, 32, 16),
	"document": Rect2(32, 0, 32, 16),
	"bomb": Rect2(64, 0, 32, 16),
}


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	if has_node("Sprite"):
		var tex: Texture2D = load("res://assets/sprites/saboteur85_items.png")
		if tex and ITEM_REGIONS.has(item_type):
			$Sprite.texture = AtlasTexture.new()
			$Sprite.texture.atlas = tex
			$Sprite.texture.region = ITEM_REGIONS[item_type]


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("player"):
		return
	if body.get("is_dead"):
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
