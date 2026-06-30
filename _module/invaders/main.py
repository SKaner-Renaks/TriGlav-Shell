import argparse
from flask import Flask, render_template_string

VERSION = '1.1'

app = Flask(__name__)

INVADERS_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Космические захватчики {{ version }}</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            background: #1a1a1a;
            color: #f2f2f2;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            flex-direction: column;
        }
        .game-container {
            background: #262626;
            border: 1px solid #404040;
            border-radius: 4px;
            padding: 20px;
            text-align: center;
            position: relative;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #404040;
        }
        .title {
            font-size: 18px;
            font-weight: 600;
            color: #47a8ff;
        }
        .stats {
            display: flex;
            gap: 20px;
            font-size: 14px;
        }
        .stat {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .stat-label {
            color: #999;
        }
        .stat-value {
            color: #f2f2f2;
            font-weight: 600;
        }
        .lives {
            color: #ff6c59;
        }
        canvas {
            border: 2px solid #404040;
            border-radius: 3px;
            display: block;
            margin: 0 auto;
        }
        .controls-info {
            margin-top: 15px;
            font-size: 12px;
            color: #f2f2f2;
        }
        .overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(26, 26, 26, 0.95);
            padding: 30px 40px;
            border-radius: 8px;
            border: 2px solid #47a8ff;
            text-align: center;
            display: block;
        }
        .overlay h2 {
            color: #47a8ff;
            margin-bottom: 10px;
        }
        .overlay p {
            margin-bottom: 15px;
            color: #ccc;
        }
        .overlay.game-over {
            border-color: #ff6c59;
        }
        .overlay.game-over h2 {
            color: #ff6c59;
        }
        .overlay .btn {
            background: #0057b3;
            color: #f2f2f2;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .overlay .btn:hover {
            background: #0073d9;
        }
    </style>
