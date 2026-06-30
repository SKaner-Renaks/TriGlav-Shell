import os
import sys
import json
import subprocess
import importlib
import argparse
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)


if sys.platform == 'win32':
    os.system('')
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = kernel32.GetConsoleMode(handle)
        kernel32.SetConsoleMode(handle, mode | 0x0004)
    except Exception:
        pass

VERSION = '1.2.2'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
MODULE_DIR = os.path.join(SHELL_DIR, '_module')

PACKAGE_IMPORT_MAP = {
    'flask': 'flask',
    'psutil': 'psutil',
    'ldap3': 'ldap3',
    'requests': 'requests',
}


def check_import(package_name):
    import_name = PACKAGE_IMPORT_MAP.get(package_name, package_name)
    try:
        importlib.import_module(import_name)
        return True, None
    except ImportError as e:
        return False, str(e)


def parse_requirements(filepath):
    packages = []
    if not os.path.exists(filepath):
        return packages
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('>=', 1)
            if len(parts) == 1:
                parts = line.split('==', 1)
            packages.append({
                'name': parts[0].strip(),
                'version': parts[1].strip() if len(parts) > 1 else 'any'
            })
    return packages


def get_all_requirements():
    result = {}

    shell_req = os.path.join(SHELL_DIR, 'requirements.txt')
    if os.path.exists(shell_req):
        result['Shell'] = {'packages': parse_requirements(shell_req), 'description': 'Ядро Shell'}

    if os.path.isdir(MODULE_DIR):
        for name in sorted(os.listdir(MODULE_DIR)):
            mod_path = os.path.join(MODULE_DIR, name)
            req_path = os.path.join(mod_path, 'requirements.txt')
            manifest_path = os.path.join(mod_path, 'manifest.json')
            if os.path.isdir(mod_path) and os.path.exists(req_path):
                pkgs = parse_requirements(req_path)
                desc = ''
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                        desc = manifest.get('description', '')
                    except Exception:
                        pass
                if pkgs:
                    result[name] = {'packages': pkgs, 'description': desc}

    return result


def install_package(package_name):
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package_name],
            capture_output=True, text=True, timeout=120
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


