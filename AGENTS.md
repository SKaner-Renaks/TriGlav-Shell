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
- **§5.2**: manifest.json — name, title, version, description, requires_admin, current_port, languages, settings
- **§5.3**: encrypt.py — шифрование care.env, динамические методы, auto-create с дефолтами
- **§6.1**: Автообнаружение модулей, выделение портов, subprocess.Popen с --host/--port
- **§6.2**: Авторизация — AD (ldap3) + local, @login_required на маршрутах Shell
- **§6.3**: Локализация Shell — _lang/ru.json, en.json, fallback ru→en→raw keys
- **§6.4**: Настройки и сброс — кнопка «Шестерёнка», сброс модуля/консоли
- **§6.5**: UI — 4 зоны, splitter с drag-to-resize, localStorage для ширины, iframe
- **§7**: Адаптация control, monitor, task_server как модулей в _module/
- **§8**: Бекап старых файлов в BackUp/2026-06-28-01
- **v1.2**: Reverse proxy для удалённого доступа, проверка firewall, визуализация запуска
- **v1.2.1**: Версионность, requirements.txt для всех модулей
- **v1.2.1+**: Модули проверки зависимостей, визуализация перезапуска модулей

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
main.py              Ядро Shell        (port 8080)   VERSION = '1.2.1'
config.cfg           Глобальные настройки (INI)
encrypt.py           Шифрование care.env (XOR+base64)
care.env             Хранилище секретов (auto-created)
_lang/               Локализация (ru.json, en.json)
_module/             Автообнаружение модулей
  task_scheduler/    Планировщик задач   (port 5002)   VERSION = 'v2.4.4'
  monitor/           Мониторинг сервера  (port 5001)   VERSION = '1.4'
  control/           Панель управления   (port 5004)   VERSION = '1.3'
  snake/             Змейка              (port 5006)   VERSION = '1.1'
  invaders/          Космические захватчики (port 5005) VERSION = '1.1'
  deps_checker/      Проверка зависимостей (port 5007) VERSION = '1.1'
```

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

## Code Conventions

- Shell config in `config.cfg` only — modules don't import shared config
- Module metadata in `manifest.json` (name, title, version, port, settings)
- Modules accept `--host` and `--port` via argparse
- Modules have NO auth — Shell handles authentication
- Version string in script header: `VERSION = 'x.y.z'`
- All Shell API routes use `@login_required` decorator
- Backup files: `BackUp/YYYYMMDD-N/` directory
- Each module and shell has its own `requirements.txt`
- При перезапуске модуля через Shell показывается спиннер с текстом «Перезапуск модуля...»
