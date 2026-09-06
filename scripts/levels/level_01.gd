extends Node2D

@onready var player: CharacterBody2D = $Player
@onready var camera: Camera2D = $Camera2D
@onready var world: Node2D = $World

const COLLISION_PATH := "res://assets/world/s2_collision.json"
const WORLD_TEX_PATH := "res://assets/world/saboteur2_world.png"
const WORLD_FG_PATH := "res://assets/world/saboteur2_fg.png"
const LIFT_TEX_PATH := "res://assets/world/s2_lift.png"
const INK_SHADER_PATH := "res://assets/shaders/zx_ink_outline.gdshader"
const LETTERBOX_PX := 160.0
# Camera stays put while Nina is more than this fraction of the playfield away
# from any edge. Crossing that band pushes the view; standing still recenters.
const CAMERA_EDGE_FRACTION := 1.0 / 3.0
const CAMERA_CATCHUP := 3.2
const CAMERA_STILL_DELAY := 0.12

var _scale: float = 2.0
var _screen := Vector2(256, 192)
var _world_size := Vector2(8192, 4608)
var _spawn := Vector2(4480, 1584)
var _cam_still := 0.0
var _bookcases: Array[Rect2] = []
var _ink_material: ShaderMaterial = null


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
	_setup_ink_outline()
	camera.position_smoothing_enabled = false
	camera.make_current()
	_update_camera(0.0, true)
	_connect_punch_areas()
	_start_demo_if_requested()


func _process(delta: float) -> void:
	_update_camera(delta, false)
	_update_ink_outline()
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

	_bookcases.clear()
	for rect in data.get("bookcases", []):
		_bookcases.append(
			Rect2(
				Vector2(float(rect[0]), float(rect[1])) * _scale,
				Vector2(float(rect[2]), float(rect[3])) * _scale
			)
		)

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

	_add_lifts(data)

	# Vertical view is exactly one 192px Spectrum screen (384 world px at
	# zoom 720/384). Horizontal view is wider; the letterbox hides the extra.
	var world_px := _world_size * _scale
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = int(world_px.x)
	camera.limit_bottom = int(world_px.y)
	camera.limit_smoothed = true
	camera.position_smoothing_enabled = false
	camera.zoom = Vector2(720.0 / (_screen.y * _scale), 720.0 / (_screen.y * _scale))


func _add_map_sprite(node_name: String, path: String, z: int) -> void:
	if not ResourceLoader.exists(path):
		push_error("Missing world texture %s" % path)
		return
	var sprite := Sprite2D.new()
	sprite.name = node_name
	sprite.centered = false
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.scale = Vector2(_scale, _scale)
	sprite.z_index = z
	var tex := load(path) as Texture2D
	if tex == null:
		push_error("Could not load world texture %s" % path)
		return
	sprite.texture = tex
	add_child(sprite)
	move_child(sprite, 0)


func _add_lifts(data: Dictionary) -> void:
	var lifts := Node2D.new()
	lifts.name = "Lifts"
	world.add_child(lifts)
	var tex: Texture2D = null
	if not ResourceLoader.exists(LIFT_TEX_PATH):
		push_error("Missing world texture %s" % LIFT_TEX_PATH)
	else:
		tex = load(LIFT_TEX_PATH) as Texture2D
		if tex == null:
			push_error("Could not load world texture %s" % LIFT_TEX_PATH)
	var script := load("res://scripts/world/lift.gd")
	for spec in data.get("lifts", []):
		var lift := AnimatableBody2D.new()
		lift.set_script(script)
		lift.z_index = 6
		var size := Vector2(float(spec["w"]), float(spec["h"])) * _scale
		lift.global_position = Vector2(float(spec["x"]), float(spec["y"])) * _scale
		var sprite := Sprite2D.new()
		sprite.centered = false
		sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		sprite.scale = Vector2(_scale, _scale)
		if tex:
			sprite.texture = tex
			if tex.get_width() > 0:
				sprite.scale.x = size.x / float(tex.get_width())
				sprite.scale.y = size.y / float(tex.get_height())
		else:
			var img := Image.create(int(spec["w"]), int(spec["h"]), false, Image.FORMAT_RGB8)
			img.fill(Color(0.0, 1.0, 1.0))
			sprite.texture = ImageTexture.create_from_image(img)
		lift.add_child(sprite)
		var col := CollisionShape2D.new()
		var shape := RectangleShape2D.new()
		shape.size = size
		col.shape = shape
		col.position = size * 0.5
		lift.add_child(col)
		lifts.add_child(lift)
		lift.setup(float(spec["top"]) * _scale, float(spec["bottom"]) * _scale, size.x)


func _add_rect_shape(body: StaticBody2D, rect: Array, _layer: int) -> void:
	var col := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	var size := Vector2(float(rect[2]), float(rect[3])) * _scale
	shape.size = size
	col.shape = shape
	col.position = Vector2(float(rect[0]), float(rect[1])) * _scale + size * 0.5
	body.add_child(col)


func _setup_ink_outline() -> void:
	if player == null or not ResourceLoader.exists(INK_SHADER_PATH):
		return
	var sprite: CanvasItem = player.get_node_or_null("AnimatedSprite2D")
	if sprite == null:
		return
	_ink_material = ShaderMaterial.new()
	_ink_material.shader = load(INK_SHADER_PATH)
	sprite.material = _ink_material


func _update_ink_outline() -> void:
	# The bookcase covers Nina, and its interior is as black as she is, so she
	# picks up the shelf ink while she is behind one.
	if _ink_material == null or player == null:
		return
	var body := Rect2(player.global_position, Vector2(48.0, 56.0) * _scale)
	var behind := false
	for rect in _bookcases:
		if rect.intersects(body):
			behind = true
			break
	_ink_material.set_shader_parameter("ink_on", 1.0 if behind else 0.0)


func _player_center() -> Vector2:
	return player.global_position + Vector2(24.0, 28.0) * _scale


func _player_is_moving() -> bool:
	if player.on_ladder:
		return absf(player._climb_axis()) > 0.1
	if player.on_lift and player.is_riding_lift():
		return true
	return absf(player.velocity.x) > 18.0 or absf(player.velocity.y) > 36.0


func _update_camera(delta: float, force: bool) -> void:
	if player == null:
		return
	var center := _player_center()
	if force:
		_cam_still = 0.0
		camera.global_position = center
		camera.reset_physics_interpolation()
		return
	if _player_is_moving():
		_cam_still = 0.0
		var playfield := _screen * _scale
		var max_off := playfield * (0.5 - CAMERA_EDGE_FRACTION)
		var cam := camera.global_position
		var off := center - cam
		if off.x > max_off.x:
			cam.x = center.x - max_off.x
		elif off.x < -max_off.x:
			cam.x = center.x + max_off.x
		if off.y > max_off.y:
			cam.y = center.y - max_off.y
		elif off.y < -max_off.y:
			cam.y = center.y + max_off.y
		camera.global_position = cam
		return
	_cam_still += delta
	if _cam_still < CAMERA_STILL_DELAY:
		return
	var t := 1.0 - exp(-CAMERA_CATCHUP * delta)
	camera.global_position = camera.global_position.lerp(center, t)


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
