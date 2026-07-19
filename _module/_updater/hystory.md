# История изменений  Updater
## v1.4.3
- **args module-level**: parser/args определены на уровне модуля, а не в __main__
- **--log support**: добавлен флаг --log для управления логированием через Shell UI
- **get_shell_port()**: port Shell читается из config.cfg вместо хардкода 8080
- **Extraction cleanup**: распаковка ZIP обёрнута в try/except с удалением битого EXTRACT_DIR
- **Thread-safe download_state**: download_lock (threading.Lock) для синхронизации доступа к download_state


## v1.4.2
- **Dev zone labels**: data-zone на header, repo_url, installed/new tables, progress modal (5 зон)
- **Debug tooltip**: hover-подсказки :: updater.zone в development mode
