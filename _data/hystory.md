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

## v1.3.4 (Shell)
- **Info block**: "Информация" → "Development"
- **Info block icon**: `developer_board.svg` с фильтром `invert(1)`
- **Development Block**: добавлен комментарий `// Development Block — блок разработчика`

## v1.3.9 (Shell)
- **Info block**: "Информация" → "Development"
- **Info block icon**: `developer_board.svg` без инверсии (SVG уже светлый)
- **Development Block**: комментарий в коде

---

## module_manager v1.2.1
- Базовый функционал управления модулями

## module_manager v1.2.2
- **Path traversal**: `sanitize_name()` — проверка имени модуля `[a-zA-Z0-9_]`
- **Auth bypass**: добавлен `proxies={'http': None, 'https': None}` для запросов к Shell API
- **XSS**: `escape_html()` для title, description, name
- **Toggle CSS/JS**: начальный класс `toggle-on` (синий, включена)
- **Shell port**: читается из `config.cfg` вместо хардкода 8080
- **Service delete dialog**: модальное окно подтверждения для удаления сервисных модулей
- **loadModules()**: показывает ошибку в `errorBanner` при неудаче
- **saveAndRestart()**: проверяет `r.ok` перед отправкой restart

## module_manager v1.3.0
- **requires_admin**: манифест обновлён — `true`
- **Module status API**: `/api/modules_status` — получение портов и статусов от Shell
- **Restart API**: `/api/module_restart?name=...` — перезапуск модуля через Shell
- **Admin status API**: `/api/admin-status` — проверка прав администратора
- **Admin badge**: в хедере показывает ✓ Admin / ⚠ Not Admin
- **Restart as Admin**: кнопка в хедере для модулей с `requires_admin`
- **Колонка Порт**: зелёный/красный индикатор статуса
- **Колонка Действия**: кнопка Restart для работающих модулей
- **Единое выравнивание**: `table-layout: fixed` с фиксированными ширинами

## module_manager v1.3.2
- **Колонка Версия**: отображение версии модуля в таблице
- **Restart lock**: кнопка Restart блокируется при включённой блокировке для сервисных модулей
- **Кнопки**: "Действия" → "Перезапуск", "Удалить" → "Remove"

## module_manager v1.3.3
- **Disabled style**: `.btn-restart:disabled` — `opacity:0.3; cursor:not-allowed; border-color:#666; color:#666`
- **Button text**: "Перезапустить" → "Restart", "Удалить" → "Remove"

## module_manager v1.3.4
- Версия обновлена для фикса disabled стиля кнопки Restart
