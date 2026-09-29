extends Node2D
## Palette, distant sky, a small pool of lamp lights and a soft light on Nina.
## F8 switches the world back to the classic ZX colours.


const WorldPalette := preload("res://scripts/world/world_palette.gd")
const LIGHT_TEX := preload("res://assets/sprites/light_disc.png")
const SKY_TEX := preload("res://assets/world/skyline.png")
const VIGNETTE := preload("res://assets/shaders/vignette.gdshader")
const WINDOWS_PATH := "res://assets/world/s2_windows.json"
const SKY_SCROLL := 0.35
# Skyline row at a window's sill: the towers stand in the frame, their foot
# in the mist.
const WINDOW_SILL := 228.0
const POOL := 8
const LAMP_REFRESH := 0.2

const LAMPS: Array[Vector2i] = [
	Vector2i(22, 2), Vector2i(18, 3), Vector2i(19, 3), Vector2i(21, 3),
	Vector2i(0, 4), Vector2i(4, 4), Vector2i(17, 4), Vector2i(23, 4),
	Vector2i(24, 4), Vector2i(26, 4), Vector2i(16, 5), Vector2i(19, 5),
	Vector2i(25, 5), Vector2i(26, 5), Vector2i(30, 5), Vector2i(8, 6),
	Vector2i(9, 6), Vector2i(10, 6), Vector2i(7, 7), Vector2i(19, 7),
	Vector2i(1, 9), Vector2i(25, 9), Vector2i(2, 10), Vector2i(11, 11),
	Vector2i(21, 11), Vector2i(23, 11), Vector2i(25, 11), Vector2i(27, 11),
	Vector2i(28, 11), Vector2i(0, 12), Vector2i(2, 12), Vector2i(29, 13),
	Vector2i(31, 13), Vector2i(2, 14), Vector2i(6, 14), Vector2i(7, 14),
	Vector2i(8, 14), Vector2i(11, 14), Vector2i(12, 14), Vector2i(13, 14),
	Vector2i(14, 14), Vector2i(16, 14), Vector2i(17, 14), Vector2i(18, 14),
	Vector2i(19, 14), Vector2i(10, 15), Vector2i(11, 15), Vector2i(10, 17),
	Vector2i(27, 18), Vector2i(2, 19), Vector2i(14, 19), Vector2i(16, 19),
	Vector2i(9, 20), Vector2i(20, 21), Vector2i(6, 22), Vector2i(6, 23),
	Vector2i(8, 23), Vector2i(9, 23), Vector2i(10, 23), Vector2i(11, 23),
	Vector2i(13, 23), Vector2i(14, 23), Vector2i(15, 23), Vector2i(16, 23),
	Vector2i(19, 23), Vector2i(22, 23), Vector2i(25, 23), Vector2i(29, 23),
	Vector2i(31, 23), Vector2i(5, 24), Vector2i(6, 24), Vector2i(7, 24),
	Vector2i(9, 24), Vector2i(10, 24), Vector2i(11, 24), Vector2i(12, 24),
	Vector2i(14, 24), Vector2i(27, 25), Vector2i(28, 25), Vector2i(29, 25),
	Vector2i(7, 27), Vector2i(15, 27), Vector2i(30, 27), Vector2i(19, 28),
	Vector2i(26, 28), Vector2i(4, 29), Vector2i(5, 29), Vector2i(6, 29),
	Vector2i(26, 29), Vector2i(27, 29), Vector2i(29, 29), Vector2i(0, 30),
	Vector2i(1, 30),
]

var _active := false
var _classic := false
var _alarm := false
var _alarm_time := 0.0
var _lamp_wait := 0.0
var _level: Node2D
var _player: Node2D
var _sky: Polygon2D
var _skyline: CanvasItem
var _sky_sprite: Sprite2D
var _window_views: Node2D
var _views: Array[Sprite2D] = []
var _modulate: CanvasModulate
var _nina_light: PointLight2D
var _pool: Array[PointLight2D] = []
var _lamps: Array[Vector2] = []
var _materials: Array[ShaderMaterial] = []

# The skyline's top and bottom rows, so the fill around the strip has no seam.
var _modern_sky := Color8(1, 15, 34)
var _classic_sky := Color8(0, 0, 206)
var _ambient := Color(0.80, 0.84, 0.90)


func setup(level: Node2D) -> void:
	_level = level
	_player = level.get_node_or_null("Player")
	_sky = level.get_node_or_null("SkyFill")
	_paint_layers(level)
	_collect_lamps(level)
	_build_sky()
	_build_lights()
	_build_vignette()
	if _sky:
		_classic_sky = _sky.color
		_sky.color = _modern_sky
	if not EventBus.alarm_raised.is_connected(_on_alarm):
		EventBus.alarm_raised.connect(_on_alarm)
	_active = true


func _process(delta: float) -> void:
	if not _active or _classic:
		return
	_alarm_time += delta
	_modulate.color = _ambient
	if _alarm:
		var pulse := 0.5 + 0.5 * sin(_alarm_time * 6.0)
		_modulate.color = _ambient.lerp(Color(0.95, 0.42, 0.40), pulse * 0.35)
	if _player and _nina_light:
		_nina_light.global_position = _player.global_position + Vector2(48, 52)
	_place_sky()
	_lamp_wait -= delta
	if _lamp_wait <= 0.0:
		_lamp_wait = LAMP_REFRESH
		_place_pool()


func _unhandled_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null or not key.pressed or key.echo or key.keycode != KEY_F8:
		return
	_set_classic(not _classic)
	get_viewport().set_input_as_handled()


