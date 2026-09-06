@tool
extends EditorPlugin

## Editor-only host for the local Godot MCP bridge.
##
## The real bridge (`res://mcp_bridge.gd`) is a developer-machine tool.
## Loading it from an EditorPlugin — never from [autoload] in project.godot —
## means a missing file cannot break a fresh clone or a game run. Editor
## plugins are not instantiated outside the editor; `export_presets.cfg`
## also excludes `addons/*` from packs. `add_autoload_singleton()` is
## intentionally not used: that call writes back into project.godot, which
## is how the autoload reappeared after fc581f2 and 6741401.
const LOCAL_BRIDGE_PATH := "res://mcp_bridge.gd"

var _bridge: Node


func _enter_tree() -> void:
	if not FileAccess.file_exists(LOCAL_BRIDGE_PATH):
		return
	var script := load(LOCAL_BRIDGE_PATH) as GDScript
	if script == null:
		return
	_bridge = script.new()
	_bridge.name = "McpBridge"
	add_child(_bridge)


func _exit_tree() -> void:
	if _bridge == null:
		return
	remove_child(_bridge)
	_bridge.queue_free()
	_bridge = null
