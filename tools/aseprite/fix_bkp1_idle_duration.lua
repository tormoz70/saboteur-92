-- Repo root is two levels above this file (tools/aseprite/).
local function repo_root()
  local src = debug.getinfo(1, "S").source
  if src:sub(1, 1) == "@" then
    src = src:sub(2)
  end
  local root = src:match("^(.*)[/\\]tools[/\\]aseprite[/\\][^/\\]+$")
  if not root or root == "" then
    error("Could not resolve repo root from script path: " .. src)
  end
  return root
end

local FILE = repo_root() .. "/assets/sprites/saboteur92_player_bkp1.aseprite"
local spr = app.open(FILE)
spr.frames[1].duration = 100
spr.frames[2].duration = 80
spr.frames[3].duration = 100
spr:saveAs(FILE)
print("idle durations fixed")
