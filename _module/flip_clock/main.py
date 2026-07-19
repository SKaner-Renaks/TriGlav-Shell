import os
import argparse
import logging
import configparser
from flask import Flask, render_template_string, send_from_directory

VERSION = '1.1.2'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
CONFIG_PATH = os.path.join(SHELL_DIR, '_data', 'config.cfg')


def get_theme():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding='utf-8')
    return cfg.get('shell', 'global_theme', fallback='dark')


@app.route('/')
def index():
    theme = get_theme()
    return render_template_string(FLIP_TEMPLATE, version=VERSION, theme=theme, environment=args.environment)


@app.route('/_images/<path:filename>')
def serve_image(filename):
    return send_from_directory(BASE_DIR, filename)


FLIP_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flip Clock {{ version }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        {% if theme == 'light' %}
        :root {
            --bg: #f5f5f5;
            --card-bg: #ffffff;
            --card-text: #1a1a1a;
            --card-border: #d0d0d0;
            --accent: #0066cc;
            --label: #666;
        }
        {% else %}
        :root {
            --bg: #0e0e10;
            --card-bg: #1e1e24;
            --card-text: #f3f3f6;
            --card-border: #141416;
            --accent: #47a8ff;
            --label: #999;
        }
        {% endif %}

        body {
            background: var(--bg);
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
        }

        .header {
            background: var(--card-bg);
            border-bottom: 1px solid var(--card-border);
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }
        .header h1 { font-size: 18px; font-weight: 600; color: var(--accent); }
        .header-info { font-size: 12px; color: var(--label); margin-top: 2px; }
        .controls { display: flex; gap: 8px; align-items: center; }
        .btn { padding: 6px 14px; border: 1px solid var(--card-border); border-radius: 3px; cursor: pointer; font-size: 12px; font-family: inherit; background: var(--card-bg); color: var(--card-text); transition: background 0.15s; }
        .btn:hover { background: var(--accent); color: #fff; border-color: var(--accent); }
        .btn svg { width: 16px; height: 16px; fill: currentColor; vertical-align: middle; }

        .fs-exit {
            position: fixed;
            top: 14px;
            right: 14px;
            width: 40px;
            height: 40px;
            cursor: pointer;
            opacity: 0.5;
            transition: opacity 0.2s;
            z-index: 100;
            display: none;
        }
        .fs-exit:hover { opacity: 1; }
        .fs-exit svg { width: 100%; height: 100%; fill: var(--label); }

        .main {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        .clock-wrap {
            display: flex;
            align-items: center;
            gap: 24px;
        }

        .group {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .digits {
            display: flex;
            gap: 4px;
        }

        .flip-card {
            position: relative;
            width: 240px;
            height: 360px;
            font-size: 220px;
            font-weight: 700;
            color: var(--card-text);
            perspective: 800px;
        }

        .card-half {
            position: absolute;
            left: 0;
            width: 100%;
            height: 50%;
            overflow: hidden;
            background: var(--card-bg);
            display: flex;
            justify-content: center;
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
        }

        .card-half span {
            position: absolute;
            left: 0;
            right: 0;
            text-align: center;
        }

        .up {
            top: 0;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid var(--card-border);
        }
        .up span {
            top: 0;
            bottom: -100%;
            line-height: 360px;
        }

        .down {
            bottom: 0;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
            box-shadow: inset 0 20px 40px rgba(0,0,0,0.15);
        }
        .down span {
            bottom: 0;
            top: -100%;
            line-height: 360px;
        }

        .flip-card .card-half.page {
            z-index: 3;
        }

        .flip-card .card-half.page.up {
            transform-origin: 50% 100%;
            animation: flipTop 0.4s ease-in forwards;
        }

        .flip-card .card-half.page.down {
            transform-origin: 50% 0%;
            animation: flipBottom 0.4s ease-out 0.4s forwards;
            transform: rotateX(90deg);
            z-index: 2;
        }

        .flip-card::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            width: 100%;
            height: 2px;
            background: rgba(0, 0, 0, 0.3);
            z-index: 5;
        }

        @keyframes flipTop {
            0%   { transform: rotateX(0deg); }
            100% { transform: rotateX(-90deg); }
        }

        @keyframes flipBottom {
            0%   { transform: rotateX(90deg); }
            100% { transform: rotateX(0deg); }
        }

        .sep {
            font-size: 160px;
            font-weight: 700;
            color: var(--accent);
            line-height: 360px;
            padding-bottom: 64px;
        }

        .lbl {
            margin-top: 10px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 3px;
            color: var(--label);
        }

        .fs { display: none; }

        @media (max-width: 768px) {
            .clock-wrap { gap: 10px; }
            .flip-card { width: 60px; height: 90px; font-size: 56px; }
            .up span, .down span { line-height: 90px; }
            .sep { font-size: 40px; line-height: 90px; padding-bottom: 16px; }
        }
    </style>
</head>
<body>
    <div class="header" id="headbar" data-zone="flip_clock.display">
        <div>
            <h1>Flip Clock {{ version }}</h1>
            <div class="header-info">Часы в стиле Flip Clock</div>
        </div>
        <div class="controls">
            <button class="btn" onclick="toggleFS()" title="Fullscreen" id="fsBtn">
                <svg id="fsIcon" viewBox="0 -960 960 960"><path d="M160-160v-270.77h30.77V-212L748-769.23H529.23V-800H800v270.77h-30.77V-748L212-190.77h218.77V-160H160Z"/></svg>
            </button>
        </div>
    </div>
    <div class="fs-exit" id="fsExit" onclick="toggleFS()" title="Exit fullscreen">
        <svg viewBox="0 -960 960 960"><path d="M303-160v-143H160v-30.77h173.77V-160H303Zm324 0v-173.77h173.77V-303h-143v143H627ZM160-626.23V-657h143v-143h30.77v173.77H160Zm467 0V-800h30.77v143h143v30.77H627Z"/></svg>
    </div>
    <div class="main">
    <div class="clock-wrap">
        <div class="group">
            <div class="digits">
                <div class="flip-card" id="h1"><div class="card-half up bg"><span>0</span></div><div class="card-half down bg"><span>0</span></div></div>
                <div class="flip-card" id="h2"><div class="card-half up bg"><span>0</span></div><div class="card-half down bg"><span>0</span></div></div>
            </div>
            <div class="lbl">Hours</div>
        </div>
        <div class="sep">:</div>
        <div class="group">
            <div class="digits">
                <div class="flip-card" id="m1"><div class="card-half up bg"><span>0</span></div><div class="card-half down bg"><span>0</span></div></div>
                <div class="flip-card" id="m2"><div class="card-half up bg"><span>0</span></div><div class="card-half down bg"><span>0</span></div></div>
            </div>
            <div class="lbl">Minutes</div>
        </div>
        <div class="sep">:</div>
        <div class="group">
            <div class="digits">
                <div class="flip-card" id="s1"><div class="card-half up bg"><span>0</span></div><div class="card-half down bg"><span>0</span></div></div>
                <div class="flip-card" id="s2"><div class="card-half up bg"><span>0</span></div><div class="card-half down bg"><span>0</span></div></div>
            </div>
            <div class="lbl">Seconds</div>
        </div>
    </div>
    </div>

    <script>
        function updateCard(id, val) {
            var card = document.getElementById(id);
            var bgUp = card.querySelector('.up.bg span');
            var bgDown = card.querySelector('.down.bg span');
            if (bgUp.textContent === val) return;

            var old = bgUp.textContent;

            var pUp = document.createElement('div');
            pUp.className = 'card-half up page';
            pUp.innerHTML = '<span>' + old + '</span>';

            var pDown = document.createElement('div');
            pDown.className = 'card-half down page';
            pDown.innerHTML = '<span>' + val + '</span>';

            bgUp.textContent = val;

            card.appendChild(pUp);
            card.appendChild(pDown);

            setTimeout(function(){ bgDown.textContent = val; }, 400);
            setTimeout(function(){ pUp.remove(); pDown.remove(); }, 800);
        }

        function tick() {
            var d = new Date();
            var h = String(d.getHours()).padStart(2, '0');
            var m = String(d.getMinutes()).padStart(2, '0');
            var s = String(d.getSeconds()).padStart(2, '0');
            updateCard('h1', h[0]);
            updateCard('h2', h[1]);
            updateCard('m1', m[0]);
            updateCard('m2', m[1]);
            updateCard('s1', s[0]);
            updateCard('s2', s[1]);
        }

        function toggleFS() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(function(){});
            } else {
                document.exitFullscreen().catch(function(){});
            }
        }

        document.addEventListener('fullscreenchange', function() {
            var bar = document.getElementById('headbar');
            var exit = document.getElementById('fsExit');
            if (document.fullscreenElement) {
                bar.style.display = 'none';
                exit.style.display = 'block';
            } else {
                bar.style.display = '';
                exit.style.display = 'none';
            }
        });

        tick();
        setInterval(tick, 1000);
    </script>
{% if environment == 'development' %}
<style>
.dev-label{position:fixed;background:rgba(0,0,0,.88);color:#47a8ff;font:600 10px/1.2 "Cascadia Mono","Consolas",monospace;padding:2px 8px;border-radius:0 0 4px 0;z-index:99999;pointer-events:none;white-space:nowrap;display:none}
</style>
<script>
(function(){var l=document.createElement("div");l.className="dev-label";document.body.appendChild(l);var timer=null,currentZone=null,mx=0,my=0;function showLabel(z){l.textContent=":: "+z.getAttribute("data-zone");l.style.display="block";var left=mx+12,top=my+12;if(left+l.offsetWidth>window.innerWidth)left=mx-12-l.offsetWidth;if(top+l.offsetHeight>window.innerHeight)top=my-12-l.offsetHeight;l.style.left=left+"px";l.style.top=top+"px"}function hideLabel(){l.style.display="none"}function startTimer(z){clearTimeout(timer);timer=setTimeout(function(){if(currentZone===z)showLabel(z)},500)}document.addEventListener("mouseover",function(e){var z=e.target.closest("[data-zone]");if(z){currentZone=z;hideLabel();startTimer(z)}});document.addEventListener("mouseout",function(e){var z=e.target.closest("[data-zone]");if(z){clearTimeout(timer);currentZone=null;hideLabel()}});document.addEventListener("mousemove",function(e){mx=e.clientX;my=e.clientY;if(l.style.display==="block"){hideLabel();if(currentZone)startTimer(currentZone)}});})();
</script>
{% endif %}

</body>
</html>
"""


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5042)
    parser.add_argument('--environment', default='production', choices=['production', 'development'])
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log_file.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('Flip Clock %s started', VERSION)

    print(f"Flip Clock {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
