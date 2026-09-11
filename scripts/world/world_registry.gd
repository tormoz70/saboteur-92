class_name WorldRegistry
extends Object

## Loads s2_objects.json (types + instances) produced by decompose_world.py.


static func load_catalog(path: String = "res://assets/world/s2_objects.json") -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("Missing object registry %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("Could not parse %s" % path)
		return {}
	return parsed


static func types_of(catalog: Dictionary) -> Dictionary:
	return catalog.get("types", {}) as Dictionary


static func instances_of(catalog: Dictionary) -> Array:
	return catalog.get("instances", []) as Array
