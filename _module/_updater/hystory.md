# История изменений  Updater




## v1.4.9 — 2026-07-16
- **Dev tooltip fix**: подсказка не обрезается у правого/нижнего края экрана — позиционируется с учётом границ viewport

## v1.4.8 — 2026-07-16
- Убранен хардкод EXCLUDE_DIRS/EXTS/FILES из кода
- Все исключения хранятся только в manifest.json
- Исправлена логика @: только корень проекта (через os.path.relpath)
- Исправлен дублированный data-zone в модалке логов
- Убранена старая функция browseFolder()

## v1.4.7 — 2026-07-16
- **Log в архиве**: .log файл добавляется внутрь .zip бекапа
- **Столбец Log** в таблице бекапов со ссылкой на просмотр лога
- **Модалка лога** `updater.modal.log` — просмотр содержимого .log с прокруткой
- **Дата/время по левому краю** в таблице бекапов
- **Download защита**: кнопка неактивна если выбрано != 1 бекапа
- **Очистка осиротевших логов**: .log без .zip удаляются при открытии окна
- **_BackUp исключён** из полного бекапа
- **Заголовок модуля**: "Обновления и Бекапы"
- Окно бекапов — модальное внутри страницы (не popup)

## v1.4.6 — 2026-07-16
- Кнопка "Folder" заменена на "Open BackUp Folder"
- Открытие web-окна со списком бекапов
- Таблица: чекбокс + дата/время + размер
- Кнопки: DownLoad (скачивание zip+log), Delete (удаление zip+log), Cancel
- Сводка: всего бекапов + общий объем
- Удален PowerShell FolderBrowserDialog

## v1.4.5 — 2026-07-16
- Новая зона `updater.backup` — полный бекап проекта
- Иконки cloud_upload (бекап) и folder (выбор папки)
- Поле пути с значением `_BackUp` по умолчанию
- Кнопка папки — нативный диалог Windows (PowerShell FolderBrowserDialog)
- Кнопка "BackUp Full" — создание полного архива проекта
- Прогресс-бар с процентами (подсчёт файлов)
- Архив: `full_BackUp_DDMMYY_HHMM.zip` + `.log`
- Исключения: .git, __pycache__, BackUp, _Download, .mimocode, *.mp3, *.log
- Ошибки доступа логируются, процесс не прерывается

## v1.4.4 — 2026-07-16
- Кнопка "Get" перенесена из header рядом с полем repo_url
- Создана зона `updater.get_online` для кнопки + поля ввода
- Добавлена SVG иконка cloud_download для статуса соединения
- Новый эндпоинт `/api/repo/check` — проверка доступности репозитория
- Иконка светится зелёным (доступен) / красным (недоступен)
- Автопроверка при загрузке модуля + debounce 1с после ввода URL

## v1.4.3
- **args module-level**: parser/args определены на уровне модуля, а не в __main__
- **--log support**: добавлен флаг --log для управления логированием через Shell UI
- **get_shell_port()**: port Shell читается из config.cfg вместо хардкода 8080
- **Extraction cleanup**: распаковка ZIP обёрнута в try/except с удалением битого EXTRACT_DIR
- **Thread-safe download_state**: download_lock (threading.Lock) для синхронизации доступа к download_state


## v1.4.2
- **Dev zone labels**: data-zone на header, repo_url, installed/new tables, progress modal (5 зон)
- **Debug tooltip**: hover-подсказки :: updater.zone в development mode
