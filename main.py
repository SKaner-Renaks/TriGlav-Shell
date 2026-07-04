import os
import sys
import json
import time
import socket
import secrets
import subprocess
import threading
import configparser
from datetime import datetime
from functools import wraps
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
import requests as req_lib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '_data')
MODULE_DIR = os.path.join(BASE_DIR, '_module')
LANG_DIR = os.path.join(DATA_DIR, '_lang')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.cfg')
CARE_ENV_PATH = os.path.join(DATA_DIR, 'care.env')

sys.path.insert(0, DATA_DIR)

VERSION = '1.3.0'

app = Flask(__name__)

config = configparser.ConfigParser()
config.read(CONFIG_PATH, encoding='utf-8')

shell_cfg = dict(config['shell']) if 'shell' in config else {}
local_cfg = dict(config['local']) if 'local' in config else {}
ad_cfg = dict(config['ad']) if 'ad' in config else {}
enc_cfg = dict(config['encryption']) if 'encryption' in config else {}
lang_cfg = dict(config['language']) if 'language' in config else {}

app.secret_key = secrets.token_hex(32)

AUTH_MODE = shell_cfg.get('auth_mode', 'both')
ENVIRONMENT = shell_cfg.get('environment', 'production')
SHELL_PORT = int(shell_cfg.get('port', '8080'))
SHELL_HOST = shell_cfg.get('host', '0.0.0.0')

LANG_CURRENT = lang_cfg.get('current', 'ru')
_lang_cache = {}

module_order_cfg = dict(config['module_order']) if 'module_order' in config else {}
MODULE_ORDER = [m.strip() for m in module_order_cfg.get('order', '').split(',') if m.strip()]

autostart_cfg = dict(config['modules_auto_start']) if 'modules_auto_start' in config else {}
AUTOSTART_USUAL = autostart_cfg.get('usual', 'all')
AUTOSTART_SERVICE = autostart_cfg.get('service', 'all')
AUTOSTART_GAME = autostart_cfg.get('game', 'all')


def load_lang(lang_code):
    if lang_code in _lang_cache:
        return _lang_cache[lang_code]
    fallback_order = [lang_code, 'en', 'ru']
    for lc in fallback_order:
        path = os.path.join(LANG_DIR, f'{lc}.json')
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                _lang_cache[lc] = data
                return data
            except Exception:
                pass
    return {}


def tr(key):
    lang = load_lang(LANG_CURRENT)
    return lang.get(key, key)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if AUTH_MODE == 'none':
            return f(*args, **kwargs)
        if not session.get('authenticated'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def authenticate_local(username, password):
    from encrypt import load_env
    key = enc_cfg.get('key', '')
    method = enc_cfg.get('method', 'xor_base64')
    if not key:
        return False
    creds = load_env(CARE_ENV_PATH, method, key)
    stored_user = creds.get('login', local_cfg.get('login', 'admin'))
    stored_pass = creds.get('password', local_cfg.get('password', 'admin'))
    return username.lower() == stored_user.lower() and password.lower() == stored_pass.lower()


def authenticate_ad(username, password):
    try:
        from ldap3 import Server, Connection, SUBTREE, ALL
        server = Server(ad_cfg.get('server', 'ldap://192.168.88.4'),
                        port=int(ad_cfg.get('port', '389')),
                        use_ssl=ad_cfg.get('use_ssl', 'false').lower() == 'true',
                        get_info=ALL)

        if '\\' in username:
            user_dn = username
            search_user = username.split('\\')[1]
        elif '@' in username:
            user_dn = username
            search_user = username.split('@')[0]
        else:
            domain = ad_cfg.get('domain', 'DOMAIN')
            user_dn = f'{domain}\\{username}'
            search_user = username

        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        conn.search(
            search_base=ad_cfg.get('base_dn', ''),
            search_filter=f'(&(objectClass=user)(sAMAccountName={search_user}))',
            search_scope=SUBTREE,
            attributes=['memberOf']
        )

        if not conn.entries:
            conn.unbind()
            return False, 'User not found in AD'

        ad_group = ad_cfg.get('group', '')
        if ad_group:
            user = conn.entries[0]
            is_member = False
            if hasattr(user, 'memberOf'):
                for group_dn in user.memberOf.values:
                    if ad_group.lower() in group_dn.lower():
                        is_member = True
                        break
            if not is_member:
                conn.unbind()
                return False, f'Not in required group: {ad_group}'

        conn.unbind()
        return True, None
    except ImportError:
        return False, 'ldap3 not installed'
    except Exception as e:
        return False, f'AD error: {str(e)}'


def get_server_info():
    hostname = socket.gethostname()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = '127.0.0.1'
    now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    return f'{hostname} | {ip} | {now}'


def is_port_free(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result != 0
    except Exception:
        return True


def check_firewall(port):
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule',
             f'name=TriGlav Shell {port}'],
            capture_output=True, timeout=10
        )
        output = result.stdout.decode('cp866', errors='replace')
        if f'TriGlav Shell {port}' in output:
            return True
        return False
    except Exception:
        return None


def add_firewall_rule(port):
    try:
        rule_name = f'TriGlav Shell {port}'
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'add', 'rule', f'name={rule_name}',
             'dir=in', 'action=allow', 'protocol=tcp', f'localport={port}'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def find_free_port(start=5000, exclude=None):
    exclude = exclude or set()
    for port in range(start, start + 100):
        if port not in exclude and is_port_free(port):
            return port
    return start


