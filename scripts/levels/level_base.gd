class_name LevelBase
extends Node2D

## Shared level runtime: camera, spawn, physics (ladders), entities, ink
## outline, debug layer toggles. A level provides tile layers either by
## instancing world chunks (override `_setup_layers`, see level_01.gd) or by
## drawing TileMapLayer nodes directly in its own scene (see level_template).

const WorldLayers := preload("res://scripts/world/world_layers.gd")

const LIFT_TEX_PATH := "res://assets/world/s2_lift.png"
const INK_SHADER_PATH := "res://assets/shaders/zx_ink_outline.gdshader"
const PICKUP_SCENE := preload("res://scenes/items/pickup.tscn")
const GUARD_SCENE := preload("res://scenes/enemies/guard.tscn")
const SABOTAGE_SCENE := preload("res://scenes/items/sabotage_target.tscn")
const EXIT_SCENE := preload("res://scenes/items/exit_zone.tscn")
const MARKER_SCRIPT := preload("res://scripts/world/mission_marker.gd")
const PASSAGE_SCRIPT := preload("res://scripts/world/bookcase_passage.gd")
const INTERLOCK_SCRIPT := preload("res://scripts/world/interlock_zone.gd")
# Side bars used to hide extra camera width at 16:9. They ate the space the
# touch pad needs and hid playable map; the camera now uses that width.
const LETTERBOX_PX := 0.0
# Camera stays put while Nina is more than this fraction of the playfield away
# from any edge. Crossing that band pushes the view; standing still recenters.
const CAMERA_EDGE_FRACTION := 1.0 / 3.0
const CAMERA_CATCHUP := 3.2
const CAMERA_STILL_DELAY := 0.12

@export var level_scale := 2.0
@export var screen_size := Vector2(256, 192)
@export var world_size := Vector2(2048, 1152)
@export var sky_color := Color(0.0, 0.0, 0.808)

var _scale: float = 2.0
var _screen := Vector2(256, 192)
var _world_size := Vector2(8192, 4608)
var _spawn := Vector2.ZERO
var _cam_still := 0.0
var _bookcases: Array[Rect2] = []
var _ink_material: ShaderMaterial = null
var _alarm_guard_spawned := false
var _map_layers: Dictionary = {}

@onready var player: CharacterBody2D = $Player
@onready var camera: Camera2D = $Camera2D
@onready var world: Node2D = $World
@onready var sky_fill: Polygon2D = $SkyFill
@onready var artifacts_layer: Node2D = $Artifacts
@onready var machines_layer: Node2D = $Machines
@onready var actors_layer: Node2D = $ActorsLayer


func _ready() -> void:
	_setup_world()
	_add_entities()
	_add_letterbox()
	if player:
		# Mosaic is SCALE× original pixels; S2 sprites are already 48×56.
		# Scene-file Player.position is a placeholder; spawn comes from data.
		player.scale = Vector2(_scale, _scale)
		player.spawn_point = _spawn
		player.global_position = _spawn
		player.z_index = WorldLayers.Z_ACTORS
	_setup_ink_outline()
	camera.position_smoothing_enabled = false
	camera.make_current()
	_update_camera(0.0, true)
	_connect_punch_areas()
	if not EventBus.player_died.is_connected(_on_player_died):
		EventBus.player_died.connect(_on_player_died)
	if not EventBus.alarm_raised.is_connected(_on_alarm_raised):
		EventBus.alarm_raised.connect(_on_alarm_raised)
	_start_demo_if_requested()


func _process(delta: float) -> void:
	_update_camera(delta, false)
	_update_ink_outline()
	if player and player.global_position.y > _world_size.y * _scale + 64.0:
		if not player.is_dead:
			player.take_damage(player.energy)


## Path to the mission entities JSON. Empty means a free-form level that only
## uses its in-scene SpawnPoint marker.
func _entities_path() -> String:
	return ""


## Path to the collision extras JSON (bookcases, lifts). Empty means none.
func _collision_data_path() -> String:
	return ""