</head>
<body>
    <div class="game-container">
        <div class="header">
            <div class="title">Космические захватчики {{ version }}</div>
            <div class="stats">
                <div class="stat">
                    <span class="stat-label">Счёт:</span>
                    <span class="stat-value" id="score">0</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Жизни:</span>
                    <span class="stat-value lives" id="lives">♥♥♥</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Уровень:</span>
                    <span class="stat-value" id="level">1</span>
                </div>
            </div>
        </div>

        <canvas id="gameCanvas" width="640" height="480"></canvas>

        <div class="overlay" id="startScreen">
            <h2>🚀 Космические захватчики</h2>
            <p>Уничтожьте все инопланетные корабли!<br>
            ← → — движение | Space — огонь</p>
            <button class="btn" onclick="startGame()">Начать игру</button>
        </div>

        <div class="overlay game-over" id="gameOverScreen" style="display:none;">
            <h2>Игра окончена!</h2>
            <p>Ваш счёт: <span id="finalScore">0</span></p>
            <button class="btn" onclick="startGame()">Играть снова</button>
        </div>

        <div class="overlay" id="levelComplete" style="display:none;">
            <h2>Уровень пройден!</h2>
            <p>Следующий уровень...</p>
        </div>

        <div class="controls-info">
            ← → — движение | Space — огонь | Enter — начать заново
        </div>
    </div>

    <script>
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');

        const PLAYER_WIDTH = 40;
        const PLAYER_HEIGHT = 30;
        const ALIEN_WIDTH = 30;
        const ALIEN_HEIGHT = 24;
        const BULLET_WIDTH = 4;
        const BULLET_HEIGHT = 12;
        const SHIELD_WIDTH = 60;
        const SHIELD_HEIGHT = 40;
        const PLAYER_SPEED = 5;
        const BULLET_SPEED = 7;
        const ALIEN_BULLET_SPEED = 4;
        const ALIEN_COLS = 11;
        const ALIEN_ROWS = 5;

        let player = { x: 300, y: 440 };
        let playerBullets = [];
        let alienBullets = [];
        let aliens = [];
        let shields = [];
        let score = 0;
        let lives = 3;
        let level = 1;
        let gameOver = false;
        let gameStarted = false;
        let alienDirection = 1;
        let alienSpeed = 0.5;
        let alienMoveTimer = 0;
        let alienMoveInterval = 60;
        let lastAlienShot = 0;
        let alienShotInterval = 120;
        let keys = {};
        let gameLoop = null;

        function initGame() {
            player = { x: canvas.width / 2 - PLAYER_WIDTH / 2, y: 440 };
            playerBullets = [];
            alienBullets = [];
            score = 0;
            lives = 3;
            gameOver = false;
            alienDirection = 1;
            alienSpeed = 0.5;
            alienMoveTimer = 0;
            alienMoveInterval = 60 - (level - 1) * 5;
            if (alienMoveInterval < 15) alienMoveInterval = 15;
            lastAlienShot = 0;
            alienShotInterval = Math.max(30, 120 - (level - 1) * 10);
            initAliens();
            initShields();
            updateUI();
        }

        function initAliens() {
            aliens = [];
            for (let row = 0; row < ALIEN_ROWS; row++) {
                for (let col = 0; col < ALIEN_COLS; col++) {
                    aliens.push({
                        x: 50 + col * 50,
                        y: 50 + row * 40,
                        alive: true,
                        type: row < 1 ? 3 : row < 3 ? 2 : 1
                    });
                }
            }
        }

        function initShields() {
            shields = [];
            for (let i = 0; i < 4; i++) {
                let sx = 80 + i * 150;
                shields.push({
                    x: sx,
                    y: 400,
                    blocks: []
                });
                for (let bx = 0; bx < SHIELD_WIDTH / 6; bx++) {
                    for (let by = 0; by < SHIELD_HEIGHT / 6; by++) {
                        if (by < 2 || (bx > 2 && bx < 8)) {
                            shields[i].blocks.push({
                                x: bx * 6,
                                y: by * 6,
                                alive: true
                            });
                        }
                    }
                }
            }
        }

        function startGame() {
            document.getElementById('startScreen').style.display = 'none';
            document.getElementById('gameOverScreen').style.display = 'none';
            document.getElementById('levelComplete').style.display = 'none';
            initGame();
            gameStarted = true;
            if (gameLoop) cancelAnimationFrame(gameLoop);
            gameLoop = requestAnimationFrame(gameStep);
        }

        function gameStep() {
            if (gameOver || !gameStarted) return;
            update();
            render();
            gameLoop = requestAnimationFrame(gameStep);
        }

        function update() {
            if (keys['ArrowLeft'] || keys['a'] || keys['A'] || keys['ф'] || keys['Ф']) {
                player.x -= PLAYER_SPEED;
                if (player.x < 0) player.x = 0;
            }
            if (keys['ArrowRight'] || keys['d'] || keys['D'] || keys['в'] || keys['В']) {
                player.x += PLAYER_SPEED;
                if (player.x > canvas.width - PLAYER_WIDTH) player.x = canvas.width - PLAYER_WIDTH;
            }

            playerBullets = playerBullets.filter(b => {
                b.y -= BULLET_SPEED;
                return b.y > -BULLET_HEIGHT;
            });

            alienBullets = alienBullets.filter(b => {
                b.y += ALIEN_BULLET_SPEED;
                return b.y < canvas.height;
            });

            alienMoveTimer++;
            if (alienMoveTimer >= alienMoveInterval) {
                alienMoveTimer = 0;
                moveAliens();
            }

            lastAlienShot++;
            if (lastAlienShot >= alienShotInterval) {
                lastAlienShot = 0;
                alienShoot();
            }

            checkCollisions();
            updateUI();
        }

        function moveAliens() {
            let hitEdge = false;
            let liveAliens = aliens.filter(a => a.alive);

            for (let alien of liveAliens) {
                alien.x += alienDirection * 10;
                if (alien.x <= 10 || alien.x >= canvas.width - ALIEN_WIDTH - 10) {
                    hitEdge = true;
                }
            }

            if (hitEdge) {
                alienDirection *= -1;
                for (let alien of liveAliens) {
                    alien.y += 20;
                    if (alien.y + ALIEN_HEIGHT > player.y) {
                        endGame();
                        return;
                    }
                }
            }

            let remaining = liveAliens.length;
            alienMoveInterval = Math.max(5, Math.floor(60 * (remaining / (ALIEN_ROWS * ALIEN_COLS))));

            if (remaining === 0) {
                levelComplete();
            }
        }

        function alienShoot() {
            let liveAliens = aliens.filter(a => a.alive);
            if (liveAliens.length === 0) return;

            let shooter = liveAliens[Math.floor(Math.random() * liveAliens.length)];
            alienBullets.push({
                x: shooter.x + ALIEN_WIDTH / 2 - BULLET_WIDTH / 2,
                y: shooter.y + ALIEN_HEIGHT
            });
        }

        function checkCollisions() {
            for (let i = playerBullets.length - 1; i >= 0; i--) {
                let b = playerBullets[i];
                for (let alien of aliens) {
                    if (alien.alive &&
                        b.x < alien.x + ALIEN_WIDTH &&
                        b.x + BULLET_WIDTH > alien.x &&
                        b.y < alien.y + ALIEN_HEIGHT &&
                        b.y + BULLET_HEIGHT > alien.y) {
                        alien.alive = false;
                        playerBullets.splice(i, 1);
                        score += alien.type * 10;
                        updateUI();
                        break;
                    }
                }
            }

            for (let i = alienBullets.length - 1; i >= 0; i--) {
                let b = alienBullets[i];
                if (b.x < player.x + PLAYER_WIDTH &&
                    b.x + BULLET_WIDTH > player.x &&
                    b.y < player.y + PLAYER_HEIGHT &&
                    b.y + BULLET_HEIGHT > player.y) {
                    alienBullets.splice(i, 1);
                    lives--;
                    updateUI();
                    if (lives <= 0) {
                        endGame();
                        return;
                    }
                    player.x = canvas.width / 2 - PLAYER_WIDTH / 2;
                }
            }

            for (let shield of shields) {
                for (let block of shield.blocks) {
                    if (!block.alive) continue;
                    let bx = shield.x + block.x;
                    let by = shield.y + block.y;

                    for (let i = playerBullets.length - 1; i >= 0; i--) {
                        let b = playerBullets[i];
                        if (b.x < bx + 6 && b.x + BULLET_WIDTH > bx &&
                            b.y < by + 6 && b.y + BULLET_HEIGHT > by) {
                            block.alive = false;
                            playerBullets.splice(i, 1);
                            break;
                        }
                    }

                    for (let i = alienBullets.length - 1; i >= 0; i--) {
                        let b = alienBullets[i];
                        if (b.x < bx + 6 && b.x + BULLET_WIDTH > bx &&
                            b.y < by + 6 && b.y + BULLET_HEIGHT > by) {
                            block.alive = false;
                            alienBullets.splice(i, 1);
                            break;
                        }
                    }
                }
            }
        }

        function endGame() {
            gameOver = true;
            cancelAnimationFrame(gameLoop);
            document.getElementById('finalScore').textContent = score;
            document.getElementById('gameOverScreen').style.display = 'block';
        }

        function levelComplete() {
            level++;
            document.getElementById('level').textContent = level;
            document.getElementById('levelComplete').style.display = 'block';
            setTimeout(() => {
                document.getElementById('levelComplete').style.display = 'none';
                initGame();
                gameLoop = requestAnimationFrame(gameStep);
            }, 2000);
        }

        function updateUI() {
            document.getElementById('score').textContent = score;
            document.getElementById('level').textContent = level;
            let heartsStr = '';
            for (let i = 0; i < lives; i++) heartsStr += '♥';
            document.getElementById('lives').textContent = heartsStr || '×';
        }

        function render() {
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.fillStyle = '#21bf4b';
            ctx.beginPath();
            ctx.moveTo(player.x + PLAYER_WIDTH / 2, player.y);
            ctx.lineTo(player.x, player.y + PLAYER_HEIGHT);
            ctx.lineTo(player.x + PLAYER_WIDTH, player.y + PLAYER_HEIGHT);
            ctx.closePath();
            ctx.fill();

            ctx.fillStyle = '#0057b3';
            ctx.fillRect(player.x + PLAYER_WIDTH / 2 - 3, player.y - 5, 6, 8);

            for (let alien of aliens) {
                if (!alien.alive) continue;
                let color = alien.type === 3 ? '#ff6c59' : alien.type === 2 ? '#ffcc00' : '#47a8ff';
                ctx.fillStyle = color;
                ctx.fillRect(alien.x + 5, alien.y, ALIEN_WIDTH - 10, ALIEN_HEIGHT - 6);
                ctx.fillRect(alien.x, alien.y + 6, ALIEN_WIDTH, ALIEN_HEIGHT - 12);
                ctx.fillRect(alien.x + 8, alien.y + ALIEN_HEIGHT - 6, 4, 4);
                ctx.fillRect(alien.x + ALIEN_WIDTH - 12, alien.y + ALIEN_HEIGHT - 6, 4, 4);
            }

            ctx.fillStyle = '#ffffff';
            for (let b of playerBullets) {
                ctx.fillRect(b.x, b.y, BULLET_WIDTH, BULLET_HEIGHT);
            }

            ctx.fillStyle = '#ff6c59';
            for (let b of alienBullets) {
                ctx.fillRect(b.x, b.y, BULLET_WIDTH, BULLET_HEIGHT);
            }

            for (let shield of shields) {
                for (let block of shield.blocks) {
                    if (!block.alive) continue;
                    ctx.fillStyle = '#21bf4b';
                    ctx.fillRect(shield.x + block.x, shield.y + block.y, 6, 6);
                }
            }

            ctx.strokeStyle = '#333';
            ctx.beginPath();
            ctx.moveTo(0, canvas.height - 20);
            ctx.lineTo(canvas.width, canvas.height - 20);
            ctx.stroke();
        }

        document.addEventListener('keydown', (e) => {
            keys[e.key] = true;

            if (e.key === ' ' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {
                e.preventDefault();
            }

            if (!gameStarted || gameOver) {
                if (e.key === 'Enter') startGame();
                return;
            }

            if (e.key === ' ' && playerBullets.length < 3) {
                playerBullets.push({
                    x: player.x + PLAYER_WIDTH / 2 - BULLET_WIDTH / 2,
                    y: player.y - BULLET_HEIGHT
                });
            }
        });

        document.addEventListener('keyup', (e) => {
            keys[e.key] = false;
        });

        document.getElementById('startScreen').style.display = 'block';
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(INVADERS_TEMPLATE, version=VERSION)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5004)
    args = parser.parse_args()

    print(f"Space Invaders {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
