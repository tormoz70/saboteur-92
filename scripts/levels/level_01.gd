extends Node2D

@onready var player: CharacterBody2D = $Player
@onready var camera: Camera2D = $Camera2D
@onready var tilemap: TileMapLayer = $TileMapLayer

const T_BRICK := Vector2i(0, 0)
const T_FLOOR := Vector2i(1, 0)
const T_LADDER := Vector2i(2, 0)
const T_DOOR := Vector2i(3, 0)
const T_CRATE := Vector2i(4, 0)
const T_WINDOW := Vector2i(5, 0)
const T_CEILING := Vector2i(6, 0)
const T_BG := Vector2i(7, 0)


const TILE_SIZE := 16
const SURFACE_GROUND_Y := 15 * TILE_SIZE
const SURFACE_UPPER_Y := 8 * TILE_SIZE
const SURFACE_CRATE_Y := 14 * TILE_SIZE
const CHAR_HEIGHT := 56.0
const PICKUP_HALF_HEIGHT := 18.0
const SABOTAGE_HALF_HEIGHT := 24.0


const CRATE_TILES := [
	Vector2i(5, 14),
	Vector2i(6, 14),
	Vector2i(12, 14),
	Vector2i(13, 14),
	Vector2i(24, 14),
]


func _ready() -> void:
	_build_tilemap()
	_spawn_crate_collisions()
	_align_entities()
	_connect_punch_areas()
	camera.make_current()
	_start_demo_if_requested()


func _start_demo_if_requested() -> void:
	if not OS.get_cmdline_user_args().has("--demo"):
		return
	var demo := Node.new()
	demo.name = "MissionDemo"
	demo.set_script(load("res://scripts/demo/mission_demo.gd"))
	add_child(demo)


func _process(_delta: float) -> void:
	if player:
		camera.global_position = player.global_position


func _place_tile(x: int, y: int, tile: Vector2i) -> void:
	tilemap.set_cell(Vector2i(x, y), 0, tile)


func _align_entities() -> void:
	_snap_character(player, SURFACE_GROUND_Y)
	_snap_character($Guards/Guard1, SURFACE_GROUND_Y)
	_snap_character($Guards/Guard2, SURFACE_GROUND_Y)
	_snap_character($Guards/Guard3, SURFACE_UPPER_Y)
	_snap_pickup($Items/Key, SURFACE_GROUND_Y)
	_snap_pickup($Items/Document, SURFACE_UPPER_Y)
	_snap_pickup($Items/Bomb, SURFACE_CRATE_Y)
	$SabotageTarget.global_position.y = SURFACE_UPPER_Y - SABOTAGE_HALF_HEIGHT
	$ExitZone.global_position.y = SURFACE_GROUND_Y - 40.0


func _snap_character(body: CharacterBody2D, surface_y: float) -> void:
	body.global_position.y = surface_y - CHAR_HEIGHT


func _snap_pickup(pickup: Node2D, surface_y: float) -> void:
	pickup.global_position.y = surface_y - PICKUP_HALF_HEIGHT


func _build_tilemap() -> void:
	# Warehouse background
	for x in range(40):
		for y in range(16):
			_place_tile(x, y, T_BG)

	# Ceiling strip
	for x in range(40):
		_place_tile(x, 0, T_CEILING)

	# Ground floor platform
	for x in range(40):
		_place_tile(x, 15, T_FLOOR)

	# Upper floor platform
	for x in range(18, 28):
		_place_tile(x, 8, T_FLOOR)

	# Left/right brick walls
	for y in range(1, 16):
		_place_tile(0, y, T_BRICK)
		_place_tile(1, y, T_BRICK)
		_place_tile(38, y, T_BRICK)
		_place_tile(39, y, T_BRICK)

	# Interior wall section
	for y in range(8, 15):
		_place_tile(18, y, T_BRICK)

	# Ladder shaft (tile + area overlap)
	for y in range(9, 14):
		_place_tile(37, y, T_LADDER)

	# Warehouse crates
	for pos in CRATE_TILES:
		_place_tile(pos.x, pos.y, T_CRATE)

	# Windows on upper wall
	for x in [22, 26, 30]:
		_place_tile(x, 7, T_WINDOW)

	# Exit door
	_place_tile(3, 14, T_DOOR)


func _spawn_crate_collisions() -> void:
	var half := TILE_SIZE * 0.5
	for pos in CRATE_TILES:
		var body := StaticBody2D.new()
		body.collision_layer = 4
		var col := CollisionShape2D.new()
		var shape := RectangleShape2D.new()
		shape.size = Vector2(TILE_SIZE, TILE_SIZE)
		col.shape = shape
		col.position = Vector2(pos.x * TILE_SIZE + half, pos.y * TILE_SIZE + half)
		body.add_child(col)
		$World.add_child(body)


func _connect_punch_areas() -> void:
	var punch_area: Area2D = player.get_node("PunchArea")
	if not punch_area.body_entered.is_connected(_on_player_punch_hit):
		punch_area.body_entered.connect(_on_player_punch_hit)


func _on_player_punch_hit(body: Node2D) -> void:
	if body.is_in_group("enemies") and body.has_method("take_damage"):
		body.take_damage()
