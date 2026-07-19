# Описание модуля _updater

**Дата создания**: 16.07.2026 21:30
**Последнее обновление**: 16.07.2026 22:00
**Версия модуля**: 1.4.3

---

## Общая структура

Flask-приложение на порту `5002`. Сервисный модуль (`type: service`), `requires_admin: false`. Скачивает архив репозитория с GitHub, распаковывает, сравнивает версии модулей, обновляет или устанавливает их.

## Константы

| Переменная | Значение |
|---|---|
| `REPO_URL` | `https://github.com/SKaner-Renaks/TriGlav-Shell` |
| `ARCHIVE_URL` | `https://github.com/SKaner-Renaks/TriGlav-Shell/archive/refs/heads/main.zip` |
| `DOWNLOAD_DIR` | `{SHELL_DIR}/_Download` |
| `ZIP_PATH` | `{DOWNLOAD_DIR}/repo.zip` |
| `EXTRACT_DIR` | `{DOWNLOAD_DIR}/TriGlav-Shell-main` |

## Ключевые функции

### get_local_modules()

Сканирует `_module/` + `_data/manifest.json`. Возвращает список словарей с добавленными полями `_local_path` и `_is_shell`. Shell добавляется первым элементом.

### get_repo_modules()

Читает манифесты из распакованного архива `EXTRACT_DIR/_module/`. Возвращает список с добавленными полями `_repo_name`, `_repo_path`. Shell берётся отдельно из `EXTRACT_DIR/_data/manifest.json`.

### download_archive()

Скачивает ZIP с GitHub в потоковом режиме с прогрессом (8KB чанки). Состояние хранится в глобальном `download_state` (status, percent, message). Распаковывает через `zipfile`. Обрабатывает `ConnectionError` и `HTTPError`.

### copy_module_from_repo(module_name, dest_dir)

Находит реальную директорию модуля в архивах по имени из манифеста. Копирует через `_copy_tree()` с retry при `PermissionError` (3 попытки, пауза 2 сек). Верифицирует количество скопированных файлов.

### _copy_tree(src, dst)

Рекурсивное копирование дерева каталогов через `shutil.copy2()`.

## API эндпоинты

| Роут | Метод | Описание |
|---|---|---|
| `/` | GET | Главная страница UI |
| `/api/config` | GET | Возвращает `modules_auto_start` из config.cfg |
| `/api/download` | POST | Запуск скачивания архива (в отдельном потоке) |
| `/api/download/status` | GET | Прогресс скачивания (polling каждые 500мс) |
| `/api/scan` | GET | Сравнение локальных и репозиторных модулей |
| `/api/install` | POST | Установка новых модулей из архива |
| `/api/update` | POST | Обновление выбранных модулей |

## Логика обновления (/api/update)

1. Если `type == 'shell'` — пропускает (требует ручного перезапуска)
2. Если `type == 'service'` — останавливает через Shell API (`POST /api/module/{name}/stop`), ждёт 3 сек
3. Находит реальную директорию модуля (с учётом префикса `_` у сервисных)
4. Копирует из архива через `copy_module_from_repo()`
5. Если `type == 'service'` и обновление успешно — запускает через Shell API (`POST /api/module/{name}/start`)

## Логика установки (/api/install)

1. Находит реальную директорию модуля в архиве по имени из манифеста
2. Если директория уже существует — пропускает (статус `exists`)
3. Копирует в `_module/{src_name}`

## UI

- Proxmox-style dark тема (#1a1a1a, #262626, #47a8ff)
- Таблица "Установленные объекты": checkbox, Type, Status (on/off), Name, Title, Local ver, Repo ver, Status (Ok/Need Update/Attention)
- Таблица "Новые модули": модули из репозитория, которых нет локально
- Поиск по обеим таблицам
- Модальное окно прогресса с progress bar
- Кнопка "Get" — скачивание архива
- Кнопка "Обновить" — обновление выбранных модулей
- Кнопка "Установить" — установка новых модулей

## Development Zone Labels (5 зон)

- `updater.header` — заголовок
- `updater.repo_url` — поле URL репозитория
- `updater.installed_table` — таблица установленных
- `updater.new_table` — таблица новых
- `updater.modal.progress` — модальное окно прогресса

## Исправления (v1.4.3)

1. **args module-level**: `parser` и `args` определены на уровне модуля (строки 17-22), а не в `__main__`. Модуль безопасно импортируется как библиотека.
2. **--log support**: добавлен `--log` флаг (строка 21) + `logging.basicConfig` (строки 39-42). Логирование управляется через Shell UI.
3. **get_shell_port()**: функция (строка 60-62) читает порт Shell из `config.cfg` секция `[shell] port`. Используется в `api_update()` вместо хардкода `8080`.
4. **Extraction cleanup**: распаковка ZIP обёрнута в `try/except` (строки 173-178) с удалением `EXTRACT_DIR` при ошибке.
5. **Thread-safe download_state**: `download_lock = threading.Lock()` (строка 34) используется при чтении/записи `download_state` в `download_archive()`, `api_download()`, `api_download_status()`.

## Замечания (устаревшие, исправлены)

1. `args` используется до определения в строке 614 (`environment=args.environment`), но работает т.к. модуль запускается только через `__main__`
2. Нет аргумента `--log` — в отличие от других модулей, `_updater` не поддерживает переключение логирования через UI Shell
3. Hardcoded Shell port `127.0.0.1:8080` в строках 714, 746 — если Shell на другом порту, stop/start не сработает
4. Нет очистки `_Download` при ошибке распаковки — `EXTRACT_DIR` может оказаться в неполном состоянии
5. `download_state` — глобальная переменная, не потокобезопасна (CPython GIL спасает, но формально — race condition)
