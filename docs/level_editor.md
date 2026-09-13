# Редактор уровня (TileMap)

Источник карты этого прохода — `assets/world/saboteur2_world2.png`.
Скрипт `python tools/saboteur_rip/slice_world_tiles.py` режет её на клетки 8×8
и собирает Godot TileSet + RLE.

## Слои этого прохода

| Узел | Что | Физика |
|---|---|---|
| SkyFill | чистый синий фон `(0, 0, 206)` | нет |
| Earth | чёрный грунт, крапинка, монолит, трещины | solid |
| Structure | красный кирпич в зелёных залах | solid |
| Wallpaper | синий кирпич подземных залов | нет |
| Mosaic | зелёная квадратная мозаика штаба | нет |
| CollisionLayer | `empty` / `solid` (earth ∪ structure) | рантайм склеивает greedy |
| Interior, Foreground | пустые, следующий проход | нет |

Клетка эксклюзивна. Неразложенный остаток (лестницы, мебель, окна, вода) —
`docs/audit_views/slice_leftover.png`. Карта классов — `slice_overlay.png`.

Полная сетка 1024×576 живёт в `s2_world_tiles.json` / `s2_collision_tiles.json`,
не в `.tscn`.

## Где панель

После перезапуска редактора (Project → Project Settings → Plugins → **Level Editor**):

1. Слева внизу, рядом с **FileSystem / History** — вкладка **Level Editor**.
2. Нижняя полоса рядом с **Output / Debugger / GUT** — кнопка **Level Editor**.
3. Меню **Project → Tools → Level Editor: Load World JSON**.

Откройте `level_01.tscn`, нажмите **Load JSON**.

## Кисть коллизии

1. Откройте `scenes/levels/level_01.tscn`.
2. Выберите `CollisionLayer`.
3. Solid / Erase. Ladder / Oneway зарезервированы, в этом проходе не используются.
4. **Save JSON** / **Load JSON** / **Validate**.

Earth / Structure по умолчанию штампуют `solid` (`LevelEditorSync`). Mosaic и wallpaper — нет.

## Пересборка тайлов

```bash
python tools/saboteur_rip/slice_world_tiles.py
```

Клавиши в игре: `0` небо, `1` грунт, `2` структура, `3` синий кирпич, `4` мозаика, `9` коллизия.

## Рантайм

[scripts/levels/level_01.gd](../scripts/levels/level_01.gd) `_setup_from_tilemap()` заливает RLE,
`_collision_rects_from_tiles()` склеивает солиды. Лифты по-прежнему из `s2_collision.json`,
если файл есть.
