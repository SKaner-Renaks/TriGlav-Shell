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
import fnmatch
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, send_file

VERSION = '1.4.9'

app = Flask(__name__)

parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=5002)
parser.add_argument('--environment', default='production', choices=['production', 'development'])
parser.add_argument('--log', action='store_true')
args = parser.parse_args()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
REPO_URL = 'https://github.com/SKaner-Renaks/TriGlav-Shell'
ARCHIVE_URL = 'https://github.com/SKaner-Renaks/TriGlav-Shell/archive/refs/heads/main.zip'
SVG_BACKUP_ICON = '<svg xmlns="http://www.w3.org/2000/svg" height="100%" viewBox="0 -960 960 960" width="100%" fill="currentColor"><path d="M250-160q-86 0-148-62T40-370q0-78 49.5-137.5T217-579q20-97 94-158.5T482-799q113 0 189.5 81.5T748-522v24q72-2 122 46.5T920-329q0 69-50 119t-119 50H510q-24 0-42-18t-18-42v-258l-83 83-43-43 156-156 156 156-43 43-83-83v258h241q45 0 77-32t32-77q0-45-32-77t-77-32h-63v-84q0-89-60.5-153T478-739q-89 0-150 64t-61 153h-19q-62 0-105 43.5T100-371q0 62 43.93 106.5T250-220h140v60H250Zm230-290Z"/></svg>'
SVG_GEAR_ICON = '<svg fill="currentColor" width="100%" height="100%" viewBox="0 0 32 32" version="1.1" xmlns="http://www.w3.org/2000/svg"> <title>gear</title> <path d="M29 11.756h-1.526c-0.109-0.295-0.229-0.584-0.361-0.87l1.087-1.076c0.441-0.389 0.717-0.956 0.717-1.587 0-0.545-0.206-1.042-0.545-1.417l0.002 0.002-3.178-3.178c-0.373-0.338-0.87-0.544-1.415-0.544-0.632 0-1.199 0.278-1.587 0.718l-0.002 0.002-1.081 1.080c-0.285-0.131-0.573-0.251-0.868-0.36l0.008-1.526c0.003-0.042 0.005-0.091 0.005-0.141 0-1.128-0.884-2.049-1.997-2.109l-0.005-0h-4.496c-1.119 0.059-2.004 0.981-2.004 2.11 0 0.049 0.002 0.098 0.005 0.147l-0-0.007v1.524c-0.295 0.109-0.584 0.229-0.87 0.361l-1.074-1.084c-0.389-0.443-0.957-0.722-1.589-0.722-0.545 0-1.042 0.206-1.416 0.545l0.002-0.002-3.179 3.179c-0.338 0.373-0.544 0.87-0.544 1.415 0 0.633 0.278 1.2 0.719 1.587l0.002 0.002 1.078 1.079c-0.132 0.287-0.252 0.576-0.362 0.872l-1.525-0.007c-0.042-0.003-0.091-0.005-0.14-0.005-1.128 0-2.050 0.885-2.11 1.998l-0 0.005v4.495c0.059 1.119 0.982 2.005 2.111 2.005 0.049 0 0.098-0.002 0.146-0.005l-0.007 0h1.525c0.109 0.295 0.229 0.584 0.361 0.87l-1.084 1.071c-0.443 0.39-0.721 0.958-0.721 1.592 0 0.545 0.206 1.043 0.545 1.418l-0.002-0.002 3.179 3.178c0.339 0.337 0.806 0.545 1.322 0.545 0.007 0 0.014-0 0.021-0h-0.001c0.653-0.013 1.24-0.287 1.662-0.722l0.001-0.001 1.079-1.079c0.287 0.132 0.577 0.252 0.873 0.362l-0.007 1.524c-0.003 0.042-0.005 0.091-0.005 0.14 0 1.128 0.885 2.050 1.998 2.11l0.005 0h4.496c1.118-0.060 2.003-0.981 2.003-2.109 0-0.050-0.002-0.099-0.005-0.147l0 0.007v-1.526c0.296-0.11 0.585-0.23 0.872-0.362l1.069 1.079c0.423 0.435 1.009 0.709 1.66 0.723l0.002 0h0.002c0.006 0 0.014 0 0.021 0 0.515 0 0.982-0.207 1.323-0.541l3.177-3.177c0.335-0.339 0.541-0.805 0.541-1.32 0-0.009-0-0.018-0-0.028l0 0.001c-0.013-0.651-0.285-1.236-0.718-1.658l-0.001-0-1.080-1.081c0.131-0.285 0.251-0.573 0.36-0.868l1.525 0.007c0.042 0.003 0.090 0.005 0.139 0.005 1.129 0 2.051-0.885 2.11-1.999l0-0.005v-4.495c-0.060-1.119-0.981-2.004-2.11-2.004-0.049 0-0.098 0.002-0.147 0.005l0.007-0zM28.75 17.749l-2.162-0.011c-0.026 0-0.048 0.013-0.074 0.015-0.093 0.009-0.179 0.026-0.261 0.053l0.008-0.002c-0.31 0.068-0.565 0.263-0.711 0.527l-0.003 0.005c-0.048 0.071-0.091 0.152-0.124 0.238l-0.003 0.008c-0.008 0.024-0.027 0.041-0.034 0.066-0.23 0.804-0.527 1.503-0.898 2.155l0.025-0.048c-0.014 0.025-0.013 0.054-0.026 0.080-0.029 0.063-0.053 0.138-0.071 0.215l-0.001 0.008c-0.023 0.072-0.040 0.156-0.048 0.242l-0 0.005c-0.002 0.027-0.004 0.058-0.004 0.089 0 0.209 0.061 0.404 0.166 0.568l-0.003-0.004c0.045 0.088 0.096 0.163 0.154 0.232l-0.001-0.002c0.017 0.019 0.022 0.043 0.040 0.061l1.529 1.531-2.469 2.467-1.516-1.529c-0.020-0.021-0.048-0.027-0.069-0.046-0.060-0.050-0.128-0.096-0.2-0.135l-0.006-0.003c-0.195-0.109-0.429-0.173-0.677-0.173-0.002 0-0.004 0-0.006 0h0c-0.076 0.008-0.145 0.022-0.211 0.040l0.009-0.002c-0.102 0.020-0.192 0.050-0.276 0.089l0.007-0.003c-0.022 0.011-0.047 0.010-0.069 0.022-0.606 0.346-1.307 0.644-2.043 0.859l-0.070 0.017c-0.027 0.008-0.045 0.027-0.071 0.037-0.084 0.033-0.157 0.071-0.224 0.116l0.004-0.003c-0.075 0.041-0.139 0.085-0.199 0.135l0.002-0.002c-0.053 0.052-0.102 0.11-0.145 0.171l-0.003 0.004c-0.103 0.113-0.176 0.254-0.206 0.411l-0.001 0.005c-0.024 0.074-0.043 0.16-0.051 0.249l-0 0.005c-0.002 0.026-0.015 0.048-0.015 0.075l-0.001 2.162h-3.491l0.011-2.156c0-0.028-0.014-0.052-0.016-0.079-0.008-0.092-0.026-0.177-0.052-0.258l0.002 0.008c-0.068-0.313-0.265-0.57-0.531-0.717l-0.006-0.003c-0.070-0.047-0.15-0.089-0.235-0.122l-0.008-0.003c-0.024-0.008-0.042-0.027-0.067-0.034-0.806-0.23-1.507-0.528-2.161-0.9l0.048 0.025c-0.023-0.013-0.050-0.012-0.073-0.023-0.072-0.033-0.156-0.061-0.244-0.079l-0.008-0.001c-0.092-0.029-0.198-0.045-0.308-0.045-0.221 0-0.426 0.066-0.597 0.18l0.004-0.002c-0.076 0.040-0.141 0.084-0.201 0.134l0.002-0.002c-0.021 0.019-0.048 0.025-0.068 0.045l-1.529 1.529-2.47-2.469 1.532-1.516c0.020-0.020 0.027-0.047 0.045-0.067 0.053-0.063 0.101-0.134 0.142-0.209l0.003-0.006c0.037-0.058 0.071-0.124 0.099-0.194l0.003-0.008c0.038-0.14 0.062-0.301 0.066-0.467l0-0.003c-0.008-0.083-0.023-0.158-0.044-0.231l0.002 0.009c-0.020-0.094-0.047-0.177-0.083-0.255l0.003 0.007c-0.012-0.025-0.011-0.052-0.025-0.076-0.347-0.605-0.645-1.305-0.858-2.041l-0.017-0.068c-0.007-0.026-0.027-0.045-0.036-0.070-0.034-0.086-0.072-0.16-0.118-0.228l0.003 0.005c-0.040-0.074-0.084-0.138-0.133-0.197l0.002 0.002c-0.052-0.053-0.109-0.101-0.169-0.144l-0.004-0.003c-0.060-0.051-0.128-0.097-0.2-0.136l-0.006-0.003c-0.057-0.026-0.126-0.049-0.196-0.066l-0.008-0.002c-0.077-0.026-0.167-0.045-0.259-0.053l-0.005-0c-0.026-0.002-0.047-0.015-0.073-0.015l-2.162-0.001v-3.492l2.162 0.011c0.16-0.002 0.311-0.035 0.45-0.092l-0.008 0.003c0.054-0.024 0.099-0.048 0.142-0.075l-0.005 0.003c0.090-0.047 0.168-0.1 0.239-0.16l-0.002 0.001c0.043-0.039 0.082-0.079 0.118-0.122l0.002-0.002c0.056-0.065 0.106-0.138 0.147-0.215l0.003-0.007c0.027-0.047 0.054-0.102 0.076-0.159l0.003-0.008c0.010-0.028 0.029-0.050 0.037-0.078 0.23-0.805 0.527-1.506 0.899-2.159l-0.025 0.048c0.014-0.024 0.013-0.052 0.025-0.076 0.031-0.067 0.057-0.147 0.075-0.229l0.001-0.008c0.020-0.086 0.032-0.185 0.032-0.287 0-0.317-0.113-0.607-0.3-0.834l0.002 0.002c-0.017-0.020-0.023-0.045-0.042-0.063l-1.527-1.529 2.469-2.469 1.518 1.531c0.055 0.045 0.116 0.087 0.18 0.122l0.006 0.003c0.042 0.033 0.089 0.065 0.138 0.094l0.006 0.003c0.16 0.088 0.35 0.142 0.551 0.148l0.002 0 0.005 0.001c0.012 0 0.023-0.009 0.034-0.009 0.186-0.008 0.359-0.056 0.513-0.135l-0.007 0.003c0.022-0.011 0.047-0.006 0.070-0.018 0.605-0.346 1.305-0.645 2.041-0.858l0.069-0.017c0.025-0.007 0.042-0.026 0.066-0.034 0.091-0.035 0.17-0.076 0.243-0.125l-0.004 0.003c0.069-0.038 0.128-0.079 0.183-0.124l-0.002 0.002c0.058-0.056 0.11-0.117 0.156-0.183l0.003-0.004c0.046-0.056 0.089-0.119 0.126-0.185l0.003-0.006c0.028-0.062 0.053-0.135 0.070-0.21l0.002-0.008c0.024-0.073 0.042-0.158 0.050-0.247l0-0.005c0.002-0.027 0.015-0.049 0.015-0.076l0.001-2.162h3.491l-0.011 2.156c-0 0.028 0.014 0.051 0.015 0.079 0.008 0.093 0.026 0.178 0.052 0.26l-0.002-0.008c0.019 0.084 0.044 0.157 0.075 0.227l-0.003-0.008c0.040 0.073 0.082 0.136 0.13 0.194l-0.002-0.002c0.048 0.070 0.101 0.131 0.158 0.187l0 0c0.053 0.044 0.112 0.084 0.174 0.12l0.006 0.003c0.068 0.046 0.147 0.087 0.23 0.119l0.008 0.003c0.025 0.009 0.043 0.028 0.069 0.035 0.804 0.229 1.503 0.527 2.155 0.899l-0.047-0.025c0.022 0.012 0.046 0.007 0.068 0.018 0.147 0.076 0.32 0.124 0.503 0.132l0.003 0c0.012 0 0.024 0.009 0.036 0.009l0.028-0.008c0.193-0.008 0.372-0.059 0.531-0.143l-0.007 0.003c0.059-0.033 0.109-0.066 0.156-0.104l-0.003 0.002c0.068-0.037 0.127-0.076 0.181-0.12l-0.002 0.002 1.531-1.528 2.469 2.47-1.531 1.516c-0.020 0.020-0.027 0.047-0.046 0.068-0.053 0.063-0.101 0.134-0.142 0.209l-0.003 0.006c-0.084 0.123-0.138 0.272-0.148 0.434l-0 0.002c-0.013 0.056-0.020 0.121-0.020 0.187 0 0.097 0.016 0.19 0.045 0.277l-0.002-0.006c0.020 0.094 0.047 0.176 0.083 0.254l-0.003-0.007c0.012 0.025 0.011 0.053 0.025 0.078 0.347 0.604 0.645 1.303 0.858 2.038l0.017 0.068c0.008 0.030 0.028 0.052 0.038 0.080 0.024 0.062 0.049 0.113 0.077 0.163l-0.003-0.006c0.211 0.397 0.619 0.665 1.090 0.674l0.001 0 2.162 0.001zM16 10.75c-2.899 0-5.25 2.351-5.25 5.25s2.351 5.25 5.25 5.25c2.899 0 5.25-2.351 5.25-5.25v0c-0.004-2.898-2.352-5.246-5.25-5.25h-0zM16 18.75c-1.519 0-2.75-1.231-2.75-2.75s1.231-2.75 2.75-2.75c1.519 0 2.75 1.231 2.75 2.75v0c-0.002 1.518-1.232 2.748-2.75 2.75h-0z"></path> </svg>'
SVG_ICON = '<svg xmlns="http://www.w3.org/2000/svg" height="100%" viewBox="0 -960 960 960" width="100%" fill="currentColor"><path d="M251-160q-88 0-149.5-61.5T40-371q0-79 50.5-137.5T217-579q15-84 82-148.5T451-792q24 0 42 13.5t18 36.5v294l83-83 43 43-156 156-156-156 43-43 83 83v-289q-86 11-135 75.5T267-522h-19q-61 0-104.5 43T100-371q0 65 45 108t106 43h500q45 0 77-32t32-77q0-45-32-77t-77-32h-63v-84q0-68-33-117.5T570-718v-65q81 29 129.5 101T748-522v24q72-2 122 46t50 123q0 69-50 119t-119 50H251Zm229-347Z"/></svg>'
DOWNLOAD_DIR = os.path.join(SHELL_DIR, '_Download')
ZIP_PATH = os.path.join(DOWNLOAD_DIR, 'repo.zip')
EXTRACT_DIR = os.path.join(DOWNLOAD_DIR, 'TriGlav-Shell-main')

