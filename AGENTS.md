# AGENTS.md — TriGlav Shell

## Язык

Коммуникация — **русский**. Все комментарии, документация, UI-лейблы — на русском.

## Окружение

- **ОС**: Windows 10/11, Windows Server 2016+ (Linux НЕ поддерживается)
- **Git**: `C:\Program Files\Git\cmd\git.exe` (v2.54.0)
- **GitHub**: репозиторий `https://github.com/SKaner-Renaks/TriGlav-Shell`
- **Зеркало**: `C:\ARS\Mimo\TriGlav-Shell` — односторонняя синхронизация из `C:\ARS\Mimo\Task Server`
- **Синхронизация**: копировать файлы в зеркало → `git add . && git commit && git push`
- **Файлы для синхронизации**: `main.py`, `AGENTS.md`, `requirements.txt`, `task.md`, `task_updater.md`, `_data/`, `_module/`
- **Исключается**: `.git/`, `__pycache__/`, `BackUp/`, `_Download/`, `screenshot.PNG`, `*.mp3`

## Запуск

```bash
pip install flask requests psutil ldap3

python main.py                # Shell на :8080 (auth + управление модулями)
```

Для включения/отключения задач (Task Scheduler) нужны права администратора:
```powershell
Start-Process python -ArgumentList '"main.py"' -Verb RunAs
```

## Архитектура

Shell (Flask, port 8080) управляет модулями через auto-discovery и subprocess. Каждый модуль — отдельный Flask без auth. Shell проксирует запросы через `/proxy/<port>/`.

```
main.py              Ядро Shell           (port 8080)   VERSION = '1.5.5'
_data/
  config.cfg         Глобальные настройки (INI)
  manifest.json      Манифест Shell
  encrypt.py         Шифрование care.env (XOR+base64)
  care.env           Хранилище секретов (auto-created)
  log_file.log       Лог Shell (Development mode)
  hystory.md         История изменений Shell
  _lang/             Локализация (ru.json, en.json)
  _ps/               PowerShell скрипты Shell
  _images/           SVG-иконки (gear, developer_board)
_module/             Автообнаружение модулей
  monitor/           Мониторинг сервера  (port 5005)   v1.5.2   type=usual
  task_scheduler/    Планировщик задач   (port 5008)   v2.4.8   type=usual
  control/           Панель управления   (port 5003)   v1.5.2   type=usual
  invaders/          Космические захватчики (port 5004) v1.2.2   type=game
  snake/             Змейка              (port 5007)   v1.2.2   type=game
  flip_clock/        Flip Clock          (port 5042)   v1.1.2   type=game
  mp3_player/        MP3 Player          (port 5009)   v1.1.2   type=game
  smb_explorer/      SMB Explorer        (port 5006)   v3.2.2   type=usual
  _deps_checker/     Проверка зависимостей (port 5000) v1.2.4   type=service
  _module_manager/   Управление модулями (port 5001)   v1.4.0   type=service (requires_admin)
  _updater/          Обновления и Бекапы (port 5002) v1.4.9  type=service
```

> **⚠ DISCREPANCY**: `main.py` строка 24 содержит `VERSION = '1.5.5'`.

## Типы модулей

| Тип | Описание | Папка | Цвет в sidebar | Автозапуск |
|-----|----------|-------|----------------|------------|
| `shell` | Ядро оболочки | корень | — | — |
| `usual` | Обычный модуль | `_module/name/` | стандартный | через config |
| `service` | Сервисный модуль | `_module/_name/` | оранжевый | через config |
| `game` | Игровой модуль | `_module/name/` | зелёный | через config |

Префикс `_` в имени папки = сервисный модуль.

## Создание модуля

### Структура

```
_module/[name]/
  main.py           # Flask-приложение
  manifest.json     # Метаданные модуля
  requirements.txt  # Зависимости
  description.md    # Описание модуля (версия, структура, API)
  hystory.md        # История изменений
```

### manifest.json — обязательные поля

```json
{
  "name": "my_module",
  "title": "Название модуля",
  "version": "1.0",
  "description": "Описание",
  "type": "usual",
  "requires_admin": false,
  "current_port": 5009,
  "languages": ["ru", "en"],
  "current_settings": {},
  "default_settings": {},
  "mode": "development"
}
```

