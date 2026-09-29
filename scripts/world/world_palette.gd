extends RefCounted
## Per-layer stand-ins for the ZX ink colours sampled from the tileset PNGs.


const SHADER := preload("res://assets/shaders/palette_remap.gdshader")

const SOURCES: Array[Color] = [
	Color8(0, 0, 0),
	Color8(0, 0, 206),
	Color8(0, 0, 255),
	Color8(255, 0, 0),
	Color8(255, 0, 255),
	Color8(0, 251, 0),
	Color8(0, 251, 255),
	Color8(255, 251, 0),
	Color8(206, 203, 0),
	Color8(255, 251, 255),
	Color8(255, 255, 255),
	Color8(206, 203, 206),
]

const _INK := Color(0.07, 0.08, 0.11)
const _NAVY := Color(0.16, 0.28, 0.40)
const _TEAL := Color(0.20, 0.42, 0.42)
const _BRICK := Color(0.48, 0.32, 0.28)
const _MAGENTA := Color(0.40, 0.26, 0.36)
const _CYAN := Color(0.38, 0.64, 0.68)
const _LAMP := Color(0.78, 0.62, 0.30)
const _DIM_LAMP := Color(0.55, 0.44, 0.22)
const _PAPER := Color(0.78, 0.80, 0.84)
const _WHITE := Color(0.90, 0.91, 0.93)
const _GREY := Color(0.42, 0.45, 0.50)


static func material_for(layer_name: String) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = SHADER
	var targets := _targets(layer_name)
	for i in SOURCES.size():
		material.set_shader_parameter("s%d" % i, SOURCES[i])
		material.set_shader_parameter("d%d" % i, targets[i])
	material.set_shader_parameter("enabled", 1.0)
	return material


static func _targets(layer_name: String) -> Array[Color]:
	match layer_name:
		"Earth":
			return _row(Color(0.11, 0.10, 0.09), _NAVY, _BRICK)
		"Structure":
			return _row(Color(0.09, 0.10, 0.13), _NAVY, _BRICK)
		"Wallpaper":
			return _row(_INK, Color(0.18, 0.30, 0.42), _BRICK)
		"Mosaic":
			return _row(_INK, _NAVY, _BRICK, _TEAL)
		"Foreground":
			return _row(Color(0.10, 0.11, 0.14), _NAVY, Color(0.55, 0.36, 0.28))
		_:
			return _row(_INK, _NAVY, _BRICK)


static func _row(
	ink: Color,
	navy: Color,
	brick: Color,
	green: Color = _TEAL,
) -> Array[Color]:
	return [
		ink,
		navy,
		navy,
		brick,
		_MAGENTA,
		green,
		_CYAN,
		_LAMP,
		_DIM_LAMP,
		_PAPER,
		_WHITE,
		_GREY,
	]
