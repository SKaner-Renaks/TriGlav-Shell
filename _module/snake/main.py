import os
import argparse
import logging
from flask import Flask, render_template_string

VERSION = '1.2'

app = Flask(__name__)

SNAKE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Змейка {{ version }}</title>
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
        .power-up-timer {
            color: #39ff14;
            font-weight: 600;
            display: none;
        }
        .power-up-timer.active {
            display: inline;
            animation: blink 0.3s infinite;
        }
        @keyframes blink {
            50% { opacity: 0.5; }
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
        .game-over {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(26, 26, 26, 0.95);
            padding: 30px 40px;
            border-radius: 8px;
            border: 2px solid #ff6c59;
            text-align: center;
            display: none;
        }
        .game-over h2 {
            color: #ff6c59;
            margin-bottom: 10px;
        }
        .game-over p {
            margin-bottom: 15px;
            color: #ccc;
        }
        .game-over .btn {
            background: #0057b3;
            color: #f2f2f2;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .game-over .btn:hover {
            background: #0073d9;
        }
        .start-screen {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(26, 26, 26, 0.95);
            padding: 30px 40px;
            border-radius: 8px;
            border: 2px solid #47a8ff;
            text-align: center;
        }
        .start-screen h2 {
            color: #47a8ff;
            margin-bottom: 10px;
        }
        .start-screen p {
            margin-bottom: 15px;
            color: #ccc;
        }
        .start-screen .btn {
            background: #0057b3;
            color: #f2f2f2;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .start-screen .btn:hover {
            background: #0073d9;
        }
        .paused {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #ffcc00;
            font-size: 24px;
            font-weight: 600;
            display: none;
        }
    </style>
</head>
<body>
    <div class="game-container" style="position: relative;">
        <div class="header">
            <div class="title">Змейка {{ version }}</div>
            <div class="stats">
                <div class="stat">
                    <span class="stat-label">Счёт:</span>
                    <span class="stat-value" id="score">0</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Бонус:</span>
                    <span class="power-up-timer" id="powerUpTimer">5 сек</span>
                </div>
            </div>
        </div>
        <canvas id="gameCanvas" width="400" height="400"></canvas>
        <div class="game-over" id="gameOver">
            <h2>Игра окончена!</h2>
            <p>Ваш счёт: <span id="finalScore">0</span></p>
            <button class="btn" onclick="resetGame()">Играть снова</button>
        </div>
        <div class="start-screen" id="startScreen">
            <h2>🐍 Змейка</h2>
            <p>Собирайте еду, избегайте стен и себя.<br>
            Ярко-зелёный бонус даёт неуязвимость на 5 секунд!</p>
            <button class="btn" onclick="startGame()">Начать игру</button>
        </div>
        <div class="paused" id="paused">ПАУЗА</div>
        <div class="controls-info">
            WASD / ↑↓←→ — управление | Space — пауза | Enter — начать заново
        </div>
    </div>

    <script>
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        const CELL_SIZE = 20;
        const GRID_SIZE = 20;
        const GAME_SPEED = 150;

        let snake = [];
        let food = null;
        let powerUp = null;
        let direction = { x: 1, y: 0 };
        let nextDirection = { x: 1, y: 0 };
        let score = 0;
        let powerUpActive = false;
        let powerUpTimer = 0;
        let powerUpInterval = null;
        let gameOver = false;
        let paused = false;
        let gameLoop = null;
        let gameStarted = false;

        function init() {
            snake = [
                { x: 5, y: 10 },
                { x: 4, y: 10 },
                { x: 3, y: 10 }
            ];
            direction = { x: 1, y: 0 };
            nextDirection = { x: 1, y: 0 };
            score = 0;
            powerUpActive = false;
            powerUpTimer = 0;
            gameOver = false;
            paused = false;
            powerUp = null;
            gameStarted = false;
            document.getElementById('score').textContent = '0';
            document.getElementById('powerUpTimer').classList.remove('active');
            document.getElementById('gameOver').style.display = 'none';
            document.getElementById('startScreen').style.display = 'block';
            document.getElementById('paused').style.display = 'none';
            spawnFood();
            render();
        }

        function startGame() {
            document.getElementById('startScreen').style.display = 'none';
            gameStarted = true;
            if (gameLoop) clearInterval(gameLoop);
            gameLoop = setInterval(gameStep, GAME_SPEED);
        }

        function spawnFood() {
            let pos;
            do {
                pos = {
                    x: Math.floor(Math.random() * GRID_SIZE),
                    y: Math.floor(Math.random() * GRID_SIZE)
                };
            } while (isOccupied(pos));
            food = pos;

            if (!powerUp && Math.random() < 0.15) {
                spawnPowerUp();
            }
        }

        function spawnPowerUp() {
            let pos;
            do {
                pos = {
                    x: Math.floor(Math.random() * GRID_SIZE),
                    y: Math.floor(Math.random() * GRID_SIZE)
                };
            } while (isOccupied(pos) || (food && pos.x === food.x && pos.y === food.y));
            powerUp = pos;
        }

        function isOccupied(pos) {
            return snake.some(seg => seg.x === pos.x && seg.y === pos.y);
        }

        function gameStep() {
            if (gameOver || paused || !gameStarted) return;

            direction = { ...nextDirection };

            let newHead = {
                x: snake[0].x + direction.x,
                y: snake[0].y + direction.y
            };

            if (powerUpActive) {
                if (newHead.x < 0) newHead.x = GRID_SIZE - 1;
                else if (newHead.x >= GRID_SIZE) newHead.x = 0;
                if (newHead.y < 0) newHead.y = GRID_SIZE - 1;
                else if (newHead.y >= GRID_SIZE) newHead.y = 0;
            } else {
                if (newHead.x < 0 || newHead.x >= GRID_SIZE ||
                    newHead.y < 0 || newHead.y >= GRID_SIZE) {
                    endGame();
                    return;
                }
                if (isOccupied(newHead)) {
                    endGame();
                    return;
                }
            }

            snake.unshift(newHead);

            if (food && newHead.x === food.x && newHead.y === food.y) {
                score++;
                document.getElementById('score').textContent = score;
                spawnFood();
            } else {
                snake.pop();
            }

            if (powerUp && newHead.x === powerUp.x && newHead.y === powerUp.y) {
                activatePowerUp();
                powerUp = null;
            }

            render();
        }

        function activatePowerUp() {
            powerUpActive = true;
            powerUpTimer += 5;
            document.getElementById('powerUpTimer').textContent = powerUpTimer + ' сек';
            document.getElementById('powerUpTimer').classList.add('active');

            if (powerUpInterval) clearInterval(powerUpInterval);
            powerUpInterval = setInterval(() => {
                powerUpTimer--;
                if (powerUpTimer <= 0) {
                    powerUpActive = false;
                    powerUpTimer = 0;
                    document.getElementById('powerUpTimer').classList.remove('active');
                    clearInterval(powerUpInterval);
                    powerUpInterval = null;
                } else {
                    document.getElementById('powerUpTimer').textContent = powerUpTimer + ' сек';
                }
            }, 1000);
        }

        function endGame() {
            gameOver = true;
            clearInterval(gameLoop);
            if (powerUpInterval) {
                clearInterval(powerUpInterval);
                powerUpInterval = null;
            }
            document.getElementById('finalScore').textContent = score;
            document.getElementById('gameOver').style.display = 'block';
        }

        function resetGame() {
            init();
        }

        function render() {
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.strokeStyle = '#333';
            ctx.lineWidth = 0.5;
            for (let i = 0; i <= GRID_SIZE; i++) {
                ctx.beginPath();
                ctx.moveTo(i * CELL_SIZE, 0);
                ctx.lineTo(i * CELL_SIZE, canvas.height);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(0, i * CELL_SIZE);
                ctx.lineTo(canvas.width, i * CELL_SIZE);
                ctx.stroke();
            }

            if (food) {
                ctx.fillStyle = '#ffffff';
                ctx.shadowColor = '#ffffff';
                ctx.shadowBlur = 10;
                ctx.fillRect(food.x * CELL_SIZE + 2, food.y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4);
                ctx.shadowBlur = 0;
            }

            if (powerUp) {
                ctx.fillStyle = '#39ff14';
                ctx.shadowColor = '#39ff14';
                ctx.shadowBlur = 15;
                ctx.fillRect(powerUp.x * CELL_SIZE + 1, powerUp.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
                ctx.shadowBlur = 0;
            }

            snake.forEach((seg, i) => {
                if (powerUpActive && Math.floor(Date.now() / 150) % 2 === 0) {
                    ctx.fillStyle = 'rgba(33, 191, 75, 0.5)';
                } else {
                    ctx.fillStyle = i === 0 ? '#21bf4b' : '#1a8a3a';
                }
                ctx.fillRect(seg.x * CELL_SIZE + 1, seg.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
            });
        }

        document.addEventListener('keydown', (e) => {
            if (!gameStarted) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    startGame();
                }
                return;
            }

            if (gameOver) {
                if (e.key === 'Enter') resetGame();
                return;
            }

            if (e.key === ' ' || e.key === 'Escape') {
                e.preventDefault();
                paused = !paused;
                document.getElementById('paused').style.display = paused ? 'block' : 'none';
                return;
            }

            switch(e.key) {
                case 'ArrowUp':
                case 'w':
                case 'W':
                case 'ц':
                case 'Ц':
                    if (direction.y !== 1) nextDirection = { x: 0, y: -1 };
                    break;
                case 'ArrowDown':
                case 's':
                case 'S':
                case 'ы':
                case 'Ы':
                    if (direction.y !== -1) nextDirection = { x: 0, y: 1 };
                    break;
                case 'ArrowLeft':
                case 'a':
                case 'A':
                case 'ф':
                case 'Ф':
                    if (direction.x !== 1) nextDirection = { x: -1, y: 0 };
                    break;
                case 'ArrowRight':
                case 'd':
                case 'D':
                case 'в':
                case 'В':
                    if (direction.x !== -1) nextDirection = { x: 1, y: 0 };
                    break;
            }
        });

        init();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(SNAKE_TEMPLATE, version=VERSION)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5003)
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log_file.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('Snake %s started', VERSION)

    print(f"Snake {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
