# История изменений Flip Clock

## v1.1.2 — 2026-07-16
- **Dev tooltip fix**: подсказка не обрезается у правого/нижнего края экрана — позиционируется с учётом границ viewport

## v1.1.1
- **Dev zone labels**: data-zone на display (1 зона)
- **Debug tooltip**: hover-подсказки :: flip_clock.zone в development mode

## v1.0
- Новый game-модуль Flip Clock
- Flip-анимация секунд/минут/часов (CSS 3D-transform)
- Поддержка светлой и тёмной темы (global_theme из config.cfg)
- Кнопка fullscreen (инлайновый SVG)
- Порт 5042, тип game

## v1.1
- **Удвоение размера**: карточки 240x360px, шрифт 220px
- **Фикс анимации**: transform-style preserve-3d, правильный z-index слоёв, botSpan обновляется сразу
- **Headbar**: заголовок с версией и описанием, кнопка fullscreen в controls
- **Fullscreen exit**: отдельная плавающая кнопка退出, видна только в fullscreen (headbar скрывается)
- **Инициализация**: при первом тике часы сразу показывают время без фиктивного переворота от нуля
- **Образец**: реализация на базе gemini-code flip clock reference
