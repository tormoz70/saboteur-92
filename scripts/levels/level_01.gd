extends Node2D

@onready var player: CharacterBody2D = $Player
@onready var guards: Node2D = $Guards
@onready var camera: Camera2D = $Camera2D
@onready var tilemap: TileMapLayer = $TileMapLayer


func _ready() -> void:
	_build_tilemap()
	_connect_punch_areas()
	camera.make_current()


func _process(_delta: float) -> void:
	if player:
		camera.global_position = player.global_position


func _build_tilemap() -> void:
	for x in range(40):
		tilemap.set_cell(Vector2i(x, 15), 0, Vector2i(1, 0))
	for x in range(18, 28):
		tilemap.set_cell(Vector2i(x, 8), 0, Vector2i(1, 0))
	for y in range(8, 15):
		tilemap.set_cell(Vector2i(18, y), 0, Vector2i(0, 0))
		tilemap.set_cell(Vector2i(39, y), 0, Vector2i(0, 0))
	for x in range(0, 2):
		for y in range(8, 16):
			tilemap.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	tilemap.set_cell(Vector2i(18, 9), 0, Vector2i(2, 0))
	tilemap.set_cell(Vector2i(18, 10), 0, Vector2i(2, 0))
	tilemap.set_cell(Vector2i(18, 11), 0, Vector2i(2, 0))
	tilemap.set_cell(Vector2i(18, 12), 0, Vector2i(2, 0))
	tilemap.set_cell(Vector2i(18, 13), 0, Vector2i(2, 0))


func _connect_punch_areas() -> void:
	var punch_area: Area2D = player.get_node("PunchArea")
	if not punch_area.body_entered.is_connected(_on_player_punch_hit):
		punch_area.body_entered.connect(_on_player_punch_hit)


func _on_player_punch_hit(body: Node2D) -> void:
	if body.is_in_group("enemies") and body.has_method("take_damage"):
		body.take_damage()