## Populate `_map_layers`, `_scale`, `_screen`, `_world_size` and the sky fill.
## Base implementation registers the TileMapLayer nodes drawn in this scene.
func _setup_layers() -> bool:
	_scale = level_scale
	_screen = screen_size
	_world_size = world_size
	_setup_sky_fill({"sky_color": [sky_color.r8, sky_color.g8, sky_color.b8]})
	_map_layers.clear()
	for child in get_children():
		if child is TileMapLayer:
			_register_layer(child)
	if sky_fill:
		_map_layers["sky"] = sky_fill
	_map_layers["artifacts"] = artifacts_layer
	_map_layers["machines"] = machines_layer
	_map_layers["actors"] = actors_layer
	return true


## TileMapLayer + world-offset pairs that carry collision/ladder tiles. Base
## implementation uses the in-scene CollisionLayer; chunked levels override.
func _collision_sources() -> Array:
	var sources: Array = []
	var collision := get_node_or_null("CollisionLayer") as TileMapLayer
	if collision:
		sources.append([collision, Vector2.ZERO])
	return sources


func _setup_world() -> void:
	if not _setup_layers():
		push_error("Level %s has no tile layers set up" % name)
		return

	var data := _load_json(_collision_data_path(), false)
	if not data.is_empty():
		var scr: Array = data.get("screen", [_screen.x, _screen.y])
		_screen = Vector2(float(scr[0]), float(scr[1]))

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

	_build_ladder_areas()

	_add_lifts(data)

	var world_px := _world_size * _scale
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = int(world_px.x)
	camera.limit_bottom = int(world_px.y)
	camera.limit_smoothed = true
	camera.position_smoothing_enabled = false
	_apply_camera_zoom()
	var vp := get_viewport()
	if vp and not vp.size_changed.is_connected(_on_viewport_size_changed):
		vp.size_changed.connect(_on_viewport_size_changed)


func _setup_sky_fill(tiles: Dictionary) -> void:
	if sky_fill == null:
		return
	var col: Array = tiles.get("sky_color", [0, 0, 206])
	sky_fill.color = Color8(int(col[0]), int(col[1]), int(col[2]))
	var world_px := _world_size * _scale
	sky_fill.polygon = PackedVector2Array(
		[Vector2.ZERO, Vector2(world_px.x, 0.0), world_px, Vector2(0.0, world_px.y)]
	)
	sky_fill.z_index = WorldLayers.Z_SKY - 1


func _register_layer(layer: TileMapLayer) -> void:
	var key := _layer_key(layer.name)
	if key == "":
		return
	if not _map_layers.has(key):
		_map_layers[key] = []
	_map_layers[key].append(layer)


func _layer_key(node_name: String) -> String:
	match node_name:
		"Earth":
			return "earth"
		"Structure":
			return "structure"
		"Wallpaper":
			return "wallpaper"
		"Mosaic":
			return "mosaic"
		"Interior":
			return "interior"
		"Foreground":
			return "fg"
		"CollisionLayer":
			return "collision"
	return ""


func _build_ladder_areas() -> void:
	var ladders := Node2D.new()
	ladders.name = "Ladders"
	world.add_child(ladders)
	for source in _collision_sources():
		var layer: TileMapLayer = source[0]
		var offset: Vector2 = source[1]
		for rect in TileMapUtils.find_ladders(layer):
			var area := Area2D.new()
			area.collision_layer = CollisionLayers.LAYER_TRIGGERS
			area.collision_mask = 0
			area.monitorable = true
			area.monitoring = false
			var col := CollisionShape2D.new()
			var shape := RectangleShape2D.new()
			var size := Vector2(float(rect[2]), float(rect[3])) * _scale
			shape.size = size
			col.shape = shape
			var origin := (offset + Vector2(float(rect[0]), float(rect[1]))) * _scale
			col.position = origin + size * 0.5
			area.add_child(col)
			ladders.add_child(area)


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
		lift.z_index = WorldLayers.Z_MACHINES
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


