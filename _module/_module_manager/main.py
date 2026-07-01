import os
import json
import shutil
import time
import argparse
import configparser
import requests
from flask import Flask, render_template_string, jsonify, request

VERSION = '1.2.1'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
CONFIG_PATH = os.path.join(SHELL_DIR, '_data', 'config.cfg')


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding='utf-8')
    return cfg


def get_autostart_config():
    cfg = load_config()
    if 'modules_auto_start' in cfg:
        return dict(cfg['modules_auto_start'])
    return {'usual': 'all', 'service': 'all', 'game': 'all'}


def save_autostart_config(usual, service, game='all'):
    cfg = load_config()
    if not cfg.has_section('modules_auto_start'):
        cfg.add_section('modules_auto_start')
    cfg.set('modules_auto_start', 'usual', usual)
    cfg.set('modules_auto_start', 'service', service)
    cfg.set('modules_auto_start', 'game', game)
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
        .content { padding:16px 20px; }
        .panel { background:#262626; border:1px solid #404040; border-radius:3px; margin-bottom:12px; }
        .panel-header { background:#333; padding:8px 12px; border-bottom:1px solid #404040; font-weight:600; color:#47a8ff; font-size:12px; }
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
        .btn-delete { background:none; border:1px solid #ff6c59; color:#ff6c59; border-radius:3px; padding:2px 8px; cursor:pointer; font-size:11px; font-family:inherit; }
        .btn-delete:hover { background:#ff6c59; color:#fff; }
        .btn-delete:disabled { opacity:0.3; cursor:not-allowed; border-color:#666; color:#666; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Модули {{ version }}</h1>
            <div class="header-info">Управление модулями оболочки</div>
        </div>
        <div class="controls">
            <button class="btn btn-primary" onclick="saveAndRestart()">Применить и перезапустить</button>
        </div>
    </div>
    <div class="content">
        <div class="panel">
            <div class="panel-header">Сервисные модули</div>
            <div class="panel-body">
                <div class="warning">Модули нужны для работы оболочки. Отключение может повлиять на функциональность.</div>
                <div class="lock-row">
                    <span class="lock-label">Блокировка:</span>
                    <button class="toggle toggle-off" id="lockToggle" onclick="toggleLock()"></button>
                    <span class="lock-label" id="lockStatus">Включена</span>
                </div>
                <table class="module-table">
                    <thead>
                        <tr><th>Модуль</th><th>Описание</th><th>Включён</th><th>Удалить</th></tr>
                    </thead>
                    <tbody id="serviceModules"></tbody>
                </table>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Обычные модули</div>
            <div class="panel-body">
                <table class="module-table">
                    <thead>
                        <tr><th>Модуль</th><th>Описание</th><th>Включён</th><th>Удалить</th></tr>
                    </thead>
                    <tbody id="usualModules"></tbody>
                </table>
            </div>
        </div>

        <div class="panel" id="gamePanel" style="display:none;">
            <div class="panel-header">Игры</div>
            <div class="panel-body">
                <table class="module-table">
                    <thead>
                        <tr><th>Модуль</th><th>Описание</th><th>Включён</th><th>Удалить</th></tr>
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
                modules = data.modules || [];
                currentConfig = data.config || {};
                renderModules();
            } catch(e) {}
        }

        function renderModules() {
            const serviceBody = document.getElementById('serviceModules');
            const usualBody = document.getElementById('usualModules');
            const gameBody = document.getElementById('gameModules');
            let serviceHtml = '';
            let usualHtml = '';
            let gameHtml = '';

            modules.forEach(m => {
                const type = m.type || 'usual';
                const configKey = type;
                const enabled = (currentConfig[configKey] === 'all' || (currentConfig[configKey] || '').split(',').map(s=>s.trim()).includes(m.name));
                const isService = type === 'service';

                const btnClass = enabled ? 'toggle-btn on' : 'toggle-btn off';
                const rowClass = enabled ? '' : 'disabled';
                const deleteDisabled = (lockEnabled && isService) ? ' disabled' : '';
                const row = '<tr class="' + rowClass + '">'
                    + '<td><strong>' + m.title + '</strong></td>'
                    + '<td>' + (m.description || '') + '</td>'
                    + '<td><button class="' + btnClass + '" data-name="' + m.name + '" onclick="toggleModule(this)"' + (lockEnabled && isService ? ' disabled' : '') + '></button></td>'
                    + '<td><button class="btn-delete" data-name="' + m.name + '" onclick="deleteModule(this)"' + deleteDisabled + '>Удалить</button></td>'
                    + '</tr>';

                if (type === 'service') serviceHtml += row;
                else if (type === 'game') gameHtml += row;
                else usualHtml += row;
            });

            serviceBody.innerHTML = serviceHtml || '<tr><td colspan="4" style="color:#999;text-align:center;">Нет сервисных модулей</td></tr>';
            usualBody.innerHTML = usualHtml || '<tr><td colspan="4" style="color:#999;text-align:center;">Нет обычных модулей</td></tr>';

            if (gameHtml) {
                document.getElementById('gamePanel').style.display = '';
                gameBody.innerHTML = gameHtml;
            } else {
                document.getElementById('gamePanel').style.display = 'none';
            }
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

        async function deleteModule(btn) {
            const name = btn.dataset.name;
            if (!confirm('Удалить модуль "' + name + '"?')) return;
            try {
                const r = await fetch('/api/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name})
                });
                const d = await r.json();
                if (d.status === 'deleted') {
                    loadModules();
                } else {
                    alert('Ошибка: ' + (d.error || 'Unknown'));
                }
            } catch(e) {
                alert('Ошибка: ' + e.message);
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
                setTimeout(() => {
                    window.parent.postMessage({action: 'restart-shell'}, '*');
                }, 500);
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
    game = data.get('game', 'all')
    save_autostart_config(usual, service, game)
    return jsonify({'status': 'saved'})


@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.get_json()
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'No name provided'}), 400

    try:
        requests.post(f'http://127.0.0.1:8080/api/module/{name}/stop', timeout=5)
    except Exception:
        pass

    time.sleep(1)

    mod_dir = os.path.join(SHELL_DIR, '_module', name)
    if os.path.isdir(mod_dir):
        try:
            shutil.rmtree(mod_dir)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5008)
    args = parser.parse_args()
    print(f"Module Manager {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
