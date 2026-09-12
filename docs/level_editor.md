# Редактор уровня (TileMap)

После инверсии пайплайна источник правды мира — визуальные `TileMapLayer` плюс семантический `CollisionLayer`. JSON остаётся компактным хранилищем полной карты 1024×576; сцена `level_01.tscn` не содержит все клетки.

## Слои

| Узел | TileSet | Физика |
|---|---|---|
| Sky, Earth, Structure, Wallpaper, Interior, Foreground | `assets/tilesets/s2_*_tileset.tres` | нет |
| CollisionLayer | `s2_collision_tileset.tres` (`empty` / `solid` / `ladder` / `oneway`) | нет полигонов; рантайм склеивает greedy |
| World/Solids, Ladders, Lifts | ноды | `StaticBody2D` / `Area2D` / `AnimatableBody2D` |

`oneway` зарезервирован, геймплея one-way платформ нет.

Люки: крышка solid + climb. В TileMap крышка рисуется как `solid`; climb крышки живёт в `ladder_rle`, чтобы не потерять шахту.

## Кисть коллизии

Плагин `addons/level_editor` (нижняя панель **Level Editor**):

1. Откройте `scenes/levels/level_01.tscn` или `screen_spawn.tscn`.
2. Выберите `CollisionLayer`.
3. Solid / Ladder / Oneway / Erase, размер 1–8.
4. ЛКМ в 2D-виде красит клетки.
5. **Save JSON** пишет `s2_world_tiles.json`, `s2_collision_tiles.json` и пересобирает прямоугольники `s2_collision.json`.
6. **Load JSON** заливает RLE обратно в слои.
7. **Validate** проверяет слои, спавн и покрытие коллизии.

Правка визуала **не затирает** уже нарисованную коллизию. Пустую клетку коллизии можно штамповать дефолтом типа (`CollisionBrush.stamp_default_if_empty`).

Полную карту в редакторе удобнее грузить через Load JSON, чем хранить 590k клеток в `.tscn`. Фрагмент 256×192 — `screen_spawn.tscn`.

## Последний прогон рипа

Нужны локальные дампы из `assets/reference/` (не в git):

```bash
python tools/saboteur_rip/decompose_world.py
python tools/saboteur_rip/test_collision_tiles.py
python tools/saboteur_rip/audit_collision.py
```

Без дампов коллизионные тайлы пересобираются из текущего JSON:

```bash
python tools/saboteur_rip/collision_tiles.py
```

## Аудит и снимки

```bash
python tools/saboteur_rip/audit_collision.py
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views/2x
```

Клавиши в игре: `0` небо, `1` грунт, `2` структура, `3` обои, `4` интерьер, `7`/`8` передний план, `9` оверлей коллизии.

## Рантайм

[scripts/levels/level_01.gd](../scripts/levels/level_01.gd) `_setup_from_tilemap()` читает RLE, `_collision_rects_from_tiles()` склеивает солиды и лестницы. Лифты и книжные шкафы по-прежнему из `s2_collision.json`. Каталог `s2_objects.json` — типы для редактора, не список спрайтов.
