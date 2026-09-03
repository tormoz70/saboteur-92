extends Node2D

@onready var player: CharacterBody2D = $Player
@onready var camera: Camera2D = $Camera2D
@onready var world: Node2D = $World

const COLLISION_PATH := "res://assets/world/s2_collision.json"
const WORLD_TEX_PATH := "res://assets/world/saboteur2_world.png"
const WORLD_FG_PATH := "res://assets/world/saboteur2_fg.png"
const CHAR_HEIGHT := 56.0
const LETTERBOX_PX := 160.0

var _scale: float = 2.0
var _screen := Vector2(256, 192)
var _world_size := Vector2(8192, 4608)
var _spawn := Vector2(4480, 1584)
var _room := Vector2i(-1, -1)


func _ready() -> void:
	_load_original_world()
	_hide_demo_entities()
	_add_letterbox()
	if player:
		# Mosaic is SCALE× original pixels; S2 sprites are already 48×56.
		player.scale = Vector2(_scale, _scale)
		player.spawn_point = _spawn
		player.global_position = _spawn
		player.z_index = 8
	camera.position_smoothing_enabled = false
	camera.make_current()
	_snap_camera(true)
	_connect_punch_areas()
	_start_demo_if_requested()


func _process(_delta: float) -> void:
	_snap_camera(false)
	if player and player.global_position.y > _world_size.y * _scale + 64.0:
		if not player.is_dead:
			player.take_damage(player.energy)


func _load_original_world() -> void:
	if not FileAccess.file_exists(COLLISION_PATH):
		push_error("Missing %s — run tools/saboteur_rip/build_s2_world.py" % COLLISION_PATH)
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(COLLISION_PATH))
	_scale = float(data.get("scale", 2))
	var scr: Array = data.get("screen", [256, 192])
	_screen = Vector2(float(scr[0]), float(scr[1]))
	var sz: Array = data.get("size", [8192, 4608])
	_world_size = Vector2(float(sz[0]), float(sz[1]))
	var sp: Array = data.get("spawn", [4480, 1640])
	_spawn = Vector2(float(sp[0]), float(sp[1]))

	_add_map_sprite("OriginalMap", WORLD_TEX_PATH, -20)
	_add_map_sprite("Foreground", WORLD_FG_PATH, 12)

	for child in world.get_children():
		world.remove_child(child)
		child.free()

	var body := StaticBody2D.new()
	body.name = "Solids"
	body.collision_layer = 4
	body.collision_mask = 0
	world.add_child(body)
	for rect in data.get("solids", []):
		_add_rect_shape(body, rect, 4)

	var ladders := Node2D.new()
	ladders.name = "Ladders"
	world.add_child(ladders)
	for rect in data.get("ladders", []):
		var area := Area2D.new()
		area.collision_layer = 16
		area.collision_mask = 0
		var col := CollisionShape2D.new()
		var shape := RectangleShape2D.new()
		var size := Vector2(float(rect[2]), float(rect[3])) * _scale
		shape.size = size
		col.shape = shape
		col.position = Vector2(float(rect[0]), float(rect[1])) * _scale + size * 0.5
		area.add_child(col)
		ladders.add_child(area)

	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = int(_world_size.x * _scale)
	camera.limit_bottom = int(_world_size.y * _scale)
	camera.zoom = Vector2(1.875, 1.875)


func _add_map_sprite(node_name: String, path: String, z: int) -> void:
	if not FileAccess.file_exists(path):
		return
	var sprite := Sprite2D.new()
	sprite.name = node_name
	sprite.centered = false
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.scale = Vector2(_scale, _scale)
	sprite.z_index = z
	var img := Image.new()
	if img.load(path) != OK:
		push_error("Could not load %s" % path)
		return
	sprite.texture = ImageTexture.create_from_image(img)
	add_child(sprite)
	move_child(sprite, 0)


func _add_rect_shape(body: StaticBody2D, rect: Array, _layer: int) -> void:
	var col := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	var size := Vector2(float(rect[2]), float(rect[3])) * _scale
	shape.size = size
	col.shape = shape
	col.position = Vector2(float(rect[0]), float(rect[1])) * _scale + size * 0.5
	body.add_child(col)


func _snap_camera(force: bool) -> void:
	if player == null:
		return
	var sw := _screen.x * _scale
	var sh := _screen.y * _scale
	var px := player.global_position.x + 24.0 * _scale
	var py := player.global_position.y + 28.0 * _scale
	var room := Vector2i(int(floor(px / sw)), int(floor(py / sh)))
	room.x = clampi(room.x, 0, int(_world_size.x / _screen.x) - 1)
	room.y = clampi(room.y, 0, int(_world_size.y / _screen.y) - 1)
	if not force and room == _room:
		return
	_room = room
	camera.global_position = Vector2((float(room.x) + 0.5) * sw, (float(room.y) + 0.5) * sh)


func _add_letterbox() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Letterbox"
	layer.layer = 3
	var left := ColorRect.new()
	left.color = Color.BLACK
	left.set_anchors_and_offsets_preset(Control.PRESET_LEFT_WIDE)
	left.offset_right = LETTERBOX_PX
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var right := ColorRect.new()
	right.color = Color.BLACK
	right.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	right.offset_left = -LETTERBOX_PX
	right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(left)
	layer.add_child(right)
	add_child(layer)


func _hide_demo_entities() -> void:
	for path in ["Guards", "Items", "SabotageTarget", "ExitZone", "TileMapLayer"]:
		var node := get_node_or_null(path)
		if node:
			node.visible = false
			node.process_mode = Node.PROCESS_MODE_DISABLED


func _start_demo_if_requested() -> void:
	if not OS.get_cmdline_user_args().has("--demo"):
		return
	var demo := Node.new()
	demo.name = "MissionDemo"
	demo.set_script(load("res://scripts/demo/mission_demo.gd"))
	add_child(demo)


func _connect_punch_areas() -> void:
	if player == null:
		return
	var punch_area: Area2D = player.get_node_or_null("PunchArea")
	if punch_area == null:
		return
	if not punch_area.body_entered.is_connected(_on_player_punch_hit):
		punch_area.body_entered.connect(_on_player_punch_hit)


func _on_player_punch_hit(body: Node2D) -> void:
	if body.is_in_group("enemies") and body.has_method("take_damage"):
		body.take_damage()
