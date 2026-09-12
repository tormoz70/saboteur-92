# Базовая линия коллизии (фаза 0)

Дата: 2026-09-12  
Ветка: `refactor/tilemap-migration`  
Команда: `python tools/saboteur_rip/audit_collision.py`

Аудит смотрит **визуал мозаики** (цвета ZX) против `s2_collision.json`. Это не «дыры в геймплее bytecode», а расхождение эвристики speckled/brick с объектной коллизией. Источник правды коллизии — `collision_source: object_bounds` (прямоугольники из типов объектов). После инверсии тем же прямоугольникам соответствует `s2_collision_tiles.json`.

## Метрики мира

- Сетка: 1024×576 ячеек (8×8), размер PNG 8192×4608, scale 2
- `s2_collision.json`: **3292** solids, **133** ladders, **6** lifts, 9 bookcases
- `s2_objects.json`: 113 типов, 6451 инстанс
- Визуальные слои (`s2_world_tiles.json`): sky 376 / earth 388 / structure 690 / wallpaper 618 / interior 815 / fg 160 уникальных тайлов
- Занятые визуальные клетки: sky 173022, earth 48540, structure 13214, wallpaper 157505, interior 31553, fg 2709
- Спавн (`s2_entities.json`): `[2240, 600]` — экран (8, 3)

Числа 4643 / 123 / 4 из старого плана относятся к предыдущей генерации; в репозитории сейчас цифры выше.

## Аудит визуал vs солиды

Биомы экранов (256×192): sky 250, cave 378, interior 140.

Грунт (speckled earth): всего 34542 ячейки, без коллизии 21251 (61.5%)

- cave: 21010 всего, дыр 12340 (58.7%)
- interior: 9266 всего, дыр 5949 (64.2%)
- sky: 4266 всего, дыр 2962 (69.4%)

Красный кирпич: всего 11559, без коллизии 6374 (55.1%)

- cave: 86.3% дыр
- interior: 34.7%
- sky: 55.3%

Экраны с наибольшим числом «провальных» ячеек грунта (в координатах экрана, мир при scale=2):

- (10, 12) cave — 689 дыр, мир ~(5120, 4608)
- (21, 11) cave — 567
- (21, 12) cave — 567
- (21, 14) cave — 567
- (21, 15) cave — 567
- (14, 17) cave — 567
- (21, 13) cave — 558
- (10, 9) cave — 514
- (10, 6) cave — 497
- (10, 13) interior — 483, мир ~(5120, 4992)

Если насильно залить speckled_earth в interior: +5949 солидов, 115 из них на лестницах. Число связных пустых областей растёт (103 → 143) — грунт режет пещеры.

## Известные баги классификации (не чинить порогами)

1. Аудит считает грунт по цвету ячейки, а коллизия штампуется с границ **объектов**. Пещера из speckled без объектного типа `solid` остаётся воздухом — это не регрессия TileMap, а причина инверсии.
2. Биом экрана (sky / interior / cave) по доле синего/зелёного красит весь 256×192. Комната с обоями помечает interior и соседнюю породу.
3. Люки: клетка и solid, и climb. Exclusive TileMap не может показать оба; `ladder_rle` хранит climb, включая крышки.
4. Тонкие лестницы короче 24 px отбрасываются (`ladder_rects`).

## Как править после инверсии

Дыру в проходимости красят кистью `solid` / `ladder` на `CollisionLayer` в плагине Level Editor. Не перезапускать классификатор по цветам.

## Проверка карты коллизии (рантайм)

`python tools/saboteur_rip/test_collision_tiles.py` — greedy из тайлов совпадает с `s2_collision.json` (3292 solids, 133 ladders). Oneway в RLE нет. Люки: 1184 клеток и solid, и climb.

GUT: `test_s2_collision` 5/5 (игрок стоит на bytecode-полу, по одному StaticBody/Area2D на запись JSON), `test_tilemap_migration` 4/4, `test_level_playable` 2/2.

Оверлей `CollisionLayer` (клавиша `9`, либо захват в каталог с `collision` в пути):

```bash
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views/collision/2x
```

Красный = solid, зелёный = ladder. Полы и лестницы на спавне/в интерьере совпадают с объектами. Мебель и ящики FG без коллизии. Платформы в небе на спавне — AABB объектов, не дыры TileMap. Пещерный кирпич справа на точке cave без солида — та же эвристика «визуал vs object_bounds», что в аудите выше.

Спавн `[2240, 600]`: хитбокс игрока в воздухе, пол под ногами на PNG y=704 (`[2240, 704, 112, 16]`) — падение ~152 world px, не пустота.

## Снимки карты

`tools/capture_map_view.gd` — spawn / rooftop / interior / cave. Снимки класть в `docs/audit_views/` через локальный Godot:

```bash
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views
tools/godot/Godot_v4.6-stable_win64_console.exe --path . -s tools/capture_map_view.gd -- docs/audit_views/2x
```

Headless-рендер текстуру не отдаёт; нужен оконный запуск. Скрипт прячет HUD, тачпад, игрока, предметы и охранников. Каталог с `2x` в пути снимает при zoom=1 (2× пикселя мозаики).

Пустые клетки слоёв (выбитый FG, шахты) раньше светились серым clear color движка. Фон в `project.godot` — чёрный, как в `saboteur2_world.png` после `punch_fg_cells`.

Сравнение 2026-09-12, целочисленный 2× vs композит шести TileMap-слоёв (и vs мозаика+FG): **spawn / rooftop / interior / cave = 100%**. Точки rooftop и cave в игровом зуме почти целиком небо — так и в мозаике, это не дыра TileMap.

Тестовый экран спавна запечён в [scenes/levels/screen_spawn.tscn](../scenes/levels/screen_spawn.tscn) и [test/fixtures/screen_spawn_tiles.json](../test/fixtures/screen_spawn_tiles.json).
