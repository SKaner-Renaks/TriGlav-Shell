import subprocess
import json
import threading
import time
import os
import socket
import re
import argparse
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

VERSION = 'v2.4.4'

app = Flask(__name__)

PS1_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_get_tasks.ps1')

PS1_CONTENT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\Windows\*' }
$results = @()
foreach ($task in $tasks) {
    $info = $task | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
    $schedule = ''
    if ($task.Triggers.Count -gt 0) {
        $triggers = @()
        foreach ($tr in $task.Triggers) {
            $cn = $tr.CimClass.CimClassName
            $rep = ''
            if ($tr.Repetition -and $tr.Repetition.Interval) {
                $rep = ' [' + $tr.Repetition.Interval + ']'
            }
            if ($cn -like '*TimeTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $triggers += ('Every ' + $time + $rep)
            } elseif ($cn -like '*DailyTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $triggers += ('Daily at ' + $time + $rep)
            } elseif ($cn -like '*WeeklyTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $days = @()
                $dw = [int]$tr.DaysOfWeek
                if ($dw -band 1) { $days += 'Mon' }
                if ($dw -band 2) { $days += 'Tue' }
                if ($dw -band 4) { $days += 'Wed' }
                if ($dw -band 8) { $days += 'Thu' }
                if ($dw -band 16) { $days += 'Fri' }
                if ($dw -band 32) { $days += 'Sat' }
                if ($dw -band 64) { $days += 'Sun' }
                $triggers += ('Weekly ' + ($days -join ',') + ' ' + $time + $rep)
            } elseif ($cn -like '*MonthlyTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $triggers += ('Monthly ' + $time + $rep)
            } else {
                $triggers += ('Other' + $rep)
            }
        }
        $schedule = $triggers -join '; '
    }
    $lastRun = ''
    $nextRun = ''
    $lastResult = ''
    if ($info) {
        if ($info.LastRunTime -and $info.LastRunTime.Year -gt 1999) { $lastRun = $info.LastRunTime.ToString('dd-MM-yyyy HH:mm') }
        if ($info.NextRunTime -and $info.NextRunTime.Year -gt 1999) { $nextRun = $info.NextRunTime.ToString('dd-MM-yyyy HH:mm') }
        $lastResult = $info.LastTaskResult
    }
    $results += @{
        Name = $task.TaskName
        Path = $task.TaskPath
        Status = $task.State.ToString()
        Schedule = $schedule
        LastRun = $lastRun
        NextRun = $nextRun
        LastResult = $lastResult
    }
}
$results | ConvertTo-Json -Compress
"""


def _ensure_ps1():
    if not os.path.exists(PS1_PATH):
        with open(PS1_PATH, 'w', encoding='utf-8') as f:
            f.write(PS1_CONTENT)


def _run_ps(cmd, timeout=30):
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', cmd],
            capture_output=True, timeout=timeout
        )
        stdout = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        stderr = result.stderr.decode('cp866', errors='replace').strip() if result.stderr else ''
        if result.returncode != 0 and stderr:
            return stdout, stderr
        return stdout, None
    except subprocess.TimeoutExpired:
        return '', 'Timeout'
    except Exception as e:
        return '', str(e)


def get_tasks():
    _ensure_ps1()
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', PS1_PATH],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            err = result.stderr.decode('cp866', errors='replace').strip() if result.stderr else f'exit code {result.returncode}'
            return [], err

        stdout = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        if not stdout:
            return [], 'Empty output from PowerShell'

        tasks = json.loads(stdout)
        if isinstance(tasks, dict):
            tasks = [tasks]

        tasks.sort(key=lambda t: t.get('Name', ''))
        return tasks, None
    except subprocess.TimeoutExpired:
        return [], 'Timeout'
    except json.JSONDecodeError as e:
        return [], f'JSON parse error: {e}'
    except Exception as e:
        return [], f'{type(e).__name__}: {e}'


def set_task_state(task_name, enable):
    if enable:
        cmd = f"Enable-ScheduledTask -TaskName '{task_name}'"
    else:
        cmd = f"Disable-ScheduledTask -TaskName '{task_name}'"
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', cmd],
            capture_output=True, timeout=15
        )
        stdout = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        stderr = result.stderr.decode('cp866', errors='replace').strip() if result.stderr else ''
        if result.returncode != 0:
            err_msg = stderr or stdout or f'exit code {result.returncode}'
            if '0x80070005' in err_msg or 'Отказано в доступе' in err_msg or 'Access is denied' in err_msg:
                err_msg = 'Access denied. Run module with Administrator rights.'
            return False, err_msg
        return True, stdout
    except Exception as e:
        return False, str(e)


def build_trigger_ps(data):
    trigger_type = data.get('trigger_type', 'daily')
    start_str = data.get('start', '')
    end_str = data.get('end', '')
    repeat = data.get('repeat', '')
    days_of_week = data.get('days_of_week', [])
    days_of_month = data.get('days_of_month', '')

    if not start_str:
        return None, 'Start date/time is required'

    ps_start = start_str.replace('T', ' ')

    if trigger_type == 'once':
        trigger_cmd = f'New-ScheduledTaskTrigger -Once -At \'{ps_start}\''
    elif trigger_type == 'daily':
        trigger_cmd = f'New-ScheduledTaskTrigger -Daily -At \'{ps_start}\''
    elif trigger_type == 'weekly':
        if not days_of_week:
            return None, 'At least one day of week is required for weekly trigger'
        day_map = {1: 'Monday', 2: 'Tuesday', 4: 'Wednesday', 8: 'Thursday', 16: 'Friday', 32: 'Saturday', 64: 'Sunday'}
        day_names = [day_map[d] for d in days_of_week if d in day_map]
        days_str = ','.join(day_names)
        trigger_cmd = f'New-ScheduledTaskTrigger -Weekly -At \'{ps_start}\' -DaysOfWeek {days_str}'
    elif trigger_type == 'monthly':
        if not days_of_month:
            return None, 'Days of month are required for monthly trigger'
        md_list = ','.join([d.strip() for d in days_of_month.split(',') if d.strip().isdigit()])
        trigger_cmd = f'New-ScheduledTaskTrigger -Monthly -At \'{ps_start}\' -DaysOfMonth {md_list}'
    else:
        return None, f'Unknown trigger type: {trigger_type}'

    if end_str:
        ps_end = end_str.replace('T', ' ')
        trigger_cmd += f' -EndAt \'{ps_end}\''

    if repeat:
        trigger_cmd += f' -RepetitionInterval (New-TimeSpan -Duration \'{repeat}\')'
        trigger_cmd += ' -RepetitionDuration (New-TimeSpan -Days 9999)'

    return trigger_cmd, None


def create_or_update_task(data, is_update=False):
    name = data.get('name', '').strip()
    if not name:
        return False, 'Task name is required'

    program = data.get('program', '').strip()
    if not program:
        return False, 'Program path is required'

    args_val = data.get('args', '').strip()
    work_dir = data.get('work_dir', '').strip()
    run_as = data.get('run_as', '').strip() or 'SYSTEM'
    password = data.get('password', '')

    trigger_cmd, err = build_trigger_ps(data)
    if err:
        return False, err

    action_cmd = f'New-ScheduledTaskAction -Execute \'{program}\''
    if args_val:
        action_cmd += f' -Argument \'{args_val}\''
    if work_dir:
        action_cmd += f' -WorkingDirectory \'{work_dir}\''

    settings_cmd = 'New-ScheduledTaskSettingSet -ExecutionTimeLimit (New-TimeSpan -Hours 72) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable'

    register_cmd = f'$action = {action_cmd}; $trigger = {trigger_cmd}; $settings = {settings_cmd}; '
    register_cmd += f'Register-ScheduledTask -TaskName \'{name}\' -Action $action -Trigger $trigger -Settings $settings'

    if run_as.upper() == 'SYSTEM':
        register_cmd += ' -User SYSTEM -Force'
    else:
        register_cmd += f' -User \'{run_as}\''
        if password:
            register_cmd += f' -Password \'{password}\''
        register_cmd += ' -Force'

    if is_update:
        unregister_cmd = f'Unregister-ScheduledTask -TaskName \'{name}\' -Confirm:$false'
        out, err = _run_ps(unregister_cmd)
        if err and 'not find' not in err.lower():
            return False, f'Failed to remove old task: {err}'

    out, err = _run_ps(register_cmd)
    if err:
        return False, f'Failed to register task: {err}'
    return True, None


def delete_task(name):
    cmd = f'Unregister-ScheduledTask -TaskName \'{name}\' -Confirm:$false'
    out, err = _run_ps(cmd)
    if err:
        return False, f'Failed to delete task: {err}'
    return True, None


def run_task(name):
    cmd = f'Start-ScheduledTask -TaskName \'{name}\''
    out, err = _run_ps(cmd)
    if err:
        return False, f'Failed to run task: {err}'
    return True, None


def copy_task(name, new_name):
    if not new_name:
        return False, 'New name is required'

    export_cmd = f'$xml = [xml](Export-ScheduledTask -TaskName \'{name}\'); $xml.OuterXml'
    xml_out, err = _run_ps(export_cmd)
    if err:
        return False, f'Failed to export task: {err}'

    if not xml_out:
        return False, 'Empty export output'

    xml_out = xml_out.replace('\'', '\'\'')
    register_cmd = f'$xmlStr = \'{xml_out}\'; $taskXml = [xml]$xmlStr; Register-ScheduledTask -TaskName \'{new_name}\' -Xml $taskXml.OuterXml -Force'
    out, err = _run_ps(register_cmd)
    if err:
        return False, f'Failed to register copied task: {err}'
    return True, None


def get_task_details(name):
    cmd = f'''$task = Get-ScheduledTask -TaskName '{name}'; $info = $task | Get-ScheduledTaskInfo; $result = @{{}}; $result['State'] = $task.State.ToString(); $action = $task.Actions[0]; $result['Program'] = $action.Execute; $result['Args'] = $action.Arguments; $result['WorkDir'] = $action.WorkingDirectory; if ($task.Triggers.Count -gt 0) {{ $tr = $task.Triggers[0]; $cn = $tr.CimClass.CimClassName; if ($cn -like '*Once*') {{ $result['TriggerType'] = 'once' }} elseif ($cn -like '*Daily*') {{ $result['TriggerType'] = 'daily' }} elseif ($cn -like '*Weekly*') {{ $result['TriggerType'] = 'weekly'; $result['DaysOfWeek'] = [int]$tr.DaysOfWeek }} elseif ($cn -like '*Monthly*') {{ $result['TriggerType'] = 'monthly' }}; $result['Start'] = $tr.StartBoundary; if ($tr.Repetition -and $tr.Repetition.Interval) {{ $result['Repeat'] = $tr.Repetition.Interval }}; if ($tr.EndBoundary) {{ $result['End'] = $tr.EndBoundary }} }}; $result | ConvertTo-Json -Compress'''
    out, err = _run_ps(cmd)
    if err:
        return None, f'Failed to get task details: {err}'
    if not out:
        return None, 'Empty output'
    try:
        details = json.loads(out)
        key_map = {
            'TriggerType': 'trigger_type',
            'Start': 'start',
            'End': 'end',
            'Repeat': 'repeat',
            'Program': 'program',
            'Args': 'args',
            'WorkDir': 'work_dir',
            'DaysOfWeek': 'days_of_week',
            'DaysOfMonth': 'days_of_month',
        }
        snake = {}
        for k, v in details.items():
            new_key = key_map.get(k, k)
            snake[new_key] = v
        if 'days_of_week' in snake and isinstance(snake['days_of_week'], int):
            dw = snake['days_of_week']
            snake['days_of_week'] = [val for val in [1, 2, 4, 8, 16, 32, 64] if dw & val]
        return snake, None
    except json.JSONDecodeError as e:
        return None, f'JSON parse error: {e}'


def browse_directory(path):
    if not path:
        path = os.getcwd()
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return None, f'Not a directory: {path}'
    try:
        entries = os.listdir(path)
        directories = sorted([e for e in entries if os.path.isdir(os.path.join(path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(path, e))])
        parent = os.path.dirname(path) if path != os.path.splitdrive(path)[0] + '\\' else None
        return {'path': path, 'directories': directories, 'files': files, 'parent': parent}, None
    except PermissionError:
        return None, 'Access denied'
    except Exception as e:
        return None, str(e)


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


VIEW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'task_server_view.py')


def load_view():
    try:
        if not os.path.exists(VIEW_PATH):
            return None
        with open(VIEW_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if not content or content == 'VISIBLE_TASKS = None':
            return None
        match = re.search(r"VISIBLE_TASKS\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if match:
            items = re.findall(r"'(.*?)'", match.group(1))
            if not items:
                return None
            current_tasks, _ = get_tasks()
            current_names = {t['Name'] for t in current_tasks}
            cleaned = [t for t in items if t in current_names]
            if len(cleaned) != len(items):
                save_view(cleaned if cleaned else None)
            return cleaned if cleaned else None
        return None
    except Exception:
        return None


def save_view(visible_tasks):
    with open(VIEW_PATH, 'w', encoding='utf-8') as f:
        if visible_tasks is None:
            f.write('VISIBLE_TASKS = None\n')
        else:
            items = ', '.join(f"'{t}'" for t in visible_tasks)
            f.write(f'VISIBLE_TASKS = [{items}]\n')


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
    return render_template_string(HTML_TEMPLATE, version=VERSION, description=description, refresh_interval=15)


@app.route('/api/tasks')
def api_tasks():
    tasks, error = get_tasks()
    return jsonify({'tasks': tasks, 'error': error})


@app.route('/api/server-info')
def api_server_info():
    return jsonify({'info': get_server_info()})


@app.route('/api/admin-status')
def api_admin_status():
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False
    return jsonify({'is_admin': is_admin})


@app.route('/api/task/enable', methods=['POST'])
def api_task_enable():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'No task name'}), 400
    ok, err = set_task_state(name, True)
    if ok:
        return jsonify({'status': 'enabled'})
    return jsonify({'error': err}), 500


@app.route('/api/task/disable', methods=['POST'])
def api_task_disable():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'No task name'}), 400
    ok, err = set_task_state(name, False)
    if ok:
        return jsonify({'status': 'disabled'})
    return jsonify({'error': err}), 500


@app.route('/api/task/create', methods=['POST'])
def api_task_create():
    data = request.get_json()
    ok, err = create_or_update_task(data, is_update=False)
    if ok:
        return jsonify({'status': 'created'})
    return jsonify({'error': err}), 500


@app.route('/api/task/update', methods=['POST'])
def api_task_update():
    data = request.get_json()
    ok, err = create_or_update_task(data, is_update=True)
    if ok:
        return jsonify({'status': 'updated'})
    return jsonify({'error': err}), 500


@app.route('/api/task/delete', methods=['POST'])
def api_task_delete():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'No task name'}), 400
    ok, err = delete_task(name)
    if ok:
        return jsonify({'status': 'deleted'})
    return jsonify({'error': err}), 500


@app.route('/api/task/run', methods=['POST'])
def api_task_run():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'No task name'}), 400
    ok, err = run_task(name)
    if ok:
        return jsonify({'status': 'running'})
    return jsonify({'error': err}), 500


@app.route('/api/task/copy', methods=['POST'])
def api_task_copy():
    data = request.get_json()
    name = data.get('name')
    new_name = data.get('new_name')
    if not name or not new_name:
        return jsonify({'error': 'Task name and new name required'}), 400
    ok, err = copy_task(name, new_name)
    if ok:
        return jsonify({'status': 'copied'})
    return jsonify({'error': err}), 500


@app.route('/api/task/get', methods=['GET'])
def api_task_get():
    name = request.args.get('name')
    if not name:
        return jsonify({'error': 'No task name'}), 400
    details, err = get_task_details(name)
    if details:
        return jsonify(details)
    return jsonify({'error': err}), 500


@app.route('/api/browse', methods=['POST'])
def api_browse():
    data = request.get_json()
    path = data.get('path', '')
    result, err = browse_directory(path)
    if result:
        return jsonify(result)
    return jsonify({'error': err}), 500


@app.route('/api/view', methods=['GET'])
def api_view_get():
    return jsonify({'visible': load_view()})


@app.route('/api/view', methods=['POST'])
def api_view_set():
    data = request.get_json()
    visible = data.get('visible')
    if visible is None or (isinstance(visible, list) and len(visible) == 0):
        visible = None
    save_view(visible)
    return jsonify({'status': 'ok'})


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Scheduler {{ version }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; background: #1a1a1a; color: #f2f2f2; min-height: 100vh; font-size: 13px; }
        .header { background: #262626; border-bottom: 1px solid #404040; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 18px; font-weight: 600; color: #47a8ff; }
        .header-info { font-size: 12px; color: #999; margin-top: 2px; }
        .controls { display: flex; gap: 8px; align-items: center; }
        .btn { padding: 6px 14px; border: 1px solid #595959; border-radius: 3px; cursor: pointer; font-size: 12px; font-family: inherit; transition: background 0.15s, border-color 0.15s; }
        .btn-primary { background: #0057b3; color: #f2f2f2; border-color: #0057b3; }
        .btn-primary:hover { background: #0073d9; border-color: #0073d9; }
        .btn-default { background: #404040; color: #f2f2f2; border-color: #595959; }
        .btn-default:hover { background: #595959; }
        .btn-danger { background: #4d1a1a; color: #ff6c59; border-color: #ff6c59; }
        .btn-danger:hover { background: #ff6c59; color: #fff; }
        .btn-success { background: #1a3d24; color: #21bf4b; border-color: #21bf4b; }
        .btn-success:hover { background: #21bf4b; color: #fff; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .toolbar { background: #262626; border-bottom: 1px solid #404040; padding: 10px 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .toolbar-group { display: flex; align-items: center; gap: 8px; }
        .toolbar-separator { width: 1px; height: 20px; background: #666; margin: 0 4px; }
        .toolbar label { font-size: 12px; color: #999; }
        .toolbar input[type="number"] { width: 60px; padding: 3px 6px; background: #1a1a1a; border: 1px solid #404040; border-radius: 3px; color: #f2f2f2; font-size: 11px; font-family: inherit; text-align: center; }
        .toolbar input[type="number"]:focus { outline: none; border-color: #0057b3; }
        .toolbar input[type="text"] { padding: 4px 8px; background: #1a1a1a; border: 1px solid #404040; border-radius: 3px; color: #f2f2f2; font-size: 12px; font-family: inherit; }
        .toolbar input[type="text"]:focus { outline: none; border-color: #0057b3; }
        .content { padding: 16px 20px; }
        .stats { display: flex; gap: 12px; margin-bottom: 12px; }
        .stat-card { background: #262626; border: 1px solid #404040; border-radius: 3px; padding: 10px 16px; min-width: 80px; text-align: center; }
        .stat-card .label { font-size: 11px; color: #999; margin-bottom: 4px; }
        .stat-card .value { font-size: 20px; font-weight: 600; color: #47a8ff; }
        .crud-toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
        .crud-toolbar .btn:disabled { opacity: 0.4; }
        .task-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .task-table th { background: #333; padding: 8px 10px; text-align: left; color: #47a8ff; font-weight: 600; border-bottom: 1px solid #404040; position: sticky; top: 0; }
        .task-table td { padding: 6px 10px; border-bottom: 1px solid #333; cursor: pointer; }
        .task-table tr:hover { background: #2d2d2d; }
        .task-table tr.selected { background: #0057b3; }
        .status { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
        .status-ready { background: #1a3d24; color: #21bf4b; }
        .status-running { background: #1a2d3d; color: #47a8ff; }
        .status-disabled { background: #3d1a1a; color: #ff6c59; }
        .toggle-btn { width: 36px; height: 20px; border-radius: 10px; border: none; cursor: pointer; position: relative; transition: background 0.3s; }
        .toggle-on { background: #21bf4b; }
        .toggle-on::after { content: ''; position: absolute; width: 14px; height: 14px; background: #fff; border-radius: 50%; top: 3px; right: 3px; transition: 0.3s; }
        .toggle-off { background: #666; }
        .toggle-off::after { content: ''; position: absolute; width: 14px; height: 14px; background: #fff; border-radius: 50%; top: 3px; left: 3px; transition: 0.3s; }
        .cell-actions { display: flex; gap: 4px; align-items: center; }
        .task-table-container { max-height: calc(100vh - 180px); overflow-y: auto; }
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 100; justify-content: center; align-items: center; }
        .modal-overlay.active { display: flex; }
        .modal { background: #262626; border: 1px solid #404040; border-radius: 4px; width: 500px; max-height: 80vh; overflow: hidden; }
        .modal-header { background: #333; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #404040; }
        .modal-header h3 { color: #47a8ff; font-size: 14px; }
        .modal-close { background: none; border: none; color: #999; font-size: 20px; cursor: pointer; }
        .modal-close:hover { color: #f2f2f2; }
        .modal-body { padding: 14px; max-height: 60vh; overflow-y: auto; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; font-size: 12px; color: #999; margin-bottom: 4px; }
        .form-group input, .form-group select { width: 100%; padding: 6px 10px; background: #1a1a1a; border: 1px solid #404040; border-radius: 3px; color: #f2f2f2; font-size: 12px; font-family: inherit; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #0057b3; }
        .form-row { display: flex; gap: 12px; }
        .form-row .form-group { flex: 1; }
        .filter-panel { display: none; background: #262626; border: 1px solid #404040; border-radius: 3px; padding: 12px; margin-bottom: 12px; }
        .filter-panel.active { display: block; }
        .filter-list { max-height: 200px; overflow-y: auto; }
        .filter-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
        .filter-item input[type="checkbox"] { accent-color: #0057b3; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Task Scheduler {{ version }}</h1>
            <div class="header-info" id="serverInfo">{{ description }}</div>
        </div>
        <div class="controls">
            <span id="adminStatus" style="font-size: 12px; margin-right: 10px;"></span>
            <button class="btn btn-primary" onclick="refreshTasks()">Refresh</button>
        </div>
    </div>
    <div class="toolbar">
        <div class="toolbar-group">
            <span id="autoIndicator" class="auto-indicator"></span>
            <label>Auto-refresh:</label>
            <input type="number" id="refreshInterval" value="{{ refresh_interval }}" min="1" max="300" onchange="updateRefresh()">
            <label>sec</label>
            <button class="btn btn-default" id="autoBtn" onclick="toggleAuto()">Pause</button>
        </div>
        <div class="toolbar-separator"></div>
        <div class="toolbar-group">
            <label>Search:</label>
            <input type="text" id="searchInput" placeholder="Filter tasks..." oninput="filterTable()">
        </div>
        <div class="toolbar-separator"></div>
        <div class="toolbar-group">
            <span id="taskCount" style="font-size:12px;color:#999;"></span>
        </div>
    </div>

    <div class="filter-panel" id="filterPanel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <strong style="color:#47a8ff;font-size:12px;">Task Visibility Filter</strong>
            <div style="display:flex;gap:6px;">
                <button class="btn btn-default" style="font-size:11px;padding:2px 8px;" onclick="showAllTasks()">Show All</button>
                <button class="btn btn-default" style="font-size:11px;padding:2px 8px;" onclick="hideAllTasks()">Hide All</button>
                <button class="btn btn-primary" style="font-size:11px;padding:2px 8px;" onclick="applyFilter()">Apply</button>
            </div>
        </div>
        <div class="filter-list" id="filterList"></div>
    </div>

    <div class="content">
        <div class="stats" id="stats"></div>
        <div class="crud-toolbar">
            <button class="btn btn-success" onclick="openCreateModal()">Add</button>
            <button class="btn btn-primary" id="btnEdit" disabled onclick="openEditModal()">Edit</button>
            <button class="btn btn-default" id="btnCopy" disabled onclick="openCopyModal()">Copy</button>
            <button class="btn btn-danger" id="btnDelete" disabled onclick="deleteSelectedTask()">Delete</button>
            <button class="btn btn-success" id="btnRun" disabled onclick="runSelectedTask()">Run</button>
            <span style="margin-left:24px"></span>
            <button class="btn btn-default" onclick="toggleFilter()">Hide/Show</button>
        </div>
        <div class="task-table-container">
            <table class="task-table">
                <thead>
                    <tr>
                        <th>Task Name</th>
                        <th>Schedule</th>
                        <th style="width:80px;">Status</th>
                        <th>Last Result</th>
                        <th style="width:140px;">Last Run</th>
                        <th style="width:140px;">Next Run</th>
                        <th style="width:60px;">Action</th>
                    </tr>
                </thead>
                <tbody id="taskBody"></tbody>
            </table>
        </div>
        <div id="footer" style="font-size:11px;color:#666;margin-top:8px;"></div>
    </div>

    <div class="modal-overlay" id="taskModal">
        <div class="modal">
            <div class="modal-header">
                <h3 id="modalTitle">Create Task</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <input type="hidden" id="editMode" value="false">
                <div class="form-group">
                    <label>Task Name *</label>
                    <input type="text" id="taskName" placeholder="My Task">
                </div>
                <div class="form-group">
                    <label>Program *</label>
                    <input type="text" id="taskProgram" placeholder="C:\Windows\notepad.exe">
                </div>
                <div class="form-group">
                    <label>Arguments</label>
                    <input type="text" id="taskArgs" placeholder="">
                </div>
                <div class="form-group">
                    <label>Working Directory</label>
                    <input type="text" id="taskWorkDir" placeholder="">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Run As</label>
                        <input type="text" id="taskRunAs" value="SYSTEM">
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="taskPassword" placeholder="">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Trigger Type</label>
                        <select id="taskTrigger" onchange="onTriggerChange()">
                            <option value="once">Once</option>
                            <option value="daily" selected>Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Start *</label>
                        <input type="datetime-local" id="taskStart">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>End</label>
                        <input type="datetime-local" id="taskEnd">
                    </div>
                    <div class="form-group">
                        <label>Repeat</label>
                        <input type="text" id="taskRepeat" placeholder="PT30M">
                    </div>
                </div>
                <div class="form-group" id="weekDaysRow" style="display:none;">
                    <label>Days of Week</label>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;">
                        <label style="font-size:11px;"><input type="checkbox" value="1" class="dow"> Mon</label>
                        <label style="font-size:11px;"><input type="checkbox" value="2" class="dow"> Tue</label>
                        <label style="font-size:11px;"><input type="checkbox" value="4" class="dow"> Wed</label>
                        <label style="font-size:11px;"><input type="checkbox" value="8" class="dow"> Thu</label>
                        <label style="font-size:11px;"><input type="checkbox" value="16" class="dow"> Fri</label>
                        <label style="font-size:11px;"><input type="checkbox" value="32" class="dow"> Sat</label>
                        <label style="font-size:11px;"><input type="checkbox" value="64" class="dow"> Sun</label>
                    </div>
                </div>
                <div class="form-group" id="monthDaysRow" style="display:none;">
                    <label>Days of Month (comma separated)</label>
                    <input type="text" id="taskMonthDays" placeholder="1,15">
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
                    <button class="btn btn-default" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="saveTask()">Save</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allTasks = [];
        let visibleTasks = null;
        let refreshTimer = null;
        let autoRefresh = true;
        let isAdmin = false;

        function getInterval() { return Math.max(1, parseInt(document.getElementById('refreshInterval').value) || 15); }

        function updateRefresh() { if (autoRefresh) startRefresh(); }

        async function checkAdminStatus() {
            try {
                const r = await fetch('/api/admin-status');
                const d = await r.json();
                isAdmin = d.is_admin;
                const statusEl = document.getElementById('adminStatus');
                if (isAdmin) {
                    statusEl.innerHTML = '<span style="color: #21bf4b;">✓ Admin</span>';
                } else {
                    statusEl.innerHTML = '<span style="color: #ffcc00;">⚠ Not Admin</span> <button class="btn btn-default" style="margin-left: 8px; padding: 3px 8px; font-size: 11px;" onclick="requestElevation()">Restart as Admin</button>';
                }
            } catch(e) {}
        }

        async function requestElevation() {
            if (confirm('Restart module with Administrator rights?')) {
                window.parent.postMessage({action: 'restart-elevated', module: 'task_scheduler'}, '*');
            }
        }

        function startRefresh() {
            if (refreshTimer) clearInterval(refreshTimer);
            refreshTimer = setInterval(refreshTasks, getInterval() * 1000);
            document.getElementById('autoIndicator').className = 'auto-indicator auto-on';
            document.getElementById('autoBtn').textContent = 'Pause';
        }

        function stopRefresh() {
            if (refreshTimer) clearInterval(refreshTimer);
            refreshTimer = null;
            document.getElementById('autoIndicator').className = 'auto-indicator auto-off';
            document.getElementById('autoBtn').textContent = 'Resume';
        }

        function toggleAuto() {
            autoRefresh = !autoRefresh;
            if (autoRefresh) startRefresh(); else stopRefresh();
        }

        async function refreshTasks() {
            try {
                const r = await fetch('/api/tasks');
                const d = await r.json();
                allTasks = d.tasks || [];
                if (d.error) console.error(d.error);
                await loadView();
                renderTable();
            } catch(e) {}
        }

        async function loadView() {
            try {
                const r = await fetch('/api/view');
                const d = await r.json();
                visibleTasks = d.visible;
            } catch(e) { visibleTasks = null; }
        }

        let selectedTaskName = null;
        let allTaskNames = [];

        function renderTable() {
            const search = (document.getElementById('searchInput').value || '').toLowerCase();
            let tasks = allTasks;
            if (visibleTasks) tasks = tasks.filter(t => visibleTasks.includes(t.Name));
            if (search) tasks = tasks.filter(t => t.Name.toLowerCase().includes(search));

            let running = tasks.filter(t => t.Status === 'Running').length;
            let ready = tasks.filter(t => t.Status === 'Ready').length;
            let disabled = tasks.filter(t => t.Status === 'Disabled').length;
            document.getElementById('stats').innerHTML =
                '<div class="stat-card"><div class="label">Total</div><div class="value">' + tasks.length + '</div></div>' +
                '<div class="stat-card"><div class="label">Ready</div><div class="value">' + ready + '</div></div>' +
                '<div class="stat-card"><div class="label">Running</div><div class="value">' + running + '</div></div>' +
                '<div class="stat-card"><div class="label">Disabled</div><div class="value">' + disabled + '</div></div>';

            let html = '';
            tasks.forEach(t => {
                let statusClass = 'status-disabled';
                if (t.Status === 'Ready') statusClass = 'status-ready';
                else if (t.Status === 'Running') statusClass = 'status-running';

                let result = t.LastResult === '0' ? 'OK (0x0)' : (t.LastResult || 'N/A');
                let resultClass = '';
                if (t.LastResult === '0') resultClass = 'color:#21bf4b';
                else if (t.LastResult && t.LastResult !== '0') resultClass = 'color:#ff6c59';

                let isDisabled = t.Status === 'Disabled';
                let toggleClass = isDisabled ? 'toggle-off' : 'toggle-on';
                let toggleTitle = isDisabled ? 'Enable' : 'Disable';
                let encodedName = encodeURIComponent(t.Name);
                let selClass = (selectedTaskName === t.Name) ? ' selected' : '';

                html += '<tr class="task-row' + selClass + '" onclick="selectTaskRow(this, \'' + t.Name.replace(/'/g, "\\'") + '\')">' +
                    '<td><strong>' + t.Name + '</strong></td>' +
                    '<td>' + (t.Schedule || '<span style="color:#666">-</span>') + '</td>' +
                    '<td><span class="status ' + statusClass + '">' + t.Status + '</span></td>' +
                    '<td style="' + resultClass + '">' + result + '</td>' +
                    '<td>' + (t.LastRun || 'Never') + '</td>' +
                    '<td>' + (t.NextRun || '-') + '</td>' +
                    '<td><div class="cell-actions">' +
                    '<button class="toggle-btn ' + toggleClass + '" title="' + toggleTitle + '" data-task="' + encodedName + '" data-disabled="' + isDisabled + '" onclick="event.stopPropagation(); toggleTask(this)"></button>' +
                    '</div></td>' +
                    '</tr>';
            });
            document.getElementById('taskBody').innerHTML = html || '<tr><td colspan="7" style="text-align:center;color:#999;padding:20px;">No tasks found</td></tr>';
            document.getElementById('footer').textContent = 'Last update: ' + new Date().toLocaleString('ru-RU');
            updateCrudButtons();
        }

        function selectTaskRow(el, name) {
            document.querySelectorAll('.task-row.selected').forEach(r => r.classList.remove('selected'));
            el.classList.add('selected');
            selectedTaskName = name;
            updateCrudButtons();
        }

        function updateCrudButtons() {
            const sel = selectedTaskName !== null;
            document.getElementById('btnEdit').disabled = !sel;
            document.getElementById('btnCopy').disabled = !sel;
            document.getElementById('btnDelete').disabled = !sel;
            document.getElementById('btnRun').disabled = !sel;
        }

        function filterTable() { renderTable(); }

        async function toggleTask(btn) {
            let name = decodeURIComponent(btn.getAttribute('data-task'));
            let isDisabled = btn.getAttribute('data-disabled') === 'true';
            let action = isDisabled ? 'enable' : 'disable';
            btn.disabled = true;
            try {
                const r = await fetch('/api/task/' + action, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name}) });
                const d = await r.json();
                if (d.error) alert('Error: ' + d.error);
                refreshTasks();
            } catch(e) { alert('Error: ' + e.message); }
            btn.disabled = false;
        }

        async function runSelectedTask() {
            if (!selectedTaskName) return;
            try {
                const r = await fetch('/api/task/run', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:selectedTaskName}) });
                const d = await r.json();
                if (d.error) alert('Error: ' + d.error);
                setTimeout(refreshTasks, 1000);
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function deleteSelectedTask() {
            if (!selectedTaskName) return;
            if (!confirm('Delete task "' + selectedTaskName + '"?')) return;
            try {
                const r = await fetch('/api/task/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:selectedTaskName}) });
                const d = await r.json();
                if (d.error) alert('Error: ' + d.error);
                selectedTaskName = null;
                refreshTasks();
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function openEditModal() {
            if (!selectedTaskName) return;
            await editTask(selectedTaskName);
        }

        async function openCopyModal() {
            if (!selectedTaskName) return;
            const newName = prompt('New name for copy:', selectedTaskName + ' (Copy)');
            if (!newName) return;
            try {
                const r = await fetch('/api/task/copy', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:selectedTaskName, new_name:newName}) });
                const d = await r.json();
                if (d.error) alert('Error: ' + d.error);
                refreshTasks();
            } catch(e) { alert('Error: ' + e.message); }
        }

        function openCreateModal() {
            document.getElementById('editMode').value = 'false';
            document.getElementById('modalTitle').textContent = 'Create Task';
            clearForm();
            document.getElementById('taskModal').classList.add('active');
        }

        async function editTask(name) {
            try {
                const r = await fetch('/api/task/get?name=' + encodeURIComponent(name));
                const d = await r.json();
                if (d.error) { alert('Error: ' + d.error); return; }
                document.getElementById('editMode').value = 'true';
                document.getElementById('modalTitle').textContent = 'Edit Task: ' + name;
                document.getElementById('taskName').value = name;
                document.getElementById('taskName').disabled = true;
                document.getElementById('taskProgram').value = d.program || '';
                document.getElementById('taskArgs').value = d.args || '';
                document.getElementById('taskWorkDir').value = d.work_dir || '';
                document.getElementById('taskTrigger').value = d.trigger_type || 'daily';
                if (d.start) {
                    const dt = d.start.replace(' ', 'T').substring(0, 16);
                    document.getElementById('taskStart').value = dt;
                }
                if (d.end) {
                    const dt = d.end.replace(' ', 'T').substring(0, 16);
                    document.getElementById('taskEnd').value = dt;
                }
                document.getElementById('taskRepeat').value = d.repeat || '';
                onTriggerChange();
                if (d.trigger_type === 'weekly' && d.days_of_week) {
                    document.querySelectorAll('.dow').forEach(cb => {
                        cb.checked = d.days_of_week.includes(parseInt(cb.value));
                    });
                }
                if (d.trigger_type === 'monthly' && d.days_of_month) {
                    document.getElementById('taskMonthDays').value = d.days_of_month;
                }
                document.getElementById('taskModal').classList.add('active');
            } catch(e) { alert('Error: ' + e.message); }
        }

        function clearForm() {
            document.getElementById('taskName').value = '';
            document.getElementById('taskName').disabled = false;
            document.getElementById('taskProgram').value = '';
            document.getElementById('taskArgs').value = '';
            document.getElementById('taskWorkDir').value = '';
            document.getElementById('taskRunAs').value = 'SYSTEM';
            document.getElementById('taskPassword').value = '';
            document.getElementById('taskTrigger').value = 'daily';
            document.getElementById('taskStart').value = '';
            document.getElementById('taskEnd').value = '';
            document.getElementById('taskRepeat').value = '';
            document.getElementById('taskMonthDays').value = '';
            document.querySelectorAll('.dow').forEach(cb => cb.checked = false);
            onTriggerChange();
        }

        function closeModal() { document.getElementById('taskModal').classList.remove('active'); }

        function onTriggerChange() {
            const v = document.getElementById('taskTrigger').value;
            document.getElementById('weekDaysRow').style.display = v === 'weekly' ? 'block' : 'none';
            document.getElementById('monthDaysRow').style.display = v === 'monthly' ? 'block' : 'none';
        }

        async function saveTask() {
            const isUpdate = document.getElementById('editMode').value === 'true';
            const data = {
                name: document.getElementById('taskName').value,
                program: document.getElementById('taskProgram').value,
                args: document.getElementById('taskArgs').value,
                work_dir: document.getElementById('taskWorkDir').value,
                run_as: document.getElementById('taskRunAs').value,
                password: document.getElementById('taskPassword').value,
                trigger_type: document.getElementById('taskTrigger').value,
                start: document.getElementById('taskStart').value,
                end: document.getElementById('taskEnd').value,
                repeat: document.getElementById('taskRepeat').value,
                days_of_week: [],
                days_of_month: document.getElementById('taskMonthDays').value,
            };
            document.querySelectorAll('.dow:checked').forEach(cb => data.days_of_week.push(parseInt(cb.value)));
            const url = isUpdate ? '/api/task/update' : '/api/task/create';
            try {
                const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
                const d = await r.json();
                if (d.error) { alert('Error: ' + d.error); return; }
                closeModal();
                refreshTasks();
            } catch(e) { alert('Error: ' + e.message); }
        }

        function toggleFilter() { document.getElementById('filterPanel').classList.toggle('active'); }

        async function applyFilter() {
            const checked = [];
            document.querySelectorAll('#filterList input[type="checkbox"]:checked').forEach(cb => checked.push(cb.value));
            visibleTasks = checked.length > 0 ? checked : null;
            try {
                await fetch('/api/view', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({visible:visibleTasks}) });
            } catch(e) {}
            renderTable();
            document.getElementById('filterPanel').classList.remove('active');
        }

        function showAllTasks() { visibleTasks = null; renderTable(); }
        function hideAllTasks() { visibleTasks = []; renderTable(); }

        function renderFilterList() {
            let html = '';
            allTasks.forEach(t => {
                const checked = !visibleTasks || visibleTasks.includes(t.Name) ? 'checked' : '';
                html += '<div class="filter-item"><input type="checkbox" value="' + t.Name + '" ' + checked + '><span>' + t.Name + '</span></div>';
            });
            document.getElementById('filterList').innerHTML = html || '<div style="color:#999;font-size:12px;">No tasks</div>';
        }

        function updateClock() {
            const now = new Date();
            const hh = String(now.getHours()).padStart(2, '0');
            const mm = String(now.getMinutes()).padStart(2, '0');
            const el = document.getElementById('headerTime');
            if (el) el.textContent = hh + ':' + mm;
        }

        refreshTasks();
        startRefresh();
        updateClock();
        setInterval(updateClock, 60000);
        checkAdminStatus();

        const origRenderFilter = renderFilterList;
        renderFilterList = function() { origRenderFilter(); };
        setInterval(() => { if (document.getElementById('filterPanel').classList.contains('active')) renderFilterList(); }, 5000);
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    print("=" * 50)
    print(f"  Task Scheduler {VERSION} - Web Server")
    print(f"  http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    app.run(host=args.host, port=args.port, debug=False)
