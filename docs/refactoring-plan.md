# 📋 Подробный план рефакторинга Saboteur-92

## 🎯 Цель рефакторинга

Переход от **пайплайна импорта** (рип → JSON → рантайм) к **редактируемой архитектуре** (редактор → рантайм), где уровень является first-class citizen в Godot.

---

## 📊 Фаза 0: Подготовка (1-2 дня)

### 0.1 Аудит текущего состояния

**Задачи:**

- [x] Запустить `tools/saboteur_rip/audit_collision.py` и зафиксировать baseline
- [x] Задокументировать все известные баги классификации
- [x] Создать backup всех JSON файлов (`s2_objects.json`, `s2_collision.json`)
- [x] Зафиксировать текущие метрики (см. `docs/audit_baseline.md`: 3292 solids, 133 ladders, 6 lifts)

**Критерии приемки:**

- Отчет аудита сохранен в `docs/audit_baseline.md`
- JSON мира живёт в git; ветка `refactor/tilemap-migration`



### 0.2 Создание тестового окружения

**Задачи:**

- [x] Создать ветку `refactor/tilemap-migration`
- [x] Настроить CI для проверки миграции
- [x] Подготовить тестовый уровень (один экран 256×192) для валидации

**Риски:**

- Потеря данных при миграции
- Несовместимость с существующим кодом

**Mitigation:**

- Работать в отдельной ветке
- Сохранить старые JSON как reference

---



## 🏗️ Фаза 1: Инверсия пайплайна (3-5 дней)



### 1.1 Генерация редактируемой TileMap

**Текущее состояние:**

```python
# decompose_world.py создает JSON с instances
catalog = {
    "types": {...},
    "instances": [
        {"type": "brick_wall", "x": 100, "y": 200, "w": 80, "h": 16},
        ...
    ]
}
```

**Целевое состояние:**

```gdscript
# Godot TileMap с двумя слоями
TileMapLayer "Visual":
  - TileSet с ~2000 уникальными тайлами
  - Позиции из instances
  
TileMapLayer "Collision":
  - TileSet с 3-4 семантическими тайлами
  - solid, ladder, oneway, empty
```

**Задачи:**

#### 1.1.1 Модификация decompose_world.py

**Файл:** `tools/saboteur_rip/decompose_world.py`

**Изменения:**

```python
def generate_tilemap_data(instances, types):
    """Генерирует данные для Godot TileMap вместо JSON instances"""
    visual_tiles = []
    collision_tiles = []
    
    for inst in instances:
        type_def = types[inst["type"]]
        
        # Visual layer: уникальный спрайт
        visual_tiles.append({
            "atlas_id": inst["type"],
            "x": inst["x"] // CELL,
            "y": inst["y"] // CELL,
            "w": inst["w"] // CELL,
            "h": inst["h"] // CELL
        })
        
        # Collision layer: семантический тип
        collision_type = map_collision_to_semantic(type_def["collision"])
        collision_tiles.append({
            "type": collision_type,  # solid/ladder/oneway/empty
            "x": inst["x"] // CELL,
            "y": inst["y"] // CELL,
            "w": inst["w"] // CELL,
            "h": inst["h"] // CELL
        })
    
    return {
        "visual": visual_tiles,
        "collision": collision_tiles,
        "tileset_atlas": extract_unique_tiles(instances, types)
    }
```

**Критерии приемки:**

- Скрипт генерирует два набора данных
- Визуальные тайлы соответствуют оригиналу
- Collision тайлы покрывают всю карту



#### 1.1.2 Создание TileSet атласа

**Новый скрипт:** `tools/saboteur_rip/build_tileset_atlas.py`

**Функциональность:**

- Извлекает уникальные тайлы из instances
- Создает атлас PNG (максимум 2048×2048)
- Генерирует TileSet resource для Godot

