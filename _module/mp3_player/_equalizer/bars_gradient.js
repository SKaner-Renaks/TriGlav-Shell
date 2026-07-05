// bars_gradient — Градиентные частотные бары (зелёный → жёлтый → красный)
function draw(ctx, data, w, h, mode) {
    ctx.clearRect(0, 0, w, h);
    var bars = data.length;
    var barW = (w / bars) * 1.2;
    var gap = 2;
    for (var i = 0; i < bars; i++) {
        var val = data[i] / 255;
        var barH = val * h * 0.9;
        var x = i * (barW + gap);
        var g = ctx.createLinearGradient(0, h, 0, 0);
        g.addColorStop(0, '#21bf4b');
        g.addColorStop(0.5, '#f0c040');
        g.addColorStop(1, '#ff6c59');
        ctx.fillStyle = g;
        ctx.fillRect(x, h - barH, barW, barH);
    }
}
