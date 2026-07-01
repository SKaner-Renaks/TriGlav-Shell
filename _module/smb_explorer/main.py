import os
import json
import logging
import argparse
import subprocess
from flask import Flask, render_template_string, jsonify

VERSION = '1.0'

app = Flask(__name__)


def run_ps(command):
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', command],
            capture_output=True, timeout=30
        )
        output = result.stdout.decode('cp866', errors='replace').strip()
        if output:
            return json.loads(output)
        return []
    except Exception:
        return []


def get_shares():
    shares = run_ps('Get-SmbShare | Select-Object Name,Path,Description,CurrentUsers | ConvertTo-Json')
    if isinstance(shares, dict):
        shares = [shares]
    result = []
    for s in shares:
        name = s.get('Name', '')
        perms = []
        if name:
            raw = run_ps(f'Get-SmbShareAccess -Name "{name}" | Select-Object AccountName,AccessRight,AccessControlType | ConvertTo-Json')
            if isinstance(raw, dict):
                raw = [raw]
            for p in raw:
                perms.append({
                    'account': p.get('AccountName', ''),
                    'right': p.get('AccessRight', ''),
                    'type': p.get('AccessControlType', '')
                })
        result.append({
            'name': name,
            'path': s.get('Path', ''),
            'description': s.get('Description', ''),
            'current_users': s.get('CurrentUsers', 0),
            'permissions': perms
        })
    return result


def get_open_files():
    files = run_ps('Get-SmbOpenFile | Select-Object FileId,Path,ClientComputerName,ClientUserName,ShareRelativePath | ConvertTo-Json')
    if isinstance(files, dict):
        files = [files]
    result = []
    for f in files:
        result.append({
            'file_id': f.get('FileId', ''),
            'path': f.get('Path', ''),
            'client_computer': f.get('ClientComputerName', ''),
            'client_user': f.get('ClientUserName', ''),
            'share_path': f.get('ShareRelativePath', '')
        })
    return result


TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>SMB Explorer {{ version }}</title>
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
        .tabs { display:flex; gap:0; margin-bottom:16px; }
        .tab { padding:8px 16px; background:#333; border:1px solid #404040; cursor:pointer; font-size:12px; color:#999; }
        .tab:first-child { border-radius:3px 0 0 3px; }
        .tab:last-child { border-radius:0 3px 3px 0; }
        .tab.active { background:#0057b3; color:#f2f2f2; border-color:#0057b3; }
        .panel { background:#262626; border:1px solid #404040; border-radius:3px; }
        .panel-header { background:#333; padding:8px 12px; border-bottom:1px solid #404040; font-weight:600; color:#47a8ff; font-size:12px; display:flex; justify-content:space-between; align-items:center; }
        .panel-body { padding:0; }
        .toolbar { display:flex; gap:8px; align-items:center; padding:10px 12px; border-bottom:1px solid #333; }
        .search { padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; width:300px; }
        .search:focus { outline:none; border-color:#0057b3; }
        select { padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; }
        table { width:100%; border-collapse:collapse; font-size:12px; }
        th { background:#333; padding:8px 10px; text-align:left; color:#47a8ff; font-weight:600; border-bottom:1px solid #404040; }
        td { padding:8px 10px; border-bottom:1px solid #333; }
        tr:hover { background:#2d2d2d; }
        .tag { display:inline-block; padding:1px 6px; border-radius:3px; font-size:10px; margin-right:4px; }
        .tag-full { background:#1a3d24; color:#21bf4b; }
        .tag-change { background:#3d2a00; color:#ffcc00; }
        .tag-read { background:#1a2a3d; color:#47a8ff; }
        .empty { text-align:center; color:#666; padding:40px; }
        .spinner { display:inline-block; width:20px; height:20px; border:2px solid #404040; border-top-color:#47a8ff; border-radius:50%; animation:spin 0.7s linear infinite; }
        @keyframes spin { to { transform:rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>SMB Explorer {{ version }}</h1>
            <div class="header-info">Просмотр SMB-ресурсов и открытых файлов</div>
        </div>
        <div class="controls">
            <button class="btn btn-primary" onclick="refresh()">Refresh</button>
        </div>
    </div>
    <div class="content">
        <div class="tabs">
            <div class="tab active" onclick="switchTab('shares')">Shares</div>
            <div class="tab" onclick="switchTab('files')">Open Files</div>
        </div>

        <div id="tab-shares" class="panel">
            <div class="panel-header">
                <span>SMB Shares</span>
                <span id="sharesCount"></span>
            </div>
            <div class="panel-body">
                <table>
                    <thead>
                        <tr><th>Name</th><th>Path</th><th>Description</th><th>Users</th><th>Permissions</th></tr>
                    </thead>
                    <tbody id="sharesBody"></tbody>
                </table>
            </div>
        </div>

        <div id="tab-files" class="panel" style="display:none;">
            <div class="panel-header">
                <span>Open Files</span>
                <span id="filesCount"></span>
            </div>
            <div class="toolbar">
                <input type="text" class="search" id="searchInput" placeholder="Search by path, user or computer..." oninput="filterFiles()">
                <select id="timerSelect" onchange="setTimer()">
                    <option value="0">Timer: Off</option>
                    <option value="1">1s</option>
                    <option value="5">5s</option>
                    <option value="10" selected>10s</option>
                    <option value="30">30s</option>
                    <option value="60">60s</option>
                    <option value="300">5min</option>
                    <option value="600">10min</option>
                </select>
            </div>
            <div class="panel-body">
                <table>
                    <thead>
                        <tr><th>File</th><th>Client</th><th>User</th><th>Share</th></tr>
                    </thead>
                    <tbody id="filesBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let currentTab = 'shares';
        let sharesData = [];
        let filesData = [];
        let timerInterval = null;

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-shares').style.display = tab === 'shares' ? '' : 'none';
            document.getElementById('tab-files').style.display = tab === 'files' ? '' : 'none';
        }

        async function refresh() {
            if (currentTab === 'shares') {
                await loadShares();
            } else {
                await loadFiles();
            }
        }

        async function loadShares() {
            try {
                const r = await fetch('/api/shares');
                sharesData = await r.json();
                renderShares();
            } catch(e) {}
        }

        async function loadFiles() {
            try {
                const r = await fetch('/api/open-files');
                filesData = await r.json();
                filterFiles();
            } catch(e) {}
        }

        function renderShares() {
            const tbody = document.getElementById('sharesBody');
            document.getElementById('sharesCount').textContent = sharesData.length + ' shares';
            if (!sharesData.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty">No shares found</td></tr>';
                return;
            }
            let html = '';
            sharesData.forEach(s => {
                const perms = s.permissions.map(p => {
                    const cls = p.right === 'Full' ? 'tag-full' : p.right === 'Change' ? 'tag-change' : 'tag-read';
                    return '<span class="tag ' + cls + '">' + p.account + ': ' + p.right + '</span>';
                }).join('');
                html += '<tr><td><strong>' + s.name + '</strong></td><td>' + s.path + '</td><td>' + (s.description||'') + '</td><td>' + s.current_users + '</td><td>' + perms + '</td></tr>';
            });
            tbody.innerHTML = html;
        }

        function filterFiles() {
            const q = document.getElementById('searchInput').value.toLowerCase();
            const filtered = filesData.filter(f =>
                (f.path||'').toLowerCase().includes(q) ||
                (f.client_user||'').toLowerCase().includes(q) ||
                (f.client_computer||'').toLowerCase().includes(q) ||
                (f.share_path||'').toLowerCase().includes(q)
            );
            renderFiles(filtered);
        }

        function renderFiles(data) {
            const tbody = document.getElementById('filesBody');
            document.getElementById('filesCount').textContent = data.length + ' files';
            if (!data.length) {
                tbody.innerHTML = '<tr><td colspan="4" class="empty">No open files</td></tr>';
                return;
            }
            let html = '';
            data.forEach(f => {
                html += '<tr><td>' + f.path + '</td><td>' + f.client_computer + '</td><td>' + f.client_user + '</td><td>' + f.share_path + '</td></tr>';
            });
            tbody.innerHTML = html;
        }

        function setTimer() {
            if (timerInterval) clearInterval(timerInterval);
            const sec = parseInt(document.getElementById('timerSelect').value);
            if (sec > 0) {
                timerInterval = setInterval(() => {
                    if (currentTab === 'files') loadFiles();
                }, sec * 1000);
            }
        }

        loadShares();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(TEMPLATE, version=VERSION)


@app.route('/api/shares')
def api_shares():
    return jsonify(get_shares())


@app.route('/api/open-files')
def api_open_files():
    return jsonify(get_open_files())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5010)
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'module.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('SMB Explorer %s started', VERSION)

    print(f"SMB Explorer {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
