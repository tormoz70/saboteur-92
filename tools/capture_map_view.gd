extends SceneTree
## Headless/windowed capture of the playfield at known camera points.
##
## Usage:
##   DISPLAY=:99 godot --path . -s tools/capture_map_view.gd -- /tmp/out_dir
##
## Hides HUD, touch controls and the player so the map itself can be
## compared pixel-for-pixel before and after the TileMapLayer conversion.

const POINTS := [
	{"name": "spawn", "pos": Vector2(4528, 1640)},
	{"name": "rooftop", "pos": Vector2(2560, 384)},
	{"name": "interior", "pos": Vector2(6400, 3200)},
	{"name": "cave", "pos": Vector2(1200, 4800)},
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
	_hide(main.get_node_or_null("HUD"))
	_hide(main.get_node_or_null("TouchControls"))
	_hide(_level.get_node_or_null("Player"))
	_hide(_level.get_node_or_null("Letterbox"))
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
