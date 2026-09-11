class_name WorldObject
extends Node2D

## One placed world object. Visual comes from the type sprite; instance
## size can tile a module (ladders, fills) or show a prefab as-is.

var type_id: String = ""
var layer_name: String = ""
var collision_kind: String = "none"


func setup(inst: Dictionary, type_def: Dictionary, world_scale: float) -> void:
	type_id = str(inst.get("type", ""))
	layer_name = str(type_def.get("layer", "interior"))
	collision_kind = str(type_def.get("collision", "none"))
	position = Vector2(float(inst.get("x", 0)), float(inst.get("y", 0))) * world_scale
	z_as_relative = false
	z_index = int(type_def.get("z", 0))
	var path := str(type_def.get("sprite", ""))
	if path == "" or not ResourceLoader.exists(path):
		return
	var tex := load(path) as Texture2D
	if tex == null:
		return
	var iw := float(inst.get("w", 8))
	var ih := float(inst.get("h", 8))
	if iw <= 0.0:
		iw = 8.0
	if ih <= 0.0:
		ih = 8.0
	var sprite := Sprite2D.new()
	sprite.centered = false
	sprite.texture = tex
	sprite.texture_filter = TEXTURE_FILTER_NEAREST
	sprite.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	var mode := str(type_def.get("mode", "prefab"))
	if mode == "module_repeat":
		sprite.region_enabled = true
		sprite.region_rect = Rect2(0, 0, iw, ih)
		sprite.scale = Vector2(world_scale, world_scale)
	else:
		sprite.scale = Vector2(world_scale, world_scale)
		if tex.get_width() > 0 and tex.get_height() > 0:
			sprite.scale.x = (iw * world_scale) / float(tex.get_width())
			sprite.scale.y = (ih * world_scale) / float(tex.get_height())
	add_child(sprite)