func _on_alarm() -> void:
	_alarm = true


func _set_classic(classic: bool) -> void:
	_classic = classic
	for material in _materials:
		material.set_shader_parameter("enabled", 0.0 if classic else 1.0)
	if _sky:
		_sky.color = _classic_sky if classic else _modern_sky
	if _skyline:
		_skyline.visible = not classic
	if _window_views:
		_window_views.visible = not classic
	if _modulate:
		_modulate.visible = not classic
	for light in _pool:
		light.visible = not classic
	if _nina_light:
		_nina_light.visible = not classic


func _paint_layers(node: Node) -> void:
	for child in node.get_children():
		var layer := child as TileMapLayer
		if layer and layer.name != "CollisionLayer":
			var material := WorldPalette.material_for(layer.name)
			layer.material = material
			_materials.append(material)
		_paint_layers(child)


func _collect_lamps(node: Node) -> void:
	for child in node.get_children():
		var layer := child as TileMapLayer
		if layer and (layer.name == "Interior1" or layer.name == "Interior2"):
			for cell in layer.get_used_cells():
				if layer.get_cell_atlas_coords(cell) in LAMPS:
					_lamps.append(layer.to_global(layer.map_to_local(cell)))
		_collect_lamps(child)


func _build_sky() -> void:
	var parallax := Parallax2D.new()
	parallax.name = "Skyline"
	parallax.scroll_scale = Vector2(SKY_SCROLL, 1.0)
	parallax.repeat_size = Vector2(SKY_TEX.get_width(), 0)
	parallax.z_index = -30
	var sprite := Sprite2D.new()
	sprite.texture = SKY_TEX
	sprite.centered = false
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	parallax.add_child(sprite)
	_level.add_child(parallax)
	_level.move_child(parallax, 1)
	_skyline = parallax
	_sky_sprite = sprite
	_build_windows()
	_place_sky()


func _build_windows() -> void:
	# Window holes sit near the top and bottom of the screen, where the strip
	# is only stars or ground. Each gets its own slice with the city in it.
	if _level.get_node_or_null("WorldMap") == null or not FileAccess.file_exists(WINDOWS_PATH):
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(WINDOWS_PATH))
	if typeof(data) != TYPE_DICTIONARY:
		return
	var level_scale := float(_level.get("_scale"))
	_window_views = Node2D.new()
	_window_views.name = "WindowViews"
	_window_views.z_index = _skyline.z_index
	for rect in data.get("windows", []):
		var size := Vector2(float(rect[2]), float(rect[3])) * level_scale
		var view := Sprite2D.new()
		view.texture = SKY_TEX
		view.centered = false
		view.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		view.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
		view.region_enabled = true
		view.region_rect = Rect2(Vector2(0.0, maxf(0.0, WINDOW_SILL - size.y)), size)
		view.position = Vector2(float(rect[0]), float(rect[1])) * level_scale
		_window_views.add_child(view)
		_views.append(view)
	_level.add_child(_window_views)
	_level.move_child(_window_views, _skyline.get_index() + 1)


func _place_sky() -> void:
	# Distant, so it scrolls sideways but stays mid-screen vertically.
	if _sky_sprite == null:
		return
	var inv := get_canvas_transform().affine_inverse()
	var size := get_viewport_rect().size
	var top := (inv * Vector2.ZERO).y
	var bottom := (inv * Vector2(0.0, size.y)).y
	_sky_sprite.position.y = roundf((top + bottom - SKY_TEX.get_height()) * 0.5)
	var shift := (inv * (size * 0.5)).x * (1.0 - SKY_SCROLL)
	var width := float(SKY_TEX.get_width())
	for view in _views:
		var region := view.region_rect
		region.position.x = roundf(fposmod(view.position.x - shift, width))
		view.region_rect = region


func _build_lights() -> void:
	_modulate = CanvasModulate.new()
	_modulate.color = _ambient
	_level.add_child(_modulate)
	_nina_light = _make_light(Color(0.72, 0.86, 1.0), 5.0, 1.15)
	_level.add_child(_nina_light)
	for _i in POOL:
		var lamp := _make_light(Color(1.0, 0.84, 0.52), 2.8, 0.8)
		lamp.visible = false
		_level.add_child(lamp)
		_pool.append(lamp)


func _make_light(color: Color, tex_scale: float, energy: float) -> PointLight2D:
	var light := PointLight2D.new()
	light.texture = LIGHT_TEX
	light.color = color
	light.texture_scale = tex_scale
	light.energy = energy
	light.shadow_enabled = false
	return light


func _build_vignette() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Vignette"
	layer.layer = 4
	var rect := ColorRect.new()
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var material := ShaderMaterial.new()
	material.shader = VIGNETTE
	rect.material = material
	layer.add_child(rect)
	_level.add_child(layer)


func _place_pool() -> void:
	if _lamps.is_empty() or _player == null:
		return
	var origin := _player.global_position
	var best: Array[Vector2] = []
	var best_d: Array[float] = []
	for point in _lamps:
		var dist := origin.distance_squared_to(point)
		var slot := best.size()
		while slot > 0 and dist < best_d[slot - 1]:
			slot -= 1
		if slot >= POOL:
			continue
		best.insert(slot, point)
		best_d.insert(slot, dist)
		if best.size() > POOL:
			best.resize(POOL)
			best_d.resize(POOL)
	for i in POOL:
		var light := _pool[i]
		if i < best.size():
			light.global_position = best[i]
			light.visible = true
		else:
			light.visible = false
