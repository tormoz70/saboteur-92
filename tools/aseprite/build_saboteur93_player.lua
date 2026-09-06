-- Build saboteur93_player.aseprite + PNG from saboteur85_player.png via Aseprite.
-- Animations: idle×2, run×4, punch×2, jump_kick×2, climb×2, crouch×2
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

local ROOT = repo_root()
local SRC85 = ROOT .. "/assets/sprites/saboteur85_player.png"
local SIT = ROOT .. "/assets/reference/original/ripped/ninja_sitting.png"
local OUT_ASE = ROOT .. "/assets/sprites/saboteur93_player.aseprite"
local OUT_PNG = ROOT .. "/assets/sprites/saboteur93_player.png"

local FW, FH = 48, 56

local function load_image(path)
  if not app.fs.isFile(path) then
    return nil
  end
  return Image{ fromFile = path }
end

local function resize_nearest(img, w, h)
  if img.width == w and img.height == h then
    return img
  end
  local out = Image(w, h, img.colorMode)
  out:drawImage(img, Point(0, 0), 0, 0, img.width, img.height, w, h)
  return out
end

local function blit_slice(dst, src, srcFrame, dy)
  local sx = srcFrame * FW
  for y = 0, FH - 1 do
    local sy = y - (dy or 0)
    if sy >= 0 and sy < FH then
      for x = 0, FW - 1 do
        local p = src:getPixel(sx + x, sy)
        if app.pixelColor.rgbaA(p) > 0 then
          dst:putPixel(x, y, p)
        end
      end
    end
  end
end

local function blit_full(dst, src, dy)
  for y = 0, FH - 1 do
    local sy = y - (dy or 0)
    if sy >= 0 and sy < FH then
      for x = 0, FW - 1 do
        local p = src:getPixel(x, sy)
        if app.pixelColor.rgbaA(p) > 0 then
          dst:putPixel(x, y, p)
        end
      end
    end
  end
end

-- { type = "slice", frame, dy } | { type = "image", dy }
local FRAME_SPECS = {
  { "slice", 0, 0 }, { "slice", 0, 1 },
  { "slice", 2, 0 }, { "slice", 3, 0 }, { "slice", 4, 0 }, { "slice", 5, 0 },
  { "slice", 0, 0 }, { "slice", 7, 0 },
  { "slice", 6, 0 }, { "slice", 8, 0 },
  { "slice", 9, 0 }, { "slice", 10, 0 },
  { "sit", 0 }, { "sit", 1 },
}

local src85 = load_image(SRC85)
if not src85 then
  error("Missing source: " .. SRC85)
end

local sitting = load_image(SIT)
if sitting then
  sitting = resize_nearest(sitting, FW, FH)
end

local spr = Sprite(FW, FH, ColorMode.RGB)
local layer = spr.layers[1]
layer.name = "ninja"

for i = 2, #FRAME_SPECS do
  spr:newEmptyFrame()
end

for i, spec in ipairs(FRAME_SPECS) do
  local frame = spr.frames[i]
  local cel = spr:newCel(layer, frame)
  local img = cel.image
  img:clear(Color{r=0, g=0, b=0, a=0})

  if spec[1] == "slice" then
    blit_slice(img, src85, spec[2], spec[3])
  elseif spec[1] == "sit" then
    if sitting then
      blit_full(img, sitting, spec[2])
    else
      blit_slice(img, src85, 0, spec[2])
    end
  end
end

-- Animation tags (1-based frame indices)
local tags = {
  { "idle", 1, 2 },
  { "run", 3, 6 },
  { "punch", 7, 8 },
  { "jump_kick", 9, 10 },
  { "climb", 11, 12 },
  { "crouch", 13, 14 },
}
for _, t in ipairs(tags) do
  local tag = spr:newTag(#spr.tags + 1)
  tag.name = t[1]
  tag.fromFrame = spr.frames[t[2]]
  tag.toFrame = spr.frames[t[3]]
  tag.aniDir = AniDir.FORWARD
end

app.activeSprite = spr
spr:saveAs(OUT_ASE)

app.command.ExportSpriteSheet{
  ui = false,
  type = SpriteSheetType.HORIZONTAL,
  textureFilename = OUT_PNG,
  dataFilename = "",
  listTags = true,
  listLayers = false,
  openGenerated = false,
}

print("Saved " .. OUT_ASE)
print("Exported " .. OUT_PNG)
