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
		area.monitorable = true
		area.monitoring = false
		var col := CollisionShape2D.new()
		var shape := RectangleShape2D.new()
		var size := Vector2(float(rect[2]), float(rect[3])) * _scale
		shape.size = size
		col.shape = shape
		col.position = Vector2(float(rect[0]), float(rect[1])) * _scale + size * 0.5
		area.add_child(col)
		ladders.add_child(area)

	# Vertical view is exactly one 192px Spectrum screen (384 world px at
	# zoom 720/384). Horizontal view is wider; the letterbox hides the extra.
	camera.limit_smoothed = false
	camera.position_smoothing_enabled = false
	camera.zoom = Vector2(720.0 / (_screen.y * _scale), 720.0 / (_screen.y * _scale))


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
	var sprite_h := CHAR_HEIGHT * _scale
	var max_rx := int(_world_size.x / _screen.x) - 1
	var max_ry := int(_world_size.y / _screen.y) - 1
	var px := player.global_position.x + 24.0 * _scale
	var origin_y := player.global_position.y
	var rx := clampi(int(floor(px / sw)), 0, max_rx)
	var ry := _room.y
	if ry < 0:
		ry = clampi(int(floor(origin_y / sh)), 0, max_ry)
	# Original flip-screen (S1 LC604/LC623, S2 32-column tile rooms): the
	# ninja stays fully inside one screen. The next step off the bottom
	# loads the room below with Y at the top; off the top loads the room
	# above with the sprite planted on that screen's bottom. Never draw a
	# sprite that straddles the seam — that is the half-Nina glitch.
	var top := float(ry) * sh
	var max_origin := top + sh - sprite_h
	var wrapped := false
	if origin_y > max_origin + 1.0 and ry < max_ry:
		ry += 1
		player.global_position.y = float(ry) * sh
		wrapped = true
	elif origin_y < top - 1.0 and ry > 0:
		ry -= 1
		player.global_position.y = float(ry + 1) * sh - sprite_h
		wrapped = true
	if wrapped:
		player.velocity.y = 0.0
		player.reset_physics_interpolation()
		if player.has_method("_sync_climb_pose"):
			player._sync_climb_pose()
	var room := Vector2i(rx, ry)
	if not force and not wrapped and room == _room:
		return
	_room = room
	camera.global_position = Vector2((float(room.x) + 0.5) * sw, (float(room.y) + 0.5) * sh)
	camera.limit_left = int(room.x * sw)
	camera.limit_right = int((room.x + 1) * sw)
	camera.limit_top = int(room.y * sh)
	camera.limit_bottom = int((room.y + 1) * sh)
	camera.reset_physics_interpolation()


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
