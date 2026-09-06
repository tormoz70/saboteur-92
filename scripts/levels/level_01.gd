extends Node2D

@onready var player: CharacterBody2D = $Player
@onready var camera: Camera2D = $Camera2D
@onready var world: Node2D = $World
@onready var visual_layer: TileMapLayer = $Visual
@onready var fg_layer: TileMapLayer = $Foreground

const COLLISION_PATH := "res://assets/world/s2_collision.json"
const ENTITIES_PATH := "res://assets/world/s2_entities.json"
const TILES_PATH := "res://assets/world/s2_world_tiles.json"
const WORLD_TILESET_PATH := "res://assets/tilesets/s2_world_tileset.tres"
const FG_TILESET_PATH := "res://assets/tilesets/s2_fg_tileset.tres"
const LIFT_TEX_PATH := "res://assets/world/s2_lift.png"
const INK_SHADER_PATH := "res://assets/shaders/zx_ink_outline.gdshader"
const PICKUP_SCENE := preload("res://scenes/items/pickup.tscn")
const GUARD_SCENE := preload("res://scenes/enemies/guard.tscn")
const SABOTAGE_SCENE := preload("res://scenes/items/sabotage_target.tscn")
const EXIT_SCENE := preload("res://scenes/items/exit_zone.tscn")
const LETTERBOX_PX := 160.0
# Camera stays put while Nina is more than this fraction of the playfield away
# from any edge. Crossing that band pushes the view; standing still recenters.
const CAMERA_EDGE_FRACTION := 1.0 / 3.0
const CAMERA_CATCHUP := 3.2
const CAMERA_STILL_DELAY := 0.12

var _scale: float = 2.0
var _screen := Vector2(256, 192)
var _world_size := Vector2(8192, 4608)
var _spawn := Vector2.ZERO
var _cam_still := 0.0
var _bookcases: Array[Rect2] = []
var _ink_material: ShaderMaterial = null


func _ready() -> void:
	_load_original_world()
	_add_entities()
	_add_letterbox()
	if player:
		# Mosaic is SCALE× original pixels; S2 sprites are already 48×56.
		# Scene-file Player.position is a placeholder; spawn comes from JSON.
		player.scale = Vector2(_scale, _scale)
		player.spawn_point = _spawn
		player.global_position = _spawn
		player.z_index = 8
	_setup_ink_outline()
	camera.position_smoothing_enabled = false
	camera.make_current()
	_update_camera(0.0, true)
	_connect_punch_areas()
	if not EventBus.player_died.is_connected(_on_player_died):
		EventBus.player_died.connect(_on_player_died)
	_start_demo_if_requested()


func _process(delta: float) -> void:
	_update_camera(delta, false)
	_update_ink_outline()
	if player and player.global_position.y > _world_size.y * _scale + 64.0:
		if not player.is_dead:
			player.take_damage(player.energy)


func _load_original_world() -> void:
	var data := _load_json(COLLISION_PATH)
	if data.is_empty():
		push_error("Missing %s — run tools/saboteur_rip/build_s2_world.py" % COLLISION_PATH)
		return
	_scale = float(data.get("scale", 2))
	var scr: Array = data.get("screen", [256, 192])
	_screen = Vector2(float(scr[0]), float(scr[1]))
	var sz: Array = data.get("size", [8192, 4608])
	_world_size = Vector2(float(sz[0]), float(sz[1]))
	# Spawn is not in this file — s2_entities.json is the source of truth.

	_add_map_layers()

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


func _add_map_layers() -> void:
	var tiles := _load_json(TILES_PATH)
	if tiles.is_empty():
		return
	_fill_visual_layer(visual_layer, WORLD_TILESET_PATH, tiles, tiles.get("world", {}), -20)
	_fill_visual_layer(fg_layer, FG_TILESET_PATH, tiles, tiles.get("fg", {}), 12)


func _fill_visual_layer(
	layer: TileMapLayer, tileset_path: String, tiles: Dictionary, spec: Dictionary, z: int
) -> void:
	if layer == null:
		push_error("Missing TileMapLayer for %s" % tileset_path)
		return
	if spec.is_empty():
		push_error("Missing tile layer data for %s" % tileset_path)
		return
	if not ResourceLoader.exists(tileset_path):
		push_error("Missing tileset %s" % tileset_path)
		return
	var tileset := load(tileset_path) as TileSet
	if tileset == null:
		push_error("Could not load tileset %s" % tileset_path)
		return
	# Visual layer only — passability stays in s2_collision.json. Identical
	# pictures can still collide differently (fill_cave_earth, thicken_floors).
	layer.tile_set = tileset
	layer.collision_enabled = false
	layer.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	layer.scale = Vector2(_scale, _scale)
	layer.z_index = z
	var src := tileset.get_source(0) as TileSetAtlasSource
	if src:
		src.use_texture_padding = true
		src.texture_region_size = Vector2i(int(tiles.get("cell", 8)), int(tiles.get("cell", 8)))
		_ensure_atlas_tiles(src, spec)
	layer.tile_map_data = _rle_to_tile_map_data(spec, int(tiles["grid"][0]))