CHECK_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Проверка зависимостей {{ version }}</title>
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
        .btn-success { background:#1a3d24; color:#21bf4b; border-color:#21bf4b; }
        .btn-success:hover { background:#21bf4b; color:#fff; }
        .content { padding:16px 20px; }
        .panel { background:#262626; border:1px solid #404040; border-radius:3px; margin-bottom:12px; }
        .panel-header { background:#333; padding:8px 12px; border-bottom:1px solid #404040; font-weight:600; color:#47a8ff; font-size:12px; display:flex; justify-content:space-between; align-items:center; }
        .panel-body { padding:12px; }
        .module-list { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
        .module-item { display:flex; align-items:center; gap:6px; padding:6px 12px; background:#333; border-radius:3px; cursor:pointer; transition:background 0.15s; }
        .module-item:hover { background:#404040; }
        .module-item input { accent-color:#0057b3; }
        .results-table { width:100%; border-collapse:collapse; font-size:12px; }
        .results-table th { background:#333; padding:8px 10px; text-align:left; color:#47a8ff; font-weight:600; border-bottom:1px solid #404040; }
        .results-table td { padding:6px 10px; border-bottom:1px solid #333; }
        .results-table tr:hover { filter:brightness(1.3); }
        .group-0 { background:#282830; }
        .group-1 { background:#2d2d2d; }
        .status-ok { color:#21bf4b; }
        .status-fail { color:#ff6c59; }
        .summary { margin-top:12px; padding:10px; background:#333; border-radius:3px; font-size:12px; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Проверка зависимостей {{ version }}</h1>
            <div class="header-info">Проверка и установка Python пакетов</div>
        </div>
        <div class="controls">
            <button class="btn btn-primary" onclick="checkSelected()">Проверить</button>
            <button class="btn btn-success" id="installBtn" onclick="installMissing()" disabled>Установить отсутствующие</button>
        </div>
    </div>
    <div class="content">
        <div class="panel">
            <div class="panel-header">Модули для проверки</div>
            <div class="panel-body">
                <div class="module-list" id="moduleList"></div>
                <div style="margin-top:8px;">
                    <button class="btn btn-primary" onclick="selectAll(true)">Выбрать все</button>
                    <button class="btn btn-primary" onclick="selectAll(false)">Снять все</button>
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Результаты проверки</div>
            <div class="panel-body">
                <table class="results-table">
                    <thead>
                        <tr><th>Модуль</th><th>Пакет</th><th>Требуется</th><th>Установлен</th><th>Статус</th></tr>
                    </thead>
                    <tbody id="resultsBody">
                        <tr><td colspan="5" style="text-align:center;color:#999;">Нажмите "Проверить" для начала</td></tr>
                    </tbody>
                </table>
                <div class="summary" id="summary" style="display:none;"></div>
            </div>
        </div>
    </div>

    <script>
        let allRequirements = {};
        let checkResults = [];
        let missingPackages = [];

        async function loadModules() {
            try {
                const r = await fetch('/api/requirements');
                allRequirements = await r.json();
                renderModuleList();
            } catch(e) {}
        }

        function renderModuleList() {
            const list = document.getElementById('moduleList');
            let html = '';
            for (const [name, info] of Object.entries(allRequirements)) {
                const desc = info.description ? ' — ' + info.description : '';
                html += '<label class="module-item"><input type="checkbox" checked data-module="' + name + '"> ' + name + ' (' + info.packages.length + ')' + desc + '</label>';
            }
            list.innerHTML = html || '<div style="color:#999;">Нет модулей</div>';
        }

        function selectAll(checked) {
            document.querySelectorAll('#moduleList input[type="checkbox"]').forEach(cb => cb.checked = checked);
        }

        async function checkSelected() {
            const selected = [];
            document.querySelectorAll('#moduleList input[type="checkbox"]:checked').forEach(cb => {
                selected.push(cb.dataset.module);
            });
            if (selected.length === 0) { alert('Выберите хотя бы один модуль'); return; }

            document.getElementById('installBtn').disabled = true;
            const tbody = document.getElementById('resultsBody');
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#47a8ff;">Проверка...</td></tr>';

            try {
                const r = await fetch('/api/check', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({modules: selected})
                });
                checkResults = await r.json();
                renderResults();
            } catch(e) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#ff6c59;">Ошибка: ' + e.message + '</td></tr>';
            }
        }

        function renderResults() {
            const tbody = document.getElementById('resultsBody');
            missingPackages = [];
            let html = '';
            let gi = 0;
            for (const [modName, pkgs] of Object.entries(checkResults)) {
                const cls = 'group-' + (gi % 2);
                gi++;
                if (gi > 1) html += '<tr><td colspan="5" style="border-top:2px solid #47a8ff;padding:0;height:0;"></td></tr>';
                for (const pkg of pkgs) {
                    const statusClass = pkg.installed ? 'status-ok' : 'status-fail';
                    const statusText = pkg.installed ? '✓' : '✗';
                    const modLabel = pkg === pkgs[0] ? '<span style="color:#47a8ff;font-weight:600;">' + modName + '</span>' : '';
                    html += '<tr class="' + cls + '"><td>' + modLabel + '</td><td>' + pkg.name + '</td><td>' + pkg.version + '</td><td>' + (pkg.installed_version || '—') + '</td><td class="' + statusClass + '">' + statusText + '</td></tr>';
                    if (!pkg.installed) missingPackages.push(pkg.name);
                }
                html += '<tr style="height:8px;"><td colspan="5"></td></tr>';
            }
            tbody.innerHTML = html || '<tr><td colspan="5" style="text-align:center;color:#999;">Нет зависимостей</td></tr>';

            const summary = document.getElementById('summary');
            summary.style.display = 'block';
            if (missingPackages.length > 0) {
                summary.innerHTML = '<span class="status-fail">Отсутствует: ' + missingPackages.join(', ') + '</span>';
                document.getElementById('installBtn').disabled = false;
            } else {
                summary.innerHTML = '<span class="status-ok">Все зависимости установлены!</span>';
                document.getElementById('installBtn').disabled = true;
            }
        }

        async function installMissing() {
            if (missingPackages.length === 0) return;
            if (!confirm('Установить: ' + missingPackages.join(', ') + '?')) return;

            const btn = document.getElementById('installBtn');
            btn.disabled = true;
            btn.textContent = 'Установка...';

            try {
                const r = await fetch('/api/install', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({packages: missingPackages})
                });
                const result = await r.json();

                if (result.success) {
                    alert('Установка завершена успешно!');
                    checkSelected();
                } else {
                    alert('Ошибка установки:\n' + (result.error || 'Unknown error'));
                }
            } catch(e) {
                alert('Ошибка: ' + e.message);
            }

            btn.disabled = false;
            btn.textContent = 'Установить отсутствующие';
        }

        loadModules();
    </script>
</body>
</html>
"""


def cli_mode():
    print("=" * 50)
    print("  Проверка зависимостей TriGlav Shell")
    print("=" * 50)

    all_reqs = get_all_requirements()
    missing = []

    for mod_name, info in all_reqs.items():
        pkgs = info['packages']
        desc = info.get('description', '')
        print()
        print(f"  Модуль: \033[96m{mod_name}\033[0m{('  — ' + desc) if desc else ''}")
        print(f"  {'Пакет':<20} {'Требуется':<10} {'Статус'}")
        print(f"  {'-'*45}")
        for pkg in pkgs:
            installed, err = check_import(pkg['name'])
            if installed:
                try:
                    mod = importlib.import_module(PACKAGE_IMPORT_MAP.get(pkg['name'], pkg['name']))
                    ver = getattr(mod, '__version__', '?')
                    status = f"\033[92m[OK]\033[0m {ver}"
                except Exception:
                    status = f"\033[92m[OK]\033[0m"
            else:
                status = f"\033[93m[MISSING]\033[0m"
                missing.append(pkg['name'])
            print(f"  {pkg['name']:<20} {pkg['version']:<10} {status}")

    if missing:
        print()
        print(f"  Отсутствует: {', '.join(set(missing))}")
        answer = input("  Установить? (y/n): ").strip().lower()
        if answer == 'y':
            for pkg in set(missing):
                print(f"  Установка {pkg}...", end=' ', flush=True)
                ok, _ = install_package(pkg)
                print("\033[92m[OK]\033[0m" if ok else "\033[93m[FAILED]\033[0m")
    else:
        print()
        print("  \033[92mВсе зависимости установлены!\033[0m")


def web_mode(host, port):
    from flask import Flask, render_template_string, jsonify, request

    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template_string(CHECK_TEMPLATE, version=VERSION)

    @app.route('/api/requirements')
    def api_requirements():
        return jsonify(get_all_requirements())

    @app.route('/api/check', methods=['POST'])
    def api_check():
        data = request.get_json()
        selected_modules = data.get('modules', [])
        result = {}

        all_reqs = get_all_requirements()
        for mod_name in selected_modules:
            if mod_name not in all_reqs:
                continue
            pkgs = all_reqs[mod_name]['packages']
            checked = []
            for pkg in pkgs:
                installed, err = check_import(pkg['name'])
                version = ''
                if installed:
                    try:
                        mod = importlib.import_module(PACKAGE_IMPORT_MAP.get(pkg['name'], pkg['name']))
                        version = getattr(mod, '__version__', '?')
                    except Exception:
                        version = '?'
                checked.append({
                    'name': pkg['name'],
                    'version': pkg['version'],
                    'installed': installed,
                    'installed_version': version if installed else None
                })
            result[mod_name] = checked

        return jsonify(result)

    @app.route('/api/install', methods=['POST'])
    def api_install():
        data = request.get_json()
        packages = data.get('packages', [])
        if not packages:
            return jsonify({'error': 'No packages specified'}), 400

        errors = []
        for pkg in packages:
            ok, output = install_package(pkg)
            if not ok:
                errors.append(f'{pkg}: {output[:200]}')

        if errors:
            return jsonify({'success': False, 'error': '\n'.join(errors)})
        return jsonify({'success': True})

    print(f"Dependency Checker {VERSION} - http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5007)
    args = parser.parse_args()

    if len(sys.argv) <= 1 or (len(sys.argv) == 3 and sys.argv[1] == '--host'):
        cli_mode()
    else:
        web_mode(args.host, args.port)