module_processes = {}
module_ports = {}


def discover_modules():
    modules = []
    if not os.path.isdir(MODULE_DIR):
        return modules
    for name in sorted(os.listdir(MODULE_DIR)):
        mod_path = os.path.join(MODULE_DIR, name)
        manifest_path = os.path.join(mod_path, 'manifest.json')
        if os.path.isdir(mod_path) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                manifest['_path'] = mod_path
                modules.append(manifest)
            except Exception:
                pass

    if MODULE_ORDER:
        order_map = {name: i for i, name in enumerate(MODULE_ORDER)}
        modules.sort(key=lambda m: order_map.get(m['name'], 999))

    return modules


module_log_enabled = {}


def start_module(manifest):
    name = manifest['name']
    if name in module_processes and module_processes[name].poll() is None:
        return True

    mod_path = manifest['_path']
    main_py = os.path.join(mod_path, 'main.py')
    if not os.path.exists(main_py):
        return False

    port = module_ports.get(name, manifest.get('current_port', 5000))
    host = '127.0.0.1' if ENVIRONMENT == 'production' else '0.0.0.0'

    cmd = [sys.executable, main_py, '--host', host, '--port', str(port)]
    if module_log_enabled.get(name):
        cmd.append('--log')
    try:
        proc = subprocess.Popen(cmd, cwd=mod_path)
        module_processes[name] = proc
        module_ports[name] = port
        return True
    except Exception:
        return False


def stop_module(name):
    if name in module_processes:
        proc = module_processes[name]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        del module_processes[name]
        if name in module_ports:
            del module_ports[name]


def stop_all_modules():
    for name in list(module_processes.keys()):
        stop_module(name)


def check_module_health(name):
    if name not in module_ports:
        return False
    port = module_ports[name]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            return s.connect_ex(('127.0.0.1', port)) == 0
    except Exception:
        return False


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if AUTH_MODE == 'none':
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        auth_type = request.form.get('auth_type', 'local')

        if auth_type == 'ad' or AUTH_MODE == 'ad':
            ok, err = authenticate_ad(username, password)
        else:
            ok = authenticate_local(username, password)
            err = None if ok else 'Invalid credentials'

        if ok:
            session['authenticated'] = True
            session['username'] = username
            session['auth_mode'] = auth_type
            return redirect(url_for('index'))
        return render_template_string(LOGIN_TEMPLATE, error=err or 'Invalid credentials',
                                      auth_mode=AUTH_MODE, version=VERSION)

    return render_template_string(LOGIN_TEMPLATE, error=None, auth_mode=AUTH_MODE, version=VERSION)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/')
@login_required
def index():
    modules = discover_modules()
    server_info = get_server_info()
    return render_template_string(SHELL_TEMPLATE, version=VERSION, server_info=server_info,
                                  modules=modules, module_ports=module_ports, lang=tr,
                                  environment=ENVIRONMENT)


@app.route('/api/modules')
@login_required
def api_modules():
    modules = discover_modules()
    result = []
    for m in modules:
        name = m['name']
        result.append({
            'name': name,
            'title': m.get('title', name),
            'version': m.get('version', '?'),
            'description': m.get('description', ''),
            'type': m.get('type', 'usual'),
            'requires_admin': m.get('requires_admin', False),
            'port': module_ports.get(name, m.get('current_port', 0)),
            'running': check_module_health(name),
        })
    return jsonify(result)


@app.route('/api/module/<name>/start', methods=['POST'])
@login_required
def api_module_start(name):
    modules = discover_modules()
    manifest = next((m for m in modules if m['name'] == name), None)
    if not manifest:
        return jsonify({'error': 'Module not found'}), 404
    ok = start_module(manifest)
    if ok:
        time.sleep(1)
        return jsonify({'status': 'started', 'port': module_ports.get(name, 0)})
    return jsonify({'error': 'Failed to start module'}), 500


@app.route('/api/module/<name>/stop', methods=['POST'])
@login_required
def api_module_stop(name):
    stop_module(name)
    return jsonify({'status': 'stopped'})


@app.route('/api/module/<name>/restart', methods=['POST'])
@login_required
def api_module_restart(name):
    stop_module(name)
    time.sleep(1)
    modules = discover_modules()
    manifest = next((m for m in modules if m['name'] == name), None)
    if manifest:
        ok = start_module(manifest)
        if ok:
            time.sleep(1)
            return jsonify({'status': 'restarted', 'port': module_ports.get(name, 0)})
    return jsonify({'error': 'Failed to restart'}), 500


@app.route('/api/module/<name>/restart-elevated', methods=['POST'])
@login_required
def api_module_restart_elevated(name):
    stop_module(name)
    time.sleep(1)
    modules = discover_modules()
    manifest = next((m for m in modules if m['name'] == name), None)
    if not manifest:
        return jsonify({'error': 'Module not found'}), 404

    mod_path = manifest['_path']
    main_py = os.path.join(mod_path, 'main.py')
    port = module_ports.get(name, manifest.get('current_port', 5000))

    try:
        import ctypes
        cmd = f'"{sys.executable}" "{main_py}" --host 127.0.0.1 --port {port}'
        ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, f'"{main_py}" --host 127.0.0.1 --port {port}', mod_path, 1)
        time.sleep(2)
        return jsonify({'status': 'elevated', 'port': port})
    except Exception as e:
        return jsonify({'error': f'Failed to elevate: {str(e)}'}), 500


