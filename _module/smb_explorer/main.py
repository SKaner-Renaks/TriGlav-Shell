import os
import json
import logging
import argparse
import subprocess
from flask import Flask, render_template_string, jsonify

VERSION = '1.3'

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
    shares = run_ps('Get-SmbShare | Select-Object Name,Path,Description,CurrentUsers,Special | ConvertTo-Json')
    if isinstance(shares, dict):
        shares = [shares]
    result = []
    for s in shares:
        name = s.get('Name', '')
        is_special = s.get('Special', False)
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
            'is_special': is_special,
            'permissions': perms
        })
    result.sort(key=lambda x: (x['is_special'], x['name']))
    return result


def get_open_files():
    files = run_ps('Get-SmbOpenFile | Select-Object FileId,Path,ClientComputerName,ClientUserName,ShareRelativePath,Locks | ConvertTo-Json')
    if isinstance(files, dict):
        files = [files]
    result = []
    for f in files:
        result.append({
            'file_id': f.get('FileId', ''),
            'path': f.get('Path', ''),
            'client_computer': f.get('ClientComputerName', ''),
            'client_user': f.get('ClientUserName', ''),
            'share_path': f.get('ShareRelativePath', ''),
            'locks': f.get('Locks', 0)
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
        .modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:100; justify-content:center; align-items:center; }
        .modal-overlay.active { display:flex; }
        .modal { background:#262626; border:1px solid #404040; border-radius:4px; padding:30px; text-align:center; }
        .spinner-lg { display:inline-block; width:40px; height:40px; border:3px solid #404040; border-top-color:#47a8ff; border-radius:50%; animation:spin 0.7s linear infinite; margin-bottom:12px; }
        .modal-text { color:#999; font-size:13px; margin-top:8px; }
        .section-header { padding:8px 12px; background:#1f1f1f; color:#47a8ff; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:1px; border-bottom:1px solid #333; }
        .toggle-group { display:inline-flex; border:1px solid #404040; border-radius:3px; overflow:hidden; }
        .toggle-btn { padding:4px 10px; background:#333; border:none; color:#999; font-size:11px; cursor:pointer; font-family:inherit; }
        .toggle-btn + .toggle-btn { border-left:1px solid #404040; }
        .toggle-btn.active { background:#0057b3; color:#fff; }
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

        <div id="tab-shares">
            <div class="panel">
                <div class="panel-header">
                    <span>User Shares</span>
                    <span id="sharesUserCount"></span>
                </div>
                <div class="panel-body">
                    <table>
                        <thead><tr><th>Name</th><th>Path</th><th>Description</th><th>Users</th><th>Permissions</th></tr></thead>
                        <tbody id="sharesUser"></tbody>
                    </table>
                </div>
            </div>
            <div class="panel" style="margin-top:12px;">
                <div class="panel-header">
                    <span>System Shares</span>
                    <span id="sharesSystemCount"></span>
                </div>
                <div class="panel-body">
                    <table>
                        <thead><tr><th>Name</th><th>Path</th><th>Description</th><th>Users</th><th>Permissions</th></tr></thead>
                        <tbody id="sharesSystem"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="tab-files" class="panel" style="display:none;">
            <div class="panel-header">
                <span>Open Files</span>
                <span id="filesCount"></span>
            </div>
            <div class="toolbar">
                <div class="toggle-group">
                    <button class="toggle-btn active" id="viewFile" onclick="setViewMode('file')">File</button>
                    <button class="toggle-btn" id="viewShare" onclick="setViewMode('share')">Share</button>
                </div>
                <select id="shareFilter" onchange="filterFiles()">
                    <option value="">All Shares</option>
                </select>
                <input type="text" class="search" id="searchInput" placeholder="Search by user, path or computer..." oninput="filterFiles()">
                <span id="timerSpinner" class="spinner" style="display:none;"></span>
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
                        <tr><th id="pathHeader">File</th><th>Client</th><th>User</th><th>Access</th></tr>
                    </thead>
                    <tbody id="filesBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="loadingModal">
        <div class="modal">
            <div class="spinner-lg"></div>
            <div class="modal-text" id="loadingText">Scanning SMB shares...</div>
        </div>
    </div>

    <script>
        let currentTab = 'shares';
        let sharesData = [];
        let filesData = [];
        let timerInterval = null;
        let viewMode = 'file';

        function setViewMode(mode) {
            viewMode = mode;
            document.getElementById('viewFile').className = mode === 'file' ? 'toggle-btn active' : 'toggle-btn';
            document.getElementById('viewShare').className = mode === 'share' ? 'toggle-btn active' : 'toggle-btn';
            document.getElementById('pathHeader').textContent = mode === 'file' ? 'File' : 'Share Path';
            filterFiles();
        }

        function showLoading(text) {
            document.getElementById('loadingText').textContent = text || 'Scanning...';
            document.getElementById('loadingModal').classList.add('active');
        }
        function hideLoading() {
            document.getElementById('loadingModal').classList.remove('active');
        }

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
                showLoading('Loading open files...');
                await loadFiles();
                hideLoading();
            }
        }

        async function loadShares() {
            showLoading('Scanning SMB shares...');
            try {
                const r = await fetch('/api/shares');
                sharesData = await r.json();
                renderShares();
                updateShareDropdown();
            } catch(e) {}
            hideLoading();
        }

        function updateShareDropdown() {
            const sel = document.getElementById('shareFilter');
            const current = sel.value;
            const custom = sharesData.filter(s => !s.is_special);
            const system = sharesData.filter(s => s.is_special);
            sel.innerHTML = '<option value="">All Shares</option>';
            if (custom.length) {
                const grp1 = document.createElement('optgroup');
                grp1.label = 'Custom Shares';
                custom.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.name;
                    opt.textContent = s.name + ' (' + s.path + ')';
                    grp1.appendChild(opt);
                });
                sel.appendChild(grp1);
            }
            if (system.length) {
                const grp2 = document.createElement('optgroup');
                grp2.label = 'System Shares';
                system.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.name;
                    opt.textContent = s.name + ' (' + s.path + ')';
                    grp2.appendChild(opt);
                });
                sel.appendChild(grp2);
            }
            sel.value = current;
        }

        async function loadFiles(fromTimer) {
            if (fromTimer) document.getElementById('timerSpinner').style.display = '';
            try {
                const r = await fetch('/api/open-files');
                filesData = await r.json();
                updateShareDropdown();
                filterFiles();
            } catch(e) {}
            document.getElementById('timerSpinner').style.display = 'none';
        }

        function renderShares() {
            const userBody = document.getElementById('sharesUser');
            const sysBody = document.getElementById('sharesSystem');
            const custom = sharesData.filter(s => !s.is_special);
            const system = sharesData.filter(s => s.is_special);

            document.getElementById('sharesUserCount').textContent = custom.length + ' shares';
            document.getElementById('sharesSystemCount').textContent = system.length + ' shares';

            function renderRows(data) {
                if (!data.length) return '<tr><td colspan="5" class="empty">No shares</td></tr>';
                let html = '';
                data.forEach(s => {
                    const perms = s.permissions.map(p => {
                        const cls = p.right === 'Full' ? 'tag-full' : p.right === 'Change' ? 'tag-change' : 'tag-read';
                        return '<span class="tag ' + cls + '">' + p.account + ': ' + p.right + '</span>';
                    }).join('');
                    html += '<tr><td><strong>' + s.name + '</strong></td><td>' + s.path + '</td><td>' + (s.description||'') + '</td><td>' + s.current_users + '</td><td>' + perms + '</td></tr>';
                });
                return html;
            }

            userBody.innerHTML = renderRows(custom);
            sysBody.innerHTML = renderRows(system);
        }

        function filterFiles() {
            const q = document.getElementById('searchInput').value.toLowerCase();
            const share = document.getElementById('shareFilter').value;
            const filtered = filesData.filter(f => {
                if (share && !(f.share_path||'').toLowerCase().includes(share.toLowerCase())) return false;
                if (!q) return true;
                return (f.path||'').toLowerCase().includes(q) ||
                    (f.client_user||'').toLowerCase().includes(q) ||
                    (f.client_computer||'').toLowerCase().includes(q) ||
                    (f.share_path||'').toLowerCase().includes(q);
            });
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
                const path = viewMode === 'share' ? (f.share_path||'') : (f.path||'');
                const accessTag = f.locks > 0
                    ? '<span class="tag tag-change">Write</span>'
                    : '<span class="tag tag-full">Read</span>';
                html += '<tr><td>' + path + '</td><td>' + f.client_computer + '</td><td>' + f.client_user + '</td><td>' + accessTag + '</td></tr>';
            });
            tbody.innerHTML = html;
        }

        function setTimer() {
            if (timerInterval) clearInterval(timerInterval);
            const sec = parseInt(document.getElementById('timerSelect').value);
            if (sec > 0) {
                timerInterval = setInterval(() => {
                    if (currentTab === 'files') loadFiles(true);
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
