import os
import json
import time
import platform
import subprocess
import logging
import socket
import argparse
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
import psutil

VERSION = '1.5'

app = Flask(__name__)


def get_server_info():
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


def get_nic_list():
    nics = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    for name, addr_list in addrs.items():
        ip = ''
        for a in addr_list:
            if a.family.name == 'AF_INET':
                ip = a.address
        if ip and name in stats and stats[name].isup:
            nics.append({'name': name, 'ip': ip})
    return nics


_prev_net = None


def get_net_usage():
    global _prev_net
    current = psutil.net_io_counters(pernic=True)
    now = time.time()
    result = {}
    if _prev_net is None:
        _prev_net = (current, now)
        for name in current:
            result[name] = {'bytes_sent': 0, 'bytes_recv': 0}
        return result
    prev_counters, prev_time = _prev_net
    dt = now - prev_time
    if dt <= 0:
        dt = 1
    for name, counters in current.items():
        prev = prev_counters.get(name)
        if prev:
            result[name] = {
                'bytes_sent': round((counters.bytes_sent - prev.bytes_sent) / dt / 1024, 1),
                'bytes_recv': round((counters.bytes_recv - prev.bytes_recv) / dt / 1024, 1),
            }
        else:
            result[name] = {'bytes_sent': 0, 'bytes_recv': 0}
    _prev_net = (current, now)
    return result


def get_system_info():
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    uname = platform.uname()

    cpu_name = uname.processor or 'Unknown'
    cpu_list = []
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_Processor | Select-Object DeviceID, Name | ConvertTo-Json -Compress'],
            capture_output=True, timeout=5
        )
        out = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        if out:
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for c in data:
                cpu_list.append({'id': c.get('DeviceID', ''), 'name': c.get('Name', 'Unknown')})
            if cpu_list:
                cpu_name = cpu_list[0]['name']
    except Exception:
        pass

    gpu_list = []
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name', '--format=csv,noheader'],
            capture_output=True, timeout=5
        )
        out = result.stdout.decode('utf-8', errors='replace').strip() if result.stdout else ''
        if out:
            for line in out.split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    gpu_list.append({'index': parts[0], 'name': parts[1]})
    except Exception:
        pass

    gpus = [g['name'] for g in gpu_list] if gpu_list else ['Unknown']

    uptime_seconds = time.time() - psutil.boot_time()
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    mins = int((uptime_seconds % 3600) // 60)
    uptime = f'{days}d {hours}h {mins}m'

    return {
        'hostname': uname.node,
        'os': f'{uname.system} {uname.release}',
        'os_version': uname.version,
        'os_build': uname.version,
        'arch': uname.machine,
        'cpu': cpu_name,
        'cpu_cores': psutil.cpu_count(logical=False),
        'cpu_threads': psutil.cpu_count(logical=True),
        'cpu_freq': f'{cpu_freq.current:.0f} MHz' if cpu_freq else 'Unknown',
        'ram_total': f'{round(mem.total / (1024**3), 1)} GB',
        'ram_used': f'{round(mem.used / (1024**3), 1)} GB',
        'ram_free': f'{round(mem.available / (1024**3), 1)} GB',
        'gpus': gpus,
        'cpu_list': cpu_list,
        'gpu_list': gpu_list,
        'nics': get_nic_list(),
        'uptime': uptime,
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S'),
    }


def get_usage():
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk_io = psutil.disk_io_counters()
    return {
        'cpu': cpu,
        'ram_percent': mem.percent,
        'ram_used': round(mem.used / (1024**3), 1),
        'ram_total': round(mem.total / (1024**3), 1),
        'disk_read': round(disk_io.read_bytes / (1024**2), 1) if disk_io else 0,
        'disk_write': round(disk_io.write_bytes / (1024**2), 1) if disk_io else 0,
    }


DISK_MODELS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_get_disk_models.ps1')
_disk_models_cache = None


def get_disk_models():
    global _disk_models_cache
    if _disk_models_cache is not None:
        return _disk_models_cache
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', DISK_MODELS_PATH],
            capture_output=True, timeout=10
        )
        out = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        if out:
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            _disk_models_cache = {d['Letter']: {'model': d['Model'], 'type': d.get('MediaType', 'Unknown'), 'label': d.get('Label', '')} for d in data}
            return _disk_models_cache
    except Exception:
        pass
    _disk_models_cache = {}
    return {}


