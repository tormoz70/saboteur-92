# Saboteur '93 — Art Bible

Visual direction for **saboteur-92** remake assets: not a 1:1 ZX Spectrum copy, but a readable late-8-bit / early-16-bit look (circa 1993).

## Goals

- Keep **gameplay grid** from the original (48×56 character, 8×8 tiles).
- Add **4–8 fixed colors** per sprite (no free-form gradients).
- Preserve **crisp pixels** (`texture_filter = Nearest` in Godot).
- One **horizontal sprite sheet** per character, 48×56 per frame.

## Technical spec (engine)

| Asset | Size | Layout |
|-------|------|--------|
| Player sheet | 672×56 (14 frames) | horizontal strip |
| Frame cell | 48×56 | `Rect2(n * 48, 0, 48, 56)` |
| Items | 24×24 | 3 icons per row |
| Tileset | 8×8 tiles | 128×16 PNG |

### Player frame map (`saboteur93_player.png`)

| Frames | X (px) | Animation | Notes |
|--------|--------|-----------|-------|
| 0–1 | 0, 48 | `idle` | breathing optional |
| 2–5 | 96–240 | `run` | 4-frame cycle |
| 6–7 | 288, 336 | `punch` | wind-up → hit |
| 8–9 | 384, 432 | `jump_kick` | also `jump` uses frame 8 |
| 10–11 | 480, 528 | `climb` | back view |
| 12–13 | 576, 624 | `crouch` | squat / low stance |
| — | 576 | `death` | placeholder until dedicated frame |

Godot scene: `scenes/player/player.tscn` → `assets/sprites/saboteur93_player.png`.

## Palette (player ninja)

Use only these colors in Aseprite (Indexed or fixed swatches):

| Role | Hex | Usage |
|------|-----|--------|
| Body / mask | `#0D0D12` | suit, hood |
| Shadow | `#2A3548` | folds, legs |
| Skin | `#8B5E3C` | face slit |
| Highlight | `#E8E8E8` | belt, boot edge |
| Accent | `#C41E24` | boots |
| Gear (opt.) | `#4A6FA5` | strap / pouch |

## Palette (guard)

Same structure; replace body with **`#1E3A8A`** (uniform blue), keep skin/boot rules.

## Style rules

1. **Side view** for run, punch, jump, crouch; **back view** for climb.
2. **Head height** constant across frames (±1 px only for idle breathe).
3. **Feet on baseline** — bottom 2 rows aligned for floor contact.
4. No anti-aliasing, no partial transparency on edges.
5. Export PNG with transparent background.

## Production pipeline

```
Ludo.ai (96 px, 16-bit pixel art, reference frame)
  → Aseprite: resize 48×56 (Nearest), enforce palette
  → Aseprite: tags + horizontal export
  → assets/sprites/saboteur93_player.png
  → Godot import: filter off
```

Rebuild from ripped frames (fallback):

```bash
python tools/saboteur_rip/build_saboteur93_player.py
```

Aseprite scripted export (from `.aseprite`):

```bash
aseprite.exe -b --script tools/aseprite/build_saboteur93_player.lua
```

---

## Ludo.ai — global settings

- **Art style:** 16-Bit Pixel Art
- **Sprite size:** 96 px (downscale in Aseprite to 48×56)
- **Animation model:** Blitz (consistency) — Eagle only if motion is too stiff
- **Export:** Pixel Art mode, horizontal sheet, transparent BG
- **Reference image:** `assets/sprites/saboteur85_player.png` or best idle from `saboteur92_player_bkp1.aseprite`

### Base character prompt

```
Side-view ninja infiltrator, 1993 retro platformer sprite, 16-bit pixel art,
dark blue-black suit, tan face visible through mask slit, white belt, red boots,
crisp pixels, no anti-aliasing, no gradients, transparent background,
single character, game sprite
```

### Negative prompt

```
blurry, smooth, realistic, 3d, anime, watercolor, soft edges, anti-aliased,
high resolution, multiple characters, background scene
```

---

## Ludo.ai — per-animation prompts

Upload the **approved idle frame** as reference for all actions below.

### 1. Idle (frames 0–1)

```
Standing idle, side view facing right, subtle breathing,
chest rises and falls slightly, feet planted, arms relaxed,
same proportions as reference, 2-frame loop
```

### 2. Run (frames 2–5)

```
Run cycle side view facing right, 4 frames, classic platformer stride,
arms counter-swing legs, red boots visible, maintain head size and belt line
```

### 3. Punch (frames 6–7)

```
Hand punch side view, frame 1 wind-up arms bent, frame 2 right arm fully extended,
torso slightly forward, feet stay on ground, same palette as reference
```

### 4. Jump kick (frames 8–9)

```
Jump kick side view, frame 1 tuck jump knees up, frame 2 flying side kick
leg extended horizontally, body angled back slightly, same ninja proportions
```

### 5. Climb (frames 10–11)

```
Climb ladder back view, 2 frames alternating arms and legs,
no face detail, shoulders same width as reference, gripping vertical ladder
```

### 6. Crouch (frames 12–13)

```
Crouch squat side view facing right, 2 frames, knees bent deep,
torso lowered, head forward, optional 1px bob between frames, feet on baseline
```

---

## Guard sheet (TODO)

Mirror player layout in `saboteur93_guard.png`. Prompt swap:

```
Security guard, blue uniform, same 48x56 proportions and pixel style as ninja reference,
side view, 1993 retro platformer
```

---

## Tileset & items (manual)

- Tiles: draw in Aseprite at **8×8**, expand palette to 8–12 colors max.
- Items (24×24): key, document, bomb — max 4 colors each.

## QA checklist before commit

- [ ] Sheet is exactly **672×56**, 14 frames
- [ ] No blurry edges at 400% zoom
- [ ] Palette matches table above
- [ ] `player.tscn` regions align with frame map
- [ ] Idle / run / climb loop cleanly in Godot
