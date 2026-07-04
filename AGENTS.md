# AGENTS.md — TriGlav Shell

## Язык

Коммуникация — **русский**. Все комментарии, документация, UI-лейблы — на русском.

## Окружение

- **ОС**: Windows 10/11, Windows Server 2016+ (Linux НЕ поддерживается)
- **Git**: `C:\Program Files\Git\cmd\git.exe` (v2.54.0)
- **GitHub**: репозиторий `https://github.com/SKaner-Renaks/TriGlav-Shell`
- **Зеркало**: `C:\ars\mimo\TriGlav-Shell` — односторонняя синхронизация из `C:\ars\mimo\Task Server`
- **Синхронизация**: копировать файлы в зеркало → `git add . && git commit && git push`
- **Файлы для синхронизации**: `main.py`, `AGENTS.md`, `requirements.txt`, `task.md`, `task_updater.md`, `_data/`, `_module/`
- **Исключается**: `.git/`, `__pycache__/`, `BackUp/`, `_Download/`, `screenshot.PNG`

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
main.py              Ядро Shell           (port 8080)   VERSION = '1.2.7'
_data/
  config.cfg         Глобальные настройки (INI)
  manifest.json      Манифест Shell
  encrypt.py         Шифрование care.env (XOR+base64)
  care.env           Хранилище секретов (auto-created)
  _lang/             Локализация (ru.json, en.json)
  _ps/               PowerShell скрипты Shell
  _images/           SVG-иконки
_module/             Автообнаружение модулей
  monitor/           Мониторинг сервера  (port 5001)   v1.5     type=usual
  task_scheduler/    Планировщик задач   (port 5002)   v2.4.5   type=usual
  control/           Панель управления   (port 5004)   v1.4     type=usual
  invaders/          Космические захватчики (port 5005) v1.2    type=game
  snake/             Змейка              (port 5006)   v1.2     type=game
  _deps_checker/     Проверка зависимостей (port 5007) v1.2.2  type=service
  _module_manager/   Управление модулями (port 5008)   v1.2.1  type=service
  _updater/          Обновления из GitHub (port 5009)  v1.4.1  type=service
```

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
  "default_settings": {}
}
```

### Требования к модулю

1. Flask-приложение с `argparse`: принимает `--host`, `--port`, опционально `--log`
2. **Без auth** — авторизацию обеспечивает Shell
3. Тема: Proxmox-style dark (#1a1a1a, #262626, #47a8ff)
4. `requirements.txt` с зависимостиями (обычно `flask>=3.0`)
5. Версия в заголовке скрипта: `VERSION = 'x.y.z'`

## Ключевые особенности

### Production vs Development

- **Production**: модули на `127.0.0.1`, доступ только через Shell proxy
- **Development**: модули на `0.0.0.0`, доступны напрямую + логирование

### Reverse Proxy

Shell проксирует HTML-ответы модулей, перезаписывая относительные URL для маршрутизации через `/proxy/<port>/`. Модули не должны использовать绝对ные пути в `fetch()`, `src=`, `href=`.

### Автозапуск (config.cfg)

```ini
[modules_auto_start]
usual = all                    # или: monitor,control,task_scheduler
service = all                  # или: deps_checker
game = all                     # или: snake,invaders
```

### Порты

- Production: Shell сканирует свободные порты, начиная с 5000. `current_port` в manifest.json перезаписывается.
- Development: порты из manifest.json используются как есть.

### Логирование

Только в Development mode. Включается чекбоксом Log в content header. Модуль перезапускается с флагом `--log`, пишет в `module.log` в своей папке.

## Gotchas

- **PowerShell encoding**: русская Windows использует cp866. Декодировать через `.decode('cp866', errors='replace')`.
- **Task enable/disable**: `schtasks /Change` не работает для задач с RunLevel=Highest. Использовать `Enable-ScheduledTask`/`Disable-ScheduledTask` (PowerShell cmdlets).
- **SSD detection**: `Win32_DiskDrive.MediaType` не различает SSD/HDD. Использовать `Get-PhysicalDisk.MediaType`.
- **GPU metrics**: WMI `Win32_VideoController.Utilization` возвращает null. Использовать `nvidia-smi`.
- **Firewall**: Shell проверяет порт при старте и предупреждает, если не открыт.
- **requires_admin**: UI показывает статус админа, кнопка «Restart as Admin» использует `ShellExecuteW` + `runas`.
- **PS1-скрипты**: Shell-скрипты в `_data/_ps/`, модульные — в папках модулей.
- **config.cfg**: хранится в `_data/config.cfg`. Модули **не** импортируют общий конфиг.
- **encrypt.py**: только XOR+base64. care.env auto-created с дефолтами admin/admin.

## Code Conventions

- Метаданные модуля в `manifest.json`, конфиг Shell — в `config.cfg`
- Shell-маршруты используют `@login_required`
- Сервисные модули: папка с `_`, оранжевый цвет в sidebar
- Обычные модули: папка без префикса, стандартный цвет
- Бекапы: `BackUp/YYYYMMDD-N/`
- Локализация: fallback ru → en → raw keys
- Каждый модуль и Shell имеют свой `requirements.txt`
