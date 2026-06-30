import os
import json
import argparse
from flask import Flask, render_template_string, jsonify, request

VERSION = '1.1'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
CONFIG_PATH = os.path.join(SHELL_DIR, '_data', 'config.cfg')

import configparser


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding='utf-8')
    return cfg


def get_autostart_config():
    cfg = load_config()
    if 'modules_auto_start' in cfg:
        return dict(cfg['modules_auto_start'])
    return {'usual': 'all', 'service': 'all'}


def save_autostart_config(usual, service):
    cfg = load_config()
    if not cfg.has_section('modules_auto_start'):
        cfg.add_section('modules_auto_start')
    cfg.set('modules_auto_start', 'usual', usual)
    cfg.set('modules_auto_start', 'service', service)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        cfg.write(f)


def get_all_modules():
    modules = []
    module_dir = os.path.join(SHELL_DIR, '_module')
    for name in sorted(os.listdir(module_dir)):
        mod_path = os.path.join(module_dir, name)
        manifest_path = os.path.join(mod_path, 'manifest.json')
        if os.path.isdir(mod_path) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                if manifest.get('name') == 'shell':
                    continue
                modules.append(manifest)
            except Exception:
                pass
    return modules


MANAGER_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Модули {{ version }}</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; background:#1a1a1a; color:#f2f2f2; min-height:100vh; font-size:13px; }
        .header { background:#262626; border-bottom:1px solid #404040; padding:14px 20px; display:flex; justify-content:space-between; align-items:center; }
        .header h1 { font-size:18px; font-weight:600; color:#47a8ff; }
        .header-info { font-size:12px; color:#999; margin-top:2px; }
        .controls { display:flex; gap:8px; align-items:center; }
        .btn { padding:6px 14px; border:1px solid #595959; border-radius:3px; cursor:pointer; font-size:12px; font-family:inherit; transition:background 0.15s; }
        .btn-primary { background:#0057b3; color:#f2f2f2; border-color:#0057b3; }
        .btn-primary:hover { background:#0073d9; }
        .btn-default { background:#404040; color:#f2f2f2; }
        .btn-default:hover { background:#595959; }
        .btn-success { background:#1a3d24; color:#21bf4b; border-color:#21bf4b; }
        .btn-success:hover { background:#21bf4b; color:#fff; }
        .content { padding:16px 20px; }
        .panel { background:#262626; border:1px solid #404040; border-radius:3px; margin-bottom:12px; }
        .panel-header { background:#333; padding:8px 12px; border-bottom:1px solid #404040; font-weight:600; color:#47a8ff; font-size:12px; display:flex; justify-content:space-between; align-items:center; }
        .panel-body { padding:12px; }
        .warning { background:#3d2a00; border:1px solid #cc7a00; border-radius:3px; padding:8px 12px; margin-bottom:12px; color:#ffcc00; font-size:12px; }
        .lock-row { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
        .lock-label { font-size:12px; color:#999; }
        .toggle { width:40px; height:22px; border-radius:11px; border:none; cursor:pointer; position:relative; transition:background 0.3s; }
        .toggle-on { background:#21bf4b; }
        .toggle-on::after { content:''; position:absolute; width:18px; height:18px; background:#fff; border-radius:50%; top:2px; right:2px; transition:0.3s; }
        .toggle-off { background:#666; }
        .toggle-off::after { content:''; position:absolute; width:18px; height:18px; background:#fff; border-radius:50%; top:2px; left:2px; transition:0.3s; }
        .module-table { width:100%; border-collapse:collapse; font-size:12px; }
        .module-table th { background:#333; padding:8px 10px; text-align:left; color:#47a8ff; font-weight:600; border-bottom:1px solid #404040; }
        .module-table td { padding:8px 10px; border-bottom:1px solid #333; }
        .module-table tr:hover { background:#2d2d2d; }
        .module-table tr.disabled td { color:#666; }
        .toggle-btn { width:36px; height:20px; border-radius:10px; border:none; cursor:pointer; position:relative; transition:background 0.3s; }
        .toggle-btn.on { background:#21bf4b; }
        .toggle-btn.on::after { content:''; position:absolute; width:14px; height:14px; background:#fff; border-radius:50%; top:3px; right:3px; transition:0.3s; }
        .toggle-btn.off { background:#666; }
        .toggle-btn.off::after { content:''; position:absolute; width:14px; height:14px; background:#fff; border-radius:50%; top:3px; left:3px; transition:0.3s; }
        .toggle-btn:disabled { opacity:0.4; cursor:not-allowed; }
        .service-section { margin-top:16px; padding-top:16px; border-top:1px solid #404040; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Модули {{ version }}</h1>
            <div class="header-info">Управление автозапуском модулей оболочки</div>
        </div>
        <div class="controls">
            <button class="btn btn-primary" onclick="saveAndRestart()">Применить и перезапустить</button>
        </div>
    </div>
    <div class="content">
        <div class="panel">
            <div class="panel-header">Обычные модули</div>
            <div class="panel-body">
                <table class="module-table">
                    <thead>
                        <tr><th>Модуль</th><th>Описание</th><th>Статус</th></tr>
                    </thead>
                    <tbody id="usualModules"></tbody>
                </table>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Сервисные модули</div>
            <div class="panel-body">
                <div class="warning">⚠ Модули нужны для работы оболочки. Отключение может повлиять на функциональность.</div>
                <div class="lock-row">
                    <span class="lock-label">Блокировка:</span>
                    <button class="toggle toggle-off" id="lockToggle" onclick="toggleLock()"></button>
                    <span class="lock-label" id="lockStatus">Включена</span>
                </div>
                <table class="module-table" id="serviceTable">
                    <thead>
                        <tr><th>Модуль</th><th>Описание</th><th>Статус</th></tr>
                    </thead>
                    <tbody id="serviceModules"></tbody>
                </table>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Игры</div>
            <div class="panel-body">
                <table class="module-table">
                    <thead>
                        <tr><th>Модуль</th><th>Описание</th><th>Статус</th></tr>
                    </thead>
                    <tbody id="gameModules"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let modules = [];
        let currentConfig = {};
        let lockEnabled = true;

        async function loadModules() {
            try {
                const r = await fetch('/api/modules_list');
                const data = await r.json();
                modules = data.modules;
                currentConfig = data.config;
                renderModules();
            } catch(e) {}
        }

        function renderModules() {
            const usualBody = document.getElementById('usualModules');
            const serviceBody = document.getElementById('serviceModules');
            const gameBody = document.getElementById('gameModules');
            let usualHtml = '';
            let serviceHtml = '';
            let gameHtml = '';

            modules.forEach(m => {
                const type = m.type || 'usual';
                const configKey = type;
                const enabled = (currentConfig[configKey] === 'all' || (currentConfig[configKey] || '').split(',').map(s=>s.trim()).includes(m.name));
                const isService = type === 'service';

                const btnClass = enabled ? 'toggle-btn on' : 'toggle-btn off';
                const rowClass = enabled ? '' : 'disabled';
                const row = '<tr class="' + rowClass + '"><td><strong>' + m.title + '</strong></td><td>' + (m.description || '') + '</td><td><button class="' + btnClass + '" data-name="' + m.name + '" onclick="toggleModule(this)" ' + (lockEnabled && isService ? 'disabled' : '') + '></button></td></tr>';

                if (type === 'service') serviceHtml += row;
                else if (type === 'game') gameHtml += row;
                else usualHtml += row;
            });

            usualBody.innerHTML = usualHtml || '<tr><td colspan="3" style="color:#999;text-align:center;">Нет обычных модулей</td></tr>';
            serviceBody.innerHTML = serviceHtml || '<tr><td colspan="3" style="color:#999;text-align:center;">Нет сервисных модулей</td></tr>';
            gameBody.innerHTML = gameHtml || '<tr><td colspan="3" style="color:#999;text-align:center;">Нет игр</td></tr>';
        }

        function toggleModule(btn) {
            const name = btn.dataset.name;
            const isOn = btn.classList.contains('on');
            btn.className = isOn ? 'toggle-btn off' : 'toggle-btn on';

            const m = modules.find(m => m.name === name);
            if (!m) return;

            const key = m.type || 'usual';
            let list = currentConfig[key] === 'all' ? modules.filter(x => (x.type || 'usual') === m.type).map(x => x.name) : (currentConfig[key] || '').split(',').map(s => s.trim());

            if (isOn) {
                list = list.filter(n => n !== name);
            } else {
                if (!list.includes(name)) list.push(name);
            }

            const allNames = modules.filter(x => x.type === m.type).map(x => x.name);
            if (list.length === allNames.length) {
                currentConfig[key] = 'all';
            } else {
                currentConfig[key] = list.join(',');
            }
        }

        function toggleLock() {
            lockEnabled = !lockEnabled;
            const toggle = document.getElementById('lockToggle');
            const status = document.getElementById('lockStatus');
            toggle.className = lockEnabled ? 'toggle toggle-on' : 'toggle toggle-off';
            status.textContent = lockEnabled ? 'Включена' : 'Отключена';
            renderModules();
        }

        async function saveAndRestart() {
            try {
                await fetch('/api/modules_save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(currentConfig)
                });
                window.parent.postMessage({action: 'restart-shell'}, '*');
                alert('Настройки сохранены. Shell перезапускается...');
            } catch(e) {
                alert('Ошибка сохранения: ' + e.message);
            }
        }

        loadModules();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(MANAGER_TEMPLATE, version=VERSION)


@app.route('/api/modules_list')
def api_modules_list():
    return jsonify({
        'modules': get_all_modules(),
        'config': get_autostart_config()
    })


@app.route('/api/modules_save', methods=['POST'])
def api_modules_save():
    data = request.get_json()
    usual = data.get('usual', 'all')
    service = data.get('service', 'all')
    save_autostart_config(usual, service)
    return jsonify({'status': 'saved'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5008)
    args = parser.parse_args()
    print(f"Module Manager {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