func _rle_to_tile_map_data(spec: Dictionary, cw: int) -> PackedByteArray:
	# Godot 4.6 TileMapLayer.tile_map_data: uint16 format, then 12-byte cells
	# (int16 x, int16 y, uint16 source, int16 atlas_x, int16 atlas_y, uint16 alt).
	var atlas_cols := int(spec["atlas_tiles"][0])
	var empty_var: Variant = spec.get("empty", null)
	var has_empty := empty_var != null
	var empty_id := int(empty_var) if has_empty else -1
	var rle: Array = spec["rle"]
	var used := 0
	var i := 0
	var rle_n: int = rle.size()
	while i < rle_n:
		var tid := int(rle[i])
		var count := int(rle[i + 1])
		i += 2
		if not (has_empty and tid == empty_id):
			used += count
	var data := PackedByteArray()
	data.resize(2 + used * 12)
	data.encode_u16(0, 0)
	var off := 2
	var cell_i := 0
	i = 0
	while i < rle_n:
		var tid := int(rle[i])
		var count := int(rle[i + 1])
		i += 2
		if has_empty and tid == empty_id:
			cell_i += count
			continue
		var ax := tid % atlas_cols
		var ay: int = tid / atlas_cols
		for _n in count:
			data.encode_s16(off, cell_i % cw)
			data.encode_s16(off + 2, cell_i / cw)
			data.encode_u16(off + 4, 0)
			data.encode_s16(off + 6, ax)
			data.encode_s16(off + 8, ay)
			data.encode_u16(off + 10, 0)
			off += 12
			cell_i += 1
	return data


func _ensure_atlas_tiles(src: TileSetAtlasSource, spec: Dictionary) -> void:
	var cols := int(spec["atlas_tiles"][0])
	var rows := int(spec["atlas_tiles"][1])
	var n := int(spec["tile_count"])
	var i := 0
	for y in rows:
		for x in cols:
			if i >= n:
				return
			var coords := Vector2i(x, y)
			if not src.has_tile(coords):
				src.create_tile(coords)
			i += 1


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


func _png_to_world(x: float, y: float) -> Vector2:
	return Vector2(x, y) * _scale


func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("Missing %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("Could not parse %s" % path)
		return {}
	return parsed


func _xy_world(spec: Dictionary, what: String) -> Vector2:
	if not spec.has("x") or not spec.has("y"):
		push_error("s2_entities.json: %s without coordinates" % what)
		return Vector2.ZERO
	return _png_to_world(float(spec["x"]), float(spec["y"]))


func _add_entities() -> void:
	var data := _load_json(ENTITIES_PATH)
	if data.is_empty():
		push_error("Mission entities missing — cannot spawn objectives")
		return
	var sp: Variant = data.get("spawn", null)
	if typeof(sp) != TYPE_ARRAY or sp.size() < 2:
		push_error("s2_entities.json: spawn missing")
		return
	_spawn = _png_to_world(float(sp[0]), float(sp[1]))
	if data.has("fuse"):
		GameManager.bomb_fuse_time = float(data["fuse"])

	var items_root := Node2D.new()
	items_root.name = "Items"
	add_child(items_root)
	for spec in data.get("items", []):
		var item: Area2D = PICKUP_SCENE.instantiate()
		item.name = str(spec.get("id", spec.get("type", "item"))).capitalize()
		item.item_type = str(spec.get("type", "key"))
		item.required_item = str(spec.get("required", ""))
		item.scale = Vector2(_scale, _scale)
		item.position = _xy_world(spec, str(spec.get("id", "item")))
		items_root.add_child(item)

	var sab: Dictionary = data.get("sabotage", {})
	var sabotage: Area2D = SABOTAGE_SCENE.instantiate()
	sabotage.name = "SabotageTarget"
	sabotage.scale = Vector2(_scale, _scale)
	sabotage.position = _xy_world(sab, "sabotage")
	add_child(sabotage)

	var ex: Dictionary = data.get("exit", {})
	var exit_zone: Area2D = EXIT_SCENE.instantiate()
	exit_zone.name = "ExitZone"
	exit_zone.scale = Vector2(_scale, _scale)
	exit_zone.position = _xy_world(ex, "exit")
	add_child(exit_zone)

	var guards_root := Node2D.new()
	guards_root.name = "Guards"
	add_child(guards_root)
	var gi := 1
	for spec in data.get("guards", []):
		var guard: CharacterBody2D = GUARD_SCENE.instantiate()
		var gid := str(spec.get("id", str(gi)))
		guard.name = "Guard%s" % gid.capitalize()
		guard.scale = Vector2(_scale, _scale)
		# patrol is PNG pixels; AI compares against global (world) X.
		guard.patrol_distance = float(spec.get("patrol", 40)) * _scale
		# Position before add_child: guard._ready() snapshots patrol_origin.
		guard.position = _xy_world(spec, "guard %s" % gid)
		guards_root.add_child(guard)
		gi += 1


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		return
	# Pickups and the bomb are queue_free'd on collect/plant. A mid-run death
	# resets inventory, so the world must get those nodes back or the attempt
	# is unwinnable. Deferred so we are not freeing during the death signal.
	call_deferred("_reset_mission_entities")


func _reset_mission_entities() -> void:
	# Move Nina off the corpse tile before pickups come back, otherwise a dead
	# body still overlapping the restored key collects it again.
	if player:
		player.spawn_point = _spawn
		player.global_position = _spawn
		player.velocity = Vector2.ZERO
	for node_name in ["Items", "Guards", "SabotageTarget", "ExitZone"]:
		var node := get_node_or_null(node_name)
		if node == null:
			continue
		remove_child(node)
		node.free()
	_add_entities()


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
