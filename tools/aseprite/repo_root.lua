-- Returns the saboteur-92 repo root (two levels above tools/aseprite/).
-- Callers: dofile this file. debug.getinfo(1) is this script, not the caller.
local src = debug.getinfo(1, "S").source
if src:sub(1, 1) == "@" then
  src = src:sub(2)
end
local root = src:match("^(.*)[/\\]tools[/\\]aseprite[/\\][^/\\]+$")
if not root or root == "" then
  error("Could not resolve repo root from script path: " .. src)
end
return root