def get_disk_info():
    models = get_disk_models()
    disks = []
    for p in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(p.mountpoint)
            device_key = p.device.replace('\\', '')
            info = models.get(device_key, {'model': 'Unknown', 'type': 'Unknown', 'label': ''})
            display_name = info['label'] if info['label'] else ''
            disks.append({
                'device': p.device,
                'mountpoint': p.mountpoint,
                'fstype': p.fstype,
                'model': display_name,
                'media_type': info['type'],
                'total': round(usage.total / (1024**3), 1),
                'used': round(usage.used / (1024**3), 1),
                'free': round(usage.free / (1024**3), 1),
                'percent': usage.percent,
            })
        except PermissionError:
            pass
    return disks


def get_smart_data(device):
    drive_letter = device.replace('\\', '').replace(':', '')
    cmd = f"""
$letter = '{drive_letter}:'
$partObj = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$letter'"
if ($partObj) {{
    $diskPart = $partObj | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($diskPart) {{
        $physDisk = $diskPart | Get-CimAssociatedInstance -ResultClassName Win32_DiskDrive -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($physDisk) {{
            $result = @{{}}
            $result['Model'] = $physDisk.Model
            $result['Size'] = [math]::Round($physDisk.Size / 1GB, 1)
            $result['Interface'] = $physDisk.InterfaceType
            $result['Serial'] = $physDisk.SerialNumber
            $result['Health'] = 'OK'
            $smart = Get-WmiObject -Namespace root\\wmi -Class MSStorageDriver_FailurePredictStatus -ErrorAction SilentlyContinue
            if ($smart) {{
                $result['Health'] = if ($smart.PredictFailure) {{ 'FAIL' }} else {{ 'OK' }}
                $result['PredictFailure'] = $smart.PredictFailure
            }}
            $attrs = Get-WmiObject -Namespace root\\wmi -Class MSStorageDriver_FailurePredictData -ErrorAction SilentlyContinue
            if ($attrs) {{
                $items = @()
                foreach ($a in $attrs) {{
                    $items += @{{
                        ID = $a.AttributeID
                        Value = $a.CurrentValue
                        Worst = $a.WorstValue
                        Threshold = $a.Threshold
                    }}
                }}
                $result['Attributes'] = $items
            }}
            $result | ConvertTo-Json -Compress
        }} else {{
            @{{ 'Error' = 'Physical disk not found' }} | ConvertTo-Json -Compress
        }}
    }} else {{
        @{{ 'Error' = 'Partition not found' }} | ConvertTo-Json -Compress
    }}
}} else {{
    @{{ 'Error' = 'Logical disk not found' }} | ConvertTo-Json -Compress
}}
"""
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', cmd],
            capture_output=True, timeout=15
        )
        out = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        if out:
            return json.loads(out)
        stderr = result.stderr.decode('cp866', errors='replace').strip() if result.stderr else ''
        return {'Error': stderr or 'No output'}
    except Exception as e:
        return {'Error': str(e)}


