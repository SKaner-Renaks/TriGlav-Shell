# История изменений module_manager

## v1.2.1
- Базовый функционал управления модулями

## v1.2.2
- **Path traversal**: `sanitize_name()` — проверка имени модуля `[a-zA-Z0-9_]`
- **Auth bypass**: добавлен `proxies={'http': None, 'https': None}` для запросов к Shell API
- **XSS**: `escape_html()` для title, description, name
- **Toggle CSS/JS**: начальный класс `toggle-on` (синий, включена)
- **Shell port**: читается из `config.cfg` вместо хардкода 8080
- **Service delete dialog**: модальное окно подтверждения для удаления сервисных модулей
- **loadModules()**: показывает ошибку в `errorBanner` при неудаче
- **saveAndRestart()**: проверяет `r.ok` перед отправкой restart

## v1.3.0
- **requires_admin**: манифест обновлён — `true`
- **Module status API**: `/api/modules_status` — получение портов и статусов от Shell
- **Restart API**: `/api/module_restart?name=...` — перезапуск модуля через Shell
- **Admin status API**: `/api/admin-status` — проверка прав администратора
- **Admin badge**: в хедере показывает ✓ Admin / ⚠ Not Admin
- **Restart as Admin**: кнопка в хедере для модулей с `requires_admin`
- **Колонка Порт**: зелёный/красный индикатор статуса
- **Колонка Действия**: кнопка Restart для работающих модулей
- **Единое выравнивание**: `table-layout: fixed` с фиксированными ширинами

## v1.3.2
- **Колонка Версия**: отображение версии модуля в таблице
- **Restart lock**: кнопка Restart блокируется при включённой блокировке для сервисных модулей
- **Кнопки**: "Действия" → "Перезапуск", "Удалить" → "Remove"

## v1.3.3
- **Disabled style**: `.btn-restart:disabled` — `opacity:0.3; cursor:not-allowed; border-color:#666; color:#666`
- **Button text**: "Перезапустить" → "Restart", "Удалить" → "Remove"

## v1.3.4
- Версия обновлена для фикса disabled стиля кнопки Restart

## v1.3.5
- **Удалён admin check**: `/api/admin-status`, `checkAdminStatus()`, `#adminStatus`, `restartElevated()` — всё перенесено в Shell

## v1.3.6
- **Log file**: `module.log` → `log_file.log`
- **Детальное логирование**: config path, shell port, modules count, delete/restart requests

## v1.3.7
- **Сепараторы в логе**: `==================================================` перед и после старта

## v1.3.8
- **Request logging**: `@before_request` логгер записывает все входящие запросы (GET/POST)