func _load_json(path: String, required: bool = true) -> Dictionary:
	if path == "" or not FileAccess.file_exists(path):
		if required:
			push_error("Missing %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("Could not parse %s" % path)
		return {}
	return parsed


func _xy_world(spec: Dictionary, what: String) -> Vector2:
	if not spec.has("x") or not spec.has("y"):
		push_error("entities: %s without coordinates" % what)
		return Vector2.ZERO
	return _png_to_world(float(spec["x"]), float(spec["y"]))


func _add_entities() -> void:
	var spawn_mark := get_node_or_null("Entities/SpawnPoint") as Marker2D
	var path := _entities_path()
	if path == "":
		# Free-form level: spawn comes from the in-scene marker only.
		if spawn_mark:
			_spawn = spawn_mark.position
		return

	var data := _load_json(path)
	if data.is_empty():
		push_error("Mission entities missing — cannot spawn objectives")
		return
	var sp: Variant = data.get("spawn", null)
	if typeof(sp) != TYPE_ARRAY or sp.size() < 2:
		push_error("entities: spawn missing")
		return
	_spawn = _png_to_world(float(sp[0]), float(sp[1]))
	if spawn_mark == null:
		var entities := get_node_or_null("Entities")
		if entities == null:
			entities = Node2D.new()
			entities.name = "Entities"
			add_child(entities)
		spawn_mark = Marker2D.new()
		spawn_mark.name = "SpawnPoint"
		entities.add_child(spawn_mark)
	spawn_mark.position = _spawn
	if data.has("fuse"):
		GameManager.bomb_fuse_time = float(data["fuse"])

	var items_root := Node2D.new()
	items_root.name = "Items"
	items_root.z_index = WorldLayers.Z_ARTIFACTS
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
	sabotage.z_index = WorldLayers.Z_ARTIFACTS
	sabotage.position = _xy_world(sab, "sabotage")
	add_child(sabotage)

	var ex: Dictionary = data.get("exit", {})
	var exit_zone: Area2D = EXIT_SCENE.instantiate()
	exit_zone.name = "ExitZone"
	exit_zone.scale = Vector2(_scale, _scale)
	exit_zone.z_index = WorldLayers.Z_ARTIFACTS
	exit_zone.position = _xy_world(ex, "exit")
	add_child(exit_zone)

	var guards_root := Node2D.new()
	guards_root.name = "Guards"
	guards_root.z_index = WorldLayers.Z_ACTORS
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
		guard.z_index = WorldLayers.Z_ACTORS
		guards_root.add_child(guard)
		gi += 1

	_add_markers(data)
	_add_passages(data)
	_add_interlock(data)
	_configure_locked_lift(data)


func _add_markers(data: Dictionary) -> void:
	var markers: Array = data.get("markers", [])
	if markers.is_empty():
		return
	var root := Node2D.new()
	root.name = "MissionMarkers"
	add_child(root)
	for spec in markers:
		var area := Area2D.new()
		area.set_script(MARKER_SCRIPT)
		area.name = "Marker_%s" % str(spec.get("id", spec.get("label", "code")))
		area.label = str(spec.get("label", ""))
		area.position = _xy_world(spec, "marker")
		var col := CollisionShape2D.new()
		var shape := CircleShape2D.new()
		shape.radius = 28.0
		col.shape = shape
		area.add_child(col)
		root.add_child(area)


func _add_passages(data: Dictionary) -> void:
	var passages: Array = data.get("passages", [])
	if passages.is_empty():
		return
	var root := Node2D.new()
	root.name = "Passages"
	add_child(root)
	for spec in passages:
		var area := Area2D.new()
		area.set_script(PASSAGE_SCRIPT)
		area.name = "Passage_%s" % str(spec.get("id", "shelf"))
		area.position = _xy_world(spec, "passage")
		area.dest_x = float(spec.get("to_x", spec["x"])) * _scale
		area.dest_y = float(spec.get("to_y", spec["y"])) * _scale
		area.need_crouch = bool(spec.get("need_crouch", true))
		var col := CollisionShape2D.new()
		var shape := RectangleShape2D.new()
		shape.size = Vector2(48.0, 40.0) * _scale
		col.shape = shape
		col.position = shape.size * 0.5
		area.add_child(col)
		root.add_child(area)


func _add_interlock(data: Dictionary) -> void:
	var spec: Variant = data.get("interlock", null)
	if typeof(spec) != TYPE_DICTIONARY or spec.is_empty():
		return
	var area := Area2D.new()
	area.set_script(INTERLOCK_SCRIPT)
	area.name = "InterlockZone"
	area.position = _xy_world(spec, "interlock")
	var col := CollisionShape2D.new()
	var shape := CircleShape2D.new()
	shape.radius = 32.0
	col.shape = shape
	area.add_child(col)
	add_child(area)


func _configure_locked_lift(data: Dictionary) -> void:
	var lock: Variant = data.get("locked_lift", null)
	if typeof(lock) != TYPE_DICTIONARY or lock.is_empty():
		return
	var lifts := world.get_node_or_null("Lifts")
	if lifts == null:
		return
	var lx := float(lock.get("x", -1.0)) * _scale
	var ly := float(lock.get("y", -1.0)) * _scale
	for child in lifts.get_children():
		if not child.has_method("start_ride"):
			continue
		var pos: Vector2 = child.global_position
		if absf(pos.x - lx) <= 4.0 and absf(pos.y - ly) <= 4.0:
			child.requires_lift_code = true
			return


func _on_alarm_raised() -> void:
	if _alarm_guard_spawned:
		return
	var path := _entities_path()
	if path == "":
		return
	var data := _load_json(path)
	var spec: Variant = data.get("alarm_guard", null)
	if typeof(spec) != TYPE_DICTIONARY or spec.is_empty():
		return
	var guards := get_node_or_null("Guards")
	if guards == null:
		guards = Node2D.new()
		guards.name = "Guards"
		add_child(guards)
	var guard: CharacterBody2D = GUARD_SCENE.instantiate()
	guard.name = "GuardAlarm"
	guard.scale = Vector2(_scale, _scale)
	guard.patrol_distance = float(spec.get("patrol", 40)) * _scale
	guard.position = _xy_world(spec, "alarm guard")
	guards.add_child(guard)
	_alarm_guard_spawned = true


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		return
	# Pickups and the bomb are queue_free'd on collect/plant. A mid-run death
	# resets inventory, so the world must get those nodes back or the attempt
	# is unwinnable. Deferred so we are not freeing during the death signal.
	call_deferred("_reset_mission_entities")


func _reset_mission_entities() -> void:
	_alarm_guard_spawned = false
	# Move Nina off the corpse tile before pickups come back, otherwise a dead
	# body still overlapping the restored key collects it again.
	if player:
		player.spawn_point = _spawn
		player.global_position = _spawn
		player.velocity = Vector2.ZERO
	for node_name in [
		"Items",
		"Guards",
		"SabotageTarget",
		"ExitZone",
		"MissionMarkers",
		"Passages",
		"InterlockZone",
	]:
		var node := get_node_or_null(node_name)
		if node == null:
			continue
		remove_child(node)
		node.free()
	_add_entities()


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
		return absf(player.get_climb_axis()) > 0.1
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


func _playfield_zoom() -> float:
	var height := 720.0
	var vp := get_viewport()
	if vp:
		var visible := vp.get_visible_rect().size.y
		if visible >= 1.0:
			height = visible
	return height / (_screen.y * _scale)


func _apply_camera_zoom() -> void:
	var z := _playfield_zoom()
	camera.zoom = Vector2(z, z)


func _on_viewport_size_changed() -> void:
	_apply_camera_zoom()


func _add_letterbox() -> void:
	if LETTERBOX_PX <= 0.0:
		return
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
	var args := OS.get_cmdline_user_args()
	if args.has("--demo") or args.has("--demo-fuse"):
		_add_probe("MissionDemo", "res://scripts/demo/mission_demo.gd")
	if args.has("--demo-tilt"):
		_add_probe("TiltDemo", "res://scripts/demo/tilt_demo.gd")
	if args.has("--demo-maze"):
		_add_probe("MazeDebug", "res://scripts/demo/maze_debug.gd")


func _add_probe(probe_name: String, script_path: String) -> void:
	var probe := Node.new()
	probe.name = probe_name
	probe.set_script(load(script_path))
	add_child(probe)


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


func _unhandled_input(event: InputEvent) -> void:
	# Debug: digit keys 0–9 toggle object layers (sky … collision).
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var layer_name := ""
	match event.keycode:
		KEY_0:
			layer_name = "sky"
		KEY_1:
			layer_name = "earth"
		KEY_2:
			layer_name = "structure"
		KEY_3:
			layer_name = "wallpaper"
		KEY_4:
			layer_name = "mosaic"
		KEY_5:
			layer_name = "machines"
		KEY_6:
			layer_name = "actors"
		KEY_7:
			layer_name = "fg"
		KEY_8:
			layer_name = "fg"
		KEY_9:
			layer_name = "collision"
		_:
			return
	var entry: Variant = _map_layers.get(layer_name)
	if entry is Array:
		for layer in entry:
			layer.visible = not layer.visible
	elif entry is Node2D:
		entry.visible = not entry.visible