def get_gpu_usage(gpu_index=0):
    try:
        result = subprocess.run(
            ['nvidia-smi', f'--id={gpu_index}', '--query-gpu=name,utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, timeout=5
        )
        out = result.stdout.decode('utf-8', errors='replace').strip() if result.stdout else ''
        if out:
            parts = [p.strip() for p in out.split(',')]
            return {'gpu_name': parts[0], 'gpu_percent': float(parts[1]), 'vram_used': float(parts[2]), 'vram_total': float(parts[3])}
    except Exception:
        pass
    return {'gpu_name': 'Unknown', 'gpu_percent': 0, 'vram_used': 0, 'vram_total': 0}


def get_all_info():
    info = get_system_info()
    info['disk_info'] = get_disk_info()
    net_io = psutil.net_io_counters()
    info['net_total_sent'] = f'{round(net_io.bytes_sent / (1024**3), 2)} GB'
    info['net_total_recv'] = f'{round(net_io.bytes_recv / (1024**3), 2)} GB'
    partitions = psutil.disk_partitions()
    disk_total = 0
    disk_used = 0
    for p in partitions:
        try:
            u = psutil.disk_usage(p.mountpoint)
            disk_total += u.total
            disk_used += u.used
        except PermissionError:
            pass
    info['disk_total'] = f'{round(disk_total / (1024**3), 1)} GB'
    info['disk_used'] = f'{round(disk_used / (1024**3), 1)} GB'
    info['disk_free'] = f'{round((disk_total - disk_used) / (1024**3), 1)} GB'
    info['cpu_list'] = []
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | ConvertTo-Json -Compress'],
            capture_output=True, timeout=15
        )
        out = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        if out:
            cpu_data = json.loads(out)
            if isinstance(cpu_data, dict):
                cpu_data = [cpu_data]
            for c in cpu_data:
                info['cpu_list'].append({
                    'name': c.get('Name', 'Unknown'),
                    'cores': c.get('NumberOfCores', '?'),
                    'threads': c.get('NumberOfLogicalProcessors', '?'),
                    'freq': c.get('MaxClockSpeed', '?'),
                })
    except Exception:
        pass
    info['gpu_list'] = []
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor | ConvertTo-Json -Compress'],
            capture_output=True, timeout=15
        )
        out = result.stdout.decode('cp866', errors='replace').strip() if result.stdout else ''
        if out:
            gpu_data = json.loads(out)
            if isinstance(gpu_data, dict):
                gpu_data = [gpu_data]
            for g in gpu_data:
                vram = g.get('AdapterRAM', 0)
                vram_str = f'{round(vram / (1024**3), 1)} GB' if isinstance(vram, (int, float)) and vram > 0 else 'Unknown'
                info['gpu_list'].append({
                    'name': g.get('Name', 'Unknown'),
                    'vram': vram_str,
                    'driver': g.get('DriverVersion', 'Unknown'),
                    'processor': g.get('VideoProcessor', 'Unknown'),
                })
    except Exception:
        pass
    info['nic_list'] = info.get('nics', [])
    return info