download_state = {'status': 'idle', 'percent': 0, 'message': ''}
download_lock = threading.Lock()

BACKUP_DIR = os.path.join(SHELL_DIR, '_BackUp')
backup_state = {'status': 'idle', 'percent': 0, 'message': '', 'log_path': '', 'zip_path': '', 'errors': []}
backup_lock = threading.Lock()

log = logging.getLogger('updater')
log.setLevel(logging.DEBUG)

if args.log:
    log_path = os.path.join(BASE_DIR, 'log_file.log')
    logging.basicConfig(filename=log_path, level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
    log.info('Updater %s started', VERSION)


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(SHELL_DIR, '_data', 'config.cfg'), encoding='utf-8')
    return cfg


def get_shell_port():
    cfg = load_config()
    return int(cfg.get('shell', 'port', fallback='8080'))


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
    with download_lock:
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
                    with download_lock:
                        download_state['percent'] = int(downloaded * 100 / total)
                        download_state['message'] = f'Downloaded {downloaded // 1024}KB / {total // 1024}KB'

        with download_lock:
            download_state['status'] = 'extracting'
            download_state['percent'] = 0
            download_state['message'] = 'Extracting archive...'

        try:
            with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
                zf.extractall(DOWNLOAD_DIR)
        except Exception as e:
            if os.path.isdir(EXTRACT_DIR):
                shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
            raise e

        with download_lock:
            download_state = {'status': 'done', 'percent': 100, 'message': 'Archive ready'}
        log.info('download: done, zip=%dKB', os.path.getsize(ZIP_PATH) // 1024)

    except requests.exceptions.ConnectionError:
        with download_lock:
            download_state = {'status': 'error', 'percent': 0, 'message': 'No connection to GitHub'}
    except requests.exceptions.HTTPError as e:
        with download_lock:
            download_state = {'status': 'error', 'percent': 0, 'message': f'HTTP error: {e.response.status_code}'}
    except Exception as e:
        with download_lock:
            download_state = {'status': 'error', 'percent': 0, 'message': str(e)}


def load_backup_settings():
    mp = os.path.join(BASE_DIR, 'manifest.json')
    try:
        with open(mp, 'r', encoding='utf-8') as f:
            m = json.load(f)
        return {
            'ignore_dirs': m.get('backup_ignore_dirs', []) or [],
            'ignore_exts': m.get('backup_ignore_exts', []) or [],
            'ignore_files': m.get('backup_ignore_files', []) or []
        }
    except Exception:
        return {'ignore_dirs': [], 'ignore_exts': [], 'ignore_files': []}


def create_backup(dest_dir):
    global backup_state
    now = datetime.now()
    name = f"full_BackUp_{now.strftime('%d%m%y_%H%M')}"
    zip_path = os.path.join(dest_dir, name + '.zip')
    log_path = os.path.join(dest_dir, name + '.log')
    errors = []

    with backup_lock:
        backup_state = {'status': 'counting', 'percent': 0, 'message': 'Подсчёт файлов...', 'log_path': '', 'zip_path': '', 'errors': []}

    log.info('backup: start -> %s', zip_path)

    settings = load_backup_settings()
    ignore_dirs = settings['ignore_dirs']
    ignore_exts = settings['ignore_exts']
    ignore_files = settings['ignore_files']
    log.info('backup: ignore_dirs=%s, ignore_exts=%s, ignore_files=%s', ignore_dirs, ignore_exts, ignore_files)

    # Collect files
    all_files = []
    for root, dirs, files in os.walk(SHELL_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ignore_exts:
                continue
            skip = False
            for pat in ignore_files:
                if pat.startswith('@'):
                    # @ = only project root: match relative path
                    rel = os.path.relpath(os.path.join(root, f), SHELL_DIR)
                    if fnmatch.fnmatch(rel, pat[1:]):
                        skip = True
                        break
                else:
                    if fnmatch.fnmatch(f, pat):
                        skip = True
                        break
            if skip:
                continue
            all_files.append(os.path.join(root, f))

    total = len(all_files)
    log.info('backup: %d files to archive', total)

    with backup_lock:
        backup_state['status'] = 'creating'
        backup_state['message'] = f'0/{total} файлов'

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, filepath in enumerate(all_files):
                try:
                    arcname = os.path.relpath(filepath, SHELL_DIR)
                    zf.write(filepath, arcname)
                except PermissionError as e:
                    msg = f'Permission denied: {filepath}'
                    errors.append(msg)
                    log.warning('backup: %s', msg)
                except Exception as e:
                    msg = f'{filepath}: {e}'
                    errors.append(msg)
                    log.warning('backup: %s', msg)

                if (i + 1) % 10 == 0 or (i + 1) == total:
                    pct = int((i + 1) * 100 / total) if total > 0 else 100
                    with backup_lock:
                        backup_state['percent'] = pct
                        backup_state['message'] = f'{i+1}/{total} файлов'

        # Write log file
        with open(log_path, 'w', encoding='utf-8') as lf:
            lf.write(f'Backup: {name}\n')
            lf.write(f'Dest: {zip_path}\n')
            lf.write(f'Files: {total}\n')
            lf.write(f'Errors: {len(errors)}\n\n')
            for e in errors:
                lf.write(e + '\n')

        # Add log file to zip
        try:
            with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zf:
                zf.write(log_path, name + '.log')
        except Exception as e:
            log.warning('backup: could not add log to zip: %s', e)

        with backup_lock:
            backup_state['status'] = 'done'
            backup_state['percent'] = 100
            backup_state['message'] = f'Готово: {total} файлов'
            backup_state['log_path'] = log_path
            backup_state['zip_path'] = zip_path
            backup_state['errors'] = errors

        log.info('backup: done, %d errors', len(errors))

    except Exception as e:
        with backup_lock:
            backup_state = {'status': 'error', 'percent': 0, 'message': str(e), 'log_path': '', 'zip_path': '', 'errors': []}
        log.error('backup: failed: %s', e)



def copy_module_from_repo(module_name, dest_dir):
    # Find actual directory in archive by manifest name
    src_dir = None
    mod_base = os.path.join(EXTRACT_DIR, '_module')
    if os.path.isdir(mod_base):
        for d in os.listdir(mod_base):
            mp = os.path.join(mod_base, d, 'manifest.json')
            if os.path.isfile(mp):
                try:
                    with open(mp, 'r', encoding='utf-8') as f:
                        mf = json.load(f)
                    if mf.get('name') == module_name:
                        src_dir = os.path.join(mod_base, d)
                        break
                except Exception:
                    pass
    if not src_dir or not os.path.isdir(src_dir):
        log.error('copy: source not found for %s', module_name)
        return False, f'Source not found for {module_name} in archive'
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
        .repo-status-ok { color: #21bf4b; filter: drop-shadow(0 0 6px #21bf4b); }
        .repo-status-fail { color: #ff6c59; filter: drop-shadow(0 0 6px #ff6c59); }
        .repo-status-checking { color: #666; }
        .modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:100; justify-content:center; align-items:center; }
        .modal-overlay.active { display:flex; }
        .modal { background:#262626; border:1px solid #404040; border-radius:4px; width:600px; max-height:80vh; overflow:hidden; }
        .modal-header { background:#333; padding:10px 14px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #404040; }
        .modal-header h3 { color:#47a8ff; font-size:14px; margin:0; }
        .modal-close { background:none; border:none; color:#999; font-size:20px; cursor:pointer; }
        .modal-close:hover { color:#f2f2f2; }
        .modal-body { padding:14px; max-height:60vh; overflow-y:auto; }
        #logContent { margin:0; }
        .backup-bar { display:flex; gap:8px; margin-bottom:12px; align-items:center; }
        .backup-bar input { flex:1; padding:6px 10px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:12px; font-family:inherit; }
    </style>
</head>
<body>
    <div class="header" data-zone="updater.header">
        <div>
            <h1>Обновления {{ version }}</h1>
            <div class="header-info">Управление модулями из GitHub</div>
        </div>
        <div class="controls">
        </div>
    </div>
    <div class="content">
        <div id="statusMessage"></div>

        <div class="repo-bar" data-zone="updater.get_online">
            <span id="repoStatusIcon" style="display:inline-flex;align-items:center;width:28px;height:28px;transition:filter 0.3s;filter:brightness(0.5);" title="Проверка...">{{ svg_icon|safe }}</span>
            <input type="text" id="repoUrl" data-zone="updater.repo_url" value="{{ repo_url }}" oninput="debounceCheckRepo()">
            <button class="btn btn-primary" id="scanBtn" onclick="startDownload()">Get</button>
        </div>

        <div class="repo-bar" data-zone="updater.backup">
            <span style="display:inline-block;width:28px;height:28px;flex-shrink:0;">{{ svg_backup_icon|safe }}</span>
            <button class="btn btn-default" onclick="openBackups()" title="Работа с Архивами">Open BackUp Folder</button>
            <button class="btn btn-success" onclick="startBackup()">BackUp Full</button>
            <button class="btn btn-default" onclick="openBackupSettings()" title="BackUp Settings" style="display:inline-flex;align-items:center;"><span style="width:16px;height:16px;display:inline-block;">{{ svg_gear_icon|safe }}</span></button>
        </div>

        <div class="section-title">Установленные объекты</div>
        <input type="text" class="search" id="searchInstalled" placeholder="Поиск..." oninput="filterInstalled()">
        <div class="panel">
            <div class="panel-body" style="padding:0;">
                <table class="module-table">
                    <thead>
                        <tr><th><input type="checkbox" id="checkAllInstalled" onchange="toggleAllInstalled()"></th><th>Type</th><th>Status</th><th>Name</th><th>Title</th><th>Local</th><th>Repo</th><th>Status</th></tr>
                    </thead>
                    <tbody id="installedBody" data-zone="updater.installed_table"></tbody>
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
                    <tbody id="newBody" data-zone="updater.new_table"></tbody>
                </table>
            </div>
        </div>

        <button class="btn btn-primary" id="installBtn" onclick="installSelected()">Установить</button>
    </div>

    <div class="modal-overlay" id="progressModal" data-zone="updater.modal.progress">
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
        let checkRepoTimer = null;

        function debounceCheckRepo() {
            clearTimeout(checkRepoTimer);
            const icon = document.getElementById("repoStatusIcon");
            icon.className = "repo-status-checking";
            icon.title = "Проверка...";
            checkRepoTimer = setTimeout(() => checkRepo(), 1000);
        }

        async function checkRepo() {
            const url = document.getElementById("repoUrl").value.trim();
            const icon = document.getElementById("repoStatusIcon");
            icon.className = "repo-status-checking";
            icon.title = "Проверка...";
            try {
                const r = await fetch("/api/repo/check?url=" + encodeURIComponent(url));
                const d = await r.json();
                if (d.available) {
                    icon.className = "repo-status-ok";
                    icon.style.color = "#21bf4b";
                    icon.title = "Репозиторий доступен (" + d.status_code + ")";
                } else {
                    icon.className = "repo-status-fail";
                    icon.style.color = "#ff6c59";
                    icon.title = "Недоступен: " + (d.reason || d.status_code);
                }
            } catch(e) {
                icon.className = "repo-status-fail";
                icon.style.color = "#ff6c59";
                icon.title = "Ошибка проверки: " + e.message;
            }
        }

        document.addEventListener("DOMContentLoaded", function() { checkRepo(); });

        async function openBackups() {
            document.getElementById('backupModal').classList.add('active');
            document.getElementById('backupSummary').textContent = 'Загрузка...';
            document.getElementById('backupList').innerHTML = '';
            try {
                const r = await fetch('/proxy/5002/api/backup/files');
                const files = await r.json();
                const totalSize = files.reduce((s, b) => s + b.size, 0);
                document.getElementById('backupSummary').textContent =
                    'Всего бекапов: ' + files.length + ', Общий объем: ' + formatSize(totalSize);
                const tbody = document.getElementById('backupList');
                if (!files.length) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#999;padding:40px;">Нет бекапов</td></tr>';
                    return;
                }
                tbody.innerHTML = files.map((b, i) =>
                    '<tr><td style="text-align:center;"><input type="checkbox" class="backup-cb" data-base="' + b.base + '" onchange="updateBackupButtons()"></td>' +
                    '<td style="text-align:left;">' + b.name + '</td><td style="text-align:right;">' + formatSize(b.size) + '</td>' +
                    '<td style="text-align:center;">' + (b.has_log ? '<a href="#" onclick="viewLog(\'' + b.base + '.log\');return false;" style="color:#47a8ff;">Log</a>' : '') + '</td></tr>'
                ).join('');
            } catch(e) {
                document.getElementById('backupSummary').textContent = 'Ошибка: ' + e.message;
            }
        }

        function closeBackupModal() {
            document.getElementById('backupModal').classList.remove('active');
        }

        async function viewLog(filename) {
            document.getElementById('logModal').classList.add('active');
            document.getElementById('logContent').textContent = 'Загрузка...';
            try {
                const r = await fetch('/proxy/5002/api/backup/log?name=' + encodeURIComponent(filename));
                const d = await r.json();
                if (d.error) {
                    document.getElementById('logContent').textContent = 'Ошибка: ' + d.error;
                } else {
                    document.getElementById('logContent').textContent = d.content;
                }
            } catch(e) {
                document.getElementById('logContent').textContent = 'Ошибка загрузки: ' + e.message;
            }
        }

        function closeLogModal() {
            document.getElementById('logModal').classList.remove('active');
        }

        function formatSize(b) {
            if (b < 1024) return b + ' B';
            if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
            return (b / 1048576).toFixed(1) + ' MB';
        }

        function toggleBackupAll() {
            const c = document.getElementById('backupCheckAll').checked;
            document.querySelectorAll('.backup-cb').forEach(cb => cb.checked = c);
            updateBackupButtons();
        }

        function updateBackupButtons() {
            const n = document.querySelectorAll('.backup-cb:checked').length;
            document.getElementById('btnBkDownload').disabled = n !== 1;
            document.getElementById('btnBkDelete').disabled = n === 0;
        }

        function getSelectedBackups() {
            return [...document.querySelectorAll('.backup-cb:checked')].map(cb => cb.dataset.base);
        }

        async function downloadBackupFiles() {
            const sel = getSelectedBackups();
            for (const base of sel) {
                const a = document.createElement('a');
                a.href = '/proxy/5002/api/backup/file?name=' + encodeURIComponent(base + '.zip');
                a.download = base + '.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
            }
        }

        async function deleteBackupFiles() {
            const sel = getSelectedBackups();
            if (!confirm('Удалить ' + sel.length + ' бекап(ов)?')) return;
            const names = sel.flatMap(b => [b + '.zip', b + '.log']);
            try {
                const r = await fetch('/proxy/5002/api/backup/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({files: names})
                });
                const d = await r.json();
                if (d.errors && d.errors.length) alert('Ошибки: ' + d.errors.join('; '));
                openBackups();
            } catch(e) { alert('Ошибка: ' + e.message); }
        }

        async function startBackup() {
            if (!confirm('\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u043e\u043b\u043d\u044b\u0439 \u0431\u0435\u043a\u0430\u043f \u043f\u0440\u043e\u0435\u043a\u0442\u0430?')) return;
            hideStatus();
            showProgress('Создание бекапа...');
            try {
                const r = await fetch('/api/backup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                });
                const d = await r.json();
                if (d.status === 'started') {
                    pollBackupStatus();
                } else {
                    hideProgress();
                    showStatus(d.message || 'Ошибка запуска', 'error');
                }
            } catch(e) { hideProgress(); showStatus('Ошибка: ' + e.message, 'error'); }
        }

        function pollBackupStatus() {
            const interval = setInterval(async () => {
                try {
                    const r = await fetch('/api/backup/status');
                    const d = await r.json();
                    if (d.status === 'counting' || d.status === 'creating') {
                        document.getElementById('progressFill').style.width = d.percent + '%';
                        document.getElementById('downloadInfo').textContent = d.message;
                    } else if (d.status === 'done') {
                        clearInterval(interval);
                        hideProgress();
                        if (d.errors && d.errors.length) {
                            showStatus('Бекап создан с ошибками (' + d.errors.length + '). Лог: ' + d.log_path, 'error');
                        } else {
                            showStatus('Бекап создан: ' + d.zip_path, 'success');
                        }
                    } else if (d.status === 'error') {
                        clearInterval(interval);
                        hideProgress();
                        showStatus('Ошибка: ' + d.message, 'error');
                    }
                } catch(e) {
                    clearInterval(interval);
                    hideProgress();
                    showStatus('Ошибка соединения: ' + e.message, 'error');
                }
            }, 500);
        }

        function openBackupSettings() {
            document.getElementById('settingsModal').classList.add('active');
            loadBackupSettings();
        }

        function closeSettingsModal() {
            document.getElementById('settingsModal').classList.remove('active');
        }

        async function loadBackupSettings() {
            try {
                const r = await fetch('/proxy/5002/api/backup/settings');
                const d = await r.json();
                document.getElementById('setIgnoreDirs').value = (d.ignore_dirs || []).join(', ');
                document.getElementById('setIgnoreExts').value = (d.ignore_exts || []).join(', ');
                document.getElementById('setIgnoreFiles').value = (d.ignore_files || []).join(', ');
            } catch(e) {}
        }

        async function saveBackupSettings() {
            const data = {
                ignore_dirs: document.getElementById('setIgnoreDirs').value.split(',').map(s => s.trim()).filter(Boolean),
                ignore_exts: document.getElementById('setIgnoreExts').value.split(',').map(s => s.trim()).filter(Boolean),
                ignore_files: document.getElementById('setIgnoreFiles').value.split(',').map(s => s.trim()).filter(Boolean)
            };
            try {
                const r = await fetch('/proxy/5002/api/backup/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const d = await r.json();
                if (d.status === 'ok') {
                    closeSettingsModal();
                    showStatus('Настройки бекапа сохранены', 'success');
                }
            } catch(e) { alert('Ошибка: ' + e.message); }
        }
    </script>

    <div class="modal-overlay" id="backupModal" data-zone="updater.modal.backup">
        <div class="modal">
            <div class="modal-header">
                <h3>BackUp</h3>
                <button class="modal-close" onclick="closeBackupModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div id="backupSummary" style="font-size:12px;color:#999;margin-bottom:12px;"></div>
                <table class="module-table">
                    <thead>
                        <tr>
                            <th style="width:40px;text-align:center;"><input type="checkbox" id="backupCheckAll" onchange="toggleBackupAll()"></th>
                            <th style="text-align:left;">Дата и время</th>
                            <th style="width:80px;text-align:right;">Размер</th>
                            <th style="width:40px;text-align:center;">Log</th>
                        </tr>
                    </thead>
                    <tbody id="backupList"></tbody>
                </table>
                <div style="padding:12px 0;display:flex;gap:8px;">
                    <button class="btn btn-primary" id="btnBkDownload" onclick="downloadBackupFiles()" disabled>DownLoad</button>
                    <button class="btn btn-danger" id="btnBkDelete" onclick="deleteBackupFiles()" disabled>Delete</button>
                    <button class="btn btn-default" onclick="closeBackupModal()">Cancel</button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="logModal" data-zone="updater.modal.log">
        <div class="modal" style="width:700px;">
            <div class="modal-header">
                <h3>Log</h3>
                <button class="modal-close" onclick="closeLogModal()">&times;</button>
            </div>
            <div class="modal-body" style="text-align:left;">
                <pre id="logContent" style="white-space:pre-wrap;word-wrap:break-word;font-size:12px;color:#f2f2f2;background:#1a1a1a;padding:12px;border-radius:3px;max-height:50vh;overflow-y:auto;margin:0;text-align:left;"></pre>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="settingsModal" data-zone="updater.modal.settings">
        <div class="modal" style="width:500px;">
            <div class="modal-header">
                <h3>BackUp Settings</h3>
                <button class="modal-close" onclick="closeSettingsModal()">&times;</button>
            </div>
            <div class="modal-body" style="text-align:left;">
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:12px;color:#47a8ff;margin-bottom:4px;">Игнорируемые папки (через запятую)</label>
                    <input type="text" id="setIgnoreDirs" style="width:100%;padding:6px 10px;background:#1a1a1a;border:1px solid #404040;border-radius:3px;color:#f2f2f2;font-size:12px;font-family:inherit;" placeholder=".git, __pycache__, _BackUp">
                </div>
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:12px;color:#47a8ff;margin-bottom:4px;">Игнорируемые расширения (через запятую)</label>
                    <input type="text" id="setIgnoreExts" style="width:100%;padding:6px 10px;background:#1a1a1a;border:1px solid #404040;border-radius:3px;color:#f2f2f2;font-size:12px;font-family:inherit;" placeholder=".mp3, .log">
                </div>
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:12px;color:#47a8ff;margin-bottom:4px;">Игнорируемые файлы (* ? допустимы)</label>
                    <div style="font-size:10px;color:#666;margin-bottom:4px;">* = любой файл, ? = один символ, @имя = корень проекта</div>
                    <input type="text" id="setIgnoreFiles" style="width:100%;padding:6px 10px;background:#1a1a1a;border:1px solid #404040;border-radius:3px;color:#f2f2f2;font-size:12px;font-family:inherit;" placeholder="@01.md, *.tmp">
                </div>
                <div style="padding:12px 0 0;display:flex;gap:8px;">
                    <button class="btn btn-success" onclick="saveBackupSettings()">Сохранить</button>
                    <button class="btn btn-default" onclick="closeSettingsModal()">Отмена</button>
                </div>
            </div>
        </div>
    </div>

{% if environment == 'development' %}
<style>
.dev-label{position:fixed;background:rgba(0,0,0,.88);color:#47a8ff;font:600 10px/1.2 "Cascadia Mono","Consolas",monospace;padding:2px 8px;border-radius:0 0 4px 0;z-index:99999;pointer-events:none;white-space:nowrap;display:none}
</style>
<script>
(function(){var l=document.createElement("div");l.className="dev-label";document.body.appendChild(l);var timer=null,currentZone=null,mx=0,my=0;function showLabel(z){l.textContent=":: "+z.getAttribute("data-zone");l.style.display="block";var left=mx+12,top=my+12;if(left+l.offsetWidth>window.innerWidth)left=mx-12-l.offsetWidth;if(top+l.offsetHeight>window.innerHeight)top=my-12-l.offsetHeight;l.style.left=left+"px";l.style.top=top+"px"}function hideLabel(){l.style.display="none"}function startTimer(z){clearTimeout(timer);timer=setTimeout(function(){if(currentZone===z)showLabel(z)},500)}document.addEventListener("mouseover",function(e){var z=e.target.closest("[data-zone]");if(z){currentZone=z;hideLabel();startTimer(z)}});document.addEventListener("mouseout",function(e){var z=e.target.closest("[data-zone]");if(z){clearTimeout(timer);currentZone=null;hideLabel()}});document.addEventListener("mousemove",function(e){mx=e.clientX;my=e.clientY;if(l.style.display==="block"){hideLabel();if(currentZone)startTimer(currentZone)}});})();
</script>
{% endif %}

</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(DOWNLOADER_TEMPLATE, version=VERSION, repo_url=REPO_URL, environment=args.environment, svg_icon=SVG_ICON, svg_backup_icon=SVG_BACKUP_ICON, svg_gear_icon=SVG_GEAR_ICON)


@app.route('/api/config')
def api_config():
    return jsonify({'config': dict(get_autostart_config())})


@app.route('/api/download', methods=['POST'])
def api_download():
    global download_state
    with download_lock:
        if download_state['status'] in ('downloading', 'extracting'):
            return jsonify({'status': 'busy', 'message': 'Download in progress'})

    thread = threading.Thread(target=download_archive, daemon=True)
    thread.start()
    return jsonify({'status': 'started'})


@app.route('/api/download/status')
def api_download_status():
    with download_lock:
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
        # Find actual directory name from repo archive
        src_name = name
        if os.path.isdir(EXTRACT_DIR):
            mod_base = os.path.join(EXTRACT_DIR, '_module')
            if os.path.isdir(mod_base):
                for d in os.listdir(mod_base):
                    mp = os.path.join(mod_base, d, 'manifest.json')
                    if os.path.isfile(mp):
                        try:
                            with open(mp, 'r', encoding='utf-8') as f:
                                mf = json.load(f)
                            if mf.get('name') == name:
                                src_name = d
                                break
                        except Exception:
                            pass

        dest_dir = os.path.join(SHELL_DIR, '_module', src_name)
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
                shell_port = get_shell_port()
                url = f'http://127.0.0.1:{shell_port}/api/module/{name}/stop'
                log.info('update: stop %s', url)
                r = requests.post(url, timeout=5)
                log.info('update: stop -> %d', r.status_code)
            except Exception as e:
                log.error('update: stop failed: %s', e)
            time.sleep(3)

        # Find actual module directory (service modules have _ prefix)
        dest_dir = None
        module_base = os.path.join(SHELL_DIR, '_module')
        for d in os.listdir(module_base):
            mp = os.path.join(module_base, d, 'manifest.json')
            if os.path.isfile(mp):
                try:
                    with open(mp, 'r', encoding='utf-8') as f:
                        mf = json.load(f)
                    if mf.get('name') == name:
                        dest_dir = os.path.join(module_base, d)
                        break
                except Exception:
                    pass
        if not dest_dir:
            log.error('update: module %s not found in _module/', name)
            results.append({'name': name, 'status': 'not_found'})
            continue

        ok, msg = copy_module_from_repo(name, dest_dir)
        log.info('update: copy result ok=%s msg=%s', ok, msg)

        if mtype == 'service' and ok:
            try:
                shell_port = get_shell_port()
                url = f'http://127.0.0.1:{shell_port}/api/module/{name}/start'
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

@app.route('/api/backup', methods=['POST'])
def api_backup():
    dest_dir = BACKUP_DIR
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    with backup_lock:
        if backup_state['status'] in ('counting', 'creating'):
            return jsonify({'status': 'busy', 'message': 'Backup in progress'})
    thread = threading.Thread(target=create_backup, args=(dest_dir,), daemon=True)
    thread.start()
    return jsonify({'status': 'started'})


@app.route('/api/backup/status')
def api_backup_status():
    with backup_lock:
        return jsonify(backup_state)



@app.route('/api/repo/check')
def api_repo_check():
    url = request.args.get('url', REPO_URL).strip()
    if not url.startswith('http'):
        return jsonify({'available': False, 'reason': 'Invalid URL'})
    try:
        r = requests.head(url, timeout=10, allow_redirects=True,
                          proxies={'http': None, 'https': None})
        return jsonify({'available': r.status_code < 400, 'status_code': r.status_code})
    except requests.exceptions.ConnectionError:
        return jsonify({'available': False, 'reason': 'Connection refused'})
    except requests.exceptions.Timeout:
        return jsonify({'available': False, 'reason': 'Timeout'})
    except Exception as e:
        return jsonify({'available': False, 'reason': str(e)})





@app.route('/api/backup/files')
def api_backup_files():
    files = []
    orphan_logs = []
    if os.path.isdir(BACKUP_DIR):
        # Collect all zip bases
        zip_bases = set()
        for f in os.listdir(BACKUP_DIR):
            if f.endswith('.zip'):
                zip_bases.add(f[:-4])

        # Find orphan logs (log without zip)
        for f in os.listdir(BACKUP_DIR):
            if f.endswith('.log'):
                log_base = f[:-4]
                if log_base not in zip_bases:
                    orphan_logs.append(os.path.join(BACKUP_DIR, f))

        # Delete orphan logs
        for lp in orphan_logs:
            try:
                os.remove(lp)
                log.info('backup: removed orphan log %s', lp)
            except Exception as e:
                log.warning('backup: failed to remove orphan %s: %s', lp, e)

        # Build file list
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.endswith('.zip'):
                base = f[:-4]
                zip_path = os.path.join(BACKUP_DIR, f)
                log_path = os.path.join(BACKUP_DIR, base + '.log')
                size = os.path.getsize(zip_path)
                has_log = os.path.exists(log_path)
                if has_log:
                    size += os.path.getsize(log_path)
                mtime = os.path.getmtime(zip_path)
                dt = datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M')
                files.append({'base': base, 'name': dt, 'size': size, 'has_log': has_log})
    files.sort(key=lambda x: x['base'], reverse=True)
    return jsonify(files)


@app.route('/api/backup/log')
def api_backup_log():
    name = request.args.get('name', '')
    if '..' in name or '/' in name or chr(92) in name:
        return jsonify({'error': 'Invalid name'}), 400
    fp = os.path.join(BACKUP_DIR, name)
    if not os.path.isfile(fp):
        return jsonify({'error': 'Not found'}), 404
    try:
        with open(fp, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/backup/file')
def api_backup_file():
    name = request.args.get('name', '')
    if '..' in name or '/' in name or chr(92) in name:
        return jsonify({'error': 'Invalid name'}), 400
    fp = os.path.join(BACKUP_DIR, name)
    if not os.path.isfile(fp):
        return jsonify({'error': 'Not found'}), 404
    return send_file(fp, as_attachment=True)


@app.route('/api/backup/delete', methods=['POST'])
def api_backup_delete():
    data = request.get_json()
    names = data.get('files', [])
    errors = []
    deleted = 0
    for name in names:
        if '..' in name or '/' in name or chr(92) in name:
            errors.append('Invalid: ' + name)
            continue
        fp = os.path.join(BACKUP_DIR, name)
        try:
            if os.path.isfile(fp):
                os.remove(fp)
                deleted += 1
        except Exception as e:
            errors.append(name + ': ' + str(e))
    return jsonify({'deleted': deleted, 'errors': errors})


@app.route('/api/backup/settings', methods=['GET'])
def api_backup_settings_get():
    settings = load_backup_settings()
    return jsonify(settings)


@app.route('/api/backup/settings', methods=['POST'])
def api_backup_settings_post():
    data = request.get_json()
    mp = os.path.join(BASE_DIR, 'manifest.json')
    try:
        with open(mp, 'r', encoding='utf-8') as f:
            m = json.load(f)
        m['backup_ignore_dirs'] = data.get('ignore_dirs', [])
        m['backup_ignore_exts'] = data.get('ignore_exts', [])
        m['backup_ignore_files'] = data.get('ignore_files', [])
        with open(mp, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500



if __name__ == '__main__':
    print(f"Updater {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