```python
def extract_unique_tiles(instances, types):
    """Собирает уникальные спрайты в атлас"""
    unique_tiles = {}
    
    for inst in instances:
        type_id = inst["type"]
        if type_id not in unique_tiles:
            sprite = build_type_sprite(type_id, bchrs, ochrs)
            unique_tiles[type_id] = {
                "image": sprite,
                "collision": types[type_id]["collision"]
            }
    
    return unique_tiles
```

**Оценка:** 1-2 дня

#### 1.1.3 Генерация Godot сцены

**Новый скрипт:** `tools/saboteur_rip/generate_tilemap_scene.py`

**Вывод:** `scenes/levels/level_01.tscn` с TileMapLayer

```python
def generate_tscn(visual_tiles, collision_tiles, tileset_path):
    """Генерирует Godot сцену с TileMapLayer"""
    tscn_template = '''
[gd_scene format=3]

[ext_resource type="TileSet" path="{tileset_path}" id="1"]

[node name="Level01" type="Node2D"]

[node name="VisualLayer" type="TileMapLayer" parent="."]
tile_set = ExtResource("1")
layer = 0

[node name="CollisionLayer" type="TileMapLayer" parent="."]
tile_set = ExtResource("1")
layer = 1
'''
    # Заполнить tiles...
    return tscn_content
```

**Критерии приемки:**

- Сцена открывается в Godot редакторе
- Визуальный слой отображает карту
- Collision слой содержит физику
- Уровень играбелен без изменений в коде

**Оценка:** 2-3 дня

### 1.2 Адаптация runtime кода

**Текущий код:** `scripts/levels/level_01.gd` читает JSON

**Целевой код:** Использует TileMapLayer напрямую

**Задачи:**

#### 1.2.1 Рефакторинг level_01.gd

**Файл:** `scripts/levels/level_01.gd`

**Изменения:**

```gdscript
# УДАЛИТЬ:
func _load_original_world() -> void:
    var data := _load_json(COLLISION_PATH)
    # ... 200 строк парсинга JSON

# ДОБАВИТЬ:
func _setup_from_tilemap() -> void:
    # Получить TileMapLayer из сцены
    var visual_layer := $VisualLayer as TileMapLayer
    var collision_layer := $CollisionLayer as TileMapLayer
    
    # Настроить collision из TileMap
    _setup_collision_from_tilemap(collision_layer)
    _setup_ladders_from_tilemap(collision_layer)
    _setup_lifts_from_tilemap(collision_layer)

func _setup_collision_from_tilemap(tilemap: TileMapLayer) -> void:
    # TileMap уже имеет collision из TileSet
    # Просто настроить collision layers
    var body := StaticBody2D.new()
    body.name = "Solids"
    body.collision_layer = CollisionLayers.LAYER_WORLD
    body.collision_mask = 0
    
    # Скопировать collision shapes из TileMap
    for cell in tilemap.get_used_cells():
        var tile_data := tilemap.get_cell_tile_data(cell)
        if tile_data and tile_data.get_custom_data("collision_type") == "solid":
            var shape := RectangleShape2D.new()
            shape.size = Vector2(CELL * SCALE, CELL * SCALE)
            # ... добавить в body
```

**Критерии приемки:**

- Уровень загружается из сцены
- Физика работает корректно
- Игрок не проваливается
- Все лестницы функционируют

**Оценка:** 2 дня

#### 1.2.2 Создание утилит для TileMap

**Новый файл:** `scripts/world/tilemap_utils.gd`

```gdscript
class_name TileMapUtils

static func get_collision_type(tilemap: TileMapLayer, cell: Vector2i) -> String:
    var tile_data := tilemap.get_cell_tile_data(cell)
    if not tile_data:
        return "empty"
    return tile_data.get_custom_data("collision_type")

static func find_ladders(tilemap: TileMapLayer) -> Array[Rect2]:
    var ladders := []
    for cell in tilemap.get_used_cells():
        if get_collision_type(tilemap, cell) == "ladder":
            # Склеить смежные ячейки
            ladders.append(cell_to_rect(cell))
    return greedy_merge_rects(ladders)
```

**Оценка:** 1 день

---



## 🎨 Фаза 2: Разделение Visual и Collision (2-3 дня)



