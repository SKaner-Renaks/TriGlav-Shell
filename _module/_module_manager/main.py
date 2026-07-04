import os
import re
import json
import shutil
import time
import logging
import argparse
import configparser
import requests
from flask import Flask, render_template_string, jsonify, request

VERSION = '1.3.0'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
CONFIG_PATH = os.path.join(SHELL_DIR, '_data', 'config.cfg')


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding='utf-8')
    return cfg


def get_shell_port():
    cfg = load_config()
    return int(cfg.get('shell', 'port', fallback='8080'))


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


def sanitize_name(name):
    if not name or not re.match(r'^[a-zA-Z0-9_]+$', name):
        return False
    if '..' in name or '/' in name or '\\' in name:
        return False
    return True


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


def shell_api_get(endpoint):
    """GET-запрос к Shell API с обходом прокси."""
    shell_port = get_shell_port()
    try:
        resp = requests.get(
            f'http://127.0.0.1:{shell_port}{endpoint}',
            timeout=5,
            proxies={'http': None, 'https': None}
        )
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def shell_api_post(endpoint):
    """POST-запрос к Shell API с обходом прокси."""
    shell_port = get_shell_port()
    try:
        resp = requests.post(
            f'http://127.0.0.1:{shell_port}{endpoint}',
            timeout=10,
            proxies={'http': None, 'https': None}
        )
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


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
        .btn-danger { background:#4d1a1a; color:#ff6c59; border-color:#ff6c59; }
        .btn-danger:hover { background:#ff6c59; color:#fff; }
        .btn-sm { padding:3px 8px; font-size:11px; }
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

        /* Единая таблица модулей */
        .module-table { width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; }
        .module-table th { background:#333; padding:8px 10px; text-align:left; color:#47a8ff; font-weight:600; border-bottom:1px solid #404040; }
        .module-table td { padding:8px 10px; border-bottom:1px solid #333; vertical-align:middle; }
        .module-table tr:hover { background:#2d2d2d; }
        .module-table tr.disabled td { color:#666; }
        .col-name { width:20%; }
        .col-desc { width:30%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .col-port { width:10%; text-align:center; }
        .col-toggle { width:10%; text-align:center; }
        .col-actions { width:15%; text-align:center; white-space:nowrap; }
        .col-delete { width:15%; text-align:center; }

        .port-running { color:#21bf4b; font-weight:600; }
        .port-stopped { color:#ff6c59; }
        .port-offline { color:#666; }

        .toggle-btn { width:36px; height:20px; border-radius:10px; border:none; cursor:pointer; position:relative; transition:background 0.3s; }
        .toggle-btn.on { background:#21bf4b; }
        .toggle-btn.on::after { content:''; position:absolute; width:14px; height:14px; background:#fff; border-radius:50%; top:3px; right:3px; transition:0.3s; }
        .toggle-btn.off { background:#666; }
        .toggle-btn.off::after { content:''; position:absolute; width:14px; height:14px; background:#fff; border-radius:50%; top:3px; left:3px; transition:0.3s; }
        .toggle-btn:disabled { opacity:0.4; cursor:not-allowed; }

        .btn-delete { background:none; border:1px solid #ff6c59; color:#ff6c59; border-radius:3px; padding:3px 8px; cursor:pointer; font-size:11px; font-family:inherit; }
        .btn-delete:hover { background:#ff6c59; color:#fff; }
        .btn-delete:disabled { opacity:0.3; cursor:not-allowed; border-color:#666; color:#666; }
        .btn-restart { background:none; border:1px solid #47a8ff; color:#47a8ff; border-radius:3px; padding:3px 8px; cursor:pointer; font-size:11px; font-family:inherit; }
        .btn-restart:hover { background:#47a8ff; color:#fff; }
        .btn-admin { background:none; border:1px solid #ff9800; color:#ff9800; border-radius:3px; padding:3px 8px; cursor:pointer; font-size:11px; font-family:inherit; }
        .btn-admin:hover { background:#ff9800; color:#fff; }

        .error-msg { background:#3d1a1a; border:1px solid #ff6c59; border-radius:3px; padding:8px 12px; margin-bottom:12px; color:#ff6c59; font-size:12px; }

        /* Модальное окно подтверждения удаления */
        .modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100; justify-content:center; align-items:center; }
        .modal-overlay.active { display:flex; }
        .modal-panel { background:#262626; border:1px solid #404040; border-radius:4px; width:420px; max-height:80vh; overflow:hidden; }
        .modal-header { background:#333; padding:10px 14px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #404040; }
        .modal-header h3 { color:#ff6c59; font-size:14px; }
        .modal-body { padding:16px; font-size:13px; line-height:1.6; }
        .modal-body .warning-icon { color:#ff6c59; font-size:24px; margin-bottom:8px; }
        .modal-body .module-name { color:#fff; font-weight:600; }
        .modal-footer { padding:12px 16px; display:flex; gap:8px; justify-content:flex-end; border-top:1px solid #404040; }

        .spinner-sm { display:inline-block; width:14px; height:14px; border:2px solid #404040; border-top-color:#47a8ff; border-radius:50%; animation:spin 0.7s linear infinite; vertical-align:middle; }
        @keyframes spin { to { transform:rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Модули {{ version }}</h1>
            <div class="header-info">Управление модулями оболочки</div>
        </div>
        <div class="controls">
            <span id="adminStatus" style="font-size:12px;margin-right:10px;"></span>
            <button id="restartAdminBtn" class="btn btn-sm btn-admin" onclick="restartElevated('module_manager')" style="display:none;">Restart as Admin</button>
            <button class="btn btn-primary" onclick="saveAndRestart()">Применить и перезапустить</button>
        </div>
    </div>
    <div class="content">
        <div id="errorBanner" class="error-msg" style="display:none;"></div>

        <div class="panel">
            <div class="panel-header">Сервисные модули</div>
            <div class="panel-body">
                <div class="warning">Модули нужны для работы оболочки. Отключение может повлиять на функциональность.</div>
                <div class="lock-row">
                    <span class="lock-label">Блокировка:</span>
                    <button class="toggle toggle-on" id="lockToggle" onclick="toggleLock()"></button>
                    <span class="lock-label" id="lockStatus">Включена</span>
                </div>
                <table class="module-table">
                    <thead>
                        <tr><th class="col-name">Модуль</th><th class="col-desc">Описание</th><th class="col-port">Порт</th><th class="col-toggle">Включён</th><th class="col-actions">Действия</th><th class="col-delete">Удалить</th></tr>
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
                        <tr><th class="col-name">Модуль</th><th class="col-desc">Описание</th><th class="col-port">Порт</th><th class="col-toggle">Включён</th><th class="col-actions">Действия</th><th class="col-delete">Удалить</th></tr>
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
                        <tr><th class="col-name">Модуль</th><th class="col-desc">Описание</th><th class="col-port">Порт</th><th class="col-toggle">Включён</th><th class="col-actions">Действия</th><th class="col-delete">Удалить</th></tr>
                    </thead>
                    <tbody id="gameModules"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Модальное окно подтверждения удаления сервисного модуля -->
    <div class="modal-overlay" id="deleteModal">
        <div class="modal-panel">
            <div class="modal-header">
                <h3>Удаление сервисного модуля</h3>
                <button onclick="closeDeleteModal()" style="background:none;border:none;color:#999;font-size:20px;cursor:pointer;">&times;</button>
            </div>
            <div class="modal-body">
                <div class="warning-icon">&#9888;</div>
                <p>Вы пытаетесь удалить <span class="module-name" id="deleteModalName"></span> — это <strong>сервисный модуль</strong>, необходимый для работы оболочки.</p>
                <p style="margin-top:8px;color:#999;">Удаление может нарушить функциональность TriGlav Shell.</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-default" onclick="closeDeleteModal()">Отмена</button>
                <button class="btn btn-danger" id="deleteConfirmBtn">Удалить</button>
            </div>
        </div>
    </div>

    <script>
        let modules = [];
        let statuses = {};
        let currentConfig = {};
        let lockEnabled = true;
        let isAdmin = false;
        let pendingDeleteName = null;

        async function loadModules() {
            try {
                const r = await fetch('/api/modules_list');
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const data = await r.json();
                modules = data.modules || [];
                currentConfig = data.config || {};
                hideError();
            } catch(e) {
                showError('Не удалось загрузить список модулей: ' + e.message);
                modules = [];
            }
            // Загружаем статусы портов от Shell
            await loadStatuses();
            renderModules();
        }

        async function loadStatuses() {
            try {
                const r = await fetch('/api/modules_status');
                if (!r.ok) return;
                const data = await r.json();
                statuses = {};
                (data.modules || []).forEach(m => {
                    statuses[m.name] = { port: m.port, running: m.running };
                });
            } catch(e) {}
        }

        function showError(msg) {
            const banner = document.getElementById('errorBanner');
            banner.textContent = msg;
            banner.style.display = 'block';
        }

        function hideError() {
            document.getElementById('errorBanner').style.display = 'none';
        }

        function escHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
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
                const st = statuses[m.name] || {};
                const running = st.running || false;
                const port = st.port || 0;
                const needsAdmin = m.requires_admin || false;

                // Порт
                let portHtml = '';
                if (running && port) {
                    portHtml = '<span class="port-running">' + port + '</span>';
                } else if (port) {
                    portHtml = '<span class="port-stopped">' + port + '</span>';
                } else {
                    portHtml = '<span class="port-offline">—</span>';
                }

                // Тоггл
                const btnClass = enabled ? 'toggle-btn on' : 'toggle-btn off';
                const rowClass = enabled ? '' : 'disabled';
                const deleteDisabled = (lockEnabled && isService) ? ' disabled' : '';

                // Кнопки действий
                let actionsHtml = '';
                if (running) {
                    actionsHtml += '<button class="btn btn-sm btn-restart" onclick="restartModule(\'' + escHtml(m.name) + '\')">Restart</button> ';
                }


                const row = '<tr class="' + rowClass + '">'
                    + '<td class="col-name"><strong>' + escHtml(m.title) + '</strong></td>'
                    + '<td class="col-desc">' + escHtml(m.description) + '</td>'
                    + '<td class="col-port">' + portHtml + '</td>'
                    + '<td class="col-toggle"><button class="' + btnClass + '" data-name="' + escHtml(m.name) + '" onclick="toggleModule(this)"' + (lockEnabled && isService ? ' disabled' : '') + '></button></td>'
                    + '<td class="col-actions">' + actionsHtml + '</td>'
                    + '<td class="col-delete"><button class="btn-delete" data-name="' + escHtml(m.name) + '" data-type="' + escHtml(type) + '" onclick="deleteModule(this)"' + deleteDisabled + '>Удалить</button></td>'
                    + '</tr>';

                if (type === 'service') serviceHtml += row;
                else if (type === 'game') gameHtml += row;
                else usualHtml += row;
            });

            serviceBody.innerHTML = serviceHtml || '<tr><td colspan="6" style="color:#999;text-align:center;">Нет сервисных модулей</td></tr>';
            usualBody.innerHTML = usualHtml || '<tr><td colspan="6" style="color:#999;text-align:center;">Нет обычных модулей</td></tr>';

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

            const modType = m.type || 'usual';
            const key = modType;
            let list = currentConfig[key] === 'all' ? modules.filter(x => (x.type || 'usual') === modType).map(x => x.name) : (currentConfig[key] || '').split(',').map(s => s.trim());

            if (isOn) {
                list = list.filter(n => n !== name);
            } else {
                if (!list.includes(name)) list.push(name);
            }

            const allNames = modules.filter(x => (x.type || 'usual') === modType).map(x => x.name);
            if (list.length === allNames.length) {
                currentConfig[key] = 'all';
            } else {
                currentConfig[key] = list.join(',');
            }
        }

        async function restartModule(name) {
            const btn = document.querySelector('button.btn-restart[onclick*="' + name + '"]');
            if (btn) btn.innerHTML = '<span class="spinner-sm"></span>';
            try {
                const r = await fetch('/api/module_restart?name=' + encodeURIComponent(name));
                await r.json();
                setTimeout(async () => {
                    await loadStatuses();
                    renderModules();
                }, 2000);
            } catch(e) {
                alert('Ошибка перезапуска: ' + e.message);
                renderModules();
            }
        }

        function restartElevated(name) {
            window.parent.postMessage({action: 'restart-elevated', module: name}, '*');
        }

        function deleteModule(btn) {
            const name = btn.dataset.name;
            const type = btn.dataset.type;

            if (type === 'service') {
                pendingDeleteName = name;
                document.getElementById('deleteModalName').textContent = name;
                document.getElementById('deleteModal').classList.add('active');
                document.getElementById('deleteConfirmBtn').onclick = function() {
                    closeDeleteModal();
                    executeDelete(pendingDeleteName);
                };
            } else {
                if (!confirm('Удалить модуль "' + name + '"?')) return;
                executeDelete(name);
            }
        }

        function closeDeleteModal() {
            document.getElementById('deleteModal').classList.remove('active');
            pendingDeleteName = null;
        }

        async function executeDelete(name) {
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
                const r = await fetch('/api/modules_save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(currentConfig)
                });
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const d = await r.json();
                if (d.status === 'saved') {
                    setTimeout(() => {
                        window.parent.postMessage({action: 'restart-shell'}, '*');
                    }, 500);
                }
            } catch(e) {
                alert('Ошибка сохранения: ' + e.message);
            }
        }

        async function checkAdminStatus() {
            try {
                const r = await fetch('/api/admin-status');
                const d = await r.json();
                isAdmin = d.is_admin;
                const statusEl = document.getElementById('adminStatus');
                const adminBtn = document.getElementById('restartAdminBtn');
                if (isAdmin) {
                    statusEl.innerHTML = '<span style="color:#21bf4b;">&#10003; Admin</span>';
                    if (adminBtn) adminBtn.style.display = 'none';
                } else {
                    statusEl.innerHTML = '<span style="color:#ffcc00;">&#9888; Not Admin</span>';
                    if (adminBtn) adminBtn.style.display = 'inline-block';
                }
            } catch(e) {}
        }

        loadModules();
        checkAdminStatus();
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


@app.route('/api/modules_status')
def api_modules_status():
    """Получение текущих портов и статусов запуска модулей от Shell."""
    data = shell_api_get('/api/modules')
    if data:
        return jsonify({'modules': data})
    return jsonify({'modules': []})


@app.route('/api/module_restart')
def api_module_restart():
    """Перезапуск модуля через Shell API."""
    name = request.args.get('name', '')
    if not sanitize_name(name):
        return jsonify({'error': 'Invalid name'}), 400
    result = shell_api_post(f'/api/module/{name}/restart')
    if result:
        return jsonify(result)
    return jsonify({'error': 'Failed to restart'}), 500


@app.route('/api/admin-status')
def api_admin_status():
    """Проверка прав администратора."""
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False
    return jsonify({'is_admin': is_admin})


@app.route('/api/modules_save', methods=['POST'])
def api_modules_save():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    usual = data.get('usual', 'all')
    service = data.get('service', 'all')
    game = data.get('game', 'all')
    for val in [usual, service, game]:
        if not isinstance(val, str):
            return jsonify({'error': 'Invalid config value'}), 400
    save_autostart_config(usual, service, game)
    return jsonify({'status': 'saved'})


@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    name = data.get('name', '')

    if not sanitize_name(name):
        return jsonify({'error': 'Invalid module name'}), 400

    # Остановка модуля через Shell API
    try:
        resp = shell_api_post(f'/api/module/{name}/stop')
        time.sleep(2)
    except Exception:
        time.sleep(1)

    mod_dir = os.path.join(SHELL_DIR, '_module', name)
    if os.path.isdir(mod_dir):
        try:
            shutil.rmtree(mod_dir)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            return jsonify({'error': f'Failed to delete: {str(e)}'}), 500
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'module.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('Module Manager %s started', VERSION)

    print(f"Module Manager {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
