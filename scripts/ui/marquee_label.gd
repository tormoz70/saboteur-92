extends Control
## One-line ticker. Text that fits stays put; a longer line scrolls.


const SPEED := 34.0
const GAP := 48.0
const HOLD := 1.1

var text: String = "":
	set(value):
		if text == value:
			return
		text = value
		_offset = 0.0
		_hold = HOLD
		visible = not text.is_empty()
		_measure()
		queue_redraw()

var _offset: float = 0.0
var _hold: float = HOLD
var _text_width: float = 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip_contents = true
	resized.connect(queue_redraw)
	_measure()


func _process(delta: float) -> void:
	if text.is_empty() or _text_width <= size.x + 1.0:
		return
	if _hold > 0.0:
		_hold -= delta
		return
	_offset += SPEED * delta
	if _offset >= _text_width + GAP:
		_offset = 0.0
		_hold = HOLD
	queue_redraw()


func _measure() -> void:
	var font := _font()
	if font == null or text.is_empty():
		_text_width = 0.0
		return
	_text_width = font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, _font_size()).x


func _draw() -> void:
	if text.is_empty():
		return
	var font := _font()
	if font == null:
		return
	var font_size := _font_size()
	var baseline := font.get_ascent(font_size)
	baseline += maxf(0.0, (size.y - font.get_height(font_size)) * 0.5)
	var color := Color(0.75, 0.88, 0.94, 1)
	var origin := Vector2(0.0, baseline)
	if _text_width > size.x + 1.0:
		origin.x = -_offset
	_draw_line(font, origin, font_size, color)
	var repeat_x := -_offset + _text_width + GAP
	if _text_width > size.x + 1.0 and repeat_x < size.x:
		_draw_line(font, Vector2(repeat_x, baseline), font_size, color)


func _draw_line(font: Font, origin: Vector2, font_size: int, color: Color) -> void:
	draw_string(
		font, origin, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color
	)


func _font() -> Font:
	return get_theme_default_font()


func _font_size() -> int:
	return 15
