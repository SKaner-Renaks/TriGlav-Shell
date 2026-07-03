import os
import json
import logging
import argparse
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

VERSION = '3.0'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, 'shares_cache.json')


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
    ps = """Get-SmbOpenFile | ForEach-Object {
        $file = $_
        $item = $null
        try { $item = Get-Item -LiteralPath $file.Path -ErrorAction Stop } catch {}
        $access = 'Read'
        if (($file.Permissions -band 0x2) -eq 0x2 -or ($file.Permissions -band 0x40000000) -eq 0x40000000) {
            $access = 'Write'
        }
        [PSCustomObject]@{
            FileId = $file.FileId
            Path = $file.Path
            ClientComputerName = $file.ClientComputerName
            ClientUserName = $file.ClientUserName
            ShareRelativePath = $file.ShareRelativePath
            Locks = $file.Locks
            Permissions = '0x{0:X}' -f $file.Permissions
            IsFolder = if ($item) { $item.PSIsContainer } else { $false }
            Access = $access
        }
    } | ConvertTo-Json"""
    files = run_ps(ps)
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
            'locks': int(f.get('Locks', 0) or 0),
            'permissions': f.get('Permissions', ''),
            'is_folder': f.get('IsFolder', False),
            'access': f.get('Access', 'Read')
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
        .btn-danger { background:#4d1a1a; color:#ff6c59; border-color:#ff6c59; }
        .btn-danger:hover { background:#ff6c59; color:#fff; }
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
        .spinner-static { animation:none; border-top-color:#404040; }
        @keyframes spin { to { transform:rotate(360deg); } }
        #tab-files table tr:hover { background:#2d2d2d; }
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
        .progress-container { width: 100%; background: #404040; border-radius: 3px; height: 12px; margin-top: 15px; overflow: hidden; display: none; }
        .progress-bar { width: 0%; height: 100%; background: #21bf4b; transition: width 0.1s ease; }
        .progress-detail { font-size: 11px; color: #aaa; margin-top: 6px; text-align: center; display: none; }
        #tab-files table th:first-child, #tab-files table td:first-child { width: 40px; text-align: center; padding-right: 0; }
        #tab-files table th:nth-child(2), #tab-files table td:nth-child(2) { width: auto; white-space: normal; word-break: break-all; }
        #tab-files table td { white-space: nowrap; }
        #tab-files table td:nth-child(2) { white-space: normal; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>SMB Explorer {{ version }}</h1>
            <div class="header-info">Просмотр SMB-ресурсов и открытых файлов</div>
        </div>
        <div class="controls">
            <span id="dataAge" style="font-size:11px;margin-right:12px;"></span>
            <button class="btn btn-primary" onclick="refresh()">Refresh</button>
        </div>
    </div>
    <div class="content">
        <div class="tabs">
            <div class="tab active" onclick="switchTab('shares')">Shares</div>
            <div class="tab" onclick="switchTab('files')">Open Files</div>
            <div class="tab" onclick="switchTab('activity')">Activity</div>
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
                <button class="btn btn-default btn-sm" id="sortBtn" onclick="toggleSort()" title="Sort">↑ A→Z</button>
                <select id="typeFilter" onchange="filterFiles()">
                    <option value="">All</option>
                    <option value="file">Files</option>
                    <option value="folder">Folders</option>
                </select>
                <select id="accessFilter" onchange="filterFiles()">
                    <option value="">All Access</option>
                    <option value="Read">Read</option>
                    <option value="Write">Write</option>
                </select>
                <select id="shareFilter" onchange="filterFiles()">
                    <option value="">All Shares</option>
                </select>
                <input type="text" class="search" id="searchInput" placeholder="Search by user, path or computer..." oninput="filterFiles()">
                <span id="timerSpinner" class="spinner spinner-static"></span>
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
                <button class="btn btn-danger btn-sm" onclick="closeSelected()" style="margin-left:auto;">Close</button>
            </div>
            <div class="panel-body">
                <table>
                    <thead>
                        <tr><th><input type="checkbox" id="selectAll" onchange="toggleAll()"></th><th id="pathHeader">File</th><th>Client</th><th>User</th><th>Access</th><th>Lock</th></tr>
                    </thead>
                    <tbody id="filesBody"></tbody>
                </table>
            </div>
        </div>

        <div id="tab-activity" class="panel" style="display:none;">
            <div class="panel-header">
                <span>User Activity (Top 10)</span>
                <span id="activityCount"></span>
            </div>
            <div class="toolbar">
                <select id="activityTimer" onchange="setActivityTimer()">
                    <option value="0">Timer: Off</option>
                    <option value="1">1s</option>
                    <option value="5">5s</option>
                    <option value="10" selected>10s</option>
                    <option value="30">30s</option>
                    <option value="60">60s</option>
                    <option value="300">5min</option>
                    <option value="600">10min</option>
                </select>
                <span id="activitySpinner" class="spinner spinner-static"></span>
                <div style="margin-left:auto; display:flex; gap:12px; align-items:center;">
                    <button class="btn btn-default btn-sm" id="closeWriteFilesBtn" onclick="closeAllWriteFiles()" disabled>Close All Write Files</button>
                    <button class="btn btn-danger btn-sm" id="kickUserBtn" onclick="kickUserWorkflow()" disabled style="opacity: 0.4;">Kick User</button>
                    <label style="display:inline-flex; align-items:center; gap:6px; font-size:11px; color:#999; cursor:pointer; user-select:none;">
                        <span>Lock</span>
                        <div style="position:relative; width:34px; height:18px; background:#404040; border-radius:9px; transition: 0.2s;">
                            <input type="checkbox" id="unlockToggle" onchange="toggleUnlockActivity()" style="position:absolute; width:100%; height:100%; opacity:0; cursor:pointer; z-index:2;">
                            <div id="toggleSlider" style="position:absolute; top:2px; left:2px; width:14px; height:14px; background:#888; border-radius:50%; transition:0.2s;"></div>
                        </div>
                        <span>Unlock</span>
                    </label>
                </div>
            </div>
            <div class="panel-body">
                <table>
                    <thead>
                        <tr><th>User</th><th>Read</th><th>Write</th><th>Total</th></tr>
                    </thead>
                    <tbody id="activityBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="loadingModal">
        <div class="modal" style="min-width: 320px; max-width: 500px;">
            <div class="spinner-lg" id="modalSpinner"></div>
            <div class="modal-text" id="loadingText">Scanning SMB shares...</div>
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar" id="progressFill"></div>
            </div>
            <div class="progress-detail" id="progressDetail"></div>
        </div>
    </div>

    <script>
        let currentTab = 'shares';
        let sharesData = [];
        let filesData = [];
        let activityData = [];
        let selectedUser = null;
        let timerInterval = null;
        let activityTimerInterval = null;
        let viewMode = 'file';
        let sortMode = 'asc'; // none, asc, desc

        function setViewMode(mode) {
            viewMode = mode;
            document.getElementById('viewFile').className = mode === 'file' ? 'toggle-btn active' : 'toggle-btn';
            document.getElementById('viewShare').className = mode === 'share' ? 'toggle-btn active' : 'toggle-btn';
            document.getElementById('pathHeader').textContent = mode === 'file' ? 'File' : 'Share Path';
            filterFiles();
        }

        function toggleSort() {
            const modes = ['none', 'asc', 'desc'];
            const labels = {none:'↕ None', asc:'↑ A→Z', desc:'↓ Z→A'};
            const idx = modes.indexOf(sortMode);
            sortMode = modes[(idx + 1) % 3];
            document.getElementById('sortBtn').textContent = labels[sortMode];
            filterFiles();
        }

        function showLoading(text, showProgress) {
            document.getElementById('loadingText').textContent = text || 'Scanning...';
            document.getElementById('loadingModal').classList.add('active');
            const pContainer = document.getElementById('progressContainer');
            const pDetail = document.getElementById('progressDetail');
            const spinner = document.getElementById('modalSpinner');
            if (showProgress) {
                pContainer.style.display = 'block';
                pDetail.style.display = 'block';
                spinner.style.display = 'none';
                document.getElementById('progressFill').style.width = '0%';
                pDetail.textContent = '';
            } else {
                pContainer.style.display = 'none';
                pDetail.style.display = 'none';
                spinner.style.display = 'inline-block';
            }
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
            document.getElementById('tab-activity').style.display = tab === 'activity' ? '' : 'none';
            if (tab === 'activity') loadActivity();
        }

        async function refresh() {
            if (currentTab === 'shares') {
                await refreshShares();
            } else {
                showLoading('Loading open files...');
                await loadFiles();
                hideLoading();
            }
        }

        async function loadShares() {
            try {
                const r = await fetch('/api/shares');
                const data = await r.json();
                sharesData = data.shares || [];
                renderShares();
                updateShareDropdown();
                showDataAge(data.updated_at);
            } catch(e) {}
        }

        async function refreshShares() {
            showLoading('Scanning SMB shares...');
            try {
                const r = await fetch('/api/shares/refresh', {method:'POST'});
                const data = await r.json();
                sharesData = data.shares || [];
                renderShares();
                updateShareDropdown();
                showDataAge(data.updated_at);
            } catch(e) {}
            hideLoading();
        }

        function showDataAge(updatedAt) {
            const el = document.getElementById('dataAge');
            if (!updatedAt) { el.textContent = 'No data'; el.style.color = '#666'; return; }
            const d = new Date(updatedAt.replace(' ', 'T'));
            const now = new Date();
            const diffMs = now - d;
            const diffMin = Math.floor(diffMs / 60000);
            let age = '';
            let color = '#21bf4b';
            if (diffMin < 1) age = 'just now';
            else if (diffMin < 60) { age = diffMin + ' min ago'; color = diffMin > 10 ? '#ffcc00' : '#21bf4b'; }
            else { const h = Math.floor(diffMin / 60); age = h + 'h ' + (diffMin % 60) + 'm ago'; color = h > 1 ? '#ff6c59' : '#ffcc00'; }
            el.textContent = 'Data: ' + updatedAt + ' (' + age + ')';
            el.style.color = color;
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
            if (fromTimer) document.getElementById('timerSpinner').classList.remove('spinner-static');
            try {
                const r = await fetch('/api/open-files');
                filesData = await r.json();
                updateShareDropdown();
                filterFiles();
            } catch(e) {}
            document.getElementById('timerSpinner').classList.add('spinner-static');
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
            const typeFilter = document.getElementById('typeFilter').value;
            const accessFilter = document.getElementById('accessFilter').value;
            const terms = q.split(/\s+/).filter(Boolean);
            const filtered = filesData.filter(f => {
                // Filter by share: match file path against share's local path
                if (share) {
                    const shareObj = sharesData.find(s => s.name === share);
                    if (shareObj && !(f.path||'').toLowerCase().startsWith(shareObj.path.toLowerCase())) return false;
                }
                // Filter by type
                if (typeFilter) {
                    if (typeFilter === 'file' && f.is_folder) return false;
                    if (typeFilter === 'folder' && !f.is_folder) return false;
                }
                // Filter by access
                if (accessFilter && (f.access||'') !== accessFilter) return false;
                // Search: all terms must match (AND)
                if (!terms.length) return true;
                return terms.every(t =>
                    (f.path||'').toLowerCase().includes(t) ||
                    (f.client_user||'').toLowerCase().includes(t) ||
                    (f.client_computer||'').toLowerCase().includes(t) ||
                    (f.share_path||'').toLowerCase().includes(t)
                );
            });
            // Sort
            if (sortMode !== 'none') {
                const key = viewMode === 'share' ? 'share_path' : 'path';
                filtered.sort((a, b) => {
                    const va = (a[key]||'').toLowerCase();
                    const vb = (b[key]||'').toLowerCase();
                    return sortMode === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
                });
            }
            renderFiles(filtered);
        }

        function renderFiles(data) {
            const tbody = document.getElementById('filesBody');
            document.getElementById('filesCount').textContent = data.length + ' files';
            const checked = new Set([...document.querySelectorAll('.file-cb:checked')].map(cb => cb.dataset.id));
            if (!data.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty">No open files</td></tr>';
                return;
            }
            let html = '';
            data.forEach(f => {
                const path = viewMode === 'share' ? (f.share_path||'') : (f.path||'');
                const acc = f.access || 'Read';
                const accCls = acc === 'Write' ? 'tag-change' : 'tag-full';
                const chk = checked.has(String(f.file_id)) ? ' checked' : '';
                html += '<tr><td><input type="checkbox" class="file-cb" data-id="' + f.file_id + '"' + chk + '></td><td>' + path + '</td><td>' + f.client_computer + '</td><td>' + f.client_user + '</td><td><span class="tag ' + accCls + '">' + acc + '</span></td><td>' + (f.locks||0) + '</td></tr>';
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

        function toggleAll() {
            const checked = document.getElementById('selectAll').checked;
            document.querySelectorAll('.file-cb').forEach(cb => cb.checked = checked);
        }

        async function closeSelected() {
            const checkedBoxes = [...document.querySelectorAll('.file-cb:checked')];
            if (!checkedBoxes.length) { alert('Select files to close'); return; }
            if (!confirm('Close ' + checkedBoxes.length + ' file(s)?')) return;
            const total = checkedBoxes.length;
            showLoading('Closing files...', true);
            for (let i = 0; i < total; i++) {
                const cb = checkedBoxes[i];
                const fid = cb.dataset.id;
                const row = cb.closest('tr');
                const fileName = row ? row.querySelectorAll('td')[1].textContent : 'Unknown';
                const shortName = fileName.length > 40 ? '...' + fileName.slice(-37) : fileName;
                const percent = Math.round((i / total) * 100);
                document.getElementById('progressFill').style.width = percent + '%';
                document.getElementById('progressDetail').innerHTML =
                    'Processing: ' + (i+1) + ' of ' + total + ' (' + percent + '%)<br>' +
                    '<span style="color:#ff6c59; font-size:11px;">Closing: ' + shortName + '</span>';
                try {
                    await fetch('/api/close-files', {
                        method:'POST', headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({file_ids:[fid]})
                    });
                } catch(e) {}
            }
            document.getElementById('progressFill').style.width = '100%';
            document.getElementById('progressDetail').textContent = 'Done!';
            await new Promise(resolve => setTimeout(resolve, 600));
            hideLoading();
            await loadFiles();
        }

        async function loadActivity() {
            document.getElementById('activitySpinner').classList.remove('spinner-static');
            try {
                const r = await fetch('/api/user-activity');
                activityData = await r.json();
                renderActivity();
            } catch(e) {}
            document.getElementById('activitySpinner').classList.add('spinner-static');
        }

        function renderActivity() {
            const tbody = document.getElementById('activityBody');
            document.getElementById('activityCount').textContent = activityData.length + ' users';
            if (!activityData.length) {
                tbody.innerHTML = '<tr><td colspan="4" class="empty">No activity</td></tr>';
                return;
            }
            let html = '';
            activityData.forEach(a => {
                const currentUserName = a.User || '';
                const isSelected = selectedUser && currentUserName === selectedUser;
                const style = isSelected ? ' style="cursor:pointer; background:#3d2a00;"' : ' style="cursor:pointer;"';
                html += '<tr' + style + ' onclick="selectUser(this, \'' + currentUserName.replace(/'/g, "\\'") + '\')"><td>' + currentUserName + '</td><td>' + (a.Read||0) + '</td><td>' + (a.Write||0) + '</td><td>' + (a.Total||0) + '</td></tr>';
            });
            tbody.innerHTML = html;
            updateActivityButtonsState();
        }

        function selectUser(row, user) {
            document.querySelectorAll('#activityBody tr').forEach(r => r.style.background = '');
            row.style.background = '#3d2a00';
            selectedUser = user;
            updateActivityButtonsState();
        }

        function toggleUnlockActivity() {
            const isUnlocked = document.getElementById('unlockToggle').checked;
            const slider = document.getElementById('toggleSlider');
            if (isUnlocked) {
                slider.style.left = '18px';
                slider.style.background = '#ff6c59';
            } else {
                slider.style.left = '2px';
                slider.style.background = '#888';
            }
            updateActivityButtonsState();
        }

        function updateActivityButtonsState() {
            const isUnlocked = document.getElementById('unlockToggle').checked;
            const hasUser = !!selectedUser;
            const closeWriteBtn = document.getElementById('closeWriteFilesBtn');
            const kickUserBtn = document.getElementById('kickUserBtn');
            if (!isUnlocked) {
                closeWriteBtn.disabled = true;
                kickUserBtn.disabled = true;
                kickUserBtn.style.opacity = '0.4';
            } else {
                closeWriteBtn.disabled = !hasUser;
                kickUserBtn.disabled = !hasUser;
                kickUserBtn.style.opacity = hasUser ? '1' : '0.4';
            }
        }

        function setActivityTimer() {
            if (activityTimerInterval) clearInterval(activityTimerInterval);
            const sec = parseInt(document.getElementById('activityTimer').value);
            if (sec > 0) {
                activityTimerInterval = setInterval(() => {
                    if (currentTab === 'activity') loadActivity();
                }, sec * 1000);
            }
        }

        async function closeAllWriteFiles() {
            if (!confirm('Close ALL open write files? Read files will not be touched.')) return;
            showLoading('Getting write files list...', true);
            try {
                const res = await fetch('/api/close-write-files', { method: 'POST' });
                const data = await res.json();
                const fileIds = data.file_ids || [];
                if (fileIds.length === 0) {
                    document.getElementById('progressDetail').textContent = 'No active write files.';
                    await new Promise(r => setTimeout(r, 1000));
                    hideLoading();
                    return;
                }
                const total = fileIds.length;
                for (let i = 0; i < total; i++) {
                    const percent = Math.round((i / total) * 100);
                    document.getElementById('progressFill').style.width = percent + '%';
                    document.getElementById('progressDetail').innerHTML = 'Closing write files: ' + (i+1) + ' of ' + total + ' (' + percent + '%)';
                    await fetch('/api/close-files', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({file_ids: [fileIds[i]]})
                    });
                }
                document.getElementById('progressFill').style.width = '100%';
                document.getElementById('progressDetail').textContent = 'Done! All write file streams closed.';
            } catch(e) {
                document.getElementById('progressDetail').textContent = 'Error occurred.';
            }
            await new Promise(r => setTimeout(r, 1000));
            hideLoading();
            if (currentTab === 'activity') loadActivity();
        }

        async function kickUserWorkflow() {
            if (!selectedUser) return;
            if (!confirm('Force kick session for ' + selectedUser + '?')) return;
            showLoading('Finding sessions for ' + selectedUser + '...', false);
            try {
                const response = await fetch('/api/kick-user/step1', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user: selectedUser})
                });
                const result = await response.json();
                hideLoading();
                const remainingCount = result.remaining_files ? result.remaining_files.length : 0;
                if (remainingCount > 0) {
                    const shouldCloseFiles = confirm('Sessions closed. ' + remainingCount + ' file(s) still open. Close them?');
                    if (shouldCloseFiles) {
                        showLoading('Closing remaining files...', true);
                        const fileIds = result.remaining_files;
                        const total = fileIds.length;
                        for (let i = 0; i < total; i++) {
                            const percent = Math.round((i / total) * 100);
                            document.getElementById('progressFill').style.width = percent + '%';
                            document.getElementById('progressDetail').textContent = 'Closing files: ' + (i+1) + ' of ' + total;
                            await fetch('/api/kick-user/step2', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({file_ids: [fileIds[i]]})
                            });
                        }
                        document.getElementById('progressFill').style.width = '100%';
                        document.getElementById('progressDetail').textContent = 'All user files closed!';
                        await new Promise(r => setTimeout(r, 1000));
                        hideLoading();
                    }
                } else {
                    alert('Sessions for ' + selectedUser + ' closed. No open files found.');
                }
            } catch(e) {
                hideLoading();
                alert('Error during Kick User operation.');
            }
            selectedUser = null;
            updateActivityButtonsState();
            loadActivity();
        }

        loadShares();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(TEMPLATE, version=VERSION)


def get_shares_cached():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('shares', []), data.get('updated_at', '')
        except Exception:
            pass
    return [], ''


def save_shares_cache(shares):
    data = {
        'shares': shares,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route('/api/shares')
def api_shares():
    shares, updated_at = get_shares_cached()
    return jsonify({'shares': shares, 'updated_at': updated_at})


@app.route('/api/shares/refresh', methods=['POST'])
def api_shares_refresh():
    shares = get_shares()
    save_shares_cache(shares)
    updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'shares': shares, 'updated_at': updated_at})


@app.route('/api/open-files')
def api_open_files():
    return jsonify(get_open_files())


@app.route('/api/close-files', methods=['POST'])
def api_close_files():
    data = request.get_json()
    file_ids = data.get('file_ids', [])
    results = []
    for fid in file_ids:
        ps = f'Close-SmbOpenFile -FileId "{fid}" -Force -ErrorAction Stop'
        out = run_ps(ps)
        results.append({'file_id': fid, 'status': 'closed'})
    return jsonify({'results': results})


@app.route('/api/user-activity')
def api_user_activity():
    ps = """Get-SmbOpenFile | Group-Object ClientUserName | Sort-Object Count -Descending |
        Select-Object -First 10 | ForEach-Object {
        $reads = ($_.Group | Where-Object { ($_.Permissions -band 0x2) -eq 0 }).Count
        $writes = ($_.Group | Where-Object { ($_.Permissions -band 0x2) -eq 0x2 }).Count
        [PSCustomObject]@{
            User = if ($_.Name) { $_.Name } else { 'Unknown' }
            Total = $_.Count
            Read = $reads
            Write = $writes
        }
    } | ConvertTo-Json"""
    data = run_ps(ps)
    if isinstance(data, dict):
        data = [data]
    return jsonify(data)


@app.route('/api/close-write-files', methods=['POST'])
def api_close_write_files():
    ps = """Get-SmbOpenFile | Where-Object {
        (($_.Permissions -band 0x2) -eq 0x2) -or (($_.Permissions -band 0x40000000) -eq 0x40000000)
    } | Select-Object -Property FileId | ConvertTo-Json"""
    files = run_ps(ps)
    if isinstance(files, dict):
        files = [files]
    file_ids = [f.get('FileId') for f in files if f.get('FileId')]
    return jsonify({'file_ids': file_ids})


@app.route('/api/kick-user/step1', methods=['POST'])
def kick_user_step1():
    user = request.json.get('user', '')
    if not user:
        return jsonify({'error': 'No user specified'}), 400
    ps_session = f'Get-SmbSession | Where-Object {{ $_.ClientUserName -like "*{user}" }} | Select-Object -Property SessionId, ClientComputerName | ConvertTo-Json'
    sessions = run_ps(ps_session)
    if isinstance(sessions, dict):
        sessions = [sessions]
    session_ids = [s.get('SessionId') for s in sessions if s.get('SessionId')]
    for sid in session_ids:
        run_ps(f'Close-SmbSession -SessionId "{sid}" -Force -ErrorAction SilentlyContinue')
    if not session_ids:
        ps_alt = f'Get-SmbOpenFile | Where-Object {{ $_.ClientUserName -like "*{user}" }} | Select-Object -Property ClientComputerName -Unique | ConvertTo-Json'
        computers = run_ps(ps_alt)
        if isinstance(computers, dict):
            computers = [computers]
        for c in computers:
            comp_name = c.get('ClientComputerName', '')
            if comp_name:
                run_ps(f'Close-SmbSession -ClientComputerName "{comp_name}" -Force -ErrorAction SilentlyContinue')
    import time
    time.sleep(0.5)
    ps_files = f'Get-SmbOpenFile | Where-Object {{ $_.ClientUserName -like "*{user}" }} | Select-Object -Property FileId | ConvertTo-Json'
    files = run_ps(ps_files)
    if isinstance(files, dict):
        files = [files]
    file_ids = [f.get('FileId') for f in files if f.get('FileId')]
    return jsonify({'session_closed': max(len(session_ids), 1), 'remaining_files': file_ids})


@app.route('/api/kick-user/step2', methods=['POST'])
def kick_user_step2():
    file_ids = request.json.get('file_ids', [])
    for fid in file_ids:
        run_ps(f'Close-SmbOpenFile -FileId "{fid}" -Force -ErrorAction SilentlyContinue')
    return jsonify({'status': 'done', 'closed_files_count': len(file_ids)})


def background_refresh():
    shares = get_shares()
    save_shares_cache(shares)


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

    threading.Thread(target=background_refresh, daemon=True).start()

    print(f"SMB Explorer {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