### 2.1 Создание двух TileSet

**Проблема:** Один TileSet смешивает визуал и физику

**Решение:** Два независимых TileSet

#### 2.1.1 Visual TileSet

**Файл:** `assets/tilesets/visual_tileset.tres`

**Характеристики:**

- ~2000 уникальных тайлов
- Размер: 8×8 пикселей (CELL)
- Без physics layers
- Только rendering



#### 2.1.2 Collision TileSet

**Файл:** `assets/tilesets/collision_tileset.tres`

**Характеристики:**

- 4 семантических тайла: solid, ladder, oneway, empty
- Physics layers настроены
- Невидимый (или debug overlay)

**Критерии приемки:**

- Два отдельных TileSet файла
- Visual TileSet содержит все спрайты
- Collision TileSet содержит 4 типа
- Слои независимы

**Оценка:** 2 дня

### 2.2 Обновление level_01.tscn

**Структура сцены:**
Level01 (Node2D)
├── VisualLayer (TileMapLayer)
│   └── tile_set = visual_tileset.tres
├── CollisionLayer (TileMapLayer)
│   └── tile_set = collision_tileset.tres
├── Ladders (Node2D)
│   └── Area2D nodes
├── Lifts (Node2D)
│   └── LiftPlatform nodes
└── Entities (Node2D)
└── Items, Guards, etc.

**Оценка:** 1 день

---



## 🛠️ Фаза 3: Редактор уровней (5-7 дней)



### 3.1 Создание LevelEditor плагина

**Новый файл:** `addons/level_editor/level_editor.gd`

**Функциональность:**

- Редактирование TileMap в Godot
- Синхронизация Visual и Collision слоев
- Инструменты для рисования коллизий
- Валидация уровня



#### 3.1.1 EditorPlugin

```gdscript
@tool
extends EditorPlugin

var editor_interface: LevelEditorInterface

func _enter_tree():
    editor_interface = LevelEditorInterface.new()
    add_control_to_bottom_panel(editor_interface, "Level Editor")

func _exit_tree():
    remove_control_from_bottom_panel(editor_interface)
```



#### 3.1.2 Синхронизация слоев

**Проблема:** При редактировании Visual слоя, Collision должен обновляться

**Решение:** Автоматическая синхронизация

```gdscript
class_name LevelEditorSync

func sync_collision_to_visual(collision_layer: TileMapLayer, visual_layer: TileMapLayer):
    """Синхронизирует Collision слой с Visual"""
    for cell in collision_layer.get_used_cells():
        var collision_type = get_collision_type(collision_layer, cell)
        
        # Найти соответствующий визуальный тайл
        var visual_tile = find_visual_tile_for_collision(collision_type, cell)
        visual_layer.set_cell(cell, visual_tile)

func on_visual_tile_placed(cell: Vector2i, tile_id: int):
    """При размещении визуального тайла, обновить collision"""
    var collision_type = get_default_collision_for_tile(tile_id)
    collision_layer.set_cell(cell, collision_type_to_tile_id(collision_type))
```

**Критерии приемки:**

- Плагин загружается в Godot
- Можно редактировать TileMap
- Слои синхронизируются автоматически
- Изменения сохраняются в сцену

**Оценка:** 3-4 дня

### 3.2 Инструменты рисования



#### 3.2.1 Collision Brush

**Файл:** `addons/level_editor/collision_brush.gd`

```gdscript
class_name CollisionBrush

enum BrushType { SOLID, LADDER, ONEWAY, ERASE }

var current_brush: BrushType = BrushType.SOLID
var brush_size: int = 1

func paint(tilemap: TileMapLayer, cell: Vector2i):
    for x in range(brush_size):
        for y in range(brush_size):
            var target = cell + Vector2i(x, y)
            tilemap.set_cell(target, brush_to_tile_id(current_brush))
```



#### 3.2.2 Валидатор уровня

**Файл:** `addons/level_editor/level_validator.gd`