@app.route('/api/module/<name>/log', methods=['POST'])
@login_required
def api_module_log(name):
    if ENVIRONMENT != 'development':
        return jsonify({'error': 'only in development mode'}), 400
    data = request.get_json()
    enabled = data.get('enabled', False)
    module_log_enabled[name] = enabled
    stop_module(name)
    time.sleep(1)
    modules = discover_modules()
    manifest = next((m for m in modules if m['name'] == name), None)
    if manifest:
        start_module(manifest)
    return jsonify({'status': 'ok', 'log': enabled})


@app.route('/api/settings', methods=['GET'])
@login_required
def api_settings_get():
    return jsonify({
        'shell': dict(shell_cfg),
        'auth_mode': AUTH_MODE,
        'environment': ENVIRONMENT,
        'language': LANG_CURRENT,
    })


@app.route('/api/module_order', methods=['POST'])
@login_required
def api_module_order():
    data = request.get_json()
    order = data.get('order', [])
    if not order:
        return jsonify({'error': 'No order provided'}), 400

    if not config.has_section('module_order'):
        config.add_section('module_order')
    config.set('module_order', 'order', ','.join(order))
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        config.write(f)

    global MODULE_ORDER
    MODULE_ORDER = order

    return jsonify({'status': 'saved', 'order': order})


@app.route('/api/settings', methods=['POST'])
@login_required
def api_settings_set():
    global AUTH_MODE, ENVIRONMENT, LANG_CURRENT

    data = request.get_json()
    if 'auth_mode' in data:
        config.set('shell', 'auth_mode', data['auth_mode'])
        AUTH_MODE = data['auth_mode']
    if 'environment' in data:
        config.set('shell', 'environment', data['environment'])
        ENVIRONMENT = data['environment']
    if 'language' in data:
        config.set('language', 'current', data['language'])
        LANG_CURRENT = data['language']
        _lang_cache.clear()
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        config.write(f)
    return jsonify({'status': 'saved'})


@app.route('/api/settings/reset', methods=['POST'])
@login_required
def api_settings_reset():
    data = request.get_json()
    target = data.get('target', 'console')
    if target == 'console':
        defaults = {
            'shell': {'port': '8080', 'host': '0.0.0.0', 'auth_mode': 'both', 'environment': 'production',
                      'global_refresh_interval': '15', 'global_theme': 'dark', 'allowed_ips': '*'},
            'local': {'login': 'admin', 'password': 'admin'},
            'language': {'current': 'ru'},
        }
        for section, values in defaults.items():
            if not config.has_section(section):
                config.add_section(section)
            for k, v in values.items():
                config.set(section, k, v)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            config.write(f)
        return jsonify({'status': 'reset'})
    elif target == 'module':
        modules = discover_modules()
        for m in modules:
            manifest_path = os.path.join(m['_path'], 'manifest.json')
            if 'default_settings' in m:
                m['current_settings'] = m['default_settings'].copy()
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump({k: v for k, v in m.items() if k != '_path'}, f, indent=2, ensure_ascii=False)
        return jsonify({'status': 'reset'})
    return jsonify({'error': 'Unknown target'}), 400


@app.route('/api/stop', methods=['POST'])
@login_required
def api_stop():
    def shutdown():
        stop_all_modules()
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=shutdown, daemon=True).start()
    return jsonify({'status': 'stopping'})


@app.route('/api/restart', methods=['POST'])
@login_required
def api_restart():
    def restart():
        stop_all_modules()
        time.sleep(1)
        subprocess.Popen([sys.executable] + sys.argv, cwd=os.getcwd())
        os._exit(0)
    threading.Thread(target=restart, daemon=True).start()
    return jsonify({'status': 'restarting'})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': VERSION})


@app.route('/proxy/<int:port>/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/proxy/<int:port>/<path:path>', methods=['GET', 'POST'])
def proxy(port, path):
    url = f'http://127.0.0.1:{port}/{path}'
    if request.query_string:
        url += '?' + request.query_string.decode()

    headers = {k: v for k, v in request.headers if k.lower() not in ('host', 'content-length')}

    try:
        noproxy = {'http': None, 'https': None}
        if request.method == 'POST':
            resp = req_lib.post(url, data=request.get_data(), headers=headers, timeout=30, proxies=noproxy)
        else:
            resp = req_lib.get(url, headers=headers, timeout=30, proxies=noproxy)

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded_headers]

        content = resp.content
        content_type = resp.headers.get('content-type', '')

        if 'text/html' in content_type:
            prefix = f'/proxy/{port}/'.encode()
            content = content.replace(b"fetch('/api/", b"fetch('" + prefix + b"api/")
            content = content.replace(b'fetch("/api/', b'fetch("' + prefix + b'api/')
            content = content.replace(b"src='/", b"src='" + prefix)
            content = content.replace(b'src="/', b'src="' + prefix)
            content = content.replace(b"href='/", b"href='" + prefix)
            content = content.replace(b'href="/', b'href="' + prefix)
            content = content.replace(b'action="/', b'action="' + prefix)

        return content, resp.status_code, response_headers
    except Exception as e:
        return jsonify({'error': str(e)}), 502




