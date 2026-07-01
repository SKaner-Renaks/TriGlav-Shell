import os
import json
import time
import shutil
import zipfile
import logging
import argparse
import requests
import configparser
import threading
from flask import Flask, render_template_string, jsonify, request

VERSION = '1.3.9'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
REPO_URL = 'https://github.com/SKaner-Renaks/TriGlav-Shell'
ARCHIVE_URL = 'https://github.com/SKaner-Renaks/TriGlav-Shell/archive/refs/heads/main.zip'
DOWNLOAD_DIR = os.path.join(SHELL_DIR, '_Download')
ZIP_PATH = os.path.join(DOWNLOAD_DIR, 'repo.zip')
EXTRACT_DIR = os.path.join(DOWNLOAD_DIR, 'TriGlav-Shell-main')

download_state = {'status': 'idle', 'percent': 0, 'message': ''}

log = logging.getLogger('updater')
log.setLevel(logging.DEBUG)


def setup_log():
    log_path = os.path.join(BASE_DIR, 'updater.log')
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(fmt)
    log.addHandler(fh)


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(SHELL_DIR, '_data', 'config.cfg'), encoding='utf-8')
    return cfg


def get_autostart_config():
    cfg = load_config()
    if 'modules_auto_start' in cfg:
        return dict(cfg['modules_auto_start'])
    return {'usual': 'all', 'service': 'all', 'game': 'all'}


def get_local_modules():
    modules = []
    module_dir = os.path.join(SHELL_DIR, '_module')
    if not os.path.isdir(module_dir):
        return modules

    for name in sorted(os.listdir(module_dir)):
        mod_path = os.path.join(module_dir, name)
        manifest_path = os.path.join(mod_path, 'manifest.json')
        if os.path.isdir(mod_path) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                manifest['_local_path'] = mod_path
                modules.append(manifest)
            except Exception:
                pass

    shell_manifest_path = os.path.join(SHELL_DIR, '_data', 'manifest.json')
    if os.path.exists(shell_manifest_path):
        try:
            with open(shell_manifest_path, 'r', encoding='utf-8') as f:
                shell = json.load(f)
            shell['_local_path'] = SHELL_DIR
            shell['_is_shell'] = True
            modules.insert(0, shell)
        except Exception:
            pass

    return modules


def get_repo_modules():
    modules = []
    if not os.path.isdir(EXTRACT_DIR):
        return modules, 'Archive not downloaded. Press Get first.'

    module_dir = os.path.join(EXTRACT_DIR, '_module')
    if not os.path.isdir(module_dir):
        return modules, '_module not found in archive'

    for name in sorted(os.listdir(module_dir)):
        mod_path = os.path.join(module_dir, name)
        manifest_path = os.path.join(mod_path, 'manifest.json')
        if os.path.isdir(mod_path) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                manifest['_repo_name'] = name
                manifest['_repo_path'] = mod_path
                modules.append(manifest)
            except Exception:
                pass

    # Shell manifest отдельно из _data/
    shell_manifest_path = os.path.join(EXTRACT_DIR, '_data', 'manifest.json')
    if os.path.exists(shell_manifest_path):
        try:
            with open(shell_manifest_path, 'r', encoding='utf-8') as f:
                shell = json.load(f)
            shell['_repo_name'] = 'shell'
            shell['_repo_path'] = os.path.join(EXTRACT_DIR, '_data')
            modules.insert(0, shell)
        except Exception:
            pass

    return modules, None


