extends CanvasLayer

@onready var lives_label: Label = $Margin/VBox/LivesLabel
@onready var score_label: Label = $Margin/VBox/ScoreLabel
@onready var inventory_label: Label = $Margin/VBox/InventoryLabel
@onready var status_label: Label = $Margin/VBox/StatusLabel
@onready var bomb_timer_label: Label = $Margin/VBox/BombTimerLabel


func _ready() -> void:
	EventBus.score_changed.connect(_on_score_changed)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.bomb_planted.connect(_on_bomb_planted)
	EventBus.mission_complete.connect(_on_mission_complete)
	EventBus.player_died.connect(_on_player_died)
	_refresh()


func _process(_delta: float) -> void:
	_update_inventory()
	if GameManager.bomb_planted and GameManager.state == GameManager.GameState.PLAYING:
		bomb_timer_label.text = "Bomb: %ds" % ceili(GameManager.bomb_timer)
	else:
		bomb_timer_label.text = ""


func _refresh() -> void:
	lives_label.text = "Lives: %d" % GameManager.lives
	score_label.text = "Score: %d" % GameManager.score
	_update_inventory()
	status_label.text = ""


func _update_inventory() -> void:
	var items: Array[String] = []
	if GameManager.has_key:
		items.append("Key")
	if GameManager.has_document:
		items.append("Doc")
	if GameManager.has_bomb:
		items.append("Bomb")
	inventory_label.text = "Items: " + (", ".join(items) if items.size() else "-")


func _on_score_changed(new_score: int) -> void:
	score_label.text = "Score: %d" % new_score


func _on_item_collected(_item_type: String) -> void:
	_update_inventory()


func _on_bomb_planted() -> void:
	status_label.text = "Bomb planted! Escape!"


func _on_mission_complete() -> void:
	status_label.text = "Mission complete!"


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		status_label.text = "Game Over"
	else:
		status_label.text = "You died!"
		await get_tree().create_timer(1.0).timeout
		status_label.text = ""
		_refresh()
