# Somake AI — Run animation (4 frames)

Use with reference: `assets/sprites/ref/ninja_idle_ref.png`

## Settings

- **Ссылка на персонажа:** upload `ninja_idle_ref.png`
- **Style:** Пиксель-арт
- **Ракурс:** Сбоку
- **Action:** Run / Бег
- **Количество кадров:** 4
- **Улучшить с помощью ИИ:** OFF

## Prompt

```
Use the uploaded sprite as a strict visual reference and preserve the character exactly.

Create a 4-frame running animation of THIS SAME ninja only.
Do not redesign, reinterpret, modernize, or replace the character.
Keep the exact black silhouette, head shape, body proportions, mask,
hands, legs, and pixel-art style from the reference.

Side-view run cycle, facing the same direction as the reference.
Frame 1: right leg forward, left leg back.
Frame 2: passing pose, legs close together.
Frame 3: left leg forward, right leg back.
Frame 4: passing pose, legs close together, opposite arm swing.

Keep the head at the same height and keep both feet aligned to the same
ground baseline in every frame. Arms swing naturally opposite to the legs.
Single character only. No weapon. No effects.

Transparent background. Crisp hard pixels. No anti-aliasing.
All four frames must have the same canvas size, character scale,
palette, and proportions. Output exactly 4 equally sized sprite frames
in one horizontal row.
```

## Negative prompt

```
new character, redesign, different costume, different face, different head,
different proportions, different pose, different camera angle, front view,
background, scene, weapon, effects, extra limbs, motion blur,
smooth art, 3D, anime, realistic, gradients, blur, anti-aliasing,
large sprite, text, watermark
```

## Local fallback (if Somake drifts from reference)

```bash
python tools/sprites/build_run_from_ref.py
```

Output: `assets/sprites/saboteur93_ninja_run4.png` (192×56, 4×48×56)
