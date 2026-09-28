extends RefCounted
## Rounded glass style for the on-screen buttons that are real Buttons.


static func apply(button: BaseButton) -> void:
	button.theme = null
	button.add_theme_stylebox_override("normal", _box(false))
	button.add_theme_stylebox_override("hover", _box(false))
	button.add_theme_stylebox_override("pressed", _box(true))
	button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	button.add_theme_color_override("font_color", Color(1, 1, 1, 0.92))
	button.add_theme_color_override("font_pressed_color", Color(1, 1, 1, 1))
	button.add_theme_font_size_override("font_size", 18)


static func _box(pressed: bool) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0.45, 0.82, 1.0, 0.38) if pressed else Color(0.06, 0.08, 0.12, 0.62)
	box.border_color = Color(1, 1, 1, 0.4)
	box.set_border_width_all(2)
	box.set_corner_radius_all(18)
	box.content_margin_left = 8.0
	box.content_margin_right = 8.0
	box.content_margin_top = 4.0
	box.content_margin_bottom = 4.0
	return box
