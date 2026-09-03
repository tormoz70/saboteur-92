extends CanvasLayer

@onready var lives_label: Label = $Margin/VBox/LivesLabel
@onready var score_label: Label = $Margin/VBox/ScoreLabel
@onready var inventory_label: Label = $Margin/VBox/InventoryLabel
@onready var energy_label: Label = $Margin/VBox/EnergyLabel
@onready var energy_bar: ProgressBar = $Margin/VBox/EnergyBar
@onready var status_label: Label = $Margin/VBox/StatusLabel
@onready var bomb_timer_label: Label = $Margin/VBox/BombTimerLabel


func _ready() -> void:
	EventBus.score_changed.connect(_on_score_changed)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.bomb_planted.connect(_on_bomb_planted)
	EventBus.mission_complete.connect(_on_mission_complete)
	EventBus.player_died.connect(_on_player_died)
	EventBus.energy_changed.connect(_on_energy_changed)
	_style_energy_bar()
	_refresh()


func _style_energy_bar() -> void:
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.12, 0.08, 0.1, 0.9)
	bg.set_border_width_all(1)
	bg.border_color = Color(0.55, 0.15, 0.15)
	energy_bar.add_theme_stylebox_override("background", bg)
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color(0.82, 0.12, 0.12)
	energy_bar.add_theme_stylebox_override("fill", fill)


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
	var player := get_tree().get_first_node_in_group("player")
	if player and "energy" in player:
		_on_energy_changed(player.energy, player.max_energy)


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


func _on_energy_changed(current: int, max_energy: int) -> void:
	energy_bar.max_value = max_energy
	energy_bar.value = current
	energy_label.text = "Energy"


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
