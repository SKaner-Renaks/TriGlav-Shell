# История изменений MP3 Player

## v1.0
- Новый game-модуль MP3 Player
- Воспроизведение MP3 через HTML5 Audio
- Web Audio API эквалайзер (визуализация частотных баров)
- Режимы: sequential, shuffle, repeat-one, repeat-all
- Громкость: ползунок 0-100%
- Прогресс-бар с перемоткой
- Чтение ID3 тегов через mutagen (русские теги)
- Обложки альбомов (APIC)
- Плейлисты: создание, сохранение, удаление (JSON в playlists/)
- Поиск по трекам
- Поддержка dark/light темы из config.cfg
- SVG-иконки для управления (play, pause, skip, shuffle, repeat, volume)
- Порт 5009, тип game

## v1.0.1
- Увеличены иконки управления в 2 раза (56px ctrl, 40px mode)
- Убран синий круг под кнопкой play
- Кнопка play и другие иконки меняют цвет на accent при активации
- Glow-эффект (drop-shadow) на активных кнопках