```gdscript
class_name LevelValidator

func validate(level: Node2D) -> Array[String]:
    var errors := []
    
    # Проверить наличие spawn point
    if not level.has_node("Entities/SpawnPoint"):
        errors.append("Missing spawn point")
    
    # Проверить connectivity
    if not is_level_connected(level):
        errors.append("Level has unreachable areas")
    
    # Проверить collision coverage
    var coverage = calculate_collision_coverage(level)
    if coverage < 0.95:
        errors.append("Collision coverage too low: %.2f" % coverage)
    
    return errors
```

**Оценка:** 2-3 дня

### 3.3 Импорт/экспорт



#### 3.3.1 Экспорт в JSON (для совместимости)

**Файл:** `addons/level_editor/export_json.gd`

**Критерии приемки:**

- Можно экспортировать уровень в JSON
- JSON совместим со старым кодом
- Round-trip (export → import) сохраняет данные

**Оценка:** 1 день

---



## 🧪 Фаза 4: Тестирование и валидация (3-4 дня)



### 4.1 Автоматические тесты



#### 4.1.1 Unit тесты для миграции

**Новый файл:** `test/unit/test_tilemap_migration.gd`

#### 4.1.2 Integration тесты

**Файл:** `test/integration/test_level_playable.gd`

**Критерии приемки:**

- Все unit тесты проходят
- Integration тесты проходят
- Визуальное сравнение показывает >95% совпадение
- Уровень играбелен от начала до конца

**Оценка:** 2-3 дня

---



## 📦 Фаза 5: Миграция и cleanup (2-3 дня)



### 5.1 Миграция всех уровней



### 5.2 Удаление старого кода



### 5.3 Обновление документации

**Оценка:** 2-3 дня

---



## 🎓 Фаза 6: Обучение и handoff (1-2 дня)



### 6.1 Документация для разработчиков



### 6.2 Видео-туториал

**Оценка:** 1 день

---



## 📅 Общий таймлайн


| Фаза                       | Длительность | Зависимости  |
| -------------------------- | ------------ | ------------ |
| Фаза 0: Подготовка         | 1-2 дня      | -            |
| Фаза 1: Инверсия пайплайна | 3-5 дней     | Фаза 0       |
| Фаза 2: Разделение слоев   | 2-3 дня      | Фаза 1       |
| Фаза 3: Редактор уровней   | 5-7 дней     | Фаза 2       |
| Фаза 4: Тестирование       | 3-4 дня      | Фаза 1, 2, 3 |
| Фаза 5: Миграция           | 2-3 дня      | Фаза 4       |
| Фаза 6: Обучение           | 1-2 дня      | Фаза 5       |


**Итого: 17-26 дней** (3-4 недели при full-time работе)

---



## ⚠️ Риски и mitigation



### Риск 1: Потеря данных при миграции

**Вероятность:** Средняя  
**Влияние:** Высокое

**Mitigation:**

- Backup всех JSON перед миграцией
- Автоматические тесты сравнения
- Возможность отката через git



### Риск 2: Несовместимость с существующим кодом

**Вероятность:** Средняя  
**Влияние:** Высокое

**Mitigation:**

- Сохранить старые функции как deprecated
- Поддерживать оба пайплайна параллельно 2 недели
- Поэтапное удаление кода

---



## ✅ Критерии успеха



### Технические:

- [x] Все уровни мигрированы на TileMap
- [x] Уровень редактируется в Godot без кода
- [x] Visual и Collision слои независимы
- [ ] Все тесты проходят
- [ ] Производительность не хуже baseline



### Функциональные:

- [x] Можно создать новый уровень за <30 минут
- [x] Можно исправить баг коллизии за <5 минут
- [ ] Уровень играбелен от начала до конца
- [ ] Все существующие фичи работают

---



## 🚀 Следующие шаги

1. **Сегодня:** Создать ветку `refactor/tilemap-migration`
2. **Завтра:** Запустить Phase 0 (аудит и backup)
3. **Эта неделя:** Начать Phase 1.1 (модификация decompose_world.py)
4. **Ревью:** Еженедельные check-ins для оценки прогресса

