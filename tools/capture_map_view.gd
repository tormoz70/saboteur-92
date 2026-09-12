extends SceneTree
## Headless/windowed capture of the playfield at known camera points.
##
## Usage:
##   DISPLAY=:99 godot --path . -s tools/capture_map_view.gd -- /tmp/out_dir
##
## Hides HUD, touch, player, items and guards so the TileMap can be
## compared pixel-for-pixel with the mosaic / layer composite.

const POINTS := [
	{"name": "spawn", "pos": Vector2(4528, 1200)},
	{"name": "rooftop", "pos": Vector2(2560, 288)},
	{"name": "interior", "pos": Vector2(6400, 2432)},
	{"name": "cave", "pos": Vector2(1200, 3648)},
]

var _frames: int = 0
var _out_dir: String = "/tmp/map_views"
var _idx: int = -1
var _level: Node2D
var _camera: Camera2D


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0 and not args[0].is_empty():
		_out_dir = args[0]
	DirAccess.make_dir_recursive_absolute(_out_dir)
	change_scene_to_file("res://scenes/main.tscn")


func _process(_dt: float) -> bool:
	_frames += 1
	if _frames == 8:
		_prepare_scene()
		return false
	if _level == null:
		if _frames > 120:
			push_error("capture_map_view: main scene did not load")
			quit()
		return false
	# One settle frame after each camera move, then grab.
	if _frames % 4 == 0 and _idx < POINTS.size():
		_grab_current()
		_idx += 1
		if _idx >= POINTS.size():
			print("capture_map_view: wrote %d shots to %s" % [POINTS.size(), _out_dir])
			quit()
			return false
		_camera.global_position = POINTS[_idx]["pos"]
		_camera.reset_physics_interpolation()
	return false


func _prepare_scene() -> void:
	var main := root.get_child(root.get_child_count() - 1)
	_level = main.get_node_or_null("Level01") as Node2D
	if _level == null:
		push_error("capture_map_view: Level01 missing")
		quit()
		return
	_camera = _level.get_node("Camera2D") as Camera2D
	_hide(_level.get_node_or_null("Player"))
	_hide(_level.get_node_or_null("Artifacts"))
	_hide(_level.get_node_or_null("ActorsLayer"))
	_hide(_level.get_node_or_null("Items"))
	_hide(_level.get_node_or_null("Guards"))
	_hide(_level.get_node_or_null("SabotageTarget"))
	_hide(_level.get_node_or_null("ExitZone"))
	_hide(main.get_node_or_null("HUD"))
	_hide(main.get_node_or_null("TouchControls"))
	_hide(_level.get_node_or_null("Letterbox"))
	# Stop the follow-cam so later viewpoints are not pulled back to spawn.
	_level.set_process(false)
	_level.set_physics_process(false)
	# Honour POINTS exactly — map limits would clamp rooftop/cave into sky.
	_camera.limit_smoothed = false
	_camera.position_smoothing_enabled = false
	_camera.limit_left = -100000
	_camera.limit_top = -100000
	_camera.limit_right = 100000
	_camera.limit_bottom = 100000
	# Integer 2× mosaic pixels when the user arg is "2x":
	# tile 8 × layer scale 2 × zoom 1. Game zoom (1.875) is the default.
	var integer_2x := _out_dir.ends_with("2x") or _out_dir.contains("2x")
	if integer_2x:
		_camera.zoom = Vector2.ONE
	if _out_dir.contains("collision"):
		var overlay := _level.get_node_or_null("CollisionLayer") as TileMapLayer
		if overlay:
			overlay.visible = true
			overlay.modulate = Color(1, 1, 1, 0.7)
	_idx = 0
	_camera.global_position = POINTS[_idx]["pos"]
	_camera.reset_physics_interpolation()


func _hide(node: Node) -> void:
	if node == null:
		return
	if node is CanvasLayer:
		(node as CanvasLayer).visible = false
	elif node is CanvasItem:
		(node as CanvasItem).visible = false
	node.process_mode = Node.PROCESS_MODE_DISABLED


func _grab_current() -> void:
	var img: Image = root.get_viewport().get_texture().get_image()
	var path := "%s/%s.png" % [_out_dir, String(POINTS[_idx]["name"])]
	img.save_png(path)
	print("capture_map_view: %s %dx%d" % [path, img.get_width(), img.get_height()])
