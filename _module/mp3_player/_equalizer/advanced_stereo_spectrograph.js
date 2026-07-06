// _equalizer/advanced_stereo_spectrograph.js
// Высокотехнологичный эквалайзер "Рельеф Фурье 2.0" — Живая реактивная сетка и глубокое свечение

(function() {
    const MAX_HISTORY = 24; // Ваша идеальная глубина шлейфа
    
    let layersL = { subBass: [], midBass: [], vocals: [], highs: [] };
    let layersR = { subBass: [], midBass: [], vocals: [], highs: [] };
    
    let globalTime = 0;

    window.draw = function(ctx, data, w, h, mode) {
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.clearRect(0, 0, w, h);

        const len = data.length;
        const centerY = h * 0.5;
        const maxAmp = mode === 'fullscreen' ? h * 0.85 : h * 0.9;
        
        globalTime += 0.022; 

        // Массив, куда мы будем собирать координаты и цвета ТОЛЬКО самых свежих (ярких) волн для подсветки фона
        let activeWavePoints = [];

        function getBandEnergy(dataArray, startIndex, endIndex) {
            let sum = 0;
            let count = 0;
            for (let i = startIndex; i <= endIndex; i++) {
                if (dataArray[i] !== undefined) {
                    sum += Math.abs(dataArray[i]);
                    count++;
                }
            }
            return count > 0 ? sum / count : 0;
        }

        // Подготовка данных
        let rawL = data.slice(0, Math.floor(len / 2));
        let rawR = data.slice(Math.floor(len / 2));
        let dataL = Array.from({length: len}, (_, i) => rawL[Math.floor(i / 2)] || 0);
        let dataR = Array.from({length: len}, (_, i) => rawR[Math.floor(i / 2)] || 0);

        let dataMid = dataL.map((v, idx) => (v + dataR[idx]) * 0.5);
        let dataSide = dataL.map((v, idx) => Math.abs(v - dataR[idx]));

        const p1 = Math.floor(len * 0.08); 
        const p2 = Math.floor(len * 0.25); 
        const p3 = Math.floor(len * 0.65); 

        let currentL = {
            subBass: [getBandEnergy(dataL, 0, p1)],       
            midBass: [getBandEnergy(dataMid, p1, p2)],     
            vocals: [getBandEnergy(dataL, p2, p3)],        
            highs: [getBandEnergy(dataSide, p3, len)]      
        };

        let currentR = {
            subBass: [getBandEnergy(dataR, 0, p1)],
            midBass: [getBandEnergy(dataMid, p1, p2)],
            vocals: [getBandEnergy(dataR, p2, p3)],
            highs: [getBandEnergy(dataSide, p3, len)]
        };

        Object.keys(layersL).forEach(key => {
            layersL[key].unshift(currentL[key][0]);
            layersR[key].unshift(currentR[key][0]);
            if (layersL[key].length > MAX_HISTORY) layersL[key].pop();
            if (layersR[key].length > MAX_HISTORY) layersR[key].pop();
        });

        // --- ВЫЧИСЛЕНИЕ ВОЛН (Сбор геометрии для отрисовки и реактивного фона) ---
        let allStrandsToRender = [];
        const renderOrder = ['subBass', 'midBass', 'vocals', 'highs'];

        function buildLayerGeometry(layerHistory, isLeftChannel, type) {
            const numStrands = layerHistory.length;
            if (numStrands === 0) return;

            let baseSpeed = 0, freq = 0, ampMod = 1.0, rgbColor = '', glowColor = '';

            if (type === 'subBass')  { baseSpeed = 1.5; freq = 0.003; ampMod = 1.3; rgbColor = '30, 110, 255'; glowColor = 'rgba(0, 90, 255, 0.95)'; }
            if (type === 'midBass')  { baseSpeed = 2.8; freq = 0.006; ampMod = 1.1; rgbColor = '210, 230, 255'; glowColor = 'rgba(180, 215, 255, 0.85)'; }
            if (type === 'vocals')   { baseSpeed = 4.2; freq = 0.012; ampMod = 0.9; rgbColor = '255, 175, 40'; glowColor = 'rgba(255, 140, 10, 0.95)'; }
            if (type === 'highs')    { baseSpeed = 6.0; freq = 0.022; ampMod = 0.6; rgbColor = '255, 30, 60'; glowColor = 'rgba(255, 10, 30, 0.95)'; }

            const direction = isLeftChannel ? 1 : -1;
            const speed = baseSpeed * direction;

            for (let s = numStrands - 1; s >= 0; s--) {
                const energy = layerHistory[s];
                const isLatest = (s === 0);
                let points = [];
                const steps = 60; // Оптимизировано для баланса расчетов эффекта освещения

                for (let i = 0; i <= steps; i++) {
                    let currentX = (i / steps) * w;
                    let ratio = i / steps;
                    let edgeDamping = Math.sin(ratio * Math.PI); 

                    let wavePhase = currentX * freq + (globalTime * speed) - (s * 0.12 * direction);
                    let sineWave = Math.sin(wavePhase) + Math.cos(wavePhase * 0.4) * 0.25;

                    let val = (energy / 255) * sineWave * edgeDamping * ampMod;
                    let currentY = centerY + (val * maxAmp * 0.5);

                    if (!isLatest) {
                        let decay = Math.pow(1 - (s / numStrands), 1.6); // Мягкий спад для истории из 24 линий
                        currentY = centerY + (currentY - centerY) * decay;
                    }

                    points.push({x: currentX, y: currentY});

                    // Сохраняем точки ТОЛЬКО самых свежих линий для расчёта освещения сетки
                    if (isLatest && energy > 5) {
                        activeWavePoints.push({ x: currentX, y: currentY, color: rgbColor, energy: energy });
                    }
                }
                points[0].y = centerY;
                points[points.length - 1].y = centerY;

                allStrandsToRender.push({
                    points: points,
                    isLatest: isLatest,
                    type: type,
                    s: s,
                    numStrands: numStrands,
                    rgbColor: rgbColor,
                    glowColor: glowColor
                });
            }
        }

        // Собираем геометрию
        renderOrder.forEach(layerName => {
            buildLayerGeometry(layersL[layerName], true, layerName);
            buildLayerGeometry(layersR[layerName], false, layerName);
        });

        // --- 1. РЕНДЕРИНГ ЖИВОЙ СЕТКИ С ФИЗИКОЙ СВЕЧЕНИЯ ---
        ctx.lineWidth = 1;
        const gridSize = mode === 'fullscreen' ? 50 : 25;
        const maxInfluenceRadius = mode === 'fullscreen' ? 140 : 85; // Радиус освещения от волны

        // Отрисовка вертикальных линий сетки
        for (let x = 0; x < w; x += gridSize) {
            ctx.beginPath();
            let grad = ctx.createLinearGradient(x, 0, x, h);
            
            // Базовый тусклый цвет сетки на границах экрана
            grad.addColorStop(0, 'rgba(230, 160, 80, 0.02)');
            
            // Проверяем влияние волн на ключевые точки вертикальной линии
            const numCheckPoints = 8;
            for (let cp = 1; cp < numCheckPoints; cp++) {
                let ratioY = cp / numCheckPoints;
                let currentY = ratioY * h;
                
                let rSum = 230, gSum = 160, bSum = 80, totalAlpha = 0.03;

                // Ищем ближайшие волны к этой точке сетки (x, currentY)
                for (let wp of activeWavePoints) {
                    let dx = wp.x - x;
                    let dy = wp.y - currentY;
                    let distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < maxInfluenceRadius) {
                        // Физический спад освещенности обратно пропорционален квадрату расстояния
                        let intensity = Math.pow(1 - (distance / maxInfluenceRadius), 2.5) * (wp.energy / 255) * 0.45;
                        
                        let [r, g, b] = wp.color.split(',').map(Number);
                        rSum += r * intensity;
                        gSum += g * intensity;
                        bSum += b * intensity;
                        totalAlpha += intensity;
                    }
                }
                totalAlpha = Math.min(totalAlpha, 0.45); // Ограничение максимальной яркости сетки
                grad.addColorStop(ratioY, `rgba(${Math.min(rSum, 255)}, ${Math.min(gSum, 255)}, ${Math.min(bSum, 255)}, ${totalAlpha})`);
            }
            grad.addColorStop(1, 'rgba(230, 160, 80, 0.02)');
            ctx.strokeStyle = grad;
            ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
        }

        // Отрисовка горизонтальных линий сетки
        for (let y = 0; y < h; y += gridSize) {
            ctx.beginPath();
            let grad = ctx.createLinearGradient(0, y, w, y);
            grad.addColorStop(0, 'rgba(230, 160, 80, 0.02)');

            const numCheckPoints = 12;
            for (let cp = 1; cp < numCheckPoints; cp++) {
                let ratioX = cp / numCheckPoints;
                let currentX = ratioX * w;

                let rSum = 230, gSum = 160, bSum = 80, totalAlpha = 0.03;

                for (let wp of activeWavePoints) {
                    let dx = wp.x - currentX;
                    let dy = wp.y - y;
                    let distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < maxInfluenceRadius) {
                        let intensity = Math.pow(1 - (distance / maxInfluenceRadius), 2.5) * (wp.energy / 255) * 0.45;
                        let [r, g, b] = wp.color.split(',').map(Number);
                        rSum += r * intensity;
                        gSum += g * intensity;
                        bSum += b * intensity;
                        totalAlpha += intensity;
                    }
                }
                totalAlpha = Math.min(totalAlpha, 0.45);
                grad.addColorStop(ratioX, `rgba(${Math.min(rSum, 255)}, ${Math.min(gSum, 255)}, ${Math.min(bSum, 255)}, ${totalAlpha})`);
            }
            grad.addColorStop(1, 'rgba(230, 160, 80, 0.02)');
            ctx.strokeStyle = grad;
            ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        }


        // --- 2. РЕНДЕРИНГ САМИХ ВОЛН (КАСКАД) ---
        ctx.globalCompositeOperation = 'screen';

        for (let strand of allStrandsToRender) {
            ctx.beginPath();
            ctx.lineWidth = strand.isLatest ? (strand.type === 'subBass' ? 4.0 : 2.5) : 0.5;
            
            let alpha = strand.isLatest ? 1.0 : 0.04 + Math.pow(1 - (strand.s / strand.numStrands), 2) * 0.35;
            
            let grad = ctx.createLinearGradient(0, 0, w, 0);
            grad.addColorStop(0, `rgba(${strand.rgbColor}, 0.0)`);
            grad.addColorStop(0.15, `rgba(${strand.rgbColor}, ${alpha})`);
            grad.addColorStop(0.85, `rgba(${strand.rgbColor}, ${alpha})`);
            grad.addColorStop(1, `rgba(${strand.rgbColor}, 0.0)`);
            ctx.strokeStyle = grad;

            if (strand.isLatest) {
                ctx.shadowBlur = mode === 'fullscreen' ? 55 : 30;
                ctx.shadowColor = strand.glowColor;
            } else {
                ctx.shadowBlur = mode === 'fullscreen' ? 12 : 6;
                ctx.shadowColor = strand.glowColor;
            }

            ctx.moveTo(strand.points[0].x, strand.points[0].y);
            for (let i = 0; i < strand.points.length - 1; i++) {
                let xc = (strand.points[i].x + strand.points[i + 1].x) / 2;
                let yc = (strand.points[i].y + strand.points[i + 1].y) / 2;
                ctx.quadraticCurveTo(strand.points[i].x, strand.points[i].y, xc, yc);
            }
            ctx.lineTo(strand.points[strand.points.length - 1].x, strand.points[strand.points.length - 1].y);
            ctx.stroke();
        }

        // Стабильная ось X
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1;
        ctx.moveTo(0, centerY); ctx.lineTo(w, centerY);
        ctx.stroke();

        ctx.globalCompositeOperation = 'source-over';
        ctx.shadowBlur = 0;

        // Маркеры каналов
        ctx.fillStyle = 'rgba(255, 255, 255, 0.15)';
        ctx.font = mode === 'fullscreen' ? 'bold 24px sans-serif' : 'bold 14px sans-serif';
        let pX = mode === 'fullscreen' ? 45 : 20;
        ctx.fillText('L', pX, centerY - (mode === 'fullscreen' ? 40 : 20));
        ctx.fillText('R', w - pX - (mode === 'fullscreen' ? 18 : 10), centerY - (mode === 'fullscreen' ? 40 : 20));
    };
})();