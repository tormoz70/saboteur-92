-- Edit saboteur92_player_bkp1.aseprite:
-- 1) Frames 1-3: standing + breathing
-- 2) Append 2 crouch frames at end
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
local FILE = ROOT .. "/assets/sprites/saboteur92_player_bkp1.aseprite"
local SIT = ROOT .. "/assets/reference/original/ripped/ninja_sitting.png"

local function get_cel(spr, layer, frameIdx)
  local cel = layer:cel(spr.frames[frameIdx])
  if not cel then
    cel = spr:newCel(layer, spr.frames[frameIdx])
  end
  return cel
end

local function cel_image(spr, layer, frameIdx)
  return Image(get_cel(spr, layer, frameIdx).image)
end

local function shift_image_y(img, dy)
  local w, h = img.width, img.height
  local out = Image(w, h, img.colorMode)
  for y = 0, h - 1 do
    local sy = y - dy
    if sy >= 0 and sy < h then
      for x = 0, w - 1 do
        local p = img:getPixel(x, sy)
        if app.pixelColor.rgbaA(p) > 0 then
          out:putPixel(x, y, p)
        end
      end
    end
  end
  return out
end

local function shift_upper_body(img, dy, splitY)
  local w, h = img.width, img.height
  local out = Image(w, h, img.colorMode)
  for y = 0, h - 1 do
    for x = 0, w - 1 do
      local p = img:getPixel(x, y)
      if app.pixelColor.rgbaA(p) == 0 then
        goto continue
      end
      local ty = y
      if y < splitY then
        ty = y + dy
      end
      if ty >= 0 and ty < h then
        out:putPixel(x, ty, p)
      end
      ::continue::
    end
  end
  return out
end

local function resize_nearest(img, w, h)
  if img.width == w and img.height == h then
    return img
  end
  local out = Image(w, h, img.colorMode)
  out:drawImage(img, Point(0, 0), 0, 0, img.width, img.height, w, h)
  return out
end

local function blit_into_cel(cel, srcImg)
  local img = cel.image
  img:clear(Color{r=0, g=0, b=0, a=0})
  for y = 0, img.height - 1 do
    for x = 0, img.width - 1 do
      local p = srcImg:getPixel(x, y)
      if app.pixelColor.rgbaA(p) > 0 then
        img:putPixel(x, y, p)
      end
    end
  end
end

local spr = app.open(FILE)
local layer = spr.layers[1]

-- --- Breathing on frames 1-3 ---
local baseImg = cel_image(spr, layer, 1)
local splitY = 28 -- head + chest move, legs stay

-- Frame 1: neutral (unchanged)
-- Frame 2: inhale — chest up 1px
blit_into_cel(get_cel(spr, layer, 2), shift_upper_body(baseImg, -1, splitY))

-- Frame 3: exhale — chest down 1px
blit_into_cel(get_cel(spr, layer, 3), shift_upper_body(baseImg, 1, splitY))

-- Update idle tag (frames 1-3), ping-pong feels like breathing
for _, tag in ipairs(spr.tags) do
  if tag.name == "idle" then
    tag.fromFrame = spr.frames[1]
    tag.toFrame = spr.frames[3]
    tag.aniDir = AniDir.PING_PONG
    tag.color = Color{r=80, g=200, b=120}
  end
end

spr.frames[1].duration = 12
spr.frames[2].duration = 10
spr.frames[3].duration = 12

-- --- Add 2 crouch frames at end ---
local lastIdx = #spr.frames
local sitImg = nil
if app.fs.isFile(SIT) then
  sitImg = resize_nearest(Image{fromFile=SIT}, spr.width, spr.height)
end

spr:newEmptyFrame()
spr:newEmptyFrame()

local celA = get_cel(spr, layer, lastIdx + 1)
local celB = get_cel(spr, layer, lastIdx + 2)

if sitImg then
  blit_into_cel(celA, sitImg)
  blit_into_cel(celB, shift_image_y(sitImg, 1))
else
  -- fallback: copy last crouch frame
  local ref = layer:cel(spr.frames[lastIdx])
  blit_into_cel(celA, Image(ref.image))
  blit_into_cel(celB, shift_image_y(Image(ref.image), 1))
end

-- Extend / create crouch tag through new frames
local crouchFrom = spr.frames[14]
local crouchTo = spr.frames[#spr.frames]
local hasCrouch = false
for _, tag in ipairs(spr.tags) do
  if tag.name == "crouch" then
    tag.fromFrame = crouchFrom
    tag.toFrame = crouchTo
    tag.aniDir = AniDir.FORWARD
    tag.color = Color{r=220, g=140, b=60}
    hasCrouch = true
  end
end
if not hasCrouch then
  local tag = spr:newTag(#spr.tags + 1)
  tag.name = "crouch"
  tag.fromFrame = crouchFrom
  tag.toFrame = crouchTo
  tag.aniDir = AniDir.FORWARD
  tag.color = Color{r=220, g=140, b=60}
end

spr:saveAs(FILE)
print("Updated " .. FILE .. " (" .. #spr.frames .. " frames)")
