# Снимки карты для визуальной регрессии

Снять (Godot 4.6 из `tools/godot`, не `--headless` — dummy-рендер не отдаёт PNG):

```bash
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views/2x
```

Точки: spawn, rooftop, interior, cave. Скрипт прячет HUD, игрока и предметы.

- Игровой зум (1.875): `docs/audit_views/*.png`
- Целочисленный 2× (zoom=1): `docs/audit_views/2x/*.png` — пиксель-в-пиксель с композитом слоёв `s2_world_tiles.json`

2026-09-12: 2× совпал на 100% на всех четырёх точках. Rooftop/cave в игровом зуме — в основном небо, как в мозаике.
