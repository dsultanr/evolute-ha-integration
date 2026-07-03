# Evolute Car Card Resources

SVG-файлы для визуализации автомобиля на карточке Home Assistant. Переиспользованы из проекта [prizrak-ha-integration](https://github.com/dsultanr/prizrak-ha-integration) — вид сверху и расположение дверей совпадают.

## Автоматическая установка

Файлы автоматически копируются в `/config/www/evolute/` при запуске интеграции (см. `_setup_www_files` в `__init__.py`).

## Файлы

### car-full.svg
Изображение автомобиля сверху — базовая картинка для `picture-elements` карточки.

### car-perimeter.svg
Голубой контур-подсветка (`#4cb2f1`). В prizrak означал "охрана включена"; здесь используется как индикатор **закрытого центрального замка** (`binary_sensor.evolute_<id>_central_lock` = `off`), поскольку у Evolute нет отдельной сигнализации/охраны — только центральный замок.

### Overlays для открытых дверей (оранжевая подсветка `#ff9800`)
- **door-fl-open.svg** — передняя левая (водительская) дверь → `binary_sensor.evolute_<id>_door_fl`
- **door-fr-open.svg** — передняя правая (пассажирская) дверь → `binary_sensor.evolute_<id>_door_fr`
- **door-rl-open.svg** — задняя левая дверь → `binary_sensor.evolute_<id>_door_rl`
- **door-rr-open.svg** — задняя правая дверь → `binary_sensor.evolute_<id>_door_rr`
- **door-trunk-open.svg** — багажник → `binary_sensor.evolute_<id>_trunk`

`door-hood-open.svg` из prizrak не скопирован — API Evolute не отдаёт статус капота.

## Использование

Полный пример карточки: [examples/car-card.yaml](../../../examples/car-card.yaml). Замените `CAR_ID_HERE` на ID вашего автомобиля.

В отличие от prizrak, кнопки управления (замок/обогрев/охлаждение/сигнал) — обычные `type: button`, без зависимости от HACS `button-card`/`card-mod`, так как у Evolute нет пар "on"/"off" команд — только toggle.

## Кастомизация

Файлы можно редактировать прямо в `/config/www/evolute/`, но при обновлении интеграции они будут перезаписаны — сохраняйте изменения отдельно.
