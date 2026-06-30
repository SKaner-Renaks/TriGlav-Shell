# AGENTS.md — TriGlav Shell

## Language
Communication language — **Russian**. All comments, docs, UI labels — русский.

## Task Requirements

Полное ТЗ находится в файле `task.md`. Ниже — статус реализации по состоянию на текущую версию.

### Выполнено (~85%)
- **§1-2**: Цель, стек, Windows-окружение, Proxmox тема
- **§3**: Единая авторизация в Shell, модули без auth, Production/Development режимы
- **§4**: Структура каталогов (main.py, config.cfg, encrypt.py, care.env, _lang/, _module/)
- **§5.1**: config.cfg — port, auth_mode, environment, global_refresh_interval, global_theme, allowed_ips
- **§5.2**: manifest.json — name, title, version, description, type, requires_admin, current_port, languages, settings
- **§5.3**: encrypt.py — шифрование care.env, динамические методы, auto-create с дефолтами
- **§6.1**: Автообнаружение модулей, выделение портов, subprocess.Popen с --host/--port
- **§6.2**: Авторизация — AD (ldap3) + local, @login_required на маршрутах Shell
- **§6.3**: Локализация Shell — _lang/ru.json, en.json, fallback ru→en→raw keys
- **§6.4**: Настройки и сброс — кнопка «Шестерёнка», сброс модуля/консоли
- **§6.5**: UI — 4 зоны, splitter с drag-to-resize, localStorage для ширины, iframe
- **§7**: Адаптация control, monitor, task_server как модулей в _module/
- **§8**: Бекап старых файлов в BackUp/
- **v1.2**: Reverse proxy для удалённого доступа, проверка firewall, визуализация запуска
- **v1.2.1**: Версионность, requirements.txt для всех модулей
- **v1.2.1+**: Модули проверки зависимостей, визуализация перезапуска модулей
- **v1.2.2**: Типы модулей (shell/usual/service), автозапуск по типу, service-стилизация
- **v1.2.3**: Оптимизация скорости загрузки модулей, модуль управления модулями

### НЕ сделано / требует доработки

**§5.3 encrypt.py:**
- ❌ Нет заглушек для будущих методов шифрования (AES/Fernet) — только XOR+base64

**§6.1 Auto-discovery:**
- ❌ `requires_admin = true` не реализован через `ShellExecuteW` + `runas` (только UI кнопка)

**§6.2 Авторизация:**
- ❌ Нет ролей/групп AD для управления видимостью модулей

**§6.3 Локализация:**
- ❌ Модули не имеют自己的 `_lang/` — локализация только в Shell

**§6.5 UI Shell:**
- ❌ Нет полноценной панели настроек (auth_mode, environment, language, port, theme)

**§6.6 Restart:**
- ❌ Нет программного перезапуска Shell при изменении настроек
- ❌ Нет long-polling health-check для автообновления страницы

---

## Architecture

Shell-оболочка управляет модулями через auto-discovery и subprocess. Каждый модуль — отдельный Flask без auth. Shell проксирует запросы к модулям через `/proxy/<port>/`.

```
main.py              Ядро Shell        (port 8080)   VERSION = '1.2.3'
manifest.json        Манифест Shell
config.cfg           Глобальные настройки (INI)
encrypt.py           Шифрование care.env (XOR+base64)
care.env             Хранилище секретов (auto-created)
_lang/               Локализация (ru.json, en.json)
_ps/                 PowerShell скрипты Shell
  _check_fw.ps1      Проверка файервола
_module/             Автообнаружение модулей
  task_scheduler/    Планировщик задач   (port 5002)   v2.4.4  type=usual
  monitor/           Мониторинг сервера  (port 5001)   v1.4    type=usual
  control/           Панель управления   (port 5004)   v1.3    type=usual
  snake/             Змейка              (port 5006)   v1.1    type=usual
  invaders/          Космические захватчики (port 5005) v1.1    type=usual
  _deps_checker/     Проверка зависимостей (port 5007) v1.2.1  type=service
  _module_manager/   Управление модулями (port 5008)   v1.0    type=service
```

