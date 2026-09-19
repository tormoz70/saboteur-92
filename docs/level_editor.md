# Редактор уровня (TileMap)

Карта Saboteur II хранится в нативном формате Godot: сцены-чанки с
`tile_map_data` и общие `TileSet`. Правится штатным редактором тайлов —
выбрал слой, взял тайл из палитры, покрасил, Ctrl+Z работает. Самописный
Load/Save JSON для карты больше не нужен и удалён.

## Слои

| Узел | TileSet | Что | Семантика |
|---|---|---|---|
| SkyFill | — | чистый синий фон `(0, 0, 206)` | нет |
| Earth | `s2_earth_tileset.tres` | чёрный грунт, крапинка, монолит | визуал |
| Structure | `s2_structure_tileset.tres` | красный кирпич | визуал |
| Wallpaper | `s2_wallpaper_tileset.tres` | синий кирпич подземных залов | визуал |
| Mosaic | `s2_mosaic_tileset.tres` | зелёная мозаика штаба | визуал |
| Interior | `s2_interior_tileset.tres` | лестницы, мебель, окна, ящики | визуал |
| Foreground | `s2_fg_tileset.tres` | передний план | визуал |
| CollisionLayer | `s2_collision_tileset.tres` | `empty`/`solid`/`ladder`/`oneway` | **физика** |

Визуальные слои — только картинка. Поведение (твёрдость, лестницы) несёт
один `CollisionLayer` через physics layer тайлсета и `custom_data`
`collision_type`. Покрашенная кистью лестница начинает работать без
перегенерации каких-либо JSON.

## Карта Saboteur II = сцены-чанки

Мир 1024×576 ячеек (8192×4608 px) нарезан на 8×8 = 64 чанка по 128×72 ячейки
в `scenes/world/chunks/chunk_XX_YY.tscn`. Каждый чанк — `Node2D` с набором
`TileMapLayer`, заполненных `tile_map_data`. `scenes/levels/level_01.tscn`
только инстансит чанки под корень `WorldMap` (см. `_setup_from_chunks()` в
[scripts/levels/level_01.gd](../scripts/levels/level_01.gd)).

Чтобы править карту, откройте нужный чанк и красьте. Правка на стыке двух
чанков требует открыть соседнюю сцену — стык раз в 4 экрана, в пределах
одного экрана редактирования это не мешает.

## Новый уровень

1. Скопируйте `scenes/levels/level_template.tscn` под новым именем.
2. В корне уже лежат все слои с привязанными общими `TileSet`, `SkyFill`,
   `Player`, `Camera2D` и маркер `Entities/SpawnPoint`.
3. Красьте слои прямо в сцене. Семантику красьте в `CollisionLayer`
   (невидим, включите глазок в дереве сцены).
4. Поставьте `SpawnPoint` туда, где появляется Нина. Размер мира и зум
   настраиваются экспортами `world_size`, `screen_size`, `level_scale`,
   `sky_color` на корневом узле.

Шаблон использует [scripts/levels/level_base.gd](../scripts/levels/level_base.gd) —
камера, спавн, лестницы из `CollisionLayer`, отладочные клавиши слоёв.
Маленькому уровню чанки не нужны: он рисуется целиком в своей сцене.

## Кисть коллизии

1. Откройте сцену уровня (или чанк карты).
2. Выберите `CollisionLayer`.
3. Красьте тайлами `solid` / `ladder` / `oneway` из `s2_collision_tileset`.
   Пустая клетка — `empty` (erase).

## Пересборка библиотеки тайлов и чанков

```bash
python tools/saboteur_rip/build_world_atlas.py    # атласы + s2_world_cells.json
python tools/saboteur_rip/build_tilesets.py       # .tres TileSet
tools/godot/Godot_v4.6-stable_win64_console.exe --headless --path . --import
tools/godot/Godot_v4.6-stable_win64_console.exe --headless --path . --script tools/build_world_chunks.gd
```

Назначение ячеек слоям — в чекинной таблице `assets/world/s2_tile_layers.json`
(`tile_id → layer`). Неверный слой правится строкой в таблице (и пересборкой)
или кистью в редакторе — пиксели при этом не теряются.

Клавиши в игре: `0` небо, `1` грунт, `2` структура, `3` синий кирпич,
`4` мозаика, `5` машины, `6` актёры, `7`/`8` передний план, `9` коллизия.
