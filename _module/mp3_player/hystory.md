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
- Inline SVG вместо <img> — фикс broken image при переключении
- Proxy маршрут /module-music/<name>/<path> для MP3 через Shell
- Proxy маршрут /module-cover/<name>/<path> для обложек через Shell
- Fallback обложки: onerror показывает default_cover.png
- Кнопка обновления списка треков (refresh)
- Одиночный/двойной клик по трекам (выбор/воспроизведение)

## v1.0.2
- Обложка альбома в центре right panel (cover-wrap 240x240)
- Размытый фон (bg-blur, blur 13px, brightness 0.3)
- Glassmorphic стиль с text-shadow
- Ползунок blur с числовым отображением
- default_cover.png — обложка по умолчанию (дракон из cover_6.png)
- Кнопка эквалайзера (EQ режим) — полноразмерный EQ как фон
- CSS: .right.eq-mode — blur/cover скрыты, eq-wrap на весь экран
- EQ canvas пересчёт размеров каждый кадр (фикс размытия)

## v1.0.3
- Числовое отображение громкости (volVal span)

## v1.0.4
- Обложки в списке треков (мини 36x36 слева в плашке)
- Placeholder поиска: "Поиск по названию или исполнителю..."

## v1.0.5
- Blur default: 40px → 13px (CSS + slider)
- Layout ползунков: число перед ползунком (label → span → input)

## v1.0.6
- Кнопка эквалайзера (equalizer.svg inline)
- EQ режим: bg-blur/cover скрыты, eq-wrap растягивается на весь экран

## v1.0.7
- Модульные эквалайзеры: _equalizer/ папка с JS-скриптами
- Выпадающий список эквалайзеров в headbar
- config.cfg модуля: blur, volume, equalizer по умолчанию
- bars_gradient.js — вынесен из main.py как первый эквалайзер
- AGENTS.md для эквалайзеров (правила создания)
- API: /api/settings, /api/equalizers, /_equalizer/<name>.js

## v1.0.8
- Fix: EQ загрузка через script tag + window.draw (eval не работал в scope)
- Proxy маршрут /module-equalizer/ в Shell для загрузки EQ через прокси
- Обновлены все версии и документация

## v1.1
- Fullscreen для PlayerZone через requestFullscreen() на iframe
- Fullscreen для PlayList через CSS zone-fullscreen (расширение ширины)
- Кнопка расширения плейлиста: иконка height.svg повёрнута на 90°, размер 20px
- Кнопка fullscreen PlayerZone: стиль mode-btn (40px, accent hover)
- flip_clock SVG скопированы в _images
