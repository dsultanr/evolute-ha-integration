# Инструкция по установке Evolute HA Integration

## Вариант 1: Локальная установка

### Шаг 1: Копирование файлов
```bash
# Скопируйте папку custom_components/evolute в директорию Home Assistant
cp -r custom_components/evolute /path/to/homeassistant/custom_components/

# Например, если Home Assistant установлен в /home/homeassistant/.homeassistant:
cp -r custom_components/evolute /home/homeassistant/.homeassistant/custom_components/
```

### Шаг 2: Перезапуск Home Assistant
```bash
sudo systemctl restart home-assistant@homeassistant
# Или через UI: Settings → System → Restart
```

### Шаг 3: Получение токенов
1. Откройте https://app.evassist.ru в браузере и войдите (телефон + SMS-код)
2. Откройте DevTools (F12) → Application/Storage → Cookies → `app.evassist.ru`
3. Скопируйте значения `evy-platform-access` и `evy-platform-refresh`

### Шаг 4: Добавление интеграции
1. Откройте Home Assistant
2. Перейдите в **Settings** → **Devices & Services**
3. Нажмите **"+ ADD INTEGRATION"**
4. Найдите **"Evolute"**
5. Вставьте Access Token и Refresh Token
6. Нажмите **Submit**

## Вариант 2: Установка через HACS

### Предварительные требования
1. Установлен HACS в Home Assistant

### Шаги:

#### 1. Добавьте в HACS
1. Откройте HACS в Home Assistant
2. Перейдите в "Integrations"
3. Нажмите три точки (⋮) → "Custom repositories"
4. URL: `https://github.com/dsultanr/evolute-ha-integration`
5. Category: "Integration"
6. Нажмите "Add"

#### 2. Установите интеграцию
1. Найдите "Evolute" в HACS
2. Нажмите "Download"
3. Перезапустите Home Assistant
4. Добавьте интеграцию через Settings → Devices & Services (см. Шаг 3-4 выше)

## Проверка установки

### 1. Проверьте логи
```bash
tail -f /home/homeassistant/.homeassistant/home-assistant.log | grep evolute
```

### 2. Проверьте наличие сенсоров
1. Перейдите в **Developer Tools** → **States**
2. Найдите сенсоры `sensor.evolute_*`, `binary_sensor.evolute_*`, `button.evolute_*`, `device_tracker.evolute_*`

### 3. Проверьте устройства
1. Перейдите в **Settings** → **Devices & Services** → **Evolute**
2. Должны отображаться ваши автомобили

## Удаление интеграции

### Через UI (рекомендуется)
1. Settings → Devices & Services
2. Найдите "Evolute"
3. Нажмите три точки (⋮) → "Delete"

### Вручную
```bash
rm -rf /path/to/homeassistant/custom_components/evolute
sudo systemctl restart home-assistant@homeassistant
```

## Устранение проблем

### Интеграция не появляется в списке
1. Проверьте, что папка `custom_components/evolute` существует
2. Проверьте права доступа: `chmod -R 755 custom_components/evolute`
3. Перезапустите Home Assistant
4. Очистите кеш браузера (Ctrl+Shift+R)

### Ошибки аутентификации / запрос повторной авторизации
1. Убедитесь, что токены скопированы без лишних пробелов и переносов строк
2. Если интеграция запросила reauth — `refresh_token` был отозван сервером, получите новые токены из браузера
3. Проверьте логи: Settings → System → Logs

### Сенсоры показывают "unavailable"
1. Проверьте интернет-соединение
2. Проверьте доступность app.evassist.ru и видимость автомобиля в приложении
3. Проверьте логи на наличие HTTP-ошибок
4. Попробуйте удалить и заново добавить интеграцию

## Дополнительная информация

- **Документация**: [README.md](README.md)
- **GitHub**: https://github.com/dsultanr/evolute-ha-integration
- **Issues**: https://github.com/dsultanr/evolute-ha-integration/issues
