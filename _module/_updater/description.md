# Описание модуля _updater

**Дата создания**: 16.07.2026 21:30
**Последнее обновление**: 16.07.2026
**Версия модуля**: 1.4.8

---

## Общая структура

Flask-приложение на порту `5002`. Сервисный модуль (`type: service`), `requires_admin: false`. Скачивает архив репозитория с GitHub, распаковывает, сравнивает версии модулей, обновляет или устанавливает их. Также обеспечивает полный бекап проекта.

## Константы

| Переменная | Значение |
|---|---|
| `REPO_URL` | `https://github.com/SKaner-Renaks/TriGlav-Shell` |
| `ARCHIVE_URL` | `https://github.com/SKaner-Renaks/TriGlav-Shell/archive/refs/heads/main.zip` |
| `DOWNLOAD_DIR` | `{SHELL_DIR}/_Download` |
| `ZIP_PATH` | `{DOWNLOAD_DIR}/repo.zip` |
| `EXTRACT_DIR` | `{DOWNLOAD_DIR}/TriGlav-Shell-main` |
| `BACKUP_DIR` | `{SHELL_DIR}/_BackUp` |
| `EXCLUDE_DIRS` | `.git, __pycache__, BackUp, _BackUp, _Download, .mimocode` |
| `EXCLUDE_EXTS` | `.mp3, .log` |

## SVG-иконки

| Константа | Файл | Описание |
|---|---|---|
| `SVG_ICON` | `cloud_download.svg` | Статус доступности репозитория |
| `SVG_BACKUP_ICON` | `cloud_upload.svg` | Иконка зоны бекапа |

## Ключевые функции

### get_local_modules()

Сканирует `_module/` + `_data/manifest.json`. Возвращает список словарей с добавленными полями `_local_path` и `_is_shell`. Shell добавляется первым элементом.

### get_repo_modules()

Читает манифесты из распакованного архива `EXTRACT_DIR/_module/`. Возвращает список с добавленными полями `_repo_name`, `_repo_path`. Shell берётся отдельно из `EXTRACT_DIR/_data/manifest.json`.

### download_archive()

Скачивает ZIP с GitHub в потоковом режиме с прогрессом (8KB чанки). Состояние хранится в глобальном `download_state` (status, percent, message). Распаковывает через `zipfile`. Обрабатывает `ConnectionError` и `HTTPError`.

### create_backup(dest_dir)

Создаёт полный архив проекта. Подсчитывает файлы, создаёт .zip с прогрессом, записывает .log, добавляет .log внутрь .zip. Ошибки доступа логируются, процесс не прерывается. Имя архива: `full_BackUp_DDMMYY_HHMM.zip`.

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
| `/api/repo/check` | GET | Проверка доступности репозитория (HEAD-запрос) |
| `/api/scan` | GET | Сравнение локальных и репозиторных модулей |
| `/api/install` | POST | Установка новых модулей из архива |
| `/api/update` | POST | Обновление выбранных модулей |
| `/api/backup` | POST | Запуск бекапа (в отдельном потоке) |
| `/api/backup/status` | GET | Прогресс бекапа |
| `/api/backup/files` | GET | Список бекапов + очистка осиротевших логов |
| `/api/backup/file` | GET | Скачивание файла бекапа |
| `/api/backup/log` | GET | Чтение содержимого лог-файла |
| `/api/backup/delete` | POST | Удаление файлов бекапа (zip + log) |

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

## Логика бекапа

### Исключения при архивации

Не архивируются: `.git/`, `__pycache__/`, `BackUp/`, `_BackUp/`, `_Download/`, `.mimocode/`, `*.mp3`, `*.log`

### Формат имени

`full_BackUp_DDMMYY_HHMM.zip` + `.log`

### Очистка осиротевших логов

При запросе `/api/backup/files` — .log файлы без соответствующего .zip удаляются автоматически.

## UI

- Proxmox-style dark тема (#1a1a1a, #262626, #47a8ff)
- Таблица "Установленные объекты": checkbox, Type, Status (on/off), Name, Title, Local ver, Repo ver, Status (Ok/Need Update/Attention)
- Таблица "Новые модули": модули из репозитория, которых нет локально
- Поиск по обеим таблицам
- Модальное окно прогресса с progress bar
- Кнопка "Get" — скачивание архива
- Кнопка "Обновить" — обновление выбранных модулей
- Кнопка "Установить" — установка новых модулей
- **Зона `updater.get_online`** — проверка доступности репозитория (облачная иконка, debounce 1с)
- **Зона `updater.backup`** — бекап проекта (icon + path + "BackUp Full")
- **Модалка `updater.modal.backup`** — список бекапов (таблица + Download/Delete/Cancel)
- **Модалка `updater.modal.log`** — просмотр лог-файла с прокруткой

## Development Zone Labels

- `updater.header` — заголовок
- `updater.repo_url` — поле URL репозитория
- `updater.get_online` — зона проверки репозитория (icon + input + Get)
- `updater.installed_table` — таблица установленных
- `updater.new_table` — таблица новых
- `updater.modal.progress` — модальное окно прогресса
- `updater.backup` — зона бекапа (icon + path + BackUp Full)
- `updater.modal.backup` — модалка списка бекапов
- `updater.modal.log` — модалка просмотра лога