@app.route('/api/module/<name>/open-folder', methods=['POST'])
@login_required
def api_module_open_folder(name):
    modules = discover_modules()
    manifest = next((m for m in modules if m['name'] == name), None)
    if not manifest:
        return jsonify({'error': 'Module not found'}), 404
    mod_path = manifest.get('_path', '')
    if not mod_path or not os.path.isdir(mod_path):
        return jsonify({'error': 'Folder not found'}), 404
    try:
        os.startfile(mod_path)
        return jsonify({'status': 'ok', 'path': mod_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/module/<name>/log-file', methods=['GET'])
@login_required
def api_module_log_file(name):
    if ENVIRONMENT != 'development':
        return jsonify({'error': 'only in development mode'}), 400
    mod_path = os.path.join(MODULE_DIR, name)
    log_path = os.path.join(mod_path, 'module.log')
    if not os.path.exists(log_path):
        return jsonify({'error': 'Log file not found', 'path': log_path}), 404
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({'status': 'ok', 'content': content, 'path': log_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/_images/<path:filename>')
def serve_image(filename):
    from flask import send_from_directory
    images_dir = os.path.join(DATA_DIR, '_images')
    return send_from_directory(images_dir, filename)


LOGIN_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Login - TriGlav Shell</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; background:#1a1a1a; color:#f2f2f2; min-height:100vh; display:flex; justify-content:center; align-items:center; }
        .login-box { background:#262626; border:1px solid #404040; border-radius:4px; padding:30px; width:360px; }
        .login-box h2 { color:#47a8ff; font-size:18px; margin-bottom:6px; text-align:center; }
        .login-box .subtitle { color:#666; font-size:11px; text-align:center; margin-bottom:20px; }
        .tabs { display:flex; gap:0; margin-bottom:16px; }
        .tab { flex:1; padding:8px; text-align:center; background:#333; border:1px solid #404040; cursor:pointer; font-size:12px; color:#999; }
        .tab:first-child { border-radius:3px 0 0 3px; }
        .tab:last-child { border-radius:0 3px 3px 0; }
        .tab.active { background:#0057b3; color:#f2f2f2; border-color:#0057b3; }
        .form-row { margin-bottom:14px; }
        .form-row label { display:block; font-size:12px; color:#999; margin-bottom:4px; }
        .form-row input { width:100%; padding:8px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:13px; font-family:inherit; }
        .form-row input:focus { outline:none; border-color:#0057b3; }
        .btn { width:100%; padding:8px; background:#0057b3; color:#f2f2f2; border:none; border-radius:3px; font-size:13px; font-family:inherit; cursor:pointer; margin-top:6px; }
        .btn:hover { background:#0073d9; }
        .error-msg { color:#ff6c59; font-size:12px; margin-bottom:10px; text-align:center; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>TriGlav Shell {{ version }}</h2>
        <div class="subtitle">Server Management Console</div>
        {% if auth_mode == 'both' %}
        <div class="tabs">
            <div class="tab active" onclick="switchTab('local')">Local</div>
            <div class="tab" onclick="switchTab('ad')">Active Directory</div>
        </div>
        {% endif %}
        {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
        <form method="post" id="loginForm">
            <input type="hidden" name="auth_type" id="authType" value="local">
            <div class="form-row"><label>Login</label><input type="text" name="username" autofocus></div>
            <div class="form-row"><label>Password</label><input type="password" name="password"></div>
            <button type="submit" class="btn">Login</button>
        </form>
    </div>
    <script>
        function switchTab(type) {
            document.getElementById('authType').value = type;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
"""


SHELL_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>TriGlav Shell {{ version }}</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; background:#1a1a1a; color:#f2f2f2; height:100vh; display:flex; flex-direction:column; overflow:hidden; }

        .top-bar { background:#262626; border-bottom:1px solid #404040; padding:10px 20px; display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }
        .top-bar h1 { font-size:18px; font-weight:600; color:#47a8ff; }
        .top-bar-info { font-size:12px; color:#999; }
        .top-bar-controls { display:flex; gap:8px; align-items:center; }
        .btn { padding:6px 14px; border:1px solid #595959; border-radius:3px; cursor:pointer; font-size:12px; font-family:inherit; transition:background 0.15s; }
        .btn-primary { background:#0057b3; color:#f2f2f2; border-color:#0057b3; }
        .btn-primary:hover { background:#0073d9; }
        .btn-default { background:#404040; color:#f2f2f2; }
        .btn-default:hover { background:#595959; }
        .btn-danger { background:#4d1a1a; color:#ff6c59; border-color:#ff6c59; }
        .btn-danger:hover { background:#ff6c59; color:#fff; }
        .btn-sm { padding:3px 8px; font-size:11px; }

        .workspace { display:flex; flex:1; overflow:hidden; }

        #sidebar { width:200px; min-width:120px; max-width:400px; background:#222; border-right:1px solid #404040; display:flex; flex-direction:column; user-select:none; }
        #sidebar h3 { padding:14px 16px 10px; font-size:13px; color:#47a8ff; border-bottom:1px solid #333; text-transform:uppercase; letter-spacing:1px; }
        #module-list { flex:1; padding:6px 0; overflow-y:auto; }
        .module-btn { display:block; width:100%; padding:10px 16px; background:none; border:none; color:#ccc; font-size:13px; text-align:left; cursor:pointer; font-family:inherit; transition:background .15s, color .15s; border-left:3px solid transparent; }
        .module-btn:hover { background:#2d2d2d; color:#fff; }
        .module-btn.active { background:#0057b3; color:#fff; border-left-color:#47a8ff; }
        .module-btn .desc { display:block; font-size:10px; color:#888; margin-top:2px; }
        .module-btn.active .desc { color:#aad4ff; }
        .module-btn.service:hover { background:#2d2520; }
        .module-btn.service.active { border-left-color:#ff9800; background:#2d2520; }
        .module-btn.service.active .desc { color:#cc7a00; }
        .module-btn.game:hover { background:#1a2a15; }
        .module-btn.game.active { border-left-color:#8bc34a; background:#1a2a15; }
        .module-btn.game.active .desc { color:#7cb342; }
        .module-btn .status { display:inline-block; width:6px; height:6px; border-radius:50%; margin-right:6px; }
        .status-running { background:#21bf4b; }
        .status-stopped { background:#ff6c59; }

        .module-btn.dragging { opacity:0.5; background:#0057b3; }
        .module-btn.drag-over { border-top:2px solid #47a8ff; }

        #divider { width:5px; cursor:col-resize; background:#333; transition:background .15s; flex-shrink:0; }
        #divider:hover, #divider.dragging { background:#0057b3; }

        #content { flex:1; display:flex; flex-direction:column; min-width:0; }
        #content-header { padding:8px 16px; background:#262626; border-bottom:1px solid #333; font-size:12px; color:#999; display:flex; align-items:center; gap:12px; }
        #content-header .port { color:#47a8ff; }
        #module-frame { flex:1; border:none; width:100%; height:100%; background:#1a1a1a; }
        #placeholder { flex:1; display:flex; justify-content:center; align-items:center; color:#555; font-size:14px; }

        .settings-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100; justify-content:center; align-items:center; }
        .settings-overlay.active { display:flex; }
        .settings-panel { background:#262626; border:1px solid #404040; border-radius:4px; width:500px; max-height:80vh; overflow:hidden; }
        .settings-header { background:#333; padding:10px 14px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #404040; }
        .settings-header h3 { color:#47a8ff; font-size:14px; }
        .settings-body { padding:14px; max-height:60vh; overflow-y:auto; }
        .settings-row { margin-bottom:12px; }
        .settings-row label { display:block; font-size:12px; color:#999; margin-bottom:4px; }
        .settings-row select, .settings-row input { width:100%; padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; font-family:inherit; }
        .spinner { display:inline-block; width:30px; height:30px; border:3px solid #404040; border-top-color:#47a8ff; border-radius:50%; animation:spin 0.7s linear infinite; }
        @keyframes spin { to { transform:rotate(360deg); } }
    </style>
</head>
<body>
    <div class="top-bar">
        <div>
            <h1>TriGlav Shell {{ version }}</h1>
            <div class="top-bar-info">{{ server_info }}</div>
        </div>
        <div class="top-bar-controls">
            <span id="headerTime" style="font-size:18px;color:#47a8ff;font-weight:600;margin-right:12px;"></span>
            <button class="btn btn-default" onclick="openSettings()" title="Settings"><img src="/_images/gear-svgrepo-com.svg" style="width:16px;height:16px;vertical-align:middle;filter:invert(1);"></button>
            <a href="/logout" class="btn btn-default" style="text-decoration:none;text-align:center;">Logout</a>
            {% if environment == 'development' %}
            <button class="btn btn-default" onclick="restartShell()">Restart</button>
            {% endif %}
            <button class="btn btn-danger" onclick="shutdownShell()">Shutdown</button>
        </div>
    </div>

    <div class="workspace">
        <div id="sidebar">
            <h3>Modules</h3>
            <div id="module-list"></div>
        </div>
        <div id="divider"></div>
        <div id="content">
            <div id="content-header" style="display:none;">
                <span id="module-name"></span>
                <span class="port" id="module-port"></span>
                {% if environment == 'development' %}<span id="module-info" style="font-size:13px;color:#999;margin-left:12px;"></span>{% endif %}
                <button class="btn btn-sm btn-default" onclick="restartModule()">Restart</button>
                {% if environment == 'development' %}
                <a id="module-web-link" href="#" target="_blank" class="btn btn-sm btn-default" style="text-decoration:none;display:none;">Web</a>
                <button id="module-folder-btn" class="btn btn-sm btn-default" onclick="openFolder()" style="display:none;">Folder</button>
                <label style="font-size:11px;color:#999;margin-left:8px;cursor:pointer;">
                    <input type="checkbox" id="logToggle" onchange="toggleLog()" style="accent-color:#0057b3;"> Log
                </label>
                <button class="btn btn-sm btn-default" onclick="openLog()">Log File</button>
                {% endif %}
            </div>
            <iframe id="module-frame" style="display:none;"></iframe>
            <div id="placeholder">Select a module</div>
        </div>
    </div>

    <div class="settings-overlay" id="settingsOverlay">
        <div class="settings-panel">
            <div class="settings-header">
                <h3>Settings</h3>
                <button class="modal-close" onclick="closeSettings()" style="background:none;border:none;color:#999;font-size:20px;cursor:pointer;">&times;</button>
            </div>
            <div class="settings-body">
                <div class="settings-row">
                    <label>Auth Mode</label>
                    <select id="setAuthMode">
                        <option value="local">Local</option>
                        <option value="ad">Active Directory</option>
                        <option value="both">Both</option>
                        <option value="none">None</option>
                    </select>
                </div>
                <div class="settings-row">
                    <label>Environment</label>
                    <select id="setEnvironment">
                        <option value="production">Production</option>
                        <option value="development">Development</option>
                    </select>
                </div>
                <div class="settings-row">
                    <label>Language</label>
                    <select id="setLanguage">
                        <option value="ru">Русский</option>
                        <option value="en">English</option>
                    </select>
                </div>
                <div style="display:flex;gap:8px;margin-top:16px;">
                    <button class="btn btn-primary" onclick="saveSettings()">Save</button>
                    <button class="btn btn-default" onclick="resetSettings('console')">Reset Console</button>
                    <button class="btn btn-default" onclick="resetSettings('module')">Reset Modules</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentModule = null;
        let modules = [];
        let divider = document.getElementById('divider');
        let sidebar = document.getElementById('sidebar');
        let dragging = false;

        async function loadModules() {
            try {
                const r = await fetch('/api/modules');
                modules = await r.json();
                renderModuleList();
            } catch(e) {}
        }

        function renderModuleList() {
            let html = '';
            modules.forEach(m => {
                const statusClass = m.running ? 'status-running' : 'status-stopped';
                const activeClass = currentModule === m.name ? 'active' : '';
                const typeClass = m.type === 'service' ? ' service' : m.type === 'game' ? ' game' : '';
                html += '<button class="module-btn ' + activeClass + typeClass + '" data-name="' + m.name + '" data-port="' + m.port + '" draggable="true" onclick="selectModule(\'' + m.name + '\')">'
                    + '<span class="status ' + statusClass + '"></span>' + m.title
                    + '<span class="desc">' + m.description + '</span></button>';
            });
            document.getElementById('module-list').innerHTML = html || '<div style="padding:16px;color:#666;font-size:12px;">No modules found</div>';
            initDragDrop();
        }

        function selectModule(name) {
            const mod = modules.find(m => m.name === name);
            if (!mod) return;
            currentModule = name;
            renderModuleList();
            
            // Update module info
            const infoEl = document.getElementById('module-info');
            if (infoEl) {
                const adminTag = mod.requires_admin ? ' | Admin' : '';
                infoEl.textContent = mod.name + ' [' + mod.type + adminTag + ']';
            }
            // Show folder button only on localhost
            const folderBtn = document.getElementById('module-folder-btn');
            if (folderBtn) {
                const isLocal = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
                folderBtn.style.display = isLocal ? 'inline-block' : 'none';
            }
            
            // Update Web link (development mode only)
            const webLink = document.getElementById('module-web-link');
            if (webLink) {
                if (mod.running && mod.port) {
                    webLink.href = 'http://127.0.0.1:' + mod.port + '/';
                    webLink.style.display = 'inline-block';
                } else {
                    webLink.style.display = 'none';
                }
            }
            
            if (mod.running && mod.port) {
                document.getElementById('content-header').style.display = 'flex';
                document.getElementById('module-name').textContent = mod.title;
                document.getElementById('module-port').textContent = ':' + mod.port;
                document.getElementById('module-frame').src = '/proxy/' + mod.port + '/';
                document.getElementById('module-frame').style.display = 'block';
                document.getElementById('placeholder').style.display = 'none';
            } else {
                document.getElementById('content-header').style.display = 'flex';
                document.getElementById('module-name').textContent = mod.title;
                document.getElementById('module-port').textContent = 'not running';
                document.getElementById('module-frame').style.display = 'none';
                document.getElementById('placeholder').style.display = 'flex';
                document.getElementById('placeholder').innerHTML = '<div style="text-align:center;"><div style="margin-bottom:12px;">Module not running</div><button class="btn btn-primary" onclick="startModule(\'' + name + '\')">Start Module</button></div>';
            }
        }

        async function startModule(name) {
            document.getElementById('placeholder').innerHTML = '<div style="text-align:center;"><div class="spinner" style="margin:0 auto 12px;"></div>Starting...</div>';
            try {
                const r = await fetch('/api/module/' + name + '/start', { method: 'POST' });
                const d = await r.json();
                if (d.status === 'started') {
                    setTimeout(() => selectModule(name), 1500);
                } else {
                    document.getElementById('placeholder').innerHTML = '<div style="text-align:center;color:#ff6c59;">Failed to start: ' + (d.error || 'Unknown error') + '</div>';
                }
            } catch(e) {
                document.getElementById('placeholder').innerHTML = '<div style="text-align:center;color:#ff6c59;">Error: ' + e.message + '</div>';
            }
        }

        async function restartModule() {
            if (!currentModule) return;
            const frame = document.getElementById('module-frame');
            const header = document.getElementById('content-header');
            const placeholder = document.getElementById('placeholder');

            frame.style.display = 'none';
            placeholder.style.display = 'flex';
            placeholder.innerHTML = '<div style="text-align:center;"><div class="spinner"></div><div style="margin-top:12px;color:#47a8ff;">РџРµСЂРµР·Р°РїСѓСЃРє РјРѕРґСѓР»СЏ...</div></div>';

            try {
                await fetch('/api/module/' + currentModule + '/restart', { method: 'POST' });
                setTimeout(() => selectModule(currentModule), 2000);
                loadModules();
            } catch(e) {
                placeholder.innerHTML = '<div style="text-align:center;color:#ff6c59;">РћС€РёР±РєР° РїРµСЂРµР·Р°РїСѓСЃРєР°</div>';
            }
        }

        async function shutdownShell() {
            if (!confirm('Shutdown Shell and all modules?')) return;
            try {
                await fetch('/api/stop', { method: 'POST' });
                document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;color:#47a8ff;font-size:24px;">Shell stopped</div>';
            } catch(e) {}
        }

        async function restartShell() {
            if (!confirm('Restart Shell and all modules?')) return;
            try {
                await fetch('/api/restart', { method: 'POST' });
                document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;color:#47a8ff;font-size:24px;">Restarting Shell...</div>';
                setTimeout(() => location.reload(), 5000);
            } catch(e) {}
        }

        async function toggleLog() {
            if (!currentModule) return;
            const enabled = document.getElementById('logToggle').checked;
            try {
                await fetch('/api/module/' + currentModule + '/log', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({enabled: enabled})
                });
            } catch(e) {}
        }

        divider.addEventListener('mousedown', function(e) {
            dragging = true;
            divider.classList.add('dragging');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            let w = e.clientX;
            if (w < 120) w = 120;
            if (w > 600) w = 600;
            sidebar.style.width = w + 'px';
            localStorage.setItem('shell_sidebar_width', w);
            const frame = document.getElementById('module-frame');
            if (frame && frame.contentWindow) {
                frame.contentWindow.postMessage('resize', '*');
            }
        });

        document.addEventListener('mouseup', function() {
            if (dragging) {
                dragging = false;
                divider.classList.remove('dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });

        function updateClock() {
            const now = new Date();
            const hh = String(now.getHours()).padStart(2, '0');
            const mm = String(now.getMinutes()).padStart(2, '0');
            document.getElementById('headerTime').textContent = hh + ':' + mm;
        }

        async function openSettings() {
            try {
                const r = await fetch('/api/settings');
                const d = await r.json();
                document.getElementById('setAuthMode').value = d.auth_mode || 'both';
                document.getElementById('setEnvironment').value = d.environment || 'production';
                document.getElementById('setLanguage').value = d.language || 'ru';
            } catch(e) {}
            document.getElementById('settingsOverlay').classList.add('active');
        }

        function closeSettings() { document.getElementById('settingsOverlay').classList.remove('active'); }

        async function saveSettings() {
            const data = {
                auth_mode: document.getElementById('setAuthMode').value,
                environment: document.getElementById('setEnvironment').value,
                language: document.getElementById('setLanguage').value,
            };
            try {
                await fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
                if (confirm('Settings saved. Reload page to apply?')) location.reload();
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function resetSettings(target) {
            if (!confirm('Reset ' + target + ' settings to defaults?')) return;
            try {
                await fetch('/api/settings/reset', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({target:target}) });
                if (target === 'console') { location.reload(); }
                else { loadModules(); }
            } catch(e) { alert('Error: ' + e.message); }
        }

        let draggedItem = null;

        function initDragDrop() {
            const items = document.querySelectorAll('.module-btn');
            items.forEach(item => {
                item.addEventListener('dragstart', handleDragStart);
                item.addEventListener('dragend', handleDragEnd);
                item.addEventListener('dragover', handleDragOver);
                item.addEventListener('dragenter', handleDragEnter);
                item.addEventListener('dragleave', handleDragLeave);
                item.addEventListener('drop', handleDrop);
            });
        }

        function handleDragStart(e) {
            draggedItem = this;
            this.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', this.dataset.name);
        }

        function handleDragEnd(e) {
            this.classList.remove('dragging');
            document.querySelectorAll('.module-btn').forEach(item => {
                item.classList.remove('drag-over');
            });
            draggedItem = null;
        }

        function handleDragOver(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        }

        function handleDragEnter(e) {
            e.preventDefault();
            if (this !== draggedItem) {
                this.classList.add('drag-over');
            }
        }

        function handleDragLeave(e) {
            this.classList.remove('drag-over');
        }

        function handleDrop(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');

            if (draggedItem === this) return;

            const draggedName = draggedItem.dataset.name;
            const targetName = this.dataset.name;

            const draggedIndex = modules.findIndex(m => m.name === draggedName);
            const targetIndex = modules.findIndex(m => m.name === targetName);

            if (draggedIndex === -1 || targetIndex === -1) return;

            const [removed] = modules.splice(draggedIndex, 1);
            modules.splice(targetIndex, 0, removed);

            renderModuleList();
            saveModuleOrder();
        }

        async function saveModuleOrder() {
            const order = modules.map(m => m.name);
            try {
                await fetch('/api/module_order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({order: order})
                });
            } catch(e) { console.error('Failed to save order:', e); }
        }

        const savedWidth = localStorage.getItem('shell_sidebar_width');
        if (savedWidth) sidebar.style.width = savedWidth + 'px';

        loadModules();
        updateClock();
        setInterval(updateClock, 60000);
        setInterval(loadModules, 10000);

                async function openFolder() {
            if (!currentModule) return;
            try {
                const r = await fetch('/api/module/' + currentModule + '/open-folder', { method: 'POST' });
                const d = await r.json();
                if (d.status !== 'ok') {
                    alert(d.error || 'Failed to open folder');
                }
            } catch(e) {
                alert('Error: ' + e.message);
            }
        }

        async function openLog() {
            if (!currentModule) return;
            try {
                const r = await fetch('/api/module/' + currentModule + '/log-file');
                const d = await r.json();
                if (d.status === 'ok') {
                    const logWindow = window.open('', '_blank', 'width=800,height=600');
                    logWindow.document.write('<html><head><title>Log: ' + currentModule + '</title><style>body{background:#1a1a1a;color:#f2f2f2;font-family:monospace;font-size:12px;padding:16px;white-space:pre-wrap;word-wrap:break-word;}</style></head><body>' + d.content.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</body></html>');
                } else {
                    alert(d.error || 'Log file not found');
                }
            } catch(e) {
                alert('Error: ' + e.message);
            }
        }


        window.addEventListener('message', async function(event) {
            const data = event.data;
            if (data && data.action === 'restart-shell') {
                try {
                    await fetch('/api/restart', { method: 'POST' });
                    document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;color:#47a8ff;font-size:24px;">РџРµСЂРµР·Р°РїСѓСЃРє Shell...</div>';
                    setTimeout(() => location.reload(), 5000);
                } catch(e) {}
            } else if (data && data.action === 'restart-elevated' && data.module) {
                if (confirm('Restart ' + data.module + ' with Administrator rights?')) {
                    try {
                        const r = await fetch('/api/module/' + data.module + '/restart-elevated', { method: 'POST' });
                        const d = await r.json();
                        if (d.status === 'elevated') {
                            setTimeout(() => selectModule(data.module), 2000);
                            loadModules();
                        } else {
                            alert('Error: ' + (d.error || 'Failed to elevate'));
                        }
                    } catch(e) { alert('Error: ' + e.message); }
                }
            }
        });
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    from encrypt import load_env, save_env, generate_key

    key = enc_cfg.get('key', '')
    method = enc_cfg.get('method', 'xor_base64')
    if not key:
        key = generate_key()
        if not config.has_section('encryption'):
            config.add_section('encryption')
        config.set('encryption', 'key', key)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            config.write(f)

    if not os.path.exists(CARE_ENV_PATH):
        save_env(CARE_ENV_PATH, {'login': 'admin', 'password': 'admin'}, method, key)

    modules = discover_modules()
    allocated_ports = set()

    print("\n  Allocating ports...")
    for m in modules:
        name = m['name']
        manifest_port = m.get('current_port', 5000)
        if ENVIRONMENT == 'production':
            if manifest_port not in allocated_ports and is_port_free(manifest_port):
                port = manifest_port
            else:
                port = find_free_port(start=5000, exclude=allocated_ports)
        else:
            port = manifest_port
        module_ports[name] = port
        allocated_ports.add(port)
        manifest_path = os.path.join(m['_path'], 'manifest.json')
        m['current_port'] = port
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump({k: v for k, v in m.items() if k != '_path'}, f, indent=2, ensure_ascii=False)
        print(f"    {m.get('title', name):25s} -> :{port}")

    def should_autostart(name, mod_type):
        if mod_type == 'service':
            allowed = AUTOSTART_SERVICE
        elif mod_type == 'game':
            allowed = AUTOSTART_GAME
        else:
            allowed = AUTOSTART_USUAL
        if allowed.lower() == 'all':
            return True
        return name in [x.strip() for x in allowed.split(',')]

    to_start = [m for m in modules if should_autostart(m['name'], m.get('type', 'usual'))]

    print("\n  Starting modules...")
    total = len(to_start)
    for i, m in enumerate(to_start, 1):
        name = m.get('title', m['name'])
        print(f"    [{i}/{total}] {name}...", end=' ', flush=True)
        ok = start_module(m)
        print("OK" if ok else "FAILED")
        time.sleep(0.5)
        if i < total:
            print()

    print("\n" + "=" * 50)
    print(f"  TriGlav Shell {VERSION}")
    print(f"  http://{SHELL_HOST}:{SHELL_PORT}")
    print(f"  Modules: {len(to_start)}/{len(modules)} (auto-started)")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    if SHELL_HOST == '0.0.0.0':
        fw_status = check_firewall(SHELL_PORT)
        if fw_status is False:
            MAGENTA = '\033[95m'
            YELLOW = '\033[93m'
            WHITE = '\033[97m'
            CYAN = '\033[96m'
            BOLD = '\033[1m'
            RESET = '\033[0m'
            print()
            print(f"  {MAGENTA}{BOLD}FIREWALL:{RESET} port {WHITE}{BOLD}{SHELL_PORT}{RESET} is NOT open!")
            print(f"  {YELLOW}Remote access will be blocked.{RESET}")
            print(f"  {YELLOW}Run as Administrator{RESET} and execute:")
            print(f"  {CYAN}{BOLD}netsh advfirewall firewall add rule name=\"TriGlav Shell {SHELL_PORT}\" dir=in action=allow protocol=tcp localport={SHELL_PORT}{RESET}")
            print()
        elif fw_status is None:
            print(f"\n  [i] Could not check firewall status")

    app.run(host=SHELL_HOST, port=SHELL_PORT, debug=False)


