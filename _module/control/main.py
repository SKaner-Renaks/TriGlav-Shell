import os
import json
import time
import shutil
import logging
import argparse
import subprocess
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, send_file
import psutil

VERSION = '1.5'

app = Flask(__name__)


def get_server_info():
    import socket
    hostname = socket.gethostname()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = '127.0.0.1'
    now = datetime.now().strftime('%H:%M')
    return f'{hostname} | {ip} | {now}'


CONTROL_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Control Panel {{ version }}</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; background:#1a1a1a; color:#f2f2f2; font-size:13px; }
        .header { background:#262626; border-bottom:1px solid #404040; padding:14px 20px; display:flex; justify-content:space-between; align-items:center; }
        .header h1 { font-size:18px; font-weight:600; color:#47a8ff; }
        .header-info { font-size:12px; color:#999; margin-top:2px; }
        .controls { display:flex; gap:8px; align-items:center; }
        .btn { padding:6px 14px; border:1px solid #595959; border-radius:3px; cursor:pointer; font-size:12px; font-family:inherit; transition:background 0.15s; }
        .btn-primary { background:#0057b3; color:#f2f2f2; border-color:#0057b3; }
        .btn-primary:hover { background:#0073d9; }
        .btn-default { background:#404040; color:#f2f2f2; }
        .btn-default:hover { background:#595959; }
        .btn-sm { padding:3px 8px; font-size:11px; }
        .content { padding:16px 20px; }
        .panel { background:#262626; border:1px solid #404040; border-radius:3px; margin-bottom:12px; }
        .panel-header { background:#333; padding:8px 12px; border-bottom:1px solid #404040; font-weight:600; color:#47a8ff; font-size:12px; display:flex; justify-content:space-between; align-items:center; }
        .panel-body { padding:12px; }
        .shell-area { background:#0d0d0d; border:1px solid #333; border-radius:3px; padding:10px; font-family:"Cascadia Mono","Consolas",monospace; font-size:12px; min-height:200px; max-height:300px; overflow-y:auto; white-space:pre-wrap; color:#21bf4b; }
        .shell-input-row { display:flex; gap:8px; margin-bottom:8px; }
        .shell-input { flex:1; padding:6px 10px; background:#0d0d0d; border:1px solid #404040; border-radius:3px; color:#21bf4b; font-family:"Cascadia Mono","Consolas",monospace; font-size:12px; }
        .shell-input:focus { outline:none; border-color:#0057b3; }
        .file-path-row { display:flex; gap:8px; margin-bottom:8px; }
        .file-path-input { flex:1; padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; font-family:inherit; }
        .file-path-input:focus { outline:none; border-color:#0057b3; }
        .file-list { max-height:400px; overflow-y:auto; }
        .file-item { display:flex; align-items:center; gap:8px; padding:6px 8px; border-bottom:1px solid #333; font-size:12px; cursor:pointer; transition:background 0.1s; }
        .file-item:hover { background:#333; }
        .file-item.selected { background:#0057b3; }
        .file-icon { width:18px; text-align:center; }
        .file-name { flex:1; }
        .file-size { color:#999; width:80px; text-align:right; }
        .file-date { color:#999; width:140px; text-align:right; }
        .upload-zone { border:2px dashed #404040; border-radius:4px; padding:20px; text-align:center; color:#999; cursor:pointer; transition:border-color 0.2s; margin-bottom:8px; }
        .upload-zone:hover { border-color:#0057b3; }
        .upload-zone.dragover { border-color:#47a8ff; background:rgba(71,168,255,0.05); }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Control Panel {{ version }}</h1>
            <div class="header-info" id="serverInfo">{{ description }}</div>
        </div>
        <div class="controls">
        </div>
    </div>
    <div class="content">
        <div class="panel">
            <div class="panel-header">PowerShell Console</div>
            <div class="panel-body">
                <div class="shell-input-row">
                    <input type="text" class="shell-input" id="shellInput" placeholder="Enter PowerShell command..." onkeydown="if(event.key==='Enter')runShell()">
                    <button class="btn btn-primary" onclick="runShell()">Execute</button>
                    <button class="btn btn-default" onclick="clearShell()">Clear</button>
                </div>
                <div class="shell-area" id="shellOutput">Ready.</div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <span>File Navigator</span>
                <div style="display:flex;gap:4px;">
                    <button class="btn btn-default btn-sm" onclick="fileNewFolder()">New Folder</button>
                    <button class="btn btn-default btn-sm" onclick="fileDelete()">Delete</button>
                    <button class="btn btn-default btn-sm" onclick="fileCopy()">Copy</button>
                    <button class="btn btn-default btn-sm" onclick="fileMove()">Move</button>
                    <button class="btn btn-default btn-sm" onclick="fileDownload()">Download</button>
                </div>
            </div>
            <div class="panel-body">
                <div class="file-path-row">
                    <select id="driveSelect" style="background:#1a1a1a;border:1px solid #404040;color:#f2f2f2;border-radius:3px;padding:6px 8px;font-size:12px;font-family:inherit;" onchange="browseTo(this.value)"></select>
                    <input type="text" class="file-path-input" id="filePath" value="C:\\" onkeydown="if(event.key==='Enter')browseTo(this.value)">
                    <button class="btn btn-primary" onclick="browseTo(document.getElementById('filePath').value)">Go</button>
                </div>
                <div class="upload-zone" id="uploadZone" onclick="document.getElementById('fileUpload').click()">
                    Drop files here or click to upload
                    <input type="file" id="fileUpload" style="display:none" multiple onchange="uploadFiles(this.files)">
                </div>
                <div class="file-list" id="fileList"><div class="loading">Loading...</div></div>
            </div>
        </div>
    </div>

    <script>
        let selectedFile = null;
        let currentPath = 'C:\\';

        async function runShell() {
            const input = document.getElementById('shellInput');
            const cmd = input.value.trim();
            if (!cmd) return;
            const out = document.getElementById('shellOutput');
            out.textContent += '\n> ' + cmd + '\n';
            input.value = '';
            out.textContent += 'Executing...\n';
            out.scrollTop = out.scrollHeight;
            try {
                const r = await fetch('/api/shell', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:cmd}) });
                const d = await r.json();
                out.textContent += (d.output || d.error || 'No output') + '\n';
            } catch(e) { out.textContent += 'Error: ' + e.message + '\n'; }
            out.scrollTop = out.scrollHeight;
        }

        function clearShell() { document.getElementById('shellOutput').textContent = 'Ready.\n'; }

        async function loadDrives() {
            try {
                const r = await fetch('/api/drives');
                const d = await r.json();
                const sel = document.getElementById('driveSelect');
                sel.innerHTML = '';
                (d.drives || []).forEach(dr => {
                    const opt = document.createElement('option');
                    opt.value = dr;
                    opt.textContent = dr;
                    sel.appendChild(opt);
                });
            } catch(e) {}
        }

        async function browseTo(path) {
            currentPath = path;
            document.getElementById('filePath').value = path;
            try {
                const r = await fetch('/api/files?path=' + encodeURIComponent(path));
                const d = await r.json();
                if (d.error) { document.getElementById('fileList').innerHTML = '<div style="color:#ff6c59;padding:8px">'+d.error+'</div>'; return; }
                let html = '';
                if (d.parent) {
                    html += '<div class="file-item" onclick="browseTo(\''+d.parent.replace(/\\/g,'\\\\')+'\')"><div class="file-icon">&uarr;</div><div class="file-name">..</div></div>';
                }
                d.directories.forEach(name => {
                    const full = path.endsWith('\\') ? path + name : path + '\\' + name;
                    html += '<div class="file-item" onclick="selectFile(this, \''+full.replace(/\\/g,'\\\\')+'\', true)" ondblclick="browseTo(\''+full.replace(/\\/g,'\\\\')+'\')">'
                        + '<div class="file-icon">[D]</div><div class="file-name">'+name+'</div></div>';
                });
                d.files.forEach(f => {
                    const full = path.endsWith('\\') ? path + f.name : path + '\\' + f.name;
                    html += '<div class="file-item" onclick="selectFile(this, \''+full.replace(/\\/g,'\\\\')+'\', false)">'
                        + '<div class="file-icon">[F]</div><div class="file-name">'+f.name+'</div><div class="file-size">'+f.size+'</div><div class="file-date">'+f.date+'</div></div>';
                });
                document.getElementById('fileList').innerHTML = html || '<div style="padding:8px;color:#999;">Empty directory</div>';
            } catch(e) { document.getElementById('fileList').innerHTML = '<div style="color:#ff6c59;padding:8px">Error loading files</div>'; }
        }

        function selectFile(el, path, isDir) {
            document.querySelectorAll('.file-item.selected').forEach(e => e.classList.remove('selected'));
            el.classList.add('selected');
            selectedFile = { path:path, isDir:isDir };
        }

        async function fileNewFolder() {
            const name = prompt('Folder name:');
            if (!name) return;
            try {
                await fetch('/api/files/mkdir', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:currentPath, name:name}) });
                browseTo(currentPath);
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function fileDelete() {
            if (!selectedFile) { alert('Select a file or folder first'); return; }
            if (!confirm('Delete ' + selectedFile.path + '?')) return;
            try {
                await fetch('/api/files/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:selectedFile.path}) });
                selectedFile = null;
                browseTo(currentPath);
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function fileCopy() {
            if (!selectedFile) { alert('Select a file or folder first'); return; }
            const dest = prompt('Copy to (full path):');
            if (!dest) return;
            try {
                await fetch('/api/files/copy', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:selectedFile.path, dest:dest}) });
                browseTo(currentPath);
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function fileMove() {
            if (!selectedFile) { alert('Select a file or folder first'); return; }
            const dest = prompt('Move to (full path):');
            if (!dest) return;
            try {
                await fetch('/api/files/move', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:selectedFile.path, dest:dest}) });
                browseTo(currentPath);
            } catch(e) { alert('Error: ' + e.message); }
        }

        function fileDownload() {
            if (!selectedFile || selectedFile.isDir) { alert('Select a file first'); return; }
            window.open('/api/files/download?path=' + encodeURIComponent(selectedFile.path));
        }

        async function uploadFiles(files) {
            for (let f of files) {
                const fd = new FormData();
                fd.append('file', f);
                fd.append('path', currentPath);
                try {
                    await fetch('/api/files/upload', { method:'POST', body:fd });
                } catch(e) { alert('Upload error: ' + e.message); }
            }
            browseTo(currentPath);
        }

        const uz = document.getElementById('uploadZone');
        uz.addEventListener('dragover', e => { e.preventDefault(); uz.classList.add('dragover'); });
        uz.addEventListener('dragleave', () => uz.classList.remove('dragover'));
        uz.addEventListener('drop', e => { e.preventDefault(); uz.classList.remove('dragover'); uploadFiles(e.dataTransfer.files); });

        function updateClock() {
            const now = new Date();
            const hh = String(now.getHours()).padStart(2, '0');
            const mm = String(now.getMinutes()).padStart(2, '0');
            const el = document.getElementById('headerTime');
            if (el) el.textContent = hh + ':' + mm;
        }

        loadDrives();
        browseTo('C:\\');
        updateClock();
        setInterval(updateClock, 60000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifest.json')
    description = ''
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        description = manifest.get('description', '')
    except Exception:
        pass
    return render_template_string(CONTROL_TEMPLATE, version=VERSION, description=description)


@app.route('/api/shell', methods=['POST'])
def api_shell():
    data = request.get_json()
    cmd = data.get('command', '')
    if not cmd:
        return jsonify({'error': 'No command'}), 400
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', cmd],
            capture_output=True, timeout=30
        )
        stdout = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        stderr = result.stderr.decode('cp866', errors='replace').strip() if result.stderr else ''
        output = stdout or stderr or f'exit code {result.returncode}'
        return jsonify({'output': output})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timed out (30s)'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drives')
def api_drives():
    drives = []
    for p in psutil.disk_partitions():
        try:
            psutil.disk_usage(p.mountpoint)
            drives.append(p.device.replace('\\', ''))
        except PermissionError:
            pass
    return jsonify({'drives': drives})


@app.route('/api/files')
def api_files_list():
    path = request.args.get('path', 'C:\\')
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return jsonify({'error': f'Not a directory: {path}'}), 400
    try:
        entries = os.listdir(path)
        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(path, e))])
        files = []
        for e in sorted(entries):
            fp = os.path.join(path, e)
            if os.path.isfile(fp):
                stat = os.stat(fp)
                size = stat.st_size
                if size < 1024:
                    size_str = f'{size} B'
                elif size < 1024 * 1024:
                    size_str = f'{size / 1024:.1f} KB'
                elif size < 1024 * 1024 * 1024:
                    size_str = f'{size / (1024 * 1024):.1f} MB'
                else:
                    size_str = f'{size / (1024 * 1024 * 1024):.1f} GB'
                files.append({
                    'name': e,
                    'size': size_str,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                })
        parent = os.path.dirname(path) if path != os.path.splitdrive(path)[0] + '\\' else None
        return jsonify({'path': path, 'directories': dirs, 'files': files, 'parent': parent})
    except PermissionError:
        return jsonify({'error': 'Access denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/mkdir', methods=['POST'])
def api_files_mkdir():
    data = request.get_json()
    path = data.get('path', '')
    name = data.get('name', '')
    if not path or not name:
        return jsonify({'error': 'Missing path or name'}), 400
    try:
        os.makedirs(os.path.join(path, name), exist_ok=True)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/delete', methods=['POST'])
def api_files_delete():
    data = request.get_json()
    path = data.get('path', '')
    if not path:
        return jsonify({'error': 'No path'}), 400
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/copy', methods=['POST'])
def api_files_copy():
    data = request.get_json()
    src = data.get('source', '')
    dst = data.get('dest', '')
    if not src or not dst:
        return jsonify({'error': 'Missing source or dest'}), 400
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/move', methods=['POST'])
def api_files_move():
    data = request.get_json()
    src = data.get('source', '')
    dst = data.get('dest', '')
    if not src or not dst:
        return jsonify({'error': 'Missing source or dest'}), 400
    try:
        shutil.move(src, dst)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/download')
def api_files_download():
    path = request.args.get('path', '')
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(path, as_attachment=True)


@app.route('/api/files/upload', methods=['POST'])
def api_files_upload():
    file = request.files.get('file')
    dest_dir = request.form.get('path', '')
    if not file or not dest_dir:
        return jsonify({'error': 'Missing file or path'}), 400
    try:
        dest = os.path.join(dest_dir, file.filename)
        file.save(dest)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5002)
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log_file.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('Control Panel %s started', VERSION)

    print("=" * 50)
    print(f"  Control Panel {VERSION}")
    print(f"  http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    app.run(host=args.host, port=args.port, debug=False)