def download_archive():
    global download_state
    download_state = {'status': 'downloading', 'percent': 0, 'message': 'Starting download...'}
    log.info('download: start %s', ARCHIVE_URL)

    try:
        if os.path.exists(DOWNLOAD_DIR):
            shutil.rmtree(DOWNLOAD_DIR)
            log.info('download: cleaned _Download')
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        r = requests.get(ARCHIVE_URL, stream=True, timeout=120)
        r.raise_for_status()

        total = int(r.headers.get('content-length', 0))
        downloaded = 0

        with open(ZIP_PATH, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    download_state['percent'] = int(downloaded * 100 / total)
                    download_state['message'] = f'Downloaded {downloaded // 1024}KB / {total // 1024}KB'

        download_state['status'] = 'extracting'
        download_state['percent'] = 0
        download_state['message'] = 'Extracting archive...'

        with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
            zf.extractall(DOWNLOAD_DIR)

        download_state = {'status': 'done', 'percent': 100, 'message': 'Archive ready'}
        log.info('download: done, zip=%dKB', os.path.getsize(ZIP_PATH) // 1024)

    except requests.exceptions.ConnectionError:
        download_state = {'status': 'error', 'percent': 0, 'message': 'No connection to GitHub'}
    except requests.exceptions.HTTPError as e:
        download_state = {'status': 'error', 'percent': 0, 'message': f'HTTP error: {e.response.status_code}'}
    except Exception as e:
        download_state = {'status': 'error', 'percent': 0, 'message': str(e)}


def copy_module_from_repo(module_name, dest_dir):
    src_dir = os.path.join(EXTRACT_DIR, '_module', module_name)
    if not os.path.isdir(src_dir):
        log.error('copy: source not found %s', src_dir)
        return False, f'Source not found: {src_dir}'
    log.info('copy: %s -> %s', src_dir, dest_dir)

    for attempt in range(3):
        try:
            _copy_tree(src_dir, dest_dir)
            # Verify copy
            src_files = []
            for root, dirs, files in os.walk(src_dir):
                for f in files:
                    src_files.append(os.path.join(root, f))
            copied = 0
            for sf in src_files:
                rel = os.path.relpath(sf, src_dir)
                df = os.path.join(dest_dir, rel)
                if os.path.exists(df):
                    copied += 1
            log.info('copy: done %d/%d files', copied, len(src_files))
            return True, f'copied {copied}/{len(src_files)} files'
        except PermissionError:
            if attempt < 2:
                time.sleep(2)
            else:
                return False, 'Permission denied - module files locked'
        except Exception as e:
            return False, str(e)

    return False, 'Failed after retries'


def _copy_tree(src, dst):
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            _copy_tree(s, d)
        else:
            shutil.copy2(s, d)


DOWNLOADER_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Обновления {{ version }}</title>
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
        .btn:disabled { opacity:0.4; cursor:not-allowed; }
        .content { padding:16px 20px; }
        .panel { background:#262626; border:1px solid #404040; border-radius:3px; margin-bottom:12px; }
        .panel-header { background:#333; padding:8px 12px; border-bottom:1px solid #404040; font-weight:600; color:#47a8ff; font-size:12px; display:flex; justify-content:space-between; align-items:center; }
        .panel-body { padding:12px; }
        .repo-bar { display:flex; gap:8px; margin-bottom:12px; align-items:center; }
        .repo-bar input { flex:1; padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; font-family:inherit; }
        .repo-bar input:focus { outline:none; border-color:#0057b3; }
        .module-table { width:100%; border-collapse:collapse; font-size:12px; }
        .module-table th { background:#333; padding:6px 8px; text-align:left; color:#47a8ff; font-weight:600; border-bottom:1px solid #404040; }
        .module-table td { padding:6px 8px; border-bottom:1px solid #333; }
        .module-table tr:hover { background:#2d2d2d; }
        .module-table input[type="checkbox"] { accent-color:#0057b3; }
        .section-title { font-size:14px; font-weight:600; color:#f2f2f2; margin:16px 0 8px; }
        .search { padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; width:250px; margin-bottom:8px; }
        .search:focus { outline:none; border-color:#0057b3; }
        .status-on { color:#21bf4b; }
        .status-off { color:#ff6c59; }
        .modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:100; justify-content:center; align-items:center; }
        .modal-overlay.active { display:flex; }
        .modal { background:#262626; border:1px solid #404040; border-radius:4px; width:500px; padding:20px; text-align:center; }
        .spinner { display:inline-block; width:30px; height:30px; border:3px solid #404040; border-top-color:#0057b3; border-radius:50%; animation:spin 0.7s linear infinite; margin-bottom:12px; }
        @keyframes spin { to { transform:rotate(360deg); } }
        .progress-bar { width:100%; height:20px; background:#333; border-radius:10px; overflow:hidden; margin:12px 0; }
        .progress-fill { height:100%; background:#0057b3; transition:width 0.3s; width:0%; }
        .error-msg { background:#4d1a1a; border:1px solid #ff6c59; border-radius:3px; padding:8px 12px; margin-bottom:12px; color:#ff6c59; font-size:12px; }
        .success-msg { background:#1a3d24; border:1px solid #21bf4b; border-radius:3px; padding:8px 12px; margin-bottom:12px; color:#21bf4b; font-size:12px; }
        #statusMessage { display:none; }
        #downloadInfo { font-size:11px; color:#999; margin-top:4px; }
        .ver-ok { color:#21bf4b; font-weight:600; }
        .ver-new { color:#ff6c59; font-weight:600; }
        .ver-old { color:#ffcc00; font-weight:600; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Обновления {{ version }}</h1>
            <div class="header-info">Управление модулями из GitHub</div>
        </div>
        <div class="controls">
            <button class="btn btn-primary" id="scanBtn" onclick="startDownload()">Get</button>
        </div>
    </div>
    <div class="content">
        <div id="statusMessage"></div>

        <div class="repo-bar">
            <input type="text" id="repoUrl" value="{{ repo_url }}">
        </div>

        <div class="section-title">Установленные объекты</div>
        <input type="text" class="search" id="searchInstalled" placeholder="Поиск..." oninput="filterInstalled()">
        <div class="panel">
            <div class="panel-body" style="padding:0;">
                <table class="module-table">
                    <thead>
                        <tr><th><input type="checkbox" id="checkAllInstalled" onchange="toggleAllInstalled()"></th><th>Type</th><th>Status</th><th>Name</th><th>Title</th><th>Local</th><th>Repo</th><th>Status</th></tr>
                    </thead>
                    <tbody id="installedBody"></tbody>
                </table>
            </div>
        </div>

        <div style="margin-bottom:16px;">
            <button class="btn btn-success" onclick="updateSelected()">Обновить</button>
        </div>

        <div class="section-title">Новые модули</div>
        <input type="text" class="search" id="searchNew" placeholder="Поиск..." oninput="filterNew()">
        <div class="panel">
            <div class="panel-body" style="padding:0;">
                <table class="module-table">
                    <thead>
                        <tr><th><input type="checkbox" id="checkAllNew" onchange="toggleAllNew()"></th><th>Type</th><th>Name</th><th>Title</th><th>Description</th><th>Repo Ver</th></tr>
                    </thead>
                    <tbody id="newBody"></tbody>
                </table>
            </div>
        </div>

        <button class="btn btn-primary" id="installBtn" onclick="installSelected()">Установить</button>
    </div>

    <div class="modal-overlay" id="progressModal">
        <div class="modal">
            <div class="spinner" id="modalSpinner"></div>
            <div id="progressText">Загрузка...</div>
            <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
            <div id="downloadInfo"></div>
        </div>
    </div>

    <script>
        let repoModules = [];
        let localModules = [];
        let moduleConfig = {};

        function showStatus(msg, type) {
            const el = document.getElementById('statusMessage');
            el.style.display = 'block';
            el.className = type === 'error' ? 'error-msg' : 'success-msg';
            el.textContent = msg;
        }

        function hideStatus() { document.getElementById('statusMessage').style.display = 'none'; }

        function showProgress(text) {
            document.getElementById('progressText').textContent = text;
            document.getElementById('progressFill').style.width = '0%';
            document.getElementById('downloadInfo').textContent = '';
            document.getElementById('progressModal').classList.add('active');
        }

        function hideProgress() { document.getElementById('progressModal').classList.remove('active'); }

        async function loadConfig() {
            try {
                const r = await fetch('/api/config');
                const d = await r.json();
                moduleConfig = d.config || {};
            } catch(e) {}
        }

        function isModuleEnabled(name, type) {
            const key = type || 'usual';
            const list = moduleConfig[key];
            if (!list || list === 'all') return true;
            return list.split(',').map(s => s.trim()).includes(name);
        }

        async function startDownload() {
            hideStatus();
            document.getElementById('scanBtn').disabled = true;
            showProgress('Скачивание архива...');

            try {
                const r = await fetch('/api/download', { method: 'POST' });
                const d = await r.json();

                if (d.status === 'error') {
                    hideProgress();
                    showStatus('Ошибка: ' + d.message, 'error');
                    document.getElementById('scanBtn').disabled = false;
                    return;
                }

                pollDownloadStatus();
            } catch(e) {
                hideProgress();
                showStatus('Ошибка: ' + e.message, 'error');
                document.getElementById('scanBtn').disabled = false;
            }
        }

        function pollDownloadStatus() {
            const interval = setInterval(async () => {
                try {
                    const r = await fetch('/api/download/status');
                    const d = await r.json();

                    if (d.status === 'downloading') {
                        document.getElementById('progressFill').style.width = d.percent + '%';
                        document.getElementById('downloadInfo').textContent = d.message;
                    } else if (d.status === 'extracting') {
                        document.getElementById('progressText').textContent = 'Распаковка...';
                        document.getElementById('progressFill').style.width = '100%';
                        document.getElementById('downloadInfo').textContent = d.message;
                    } else if (d.status === 'done') {
                        clearInterval(interval);
                        document.getElementById('progressText').textContent = 'Архив готов';
                        document.getElementById('progressFill').style.width = '100%';
                        setTimeout(async () => {
                            hideProgress();
                            showStatus('Архив скачан и распакован', 'success');
                            await scanRepo();
                        }, 500);
                    } else if (d.status === 'error') {
                        clearInterval(interval);
                        hideProgress();
                        showStatus('Ошибка: ' + d.message, 'error');
                        document.getElementById('scanBtn').disabled = false;
                    }
                } catch(e) {
                    clearInterval(interval);
                    hideProgress();
                    showStatus('Ошибка соединения: ' + e.message, 'error');
                    document.getElementById('scanBtn').disabled = false;
                }
            }, 500);
        }

        async function scanRepo() {
            await loadConfig();
            try {
                const r = await fetch('/api/scan');
                const data = await r.json();
                repoModules = data.repo_modules || [];
                localModules = data.local_modules || [];

                if (data.error) {
                    showStatus(data.error, 'error');
                } else {
                    showStatus('Найдено модулей: ' + repoModules.length, 'success');
                }

                buildInstalledTable();
                buildNewTable();
            } catch(e) {
                showStatus('Ошибка сканирования: ' + e.message, 'error');
            }
            document.getElementById('scanBtn').disabled = false;
        }

        function compareVersions(local, repo) {
            if (!repo || repo === '-') return '';
            if (!local) return '';
            const lp = local.split('.').map(Number);
            const rp = repo.split('.').map(Number);
            for (let i = 0; i < Math.max(lp.length, rp.length); i++) {
                const l = lp[i] || 0;
                const r = rp[i] || 0;
                if (l > r) return 'old';
                if (l < r) return 'new';
            }
            return 'ok';
        }

        function buildInstalledTable() {
            const tbody = document.getElementById('installedBody');
            let html = '';
            const sorted = [...localModules].sort((a,b) => {
                if (a._is_shell) return -1;
                if (b._is_shell) return 1;
                const order = {service:1, usual:2, game:3};
                return (order[a.type]||9) - (order[b.type]||9);
            });
            sorted.forEach(m => {
                const repoM = repoModules.find(r => r.name === m.name);
                const repoVer = repoM ? repoM.version : '-';
                const enabled = isModuleEnabled(m.name, m.type || 'usual');
                const statusClass = enabled ? 'status-on' : 'status-off';
                const statusText = enabled ? 'on' : 'off';
                const verStatus = compareVersions(m.version, repoVer);
                const verClass = verStatus === 'ok' ? 'ver-ok' : verStatus === 'new' ? 'ver-new' : verStatus === 'old' ? 'ver-old' : '';
                const verText = verStatus === 'ok' ? 'Ok' : verStatus === 'new' ? 'Need Update' : verStatus === 'old' ? 'Attention' : '-';
                html += '<tr><td><input type="checkbox" data-name="'+m.name+'" data-type="'+(m.type||'usual')+'" class="installed-cb"></td>';
                html += '<td>'+(m.type||'usual')+'</td>';
                html += '<td class="'+statusClass+'">'+statusText+'</td>';
                html += '<td>'+m.name+'</td>';
                html += '<td>'+m.title+'</td>';
                html += '<td>'+(m.version||'?')+'</td>';
                html += '<td>'+repoVer+'</td>';
                html += '<td class="'+verClass+'">'+verText+'</td></tr>';
            });
            tbody.innerHTML = html || '<tr><td colspan="8" style="text-align:center;color:#999;">No data. Press Get to download.</td></tr>';
        }

        function buildNewTable() {
            const tbody = document.getElementById('newBody');
            let html = '';
            const localNames = localModules.map(m => m.name);
            const newModules = repoModules.filter(m => !localNames.includes(m.name));
            newModules.forEach(m => {
                html += '<tr><td><input type="checkbox" data-name="'+m.name+'" class="new-cb"></td>';
                html += '<td>'+(m.type||'usual')+'</td>';
                html += '<td>'+m.name+'</td>';
                html += '<td>'+m.title+'</td>';
                html += '<td>'+(m.description||'')+'</td>';
                html += '<td>'+(m.version||'?')+'</td></tr>';
            });
            tbody.innerHTML = html || '<tr><td colspan="6" style="text-align:center;color:#999;">No new modules</td></tr>';
        }

        function filterInstalled() {
            const q = document.getElementById('searchInstalled').value.toLowerCase();
            document.querySelectorAll('#installedBody tr').forEach(tr => {
                tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
            });
        }

        function filterNew() {
            const q = document.getElementById('searchNew').value.toLowerCase();
            document.querySelectorAll('#newBody tr').forEach(tr => {
                tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
            });
        }

        function toggleAllInstalled() {
            const checked = document.getElementById('checkAllInstalled').checked;
            document.querySelectorAll('.installed-cb').forEach(cb => cb.checked = checked);
        }

        function toggleAllNew() {
            const checked = document.getElementById('checkAllNew').checked;
            document.querySelectorAll('.new-cb').forEach(cb => cb.checked = checked);
        }

        function getSelectedInstalled() {
            return [...document.querySelectorAll('.installed-cb:checked')].map(cb => ({
                name: cb.dataset.name, type: cb.dataset.type
            }));
        }

        function getSelectedNew() {
            return [...document.querySelectorAll('.new-cb:checked')].map(cb => cb.dataset.name);
        }

        async function updateSelected() {
            const selected = getSelectedInstalled();
            if (selected.length === 0) { alert('Выберите модули для обновления'); return; }
            if (!confirm('Обновить: ' + selected.map(s=>s.name).join(', ') + '?')) return;
            showProgress('Обновление...');
            document.getElementById('installBtn').disabled = true;
            try {
                const r = await fetch('/api/update', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({modules: selected}) });
                const d = await r.json();
                hideProgress();
                let msg = d.message;
                if (d.results) {
                    const details = d.results.map(r => {
                        if (r.status === 'updated') return r.name + ': OK (' + (r.info||'') + ')';
                        if (r.status === 'skipped') return r.name + ': skipped (' + r.reason + ')';
                        if (r.status === 'failed') return r.name + ': FAILED (' + r.error + ')';
                        return r.name + ': ' + r.status;
                    }).join('\n');
                    msg = d.message + '\n' + details;
                }
                showStatus(msg, d.errors && d.errors.length ? 'error' : 'success');
                scanRepo();
            } catch(e) { hideProgress(); showStatus('Ошибка: ' + e.message, 'error'); }
            document.getElementById('installBtn').disabled = false;
        }

        async function installSelected() {
            const selected = getSelectedNew();
            if (selected.length === 0) { alert('Выберите модули для установки'); return; }
            if (!confirm('Установить: ' + selected.join(', ') + '?')) return;
            showProgress('Установка...');
            document.getElementById('installBtn').disabled = true;
            try {
                const r = await fetch('/api/install', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({modules: selected}) });
                const d = await r.json();
                hideProgress();
                if (d.errors && d.errors.length) {
                    showStatus(d.message + '\n' + d.errors.join('; '), 'error');
                } else {
                    showStatus(d.message, 'success');
                }
                scanRepo();
            } catch(e) { hideProgress(); showStatus('Ошибка: ' + e.message, 'error'); }
            document.getElementById('installBtn').disabled = false;
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(DOWNLOADER_TEMPLATE, version=VERSION, repo_url=REPO_URL)


@app.route('/api/config')
def api_config():
    return jsonify({'config': dict(get_autostart_config())})


@app.route('/api/download', methods=['POST'])
def api_download():
    global download_state
    if download_state['status'] in ('downloading', 'extracting'):
        return jsonify({'status': 'busy', 'message': 'Download in progress'})

    thread = threading.Thread(target=download_archive, daemon=True)
    thread.start()
    return jsonify({'status': 'started'})


@app.route('/api/download/status')
def api_download_status():
    return jsonify(download_state)


@app.route('/api/scan')
def api_scan():
    repo_modules, error = get_repo_modules()
    local_modules = get_local_modules()
    return jsonify({
        'repo_modules': repo_modules,
        'local_modules': local_modules,
        'error': error
    })


@app.route('/api/install', methods=['POST'])
def api_install():
    data = request.get_json()
    modules = data.get('modules', [])
    results = []
    errors = []

    for name in modules:
        dest_dir = os.path.join(SHELL_DIR, '_module', name)
        if os.path.exists(dest_dir):
            results.append({'name': name, 'status': 'exists'})
            continue

        ok, msg = copy_module_from_repo(name, dest_dir)
        if ok:
            results.append({'name': name, 'status': 'installed'})
        else:
            results.append({'name': name, 'status': 'failed', 'error': msg})
            errors.append(f'{name}: {msg}')

    installed = len([r for r in results if r['status'] == 'installed'])
    return jsonify({
        'status': 'done',
        'message': f'Installed: {installed}/{len(modules)}',
        'results': results,
        'errors': errors
    })


@app.route('/api/update', methods=['POST'])
def api_update():
    data = request.get_json()
    modules = data.get('modules', [])
    results = []
    errors = []

    for m in modules:
        name = m['name']
        mtype = m.get('type', 'usual')
        log.info('update: module=%s type=%s', name, mtype)

        if mtype == 'shell':
            log.info('update: skip shell')
            results.append({'name': name, 'status': 'skipped', 'reason': 'shell requires manual restart'})
            continue

        if mtype == 'service':
            try:
                url = f'http://127.0.0.1:8080/api/module/{name}/stop'
                log.info('update: stop %s', url)
                r = requests.post(url, timeout=5)
                log.info('update: stop -> %d', r.status_code)
            except Exception as e:
                log.error('update: stop failed: %s', e)
            time.sleep(3)

        dest_dir = os.path.join(SHELL_DIR, '_module', name)
        if not os.path.isdir(dest_dir):
            log.error('update: dest not found %s', dest_dir)
            results.append({'name': name, 'status': 'not_found'})
            continue

        ok, msg = copy_module_from_repo(name, dest_dir)
        log.info('update: copy result ok=%s msg=%s', ok, msg)

        if mtype == 'service' and ok:
            try:
                url = f'http://127.0.0.1:8080/api/module/{name}/start'
                log.info('update: start %s', url)
                r = requests.post(url, timeout=10)
                log.info('update: start -> %d', r.status_code)
            except Exception as e:
                log.error('update: start failed: %s', e)

        if ok:
            results.append({'name': name, 'status': 'updated', 'info': msg})
        else:
            results.append({'name': name, 'status': 'failed', 'error': msg})
            errors.append(f'{name}: {msg}')

    updated = len([r for r in results if r['status'] == 'updated'])
    return jsonify({
        'status': 'done',
        'message': f'Updated: {updated}/{len(modules)}',
        'results': results,
        'errors': errors
    })


if __name__ == '__main__':
    setup_log()
    log.info('=== Updater %s started ===', VERSION)

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5009)
    args = parser.parse_args()
    print(f"Updater {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
