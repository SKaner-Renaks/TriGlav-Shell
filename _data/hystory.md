# История изменений TriGlav Shell

## v1.2.8
- **Фикс sidebar**: удалён `if (!m.running) return;` из `renderModuleList()` — незапущенные модули теперь отображаются в sidebar с красным индикатором
- **Proxy bypass**: добавлен `proxies={'http': None, 'https': None}` в `proxy()` для обхода системного прокси Windows (`127.0.0.1:12334`)

## v1.2.9
- **Фикс кодировки языка**: исправлены кракозябры в dropdown Language ("Русский" отображалась корректно)
- **Development mode**: добавлены кнопки Web, Log, Log File в Development Block
- **Log API**: эндпоинт `/api/module/<name>/log-file` — возвращает содержимое лога модуля
- **Module info**: поле с типом модуля и requires_admin в Development Block

## v1.3.0
- **Folder button**: кнопка открытия папки модуля (только на localhost/127.0.0.1)
- **Folder API**: эндпоинт `POST /api/module/<name>/open-folder`
- **Module name в info block**: техническое имя модуля белым цветом в Development Block

## v1.3.1
- **Folder foreground**: `ShellExecuteW` с `EnumWindows` + `SetForegroundWindow` + `BringWindowToTop`
- **Модульное имя выделено**: белый цвет `#fff`, жирный `font-weight:600`

## v1.3.2
- **Фикс JS синтаксиса**: `innerHTML` имел `''` внутри одинарной строки — заменено на двойные кавычки
- **Open folder indentation**: исправлен отступ функции `openFolder()`

## v1.3.3
- **Reset Modules**: теперь сбрасывает `current_port` в манифестах (раньше только `current_settings`)
- **Port allocation**: если `current_port` пустой или `0` — генерируется через `5000 + hash(name) % 100`
- **Folder foreground**: полная реализация через `EnumWindows` + `ShowWindow(SW_RESTORE)` + `SetForegroundWindow`

## v1.3.4
- **Info block**: "Информация" → "Development"
- **Info block icon**: `developer_board.svg` с фильтром `invert(1)`
- **Development Block**: добавлен комментарий `// Development Block — блок разработчика`

## v1.3.5
- **Фикс JS innerHTML**: заменены `''` на двойные кавычки в строке с `style`

## v1.3.6
- **Info block icon**: `developer_board.svg` без инверсии (SVG уже светлый)

## v1.3.9
- **Info block**: "Информация" → "Development" (финальная версия)
- **Info block icon**: `developer_board.svg` без инверсии

## v1.4.0
- **Admin check в Shell**: добавлен `/api/admin-status`, `checkAdminStatus()`, `#adminStatus`, "Restart as Admin" в Development Block
- **Admin badge**: показывает "Admin required" для модулей с `requires_admin`
- **Admin CSS**: `.btn-admin` для кнопки "Restart as Admin"

## v1.4.1
- **Proxy bypass**: исправлен `log-file` endpoint — использует `manifest['_path']` вместо `os.path.join(MODULE_DIR, name)`
- **Логирование**: добавлен вывод в `_data/log_file.log` при старте Shell

## v1.4.2
- **Фикс log-file endpoint**: исправлен путь для сервисных модулей с префиксом `_`

## v1.4.3
- **Log checkbox persistence**: состояние галочки Log сохраняется в `config.cfg` секция `[log_enabled]`
- **load_log_enabled() / save_log_enabled()**: загрузка/сохранение состояний логирования
- **Удалён `--log-file`**: модули используют только `--log`, путь лога определяется модулем

## v1.4.4
- **Restart-elevated fix**: проверка `IsUserAnAdmin()` перед запуском
- **Log separators**: `==================================================` в логе при каждом старте модуля
- **Детальное логирование restart-elevated**: попытка, статус, ошибки

## v1.4.5
- **Mode: Admin/User**: отображается в хедере Shell рядом с IP и временем

## v1.4.6
- **Log checkbox state**: галочка устанавливается из данных сервера при выборе модуля

## v1.4.7
- **Restart-elevated port wait**: ожидание освобождения порта до 10 попыток
- **Port availability check**: проверка занятости порта перед запуском нового процесса

## v1.4.8
- **Убран confirm()**: только UAC-промпт Windows, без лишнего окна подтверждения
- **Улучшен restart-elevated**: ожидание освобождения порта + проверка запуска

## v1.4.9
- **PowerShell Start-Process**: заменён `ShellExecuteW` на `Start-Process` с `-WorkingDirectory` для корректного запуска модулей с правами администратора

## v1.5.0
- **Удалён admin elevation**: удалены `/api/module/<name>/restart-elevated`, `/api/admin-status`, кнопка "Restart as Admin", "Admin required" badge, JS `restartElevated()`, обработчик `postMessage`
- **Оставлено**: `is_admin` в `get_server_info()` для отображения "Mode: Admin/User"

## v1.5.1
- **Фикс JS синтаксиса**: исправлена лишняя `}` в `selectModule()` (строка 950) и лишний код в `postMessage` обработчике