### Требования к модулю

1. Flask-приложение с `argparse`: принимает `--host`, `--port`, `--environment production|development`, опционально `--log`
2. **Без auth** — авторизацию обеспечивает Shell
3. Тема: Proxmox-style dark (#1a1a1a, #262626, #47a8ff)
4. `requirements.txt` с зависимостиями (обычно `flask>=3.0`)
5. Версия в заголовке скрипта: `VERSION = 'x.y.z'`
6. **manifest.json БЕЗ BOM** — PowerShell `Set-Content -Encoding UTF8` добавляет BOM, который ломает `json.load()`. Использовать Python для записи манифестов.

## Ключевые особенности

### Production vs Development

- **Production**: модули на `127.0.0.1`, доступ только через Shell proxy
- **Development**: модули на `0.0.0.0`, доступны напрямую + логирование

### Development Block

Блок информации о модуле в content header называется **Development Block** — блок разработчика. Показывает иконку `developer_board.svg` + "Development". Отображает порт модуля, кнопки управления (Restart, Web, Folder, Log). Доступен только в Development mode.

### Development Zone Labels

В режиме `development` каждая UI-зона в Shell и модулях должна иметь атрибут `data-zone="module.zone_name"`. При наведении мыши (после 500ms задержки) появляется floating label `:: module.zone_name`. При движении мыши — исчезает.

**Правила именования зон:**
- Формат: `{module_name}.{zone}` — lowercase, underscore для пробелов
- Зоны могут быть вложенные: `module.parent.child.subchild` — чем глубже вложенность, тем длиннее формат
- Namespace = имя модуля из `manifest.json`. Для Shell = `shell`
- Примеры: `shell.top_bar`, `monitor.cpu_chart`, `mp3_player.cover`, `smb.tab_files`
- Примеры вложенных: `task_scheduler.modal.create.confirm`, `smb.tab_files.row.actions`, `shell.settings.panel.auth`

**Обязательные зоны для каждого модуля:**
- Заголовок: `module.header`
- Основные панели/блоки: `module.{panel_name}`
- Таблицы: `module.{table_name}`
- Модальные окна: `module.modal.{name}`
- Canvas/game: `module.game`, `module.canvas`

**Реализация:**
- Shell: `data-zone` на элементах SHELL_TEMPLATE + LOGIN_TEMPLATE, debug snippet в `{% if environment == 'development' %}`
- Модули: `data-zone` на элементах HTML-шаблона, `--environment` аргумент в argparse, `environment=args.environment` в `render_template_string()`
- Debug snippet: CSS `.dev-label` + JS с `setTimeout(500ms)`, hide on `mousemove`
- При добавлении нового UI-элемента — **обязательно** добавлять `data-zone` если элемент является зоной/панелью/таблицей/модалкой

### Reverse Proxy

Shell проксирует HTML-ответы модулей, перезаписывая относительные URL для маршрутизации через `/proxy/<port>/`. Модули не должны использовать абсолютные пути в `fetch()`, `src=`, `href=`.

### Proxy bypass

Системный прокси Windows (`ProxyServer=http://127.0.0.1:12334`) перехватывает запросы `requests`. В `proxy()` функции добавлен `proxies={'http': None, 'https': None}` для обхода прокси при запросах к модулям.

### Автозапуск (config.cfg)

```ini
[modules_auto_start]
usual = all                    # или: monitor,control,task_scheduler
service = all                  # или: deps_checker,module_manager,updater
game = all                     # или: snake,invaders
```

### Порты

- Production: Shell сканирует свободные порты, начиная с 5000. `current_port` в manifest.json перезаписывается.
- Development: порты из manifest.json используются как есть.
- Shell проверяет: если `current_port` пустой или `0` — генерирует порт через `5000 + hash(name) % 100`.

### Порядок модулей

Порядок отображения в sidebar сохраняется в `config.cfg` секция `[module_order]`. Пользователь может перетаскиванием (drag-drop) менять порядок — фронтенд отправляет `POST /api/module_order` с массивом имён. При старте Shell сортирует модули по этому списку.

### Логирование

Только в Development mode. Включается чекбоксом Log в content header. Модуль перезапускается с флагом `--log`, пишет в `log_file.log` в своей папке. Состояние чекбокса сохраняется в `config.cfg` секция `[log_enabled]`.

### Log file naming

- Лог-файл модуля = `<папка_модуля>/log_file.log`
- Лог Shell = `_data/log_file.log`
- Единое имя для всех

### Доступ модулей к конфигу Shell

Модули вычисляют путь к конфигу Shell через `os.path.dirname(os.path.dirname(BASE_DIR))` (два уровня вверх от папки модуля). Не импортируют общий конфиг — читают `config.cfg` напрямую через `configparser`.

### Шаблоны HTML

Shell и модули хранят HTML-шаблоны прямо в Python-кодах (`render_template_string`). Отдельных `.html` файлов нет.

### module_manager

- Сервисный модуль с `requires_admin: true`
- Показывает порты и статус запуска всех модулей (запрашивает Shell API через `requests`)
- Кнопка **Restart** для каждого модуля (блокируется при включённой блокировке для сервисных)
- Кнопка **Remove** с модальным подтверждением для сервисных модулей
- Колонка **Версия** в таблицах модулей
- **Стили disabled**: `opacity:0.3; cursor:not-allowed; border-color:#666; color:#666`

### _updater

- Сервисный модуль, скачивает архив репозитория с GitHub
- `get_shell_port()` — читает порт Shell из `config.cfg` (не хардкодит 8080)
- `--log` флаг — управление логированием через Shell UI
- `download_lock` (threading.Lock) — потокобезопасность `download_state`
- Распаковка ZIP обёрнута в try/except — очистка `EXTRACT_DIR` при ошибке
- Остановка/запуск сервисных модулей через Shell API

## Gotchas

- **Git push**: НЕ пушить на GitHub без явного разрешения пользователя. Всегда спрашивать перед `git push`.

- **PowerShell encoding**: русская Windows использует cp866. Декодировать через `.decode('cp866', errors='replace')`.
- **Task enable/disable**: `schtasks /Change` не работает для задач с RunLevel=Highest. Использовать `Enable-ScheduledTask`/`Disable-ScheduledTask` (PowerShell cmdlets).
- **SSD detection**: `Win32_DiskDrive.MediaType` не различает SSD/HDD. Использовать `Get-PhysicalDisk.MediaType`.
- **GPU metrics**: WMI `Win32_VideoController.Utilization` возвращает null. Использовать `nvidia-smi`.
- **Firewall**: Shell проверяет порт при старте и предупреждает, если не открыт.
- **PS1-скрипты**: Shell-скрипты в `_data/_ps/`, модульные — в папках модулей.
- **config.cfg**: хранится в `_data/config.cfg`. Модули **не** импортируют общий конфиг.
- **encrypt.py**: только XOR+base64. care.env auto-created с дефолтами admin/admin.
- **Manifest BOM**: PowerShell `Set-Content -Encoding UTF8` добавляет BOM. Использовать Python или `System.Text.UTF8Encoding $false` для записи JSON без BOM.
- **Folder button**: `ShellExecuteW` с `SW_SHOWNORMAL` не гарантирует foreground. Использовать `EnumWindows` + `SetForegroundWindow` + `BringWindowToTop`.
- **Dev zone labels**: при добавлении нового UI-элемента в Development mode — добавлять `data-zone="module.name"` на элемент. Debug snippet автоматически покажет label при наведении.
- **MP3 файлы**: на GitHub **не выгружать** `*.mp3` файлы. Локально хранятся в `_module/mp3_player/music/`. Добавлено в `.gitignore`.
- **description.md**: каждый модуль имеет `description.md` с текущей версией, описанием структуры, API и замечаниями. Обновлять при изменении модуля.
- **hystory.md**: каждый модуль имеет `hystory.md` с историей изменений. Добавлять запись при каждом изменении.

## Code Conventions

- Метаданные модуля в `manifest.json`, конфиг Shell — в `config.cfg`
- Shell-маршруты используют `@login_required`
- Сервисные модули: папка с `_`, оранжевый цвет в sidebar
- Обычные модули: папка без префикса, стандартный цвет
- Бекапы: `BackUp/YYYYMMDD-N/`
- Локализация: fallback ru → en → raw keys
- Каждый модуль и Shell имеют свой `requirements.txt`
- Манифесты писать через Python `json.dump()` — без BOM, с `ensure_ascii=False`
