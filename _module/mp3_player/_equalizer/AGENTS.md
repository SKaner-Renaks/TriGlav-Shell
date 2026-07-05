# Правила эквалайзеров MP3 Player

## Формат файла
JS-файл в папке `_equalizer/`. Имя файла = имя эквалайзера (без `.js`).

## Обязательная функция

```javascript
window.draw = function(ctx, data, w, h, mode) {
    // ...
};
```

Важно: функция ДОЛЖНА быть присвоена на `window.draw`, а не просто объявлена как `function draw()`. Это необходимо для корректной загрузки через `eval()`.

- `ctx` — Canvas 2D context
- `data` — Uint8Array частотных данных (analyser.frequencyBinCount)
- `w`, `h` — текущие размеры canvas в пикселях
- `mode` — `'normal'` (маленький бар 70px) или `'fullscreen'` (весь экран)

## Правила

1. Не использовать внешние библиотеки (только нативный Canvas 2D API)
2. Не изменять глобальный scope кроме функции `draw`
3. Всегда очищать canvas перед отрисовкой (`ctx.clearRect`)
4. Адаптироваться к любым `w` и `h`
5. Корректно работать в обоих режимах (normal / fullscreen)
6. Каждый кадр вызывается через `requestAnimationFrame` — не создавать свой цикл
7. Данные `data` обновляются автоматически перед каждым вызовом `draw`

## Регистрация

Новый эквалайзер — просто положить `.js` файл в `_equalizer/`. Модуль автоматически подхватит его и покажет в выпадающем списке.

## Пример minimal

```javascript
window.draw = function(ctx, data, w, h, mode) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#47a8ff';
    var barW = w / data.length;
    for (var i = 0; i < data.length; i++) {
        var barH = (data[i] / 255) * h;
        ctx.fillRect(i * barW, h - barH, barW - 1, barH);
    }
};
```
