extends GutTest
## GameSettings: saved to a temp ConfigFile here, so the player's
## user://settings.cfg must come out of this script byte for byte unchanged.

const TEMP_PATH := "user://test_settings_tmp.cfg"
const TOUCH_SCENE := preload("res://scenes/ui/touch_controls.tscn")

var _user_file_before: String = ""


func before_all() -> void:
	_user_file_before = _read(TiltSteer.CONFIG_PATH)


func before_each() -> void:
	_remove_temp()
	GameSettings.use_config_path(TEMP_PATH)
	GameSettings.load_settings()


func after_each() -> void:
	# Put tilt back while TiltSteer still saves to the temp file: flipping it
	# after the switch would rewrite the player's file.
	var user := ConfigFile.new()
	user.load(TiltSteer.CONFIG_PATH)
	TiltSteer.enabled = bool(user.get_value("controls", TiltSteer.CONFIG_KEY, false))
	GameSettings.use_config_path(TiltSteer.CONFIG_PATH)
	GameSettings.load_settings()
	_remove_temp()


func after_all() -> void:
	assert_eq(_read(TiltSteer.CONFIG_PATH), _user_file_before, "user settings file untouched")


func test_missing_file_gives_defaults() -> void:
	assert_eq(GameSettings.sfx_volume, GameSettings.DEFAULTS["sfx_volume"])
	assert_eq(GameSettings.music_volume, GameSettings.DEFAULTS["music_volume"])
	assert_eq(GameSettings.tilt_sensitivity, 1.0)
	assert_eq(GameSettings.pad_scale, 1.0)
	assert_eq(GameSettings.pad_opacity, 1.0)
	assert_false(FileAccess.file_exists(TEMP_PATH), "loading alone does not write")


func test_load_restores_every_option() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("audio", "sfx_volume", 0.3)
	cfg.set_value("audio", "music_volume", 0.5)
	cfg.set_value("controls", "tilt_steer", true)
	cfg.set_value("controls", "tilt_sensitivity", 1.5)
	cfg.set_value("controls", "pad_scale", 1.2)
	cfg.set_value("controls", "pad_opacity", 0.6)
	cfg.save(TEMP_PATH)
	GameSettings.load_settings()
	assert_almost_eq(GameSettings.sfx_volume, 0.3, 0.0001)
	assert_almost_eq(GameSettings.music_volume, 0.5, 0.0001)
	assert_true(TiltSteer.enabled, "tilt on/off comes from the shared key")
	assert_almost_eq(TiltSteer.sensitivity, 1.5, 0.0001)
	assert_almost_eq(GameSettings.pad_scale, 1.2, 0.0001)
	assert_almost_eq(GameSettings.pad_opacity, 0.6, 0.0001)
	assert_almost_eq(_bus_db(&"SFX"), linear_to_db(0.3), 0.01)
	assert_almost_eq(_bus_db(&"Music"), linear_to_db(0.5), 0.01)


func test_changing_a_value_saves_it_at_once() -> void:
	GameSettings.music_volume = 0.4
	GameSettings.pad_scale = 1.3
	var cfg := ConfigFile.new()
	assert_eq(cfg.load(TEMP_PATH), OK)
	assert_almost_eq(float(cfg.get_value("audio", "music_volume")), 0.4, 0.0001)
	assert_almost_eq(float(cfg.get_value("controls", "pad_scale")), 1.3, 0.0001)


func test_saving_keeps_keys_it_does_not_own() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("controls", "tilt_steer", true)
	cfg.set_value("other", "keep_me", 7)
	cfg.save(TEMP_PATH)
	GameSettings.sfx_volume = 0.2
	var after := ConfigFile.new()
	after.load(TEMP_PATH)
	assert_true(bool(after.get_value("controls", "tilt_steer", false)))
	assert_eq(int(after.get_value("other", "keep_me", 0)), 7)
	assert_almost_eq(float(after.get_value("audio", "sfx_volume")), 0.2, 0.0001)


func test_tilt_toggle_goes_to_the_same_file() -> void:
	GameSettings.tilt_enabled = true
	var cfg := ConfigFile.new()
	cfg.load(TEMP_PATH)
	assert_true(bool(cfg.get_value("controls", "tilt_steer", false)))
	GameSettings.tilt_enabled = false


func test_values_are_clamped() -> void:
	GameSettings.pad_scale = 5.0
	GameSettings.pad_opacity = 0.0
	GameSettings.tilt_sensitivity = 9.0
	GameSettings.sfx_volume = -1.0
	assert_eq(GameSettings.pad_scale, GameSettings.MAX_PAD_SCALE)
	assert_eq(GameSettings.pad_opacity, GameSettings.MIN_PAD_OPACITY)
	assert_eq(GameSettings.tilt_sensitivity, TiltSteer.MAX_SENSITIVITY)
	assert_eq(GameSettings.sfx_volume, 0.0)


func test_higher_sensitivity_walks_at_a_smaller_lean() -> void:
	assert_eq(TiltSteer.axis_from_tilt(1.5, 0.0, 1.0), 0.0)
	assert_eq(TiltSteer.axis_from_tilt(1.5, 0.0, 2.0), 1.0)
	assert_eq(TiltSteer.axis_from_tilt(-3.0, 0.0, 0.5), 0.0)


func test_touch_pad_follows_size_and_opacity() -> void:
	var touch: CanvasLayer = TOUCH_SCENE.instantiate()
	add_child_autofree(touch)
	GameSettings.pad_scale = 1.3
	GameSettings.pad_opacity = 0.5
	assert_almost_eq(touch.left_pad.scale.x, 1.3, 0.0001)
	assert_almost_eq(touch.right_pad.scale.y, 1.3, 0.0001)
	assert_almost_eq(touch.left_pad.modulate.a, 0.5, 0.0001)
	var pad: Control = touch.left_pad
	var rect := pad.get_global_rect()
	assert_almost_eq(rect.end.y, pad.position.y + pad.size.y, 0.5, "bottom edge stays put")
	assert_almost_eq(rect.position.x, pad.position.x, 0.5, "left edge stays put")


func _bus_db(bus: StringName) -> float:
	return AudioServer.get_bus_volume_db(AudioServer.get_bus_index(bus))


func _read(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	return FileAccess.get_file_as_string(path)


func _remove_temp() -> void:
	if FileAccess.file_exists(TEMP_PATH):
		DirAccess.remove_absolute(TEMP_PATH)