DASHBOARD_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor {{ version }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
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
        .info-grid { display:grid; grid-template-columns:120px 1fr; gap:4px 12px; font-size:12px; }
        .info-label { color:#999; }
        .info-value { color:#f2f2f2; }
        .chart-container { height:120px; position:relative; width:100%; min-width:0; overflow:hidden; }
        .disk-item { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid #333; font-size:12px; }
        .disk-item:last-child { border-bottom:none; }
        .disk-bar { width:200px; height:8px; background:#333; border-radius:4px; overflow:hidden; }
        .disk-bar-fill { height:100%; border-radius:4px; transition:width 0.3s; }
        .refresh-row { display:flex; align-items:center; gap:8px; }
        .refresh-row label { font-size:11px; color:#999; }
        .refresh-row input { width:60px; padding:3px 6px; background:#1a1a1a; border:1px solid #404040; border-radius:3px; color:#f2f2f2; font-size:11px; font-family:inherit; text-align:center; }
        .refresh-row input:focus { outline:none; border-color:#0057b3; }
        .modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100; justify-content:center; align-items:center; }
        .modal-overlay.active { display:flex; }
        .modal { background:#262626; border:1px solid #404040; border-radius:4px; width:600px; max-height:80vh; overflow:hidden; }
        .modal-header { background:#333; padding:10px 14px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #404040; }
        .modal-header h3 { color:#47a8ff; font-size:14px; }
        .modal-close { background:none; border:none; color:#999; font-size:20px; cursor:pointer; }
        .modal-close:hover { color:#f2f2f2; }
        .modal-body { padding:14px; max-height:60vh; overflow-y:auto; }
        .smart-table { width:100%; border-collapse:collapse; font-size:11px; }
        .smart-table th { background:#333; padding:6px 8px; text-align:left; color:#999; border-bottom:1px solid #404040; }
        .smart-table td { padding:6px 8px; border-bottom:1px solid #333; }
        .spinner { display:inline-block; width:30px; height:30px; border:3px solid #404040; border-top-color:#0057b3; border-radius:50%; animation:spin 0.7s linear infinite; }
        @keyframes spin { to { transform:rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Monitor {{ version }}</h1>
            <div class="header-info" id="serverInfo">{{ description }}</div>
        </div>
        <div class="controls"></div>
    </div>
    <div class="content">
        <div id="sysInfoBar" style="background:#262626;border:1px solid #404040;border-radius:3px;padding:8px 14px;margin-bottom:12px;font-size:12px;color:#999;display:flex;justify-content:space-between;align-items:center;">
            <span id="sysInfoText">Loading...</span>
            <button class="btn btn-default btn-sm" onclick="showAllInfo()">All Info</button>
        </div>

        <div class="panel">
            <div class="panel-header">
                <span>CPU / Memory / GPU / Network</span>
                <div class="refresh-row">
                    <label>Refresh:</label>
                    <input type="number" id="refreshInterval" value="5" min="1" max="600" onchange="updateRefresh()">
                    <label>sec</label>
                </div>
            </div>
            <div class="panel-body">
                <div style="display:flex;gap:12px;min-width:0;">
                    <div style="flex:1;min-width:0;">
                        <div style="margin-bottom:4px;">
                            <select id="cpuSelect" style="background:#1a1a1a;border:1px solid #404040;color:#f2f2f2;border-radius:3px;padding:2px 6px;font-size:10px;font-family:inherit;width:100%;max-width:180px;" onchange="selectedCpu=this.value"></select>
                        </div>
                        <div class="chart-container"><canvas id="cpuChart"></canvas></div>
                        <div id="cpuLabel" style="text-align:center;font-size:11px;color:#f2f2f2;margin-top:4px;">CPU</div>
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div style="margin-bottom:4px;">
                            <select style="background:#1a1a1a;border:1px solid #404040;color:transparent;border-radius:3px;padding:2px 6px;font-size:10px;font-family:inherit;width:100%;max-width:180px;pointer-events:none;"><option>-</option></select>
                        </div>
                        <div class="chart-container"><canvas id="memChart"></canvas></div>
                        <div id="memLabel" style="text-align:center;font-size:11px;color:#f2f2f2;margin-top:4px;">Memory</div>
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div style="margin-bottom:4px;">
                            <select id="gpuSelect" style="background:#1a1a1a;border:1px solid #404040;color:#f2f2f2;border-radius:3px;padding:2px 6px;font-size:10px;font-family:inherit;width:100%;max-width:180px;" onchange="selectedGpu=this.value"></select>
                        </div>
                        <div class="chart-container"><canvas id="gpuChart"></canvas></div>
                        <div id="gpuLabel" style="text-align:center;font-size:11px;color:#f2f2f2;margin-top:4px;">GPU</div>
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div style="margin-bottom:4px;">
                            <select style="background:#1a1a1a;border:1px solid #404040;color:transparent;border-radius:3px;padding:2px 6px;font-size:10px;font-family:inherit;width:100%;max-width:180px;pointer-events:none;"><option>-</option></select>
                        </div>
                        <div class="chart-container"><canvas id="vramChart"></canvas></div>
                        <div id="vramLabel" style="text-align:center;font-size:11px;color:#f2f2f2;margin-top:4px;">VRAM</div>
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div style="margin-bottom:4px;">
                            <select id="nicSelect" style="background:#1a1a1a;border:1px solid #404040;color:#f2f2f2;border-radius:3px;padding:2px 6px;font-size:10px;font-family:inherit;width:100%;max-width:180px;" onchange="updateNetLabel()"></select>
                        </div>
                        <div class="chart-container"><canvas id="netChart"></canvas></div>
                        <div id="netLabel" style="text-align:center;font-size:11px;color:#f2f2f2;margin-top:4px;">Network</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <span>Disk Usage</span>
                <button class="btn btn-default btn-sm" onclick="loadDisks()">Refresh</button>
            </div>
            <div class="panel-body" id="diskList"><div class="loading">Loading...</div></div>
        </div>
    </div>

    <div class="modal-overlay" id="smartModal">
        <div class="modal">
            <div class="modal-header">
                <h3>S.M.A.R.T Data</h3>
                <button class="modal-close" onclick="closeSmart()">&times;</button>
            </div>
            <div class="modal-body" id="smartBody"></div>
        </div>
    </div>

    <div class="modal-overlay" id="allInfoModal">
        <div class="modal" style="width:700px;">
            <div class="modal-header">
                <h3>All System Info</h3>
                <div style="display:flex;gap:8px;align-items:center;">
                    <button class="btn btn-primary btn-sm" onclick="copyAllInfo()">Copy to Clipboard</button>
                    <button class="modal-close" onclick="closeAllInfo()">&times;</button>
                </div>
            </div>
            <div class="modal-body" id="allInfoBody"></div>
        </div>
    </div>

    <script>
        let cpuData = [];
        let memData = [];
        let gpuData = [];
        let vramData = [];
        let netData = [];
        let chartLabels = [];
        let cpuChart, memChart, gpuChart, vramChart, netChart;
        let refreshTimer = null;
        let allNicData = {};
        let selectedNic = '';
        let selectedCpu = 'overall';
        let selectedGpu = '0';

        function getInterval() {
            return Math.max(1, parseInt(document.getElementById('refreshInterval').value) || 5);
        }

        function updateRefresh() {
            startRefresh();
        }

        function startRefresh() {
            if (refreshTimer) clearInterval(refreshTimer);
            refreshTimer = setInterval(fetchUsage, getInterval() * 1000);
        }

        function initCharts() {
            const opts = { responsive:true, maintainAspectRatio:false, animation:{duration:0},
                scales:{ y:{ min:0, max:100, ticks:{color:'#999',font:{size:10}}, grid:{color:'#333'} },
                         x:{ ticks:{color:'#999',font:{size:10}}, grid:{color:'#333'} } },
                plugins:{ legend:{display:false} } };
            cpuChart = new Chart(document.getElementById('cpuChart'), { type:'line',
                data:{ labels:chartLabels, datasets:[{ data:cpuData, borderColor:'#0057b3', backgroundColor:'rgba(0,87,179,0.1)', fill:true, tension:0.3, pointRadius:0 }] }, options:opts });
            memChart = new Chart(document.getElementById('memChart'), { type:'line',
                data:{ labels:chartLabels, datasets:[{ data:memData, borderColor:'#21bf4b', backgroundColor:'rgba(33,191,75,0.1)', fill:true, tension:0.3, pointRadius:0 }] }, options:opts });
            gpuChart = new Chart(document.getElementById('gpuChart'), { type:'line',
                data:{ labels:chartLabels, datasets:[{ data:gpuData, borderColor:'#ffcc00', backgroundColor:'rgba(255,204,0,0.1)', fill:true, tension:0.3, pointRadius:0 }] }, options:opts });
            vramChart = new Chart(document.getElementById('vramChart'), { type:'line',
                data:{ labels:chartLabels, datasets:[{ data:vramData, borderColor:'#ff6c59', backgroundColor:'rgba(255,108,89,0.1)', fill:true, tension:0.3, pointRadius:0 }] }, options:opts });
            const netOpts = JSON.parse(JSON.stringify(opts));
            netOpts.scales.y = { min:0, ticks:{color:'#999',font:{size:10},callback:v=>v+'KB/s'}, grid:{color:'#333'} };
            netChart = new Chart(document.getElementById('netChart'), { type:'line',
                data:{ labels:chartLabels, datasets:[
                    { data:netData, borderColor:'#a78bfa', backgroundColor:'rgba(167,139,250,0.1)', fill:true, tension:0.3, pointRadius:0, label:'KB/s' }
                ] }, options:netOpts });
        }

        async function fetchUsage() {
            try {
                const [usageR, netR] = await Promise.all([fetch('/api/usage?gpu=' + selectedGpu), fetch('/api/net')]);
                const d = await usageR.json();
                const net = await netR.json();
                allNicData = net;
                const now = new Date().toLocaleTimeString('ru-RU');
                chartLabels.push(now);
                cpuData.push(d.cpu);
                memData.push(d.ram_percent);
                gpuData.push(d.gpu_percent);
                vramData.push(d.vram_total > 0 ? Math.round(d.vram_used / d.vram_total * 100) : 0);
                const activeNic = selectedNic || Object.keys(net)[0] || '';
                const nicNet = net[activeNic] || {bytes_sent:0, bytes_recv:0};
                netData.push(Math.round((nicNet.bytes_sent + nicNet.bytes_recv)));
                if (chartLabels.length > 60) { chartLabels.shift(); cpuData.shift(); memData.shift(); gpuData.shift(); vramData.shift(); netData.shift(); }
                cpuChart.update(); memChart.update(); gpuChart.update(); vramChart.update(); netChart.update();
                document.getElementById('gpuLabel').textContent = d.gpu_name || 'Unknown GPU';
                const vramUsedGB = (d.vram_used / 1024).toFixed(1);
                const vramTotalGB = (d.vram_total / 1024).toFixed(1);
                const vramFreeGB = ((d.vram_total - d.vram_used) / 1024).toFixed(1);
                document.getElementById('vramLabel').textContent = 'Total: ' + vramTotalGB + ' GB / Used: ' + vramUsedGB + ' GB / Free: ' + vramFreeGB + ' GB';
                updateNetLabel();
            } catch(e) {}
        }

        function updateNetLabel() {
            const sel = document.getElementById('nicSelect');
            if (sel && sel.value) selectedNic = sel.value;
            const nic = allNicData[selectedNic] || {};
            const sent = (nic.bytes_sent || 0).toFixed(1);
            const recv = (nic.bytes_recv || 0).toFixed(1);
            document.getElementById('netLabel').textContent = (selectedNic || '-') + ' | UP ' + sent + ' KB/s | DOWN ' + recv + ' KB/s';
        }

        async function loadSystemInfo() {
            try {
                const r = await fetch('/api/system');
                const d = await r.json();
                document.getElementById('sysInfoText').innerHTML =
                    '<strong>' + d.hostname + '</strong> &nbsp;|&nbsp; ' + d.os + ' (' + d.os_build + ') ' + d.arch
                    + ' &nbsp;|&nbsp; Uptime: ' + d.uptime;
                document.getElementById('cpuLabel').textContent = d.cpu + ' / ' + d.cpu_cores + ' cores / ' + d.cpu_threads + ' threads';
                document.getElementById('memLabel').textContent = 'Total: ' + d.ram_total + ' / Used: ' + d.ram_used + ' / Free: ' + d.ram_free;
                const cpuSel = document.getElementById('cpuSelect');
                if (d.cpu_list && d.cpu_list.length > 1) {
                    cpuSel.innerHTML = '<option value="overall">Overall</option>';
                    d.cpu_list.forEach(c => {
                        const opt = document.createElement('option');
                        opt.value = c.id;
                        opt.textContent = c.name.substring(0, 30);
                        cpuSel.appendChild(opt);
                    });
                } else {
                    cpuSel.innerHTML = '<option value="overall">' + (d.cpu_list && d.cpu_list[0] ? d.cpu_list[0].name.substring(0, 30) : 'CPU') + '</option>';
                }
                const gpuSel = document.getElementById('gpuSelect');
                if (d.gpu_list && d.gpu_list.length > 0) {
                    gpuSel.innerHTML = '';
                    d.gpu_list.forEach(g => {
                        const opt = document.createElement('option');
                        opt.value = g.index;
                        opt.textContent = g.name.substring(0, 30);
                        gpuSel.appendChild(opt);
                    });
                }
                const sel = document.getElementById('nicSelect');
                if (d.nics && d.nics.length > 0) {
                    sel.innerHTML = '';
                    d.nics.forEach(n => {
                        const opt = document.createElement('option');
                        opt.value = n.name;
                        opt.textContent = n.name + ' (' + n.ip + ')';
                        sel.appendChild(opt);
                    });
                    selectedNic = d.nics[0].name;
                }
            } catch(e) {}
        }

        async function loadDisks() {
            try {
                const r = await fetch('/api/disks');
                const disks = await r.json();
                let html = '';
                disks.forEach(d => {
                    let color = d.percent < 70 ? '#21bf4b' : d.percent < 90 ? '#ffcc00' : '#ff6c59';
                    let typeLabel = d.media_type || 'Unknown';
                    html += '<div class="disk-item" style="display:grid;grid-template-columns:35px 55px 50px 130px 200px 1fr;gap:8px;align-items:center;">'
                        + '<strong>'+d.device+'</strong>'
                        + '<span style="color:#47a8ff;font-size:11px;">'+typeLabel+'</span>'
                        + '<span style="color:#999;font-size:11px;">'+d.fstype+'</span>'
                        + '<span style="font-size:11px;color:#ccc;">[ '+d.total+' GB ] '+d.used+' / '+d.free+'</span>'
                        + '<span style="font-size:11px;color:#999;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="'+d.model+'">'+d.model+'</span>'
                        + '<div class="disk-bar"><div class="disk-bar-fill" style="width:'+d.percent+'%;background:'+color+'"></div></div>'
                        + '</div>';
                });
                document.getElementById('diskList').innerHTML = html || '<div class="info-label">No disks found</div>';
            } catch(e) {}
        }

        async function showSmart(device) {
            document.getElementById('smartBody').innerHTML = '<div class="loading">Loading S.M.A.R.T data...</div>';
            document.getElementById('smartModal').classList.add('active');
            try {
                const r = await fetch('/api/smart', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({device:device}) });
                const d = await r.json();
                let html = '<div class="info-grid" style="margin-bottom:12px;">';
                html += '<div class="info-label">Model</div><div class="info-value">'+(d.Model||'N/A')+'</div>';
                html += '<div class="info-label">Size</div><div class="info-value">'+(d.Size||'N/A')+' GB</div>';
                html += '<div class="info-label">Health</div><div class="info-value">'+(d.Health||'N/A')+'</div>';
                html += '<div class="info-label">Interface</div><div class="info-value">'+(d.Interface||'N/A')+'</div>';
                html += '</div>';
                if (d.Attributes && d.Attributes.length > 0) {
                    html += '<table class="smart-table"><thead><tr><th>ID</th><th>Value</th><th>Worst</th><th>Threshold</th></tr></thead><tbody>';
                    d.Attributes.forEach(a => { html += '<tr><td>'+a.ID+'</td><td>'+a.Value+'</td><td>'+a.Worst+'</td><td>'+a.Threshold+'</td></tr>'; });
                    html += '</tbody></table>';
                }
                if (d.Error) { html = '<div style="color:#ff6c59">'+d.Error+'</div>'; }
                document.getElementById('smartBody').innerHTML = html;
            } catch(e) { document.getElementById('smartBody').innerHTML = '<div style="color:#ff6c59">Error loading S.M.A.R.T</div>'; }
        }

        function closeSmart() { document.getElementById('smartModal').classList.remove('active'); }

        function updateClock() {
            const now = new Date();
            const hh = String(now.getHours()).padStart(2, '0');
            const mm = String(now.getMinutes()).padStart(2, '0');
            const el = document.getElementById('headerTime');
            if (el) el.textContent = hh + ':' + mm;
        }

        async function showAllInfo() {
            document.getElementById('allInfoBody').innerHTML = '<div style="text-align:center;padding:40px;"><div class="spinner"></div><div style="margin-top:12px;color:#999;">Collecting system information...</div></div>';
            document.getElementById('allInfoModal').classList.add('active');
            try {
                const r = await fetch('/api/all-info');
                const d = await r.json();
                let text = '';
                let html = '<div style="font-family:monospace;font-size:12px;white-space:pre-wrap;line-height:1.6;">';
                html += '<strong>=== SYSTEM ===</strong>\n';
                html += 'Hostname: ' + d.hostname + '\n';
                html += 'OS: ' + d.os + ' Build ' + d.os_build + '\n';
                html += 'Arch: ' + d.arch + '\n';
                html += 'Uptime: ' + d.uptime + '\n';
                html += 'Boot: ' + d.boot_time + '\n\n';
                html += '<strong>=== CPU ===</strong>\n';
                (d.cpu_list || []).forEach((c,i) => {
                    html += 'CPU ' + (i+1) + ': ' + c.name + '\n';
                    html += '  Cores: ' + c.cores + ' / Threads: ' + c.threads + ' / Freq: ' + c.freq + ' MHz\n';
                });
                html += '\n<strong>=== MEMORY ===</strong>\n';
                html += 'Total: ' + d.ram_total + ' / Used: ' + d.ram_used + ' / Free: ' + d.ram_free + '\n\n';
                html += '<strong>=== GPU ===</strong>\n';
                (d.gpu_list || []).forEach((g,i) => {
                    html += 'GPU ' + (i+1) + ': ' + g.name + '\n';
                    html += '  VRAM: ' + g.vram + ' / Driver: ' + g.driver + '\n';
                    html += '  Processor: ' + g.processor + '\n';
                });
                html += '\n<strong>=== DISKS ===</strong>\n';
                (d.disk_info || []).forEach(dk => {
                    html += dk.device + ' (' + dk.model + ') ' + dk.fstype + ' - ' + dk.used + '/' + dk.total + ' GB (' + dk.percent + '%)\n';
                });
                html += 'Total: ' + d.disk_total + ' / Used: ' + d.disk_used + ' / Free: ' + d.disk_free + '\n\n';
                html += '<strong>=== NETWORK ===</strong>\n';
                (d.nic_list || []).forEach(n => {
                    html += n.name + ': ' + n.ip + '\n';
                });
                html += 'Total sent: ' + d.net_total_sent + ' / recv: ' + d.net_total_recv + '\n';
                html += '</div>';
                text = 'Hostname: ' + d.hostname + '\nOS: ' + d.os + ' Build ' + d.os_build + '\nArch: ' + d.arch + '\nUptime: ' + d.uptime + '\n\n';
                text += '=== CPU ===\n';
                (d.cpu_list || []).forEach((c,i) => { text += 'CPU ' + (i+1) + ': ' + c.name + ' / ' + c.cores + ' cores / ' + c.threads + ' threads / ' + c.freq + ' MHz\n'; });
                text += '\n=== MEMORY ===\nTotal: ' + d.ram_total + ' / Used: ' + d.ram_used + ' / Free: ' + d.ram_free + '\n';
                text += '\n=== GPU ===\n';
                (d.gpu_list || []).forEach((g,i) => { text += 'GPU ' + (i+1) + ': ' + g.name + ' / VRAM: ' + g.vram + ' / Driver: ' + g.driver + '\n'; });
                text += '\n=== DISKS ===\n';
                (d.disk_info || []).forEach(dk => { text += dk.device + ' (' + dk.model + ') ' + dk.used + '/' + dk.total + ' GB (' + dk.percent + '%)\n'; });
                text += 'Total: ' + d.disk_total + ' / Used: ' + d.disk_used + ' / Free: ' + d.disk_free + '\n';
                text += '\n=== NETWORK ===\n';
                (d.nic_list || []).forEach(n => { text += n.name + ': ' + n.ip + '\n'; });
                text += 'Total sent: ' + d.net_total_sent + ' / recv: ' + d.net_total_recv + '\n';
                document.getElementById('allInfoBody').innerHTML = html;
                window._allInfoText = text;
            } catch(e) { document.getElementById('allInfoBody').innerHTML = '<div style="color:#ff6c59">Error loading info</div>'; }
        }

        function copyAllInfo() {
            if (window._allInfoText) {
                navigator.clipboard.writeText(window._allInfoText).then(() => { alert('Copied to clipboard!'); });
            }
        }

        function closeAllInfo() { document.getElementById('allInfoModal').classList.remove('active'); }

        loadSystemInfo();
        initCharts();
        fetchUsage();
        startRefresh();
        loadDisks();

        function resizeCharts() {
            if (cpuChart) cpuChart.resize();
            if (memChart) memChart.resize();
            if (gpuChart) gpuChart.resize();
            if (vramChart) vramChart.resize();
            if (netChart) netChart.resize();
        }

        window.addEventListener('resize', resizeCharts);

        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(resizeCharts).observe(document.body);
        }

        window.addEventListener('message', function(e) {
            if (e.data === 'resize') {
                setTimeout(resizeCharts, 100);
                setTimeout(resizeCharts, 300);
            }
        });
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
    return render_template_string(DASHBOARD_TEMPLATE, version=VERSION, description=description)


@app.route('/api/system')
def api_system():
    return jsonify(get_system_info())


@app.route('/api/usage')
def api_usage():
    gpu_index = request.args.get('gpu', 0, type=int)
    data = get_usage()
    data.update(get_gpu_usage(gpu_index))
    return jsonify(data)


@app.route('/api/disks')
def api_disks():
    return jsonify(get_disk_info())


@app.route('/api/smart', methods=['POST'])
def api_smart():
    data = request.get_json()
    device = data.get('device', '')
    if not device:
        return jsonify({'error': 'No device'}), 400
    return jsonify(get_smart_data(device))


@app.route('/api/net')
def api_net():
    return jsonify(get_net_usage())


@app.route('/api/all-info')
def api_all_info():
    return jsonify(get_all_info())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'module.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('Monitor %s started', VERSION)

    print("=" * 50)
    print(f"  Monitor {VERSION} - System Dashboard")
    print(f"  http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    app.run(host=args.host, port=args.port, debug=False)
