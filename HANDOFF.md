# HANDOFF — TriGlav Shell Project Session
**Дата**: 2026-07-16
**Сессия**: ses_094ad0bfaffe5u5vXNRANRKQV6

---

## 1. Текущая версия

- **Shell**: v1.5.5
- **module_manager**: v1.4.0
- **task_scheduler**: v2.4.8
- **control**: v1.5.2
- **monitor**: v1.5.2
- **invaders**: v1.2.2
- **snake**: v1.2.2
- **flip_clock**: v1.1.2
- **mp3_player**: v1.1.2
- **smb_explorer**: v3.2.2
- **deps_checker**: v1.2.4
- **updater**: v1.4.9

## 2. Архитектура проекта

### Структура каталогов
```
C:\ARS\Mimo\Task Server\
├── main.py              Ядро Shell (port 8080) v1.5.5
├── AGENTS.md            Документация для AI
├── HANDOFF.md           Передача сессии
├── task.md              ТЗ проекта
├── task_updater.md      ТЗ модуля обновлений
├── requirements.txt     flask, requests, psutil, ldap3
├── .gitignore
├── _data\
│   ├── config.cfg       Глобальные настройки (INI)
│   ├── manifest.json    Манифест Shell
│   ├── encrypt.py       Шифрование care.env (XOR+base64)
│   ├── care.env         Хранилище секретов (auto-created)
│   ├── log_file.log     Лог Shell (Development mode)
│   ├── hystory.md       История изменений Shell
│   ├── _lang\
│   │   ├── ru.json      Русская локализация
│   │   └── en.json      Английская локализация
│   ├── _images\
│   │   ├── gear.svg
│   │   └── developer_board.svg
│   │   └── frame_bug.svg
│   └── _ps\
│       └── _check_fw.ps1
└── _module\
    ├── monitor\         Мониторинг сервера (port 5005) v1.5.2
    ├── task_scheduler\  Планировщик задач (port 5008) v2.4.8
    ├── control\         Панель управления (port 5003) v1.5.2
    ├── invaders\        Космические захватчики (port 5004) v1.2.2
    ├── snake\           Змейка (port 5007) v1.2.2
    ├── flip_clock\      Flip Clock (port 5042) v1.1.2
    ├── mp3_player\      MP3 Player (port 5009) v1.1.2
    ├── smb_explorer\    SMB Explorer (port 5006) v3.2.2
    ├── _deps_checker\   Проверка зависимостей (port 5000) v1.2.4
    ├── _module_manager\ Управление модулями (port 5001) v1.4.0
    └── _updater\        Обновления и Бекапы (port 5002) v1.4.9
```

## 3. Окружение

| Параметр | Значение |
|----------|----------|
| OS | Windows 11 Pro (Win32) |
| Python | 3.13.14 |
| Git | `C:\Program Files\Git\cmd\git.exe` v2.54.0 |
| GitHub | `SKaner-Renaks` (токен в Credential Manager) |
| Репозиторий | `https://github.com/SKaner-Renaks/TriGlav-Shell` |
| Рабочая папка | `C:\ARS\Mimo\Task Server\` |
| Зеркало | `C:\ARS\Mimo\TriGlav-Shell` |

## 4. Ключевые особенности

### Proxy bypass
Системный прокси Windows (`127.0.0.1:12334`) перехватывает запросы `requests`. В `proxy()` функции добавлен `proxies={'http': None, 'https': None}`.

### Log file naming
- Модули: `<папка_модуля>/log_file.log`
- Shell: `_data/log_file.log`

### Development Block
Блок информации о модуле в content header. Показывает иконку `developer_board.svg
│   │   └── frame_bug.svg` + "Development". Доступен только в Development mode.

### Log checkbox persistence
Состояние галочки Log сохраняется в `config.cfg` секция `[log_enabled]`.

## 5. Git workflow

```bash
# Зеркало: C:\ARS\Mimo\TriGlav-Shell
git add .
git commit -m "v1.5.x: описание"
# НЕ пушить без явного разрешения пользователя!
```

## 5.1 Development mode zone labels

В development mode каждая UI-зона имеет `data-zone="module.zone_name"`. Tooltip появляется через 500ms. Реализация: CSS `.dev-label` + JS в debug snippet.

## 5.2 manifest.json — поле mode

Все манифесты содержат поле `"mode": "development"` или `"mode": "production"`. Определяет режим работы модуля.

## 5.3 _updater v1.4.3

- `args` определён на уровне модуля (не в `__main__`)
- `--log` флаг для управления логированием через Shell UI
- `get_shell_port()` читает порт из `config.cfg` вместо хардкода
- Распаковка ZIP обёрнута в try/except с очисткой при ошибке
- `download_lock` (threading.Lock) для потокобезопасности
- `description.md` — описание модуля с текущей версией

## 6. Известные ограничения

- **Manifest BOM**: PowerShell `Set-Content -Encoding UTF8` добавляет BOM. Использовать Python для записи JSON.
- **Folder button**: `ShellExecuteW` не гарантирует foreground. Использовать `EnumWindows` + `SetForegroundWindow`.
- **Логирование**: только в Development mode. `--log` через argparse.

## 7. Следующие шаги (рекомендации)

1. **Доработка шифрования** — добавить AES/Fernet в encrypt.py
2. **Полноценная панель настроек** — UI для auth_mode, environment, language, port, theme
3. **Программный перезапуск Shell** — при изменении настроек
4. **Long-polling health-check** — автообновление страницы после рестарта
5. **Роли AD** — управление видимостью модулей по группам
6. **Локализация модулей** — каждому модулю свою `_lang/`

---

**Следующий агент**: начни с `C:\ARS\Mimo\Task Server\` — проект полностью изучен, готов к доработке.