---

## Создание модулей

### Типы модулей

| Тип | Описание | Папка | Цвет в sidebar | Автозапуск |
|-----|----------|-------|----------------|------------|
| `shell` | Ядро оболочки | корень | — | — |
| `usual` | Обычный модуль | `_module/name/` | стандартный | через config |
| `service` | Сервисный модуль | `_module/_name/` | оранжевый (hover) | через config |

### Именование папок

- **Обычные модули**: `_module/task_scheduler/`, `_module/monitor/`
- **Сервисные модули**: `_module/_deps_checker/`, `_module/_module_manager/`
- Префикс `_` = сервисный модуль

### Структура модуля

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
  "description": "Описание модуля",
  "type": "usual",
  "requires_admin": false,
  "current_port": 5009,
  "languages": ["ru", "en"],
  "current_settings": {},
  "default_settings": {}
}
```

### Требования к модулю

1. **Flask-приложение**: принимает `--host` и `--port` через argparse
2. **Без auth**: авторизацию обеспечивает Shell
3. **Тема**: Proxmox-style dark theme (#1a1a1a, #262626, #47a8ff)
4. **requirements.txt**: указать зависимости (обычно `flask>=3.0`)
5. **PS1-скрипты**: если нужны — в папке модуля (не в корне)

### Требования к отображению в Shell

- Обычные модули: стандартный фон в sidebar
- Сервисные модули: оранжевый фон при наведении и выборе
- Отключённые модули: НЕ отображаются в sidebar Shell
- Модуль Manager (`_module_manager`): отображает ВСЕ модули (включая отключённые)

### Конфиг автозапуска (config.cfg)

```ini
[modules_auto_start]
usual = all                    # или: monitor,control,task_scheduler
service = all                  # или: deps_checker
```

---

## Running

```bash
python -m pip install flask requests psutil ldap3

python main.py                # Shell on :8080 (auth + module management)
```

Модули запускаются Shell автоматически при выборе в UI.

Admin rights needed for task enable/disable:
```powershell
Start-Process python -ArgumentList '"main.py"' -Verb RunAs
```

## Key Gotchas

- **PowerShell encoding**: Russian Windows uses cp866. Decode with `.decode('cp866', errors='replace')`.
- **Task enable/disable**: `schtasks /Change` fails for RunLevel=Highest tasks. Use `Enable-ScheduledTask`/`Disable-ScheduledTask` PowerShell cmdlets.
- **SSD detection**: `Win32_DiskDrive.MediaType` can't distinguish SSD from HDD. Use `Get-PhysicalDisk.MediaType` instead.
- **GPU metrics**: WMI `Win32_VideoController.Utilization` returns null. Use `nvidia-smi` CLI.
- **Production mode**: All modules bind to `127.0.0.1`. External access only through Shell proxy.
- **Development mode**: Modules bind to `0.0.0.0`. Accessible directly.
- **Firewall**: Shell checks if port is open on startup and warns if not.
- **Proxy**: Shell rewrites relative URLs in module HTML to route through `/proxy/<port>/`.
- **requires_admin**: UI shows admin status, "Restart as Admin" button uses ShellExecuteW + runas.
- **PS1 files**: `_check_fw.ps1` в `_ps/`, модульные PS1 в папках модулей.

## Code Conventions

- Shell config in `config.cfg` only — modules don't import shared config
- Module metadata in `manifest.json` (name, title, version, description, type, port, settings)
- Modules accept `--host` and `--port` via argparse
- Modules have NO auth — Shell handles authentication
- Version string in script header: `VERSION = 'x.y.z'`
- All Shell API routes use `@login_required` decorator
- Backup files: `BackUp/YYYYMMDD-N/` directory
- Each module and shell has its own `requirements.txt`
- При перезапуске модуля через Shell показывается спиннер с текстом «Перезапуск модуля...»
- Сервисные модули: папка с префиксом `_`, оранжевый цвет в sidebar
- Обычные модули: папка без префикса, стандартный цвет в sidebar
