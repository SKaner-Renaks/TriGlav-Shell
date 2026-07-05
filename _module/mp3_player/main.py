import os
import json
import glob
import argparse
import logging
import configparser
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, send_from_directory

VERSION = '1.0'

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, 'music')
PLAYLISTS_DIR = os.path.join(BASE_DIR, 'playlists')
SHELL_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
CONFIG_PATH = os.path.join(SHELL_DIR, '_data', 'config.cfg')

os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(PLAYLISTS_DIR, exist_ok=True)


def get_theme():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding='utf-8')
    return cfg.get('shell', 'global_theme', fallback='dark')


def scan_music():
    tracks = []
    for root, dirs, files in os.walk(MUSIC_DIR):
        for f in files:
            if f.lower().endswith('.mp3'):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, MUSIC_DIR).replace('\\', '/')
                meta = read_tags(full)
                meta['file'] = rel
                meta['filename'] = f
                tracks.append(meta)
    tracks.sort(key=lambda t: (t.get('artist', ''), t.get('album', ''), t.get('title', t['filename'])))
    return tracks


def read_tags(filepath):
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, TDRC
        audio = MP3(filepath, ID3=ID3)
        tags = audio.get('TIT2')
        artist = audio.get('TPE1')
        album = audio.get('TALB')
        year = audio.get('TDRC')
        duration = int(audio.info.length) if audio.info else 0
        has_cover = any(isinstance(t, APIC) for t in audio.tags.values()) if audio.tags else False
        return {
            'title': str(tags) if tags else '',
            'artist': str(artist) if artist else '',
            'album': str(album) if album else '',
            'year': str(year) if year else '',
            'duration': duration,
            'has_cover': has_cover,
        }
    except Exception:
        return {'title': '', 'artist': '', 'album': '', 'year': '', 'duration': 0, 'has_cover': False}


@app.route('/')
def index():
    theme = get_theme()
    return render_template_string(PLAYER_TEMPLATE, version=VERSION, theme=theme)


@app.route('/api/tracks')
def api_tracks():
    return jsonify(scan_music())


@app.route('/music/<path:filepath>')
def serve_music(filepath):
    return send_from_directory(MUSIC_DIR, filepath)


@app.route('/api/cover/<path:filepath>')
def serve_cover(filepath):
    try:
        from mutagen.id3 import ID3, APIC
        full = os.path.join(MUSIC_DIR, filepath)
        tags = ID3(full)
        for t in tags.values():
            if isinstance(t, APIC):
                return t.data, 200, {'Content-Type': t.mime}
    except Exception:
        pass
    return '', 404


@app.route('/api/playlists')
def api_playlists_list():
    playlists = []
    for f in os.listdir(PLAYLISTS_DIR):
        if f.endswith('.json'):
            try:
                with open(os.path.join(PLAYLISTS_DIR, f), 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    playlists.append({'name': data.get('name', f[:-5]), 'tracks': len(data.get('tracks', []))})
            except Exception:
                pass
    return jsonify(playlists)


@app.route('/api/playlist/<name>')
def api_playlist_get(name):
    path = os.path.join(PLAYLISTS_DIR, name + '.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/playlist', methods=['POST'])
def api_playlist_save():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    safe = name.replace('/', '_').replace('\\', '_')
    payload = {
        'name': name,
        'tracks': data.get('tracks', []),
        'created': data.get('created', datetime.now().strftime('%Y-%m-%d %H:%M')),
    }
    path = os.path.join(PLAYLISTS_DIR, safe + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return jsonify({'status': 'ok', 'name': name})


@app.route('/api/playlist/<name>', methods=['DELETE'])
def api_playlist_delete(name):
    path = os.path.join(PLAYLISTS_DIR, name + '.json')
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Not found'}), 404


PLAYER_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MP3 Player {{ version }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        {% if theme == 'light' %}
        :root {
            --bg: #f5f5f5;
            --panel: #ffffff;
            --text: #1a1a1a;
            --accent: #0066cc;
            --border: #d0d0d0;
            --muted: #666;
            --hover: #e8e8e8;
            --active: #d0d0d0;
        }
        {% else %}
        :root {
            --bg: #1a1a1a;
            --panel: #262626;
            --text: #f2f2f2;
            --accent: #47a8ff;
            --border: #404040;
            --muted: #999;
            --hover: #333;
            --active: #404040;
        }
        {% endif %}

        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
            font-size: 13px;
        }

        /* HEADER */
        .header {
            background: var(--panel);
            border-bottom: 1px solid var(--border);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }
        .header h1 { font-size: 16px; font-weight: 600; color: var(--accent); }
        .header-controls { display: flex; gap: 8px; align-items: center; }
        .vol-wrap { display: flex; align-items: center; gap: 6px; }
        .vol-wrap label { font-size: 11px; color: var(--muted); }
        input[type=range] {
            -webkit-appearance: none;
            width: 100px;
            height: 4px;
            background: var(--border);
            border-radius: 2px;
            outline: none;
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            background: var(--accent);
            border-radius: 50%;
            cursor: pointer;
        }

        /* MAIN LAYOUT */
        .main {
            flex: 1;
            display: flex;
            overflow: hidden;
        }

        /* LEFT PANEL */
        .left {
            width: 320px;
            min-width: 240px;
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            background: var(--panel);
        }
        .left-section { padding: 10px 14px; }
        .left-section h3 {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--muted);
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .left-section h3 button {
            background: none;
            border: 1px solid var(--border);
            color: var(--accent);
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 3px;
            cursor: pointer;
        }
        .left-section h3 button:hover { background: var(--hover); }

        .pl-list { list-style: none; max-height: 140px; overflow-y: auto; }
        .pl-list li {
            padding: 6px 8px;
            cursor: pointer;
            border-radius: 3px;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .pl-list li:hover { background: var(--hover); }
        .pl-list li.active { background: var(--accent); color: #fff; }
        .pl-list li .pl-count { font-size: 10px; color: var(--muted); }
        .pl-list li.active .pl-count { color: rgba(255,255,255,0.7); }
        .pl-list li .pl-del {
            background: none; border: none; color: var(--muted); cursor: pointer;
            font-size: 14px; line-height: 1; padding: 0 4px;
        }
        .pl-list li .pl-del:hover { color: #ff6c59; }

        .search-box {
            width: 100%;
            padding: 6px 10px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 3px;
            color: var(--text);
            font-size: 12px;
            font-family: inherit;
            margin-bottom: 8px;
        }
        .search-box:focus { outline: none; border-color: var(--accent); }

        .track-list {
            flex: 1;
            overflow-y: auto;
            padding: 0 14px 10px;
        }
        .track-item {
            padding: 7px 8px;
            cursor: pointer;
            border-radius: 3px;
            font-size: 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .track-item:hover { background: var(--hover); }
        .track-item.active { background: var(--accent); color: #fff; }
        .track-item .ti-info { flex: 1; min-width: 0; }
        .track-item .ti-title { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .track-item .ti-artist { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .track-item.active .ti-artist { color: rgba(255,255,255,0.7); }
        .track-item .ti-dur { font-size: 11px; color: var(--muted); margin-left: 8px; flex-shrink: 0; }
        .track-item.active .ti-dur { color: rgba(255,255,255,0.7); }

        /* RIGHT PANEL */
        .right {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            gap: 16px;
            overflow: hidden;
        }

        /* EQ CANVAS */
        .eq-wrap {
            width: 100%;
            max-width: 500px;
            height: 120px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }
        .eq-wrap canvas { width: 100%; height: 100%; display: block; }

        /* NOW PLAYING */
        .np-info { text-align: center; }
        .np-title { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
        .np-artist { font-size: 14px; color: var(--muted); margin-bottom: 2px; }
        .np-file { font-size: 11px; color: var(--muted); font-style: italic; }

        /* PROGRESS */
        .progress-wrap {
            width: 100%;
            max-width: 500px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .progress-wrap .time { font-size: 11px; color: var(--muted); min-width: 40px; }
        .progress-wrap .time:last-child { text-align: right; }
        .progress-bar {
            flex: 1;
            height: 6px;
            background: var(--border);
            border-radius: 3px;
            cursor: pointer;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background: var(--accent);
            border-radius: 3px;
            width: 0%;
            pointer-events: none;
        }

        /* CONTROLS */
        .controls {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .ctrl-btn {
            background: none;
            border: none;
            color: var(--text);
            cursor: pointer;
            font-size: 22px;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: background 0.15s;
        }
        .ctrl-btn:hover { background: var(--hover); }
        .ctrl-btn.play-btn { font-size: 28px; background: var(--accent); color: #fff; width: 56px; height: 56px; }
        .ctrl-btn.play-btn:hover { opacity: 0.85; }
        .ctrl-btn.active-mode { color: var(--accent); }

        /* MODE BUTTONS */
        .mode-btn {
            background: none;
            border: none;
            color: var(--muted);
            cursor: pointer;
            font-size: 16px;
            padding: 6px;
            border-radius: 4px;
            transition: color 0.15s;
        }
        .mode-btn:hover { color: var(--text); }
        .mode-btn.active { color: var(--accent); }

        /* MODAL */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 200;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.active { display: flex; }
        .modal {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 20px;
            width: 340px;
        }
        .modal h3 { font-size: 14px; margin-bottom: 12px; color: var(--accent); }
        .modal input {
            width: 100%;
            padding: 8px 10px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 3px;
            color: var(--text);
            font-size: 13px;
            font-family: inherit;
            margin-bottom: 12px;
        }
        .modal input:focus { outline: none; border-color: var(--accent); }
        .modal-btns { display: flex; gap: 8px; justify-content: flex-end; }
        .modal-btns button {
            padding: 6px 16px;
            border: 1px solid var(--border);
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            font-family: inherit;
            background: var(--panel);
            color: var(--text);
        }
        .modal-btns .btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
        .modal-btns button:hover { opacity: 0.85; }

        .empty-msg { color: var(--muted); font-size: 12px; text-align: center; padding: 20px; }

        /* SCROLLBAR */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--muted); }
    </style>
</head>
<body>
    <div class="header">
        <h1>MP3 Player {{ version }}</h1>
        <div class="header-controls">
            <div class="vol-wrap">
                <label>Vol</label>
                <input type="range" id="volume" min="0" max="100" value="80" oninput="setVolume(this.value)">
            </div>
        </div>
    </div>

    <div class="main">
        <div class="left">
            <div class="left-section">
                <h3>Плейлисты <button onclick="showNewPL()">+ Новый</button></h3>
                <ul class="pl-list" id="plList"></ul>
            </div>
            <div class="left-section" style="padding-top:0;">
                <h3>Треки <span id="trackCount"></span></h3>
                <input class="search-box" id="searchBox" placeholder="Поиск..." oninput="filterTracks()">
            </div>
            <div class="track-list" id="trackList"></div>
        </div>
        <div class="right">
            <div class="eq-wrap"><canvas id="eqCanvas"></canvas></div>
            <div class="np-info">
                <div class="np-title" id="npTitle">—</div>
                <div class="np-artist" id="npArtist"></div>
                <div class="np-file" id="npFile"></div>
            </div>
            <div class="progress-wrap">
                <span class="time" id="curTime">0:00</span>
                <div class="progress-bar" id="progBar" onclick="seek(event)">
                    <div class="progress-fill" id="progFill"></div>
                </div>
                <span class="time" id="totTime">0:00</span>
            </div>
            <div class="controls">
                <button class="mode-btn" id="btnShuffle" onclick="toggleShuffle()" title="Перемешать">🔀</button>
                <button class="ctrl-btn" onclick="prevTrack()" title="Предыдущий">⏮</button>
                <button class="ctrl-btn play-btn" id="btnPlay" onclick="togglePlay()" title="Воспроизвести">▶</button>
                <button class="ctrl-btn" onclick="nextTrack()" title="Следующий">⏭</button>
                <button class="mode-btn" id="btnRepeat" onclick="toggleRepeat()" title="Повтор">🔁</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
        <div class="modal">
            <h3>Новый плейлист</h3>
            <input id="plNameInput" placeholder="Название плейлиста..." onkeydown="if(event.key==='Enter')saveNewPL()">
            <div class="modal-btns">
                <button onclick="closeModal()">Отмена</button>
                <button class="btn-primary" onclick="saveNewPL()">Создать</button>
            </div>
        </div>
    </div>

    <audio id="audio" preload="auto"></audio>

    <script>
        var allTracks = [];
        var playlist = [];
        var plTracks = [];
        var currentIdx = -1;
        var shuffleMode = false;
        var repeatMode = 0;
        var audioCtx, analyser, source, gainNode;
        var eqInited = false;
        var eqData = new Uint8Array(64);

        var audio = document.getElementById('audio');

        /* INIT */
        function init() {
            loadTracks();
            loadPlaylists();
            initEQ();
        }

        /* AUDIO CONTEXT & EQ */
        function initEQ() {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                analyser = audioCtx.createAnalyser();
                analyser.fftSize = 128;
                gainNode = audioCtx.createGain();
                gainNode.gain.value = 0.8;
                eqData = new Uint8Array(analyser.frequencyBinCount);
                drawEQ();
            } catch(e) {}
        }

        function connectSource() {
            if (eqInited) return;
            try {
                source = audioCtx.createMediaElementSource(audio);
                source.connect(analyser);
                analyser.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                eqInited = true;
            } catch(e) {}
        }

        function drawEQ() {
            var canvas = document.getElementById('eqCanvas');
            var ctx = canvas.getContext('2d');
            var w = canvas.parentElement.clientWidth;
            var h = canvas.parentElement.clientHeight;
            canvas.width = w;
            canvas.height = h;

            function frame() {
                requestAnimationFrame(frame);
                if (!analyser) return;
                analyser.getByteFrequencyData(eqData);
                ctx.clearRect(0, 0, w, h);
                var bars = eqData.length;
                var barW = (w / bars) * 1.2;
                var gap = 2;
                for (var i = 0; i < bars; i++) {
                    var val = eqData[i] / 255;
                    var barH = val * h * 0.9;
                    var x = i * (barW + gap);
                    var g = ctx.createLinearGradient(0, h, 0, 0);
                    g.addColorStop(0, '#21bf4b');
                    g.addColorStop(0.5, '#f0c040');
                    g.addColorStop(1, '#ff6c59');
                    ctx.fillStyle = g;
                    ctx.fillRect(x, h - barH, barW, barH);
                }
            }
            frame();
        }

        /* TRACKS */
        function loadTracks() {
            fetch('/api/tracks')
                .then(function(r){ return r.json(); })
                .then(function(data){
                    allTracks = data;
                    playlist = data.map(function(_,i){ return i; });
                    renderTracks();
                });
        }

        function renderTracks() {
            var list = document.getElementById('trackList');
            var q = document.getElementById('searchBox').value.toLowerCase();
            var indices = playlist.filter(function(i){
                var t = allTracks[i];
                if (!t) return false;
                if (!q) return true;
                return (t.title+t.artist+t.album+t.filename).toLowerCase().indexOf(q) !== -1;
            });
            document.getElementById('trackCount').textContent = indices.length + ' / ' + allTracks.length;
            if (!indices.length) {
                list.innerHTML = '<div class="empty-msg">Нет треков</div>';
                return;
            }
            var html = '';
            indices.forEach(function(i){
                var t = allTracks[i];
                var dur = fmtTime(t.duration);
                var title = t.title || t.filename;
                var cls = (i === currentIdx) ? ' active' : '';
                html += '<div class="track-item'+cls+'" onclick="playTrack('+i+')">'
                    + '<div class="ti-info"><div class="ti-title">'+esc(title)+'</div>'
                    + '<div class="ti-artist">'+esc(t.artist||'—')+'</div></div>'
                    + '<div class="ti-dur">'+dur+'</div></div>';
            });
            list.innerHTML = html;
        }

        function filterTracks() { renderTracks(); }

        function esc(s) {
            var d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        function fmtTime(s) {
            if (!s || isNaN(s)) return '0:00';
            var m = Math.floor(s/60);
            var sec = Math.floor(s%60);
            return m+':'+(sec<10?'0':'')+sec;
        }

        /* PLAYBACK */
        function playTrack(idx) {
            if (idx < 0 || idx >= allTracks.length) return;
            connectSource();
            if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
            currentIdx = idx;
            var t = allTracks[idx];
            audio.src = '/music/' + encodeURIComponent(t.file);
            audio.play();
            document.getElementById('btnPlay').textContent = '⏸';
            document.getElementById('npTitle').textContent = t.title || t.filename;
            document.getElementById('npArtist').textContent = [t.artist, t.album].filter(Boolean).join(' — ');
            document.getElementById('npFile').textContent = t.file;
            document.getElementById('totTime').textContent = fmtTime(t.duration);
            renderTracks();
        }

        function togglePlay() {
            if (!audio.src) {
                if (playlist.length) playTrack(playlist[0]);
                return;
            }
            if (audio.paused) {
                connectSource();
                if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
                audio.play();
                document.getElementById('btnPlay').textContent = '⏸';
            } else {
                audio.pause();
                document.getElementById('btnPlay').textContent = '▶';
            }
        }

        function nextTrack() {
            if (!playlist.length) return;
            var pos = playlist.indexOf(currentIdx);
            if (shuffleMode) {
                var next = playlist[Math.floor(Math.random() * playlist.length)];
                playTrack(next);
            } else {
                var next = (pos + 1) % playlist.length;
                playTrack(playlist[next]);
            }
        }

        function prevTrack() {
            if (!playlist.length) return;
            if (audio.currentTime > 3) {
                audio.currentTime = 0;
                return;
            }
            var pos = playlist.indexOf(currentIdx);
            var prev = (pos - 1 + playlist.length) % playlist.length;
            playTrack(playlist[prev]);
        }

        audio.addEventListener('ended', function(){
            if (repeatMode === 1) {
                audio.currentTime = 0;
                audio.play();
            } else if (repeatMode === 2 || playlist.indexOf(currentIdx) < playlist.length - 1) {
                nextTrack();
            } else {
                document.getElementById('btnPlay').textContent = '▶';
            }
        });

        audio.addEventListener('timeupdate', function(){
            document.getElementById('curTime').textContent = fmtTime(audio.currentTime);
            if (audio.duration) {
                document.getElementById('progFill').style.width = (audio.currentTime/audio.duration*100)+'%';
            }
        });

        function seek(e) {
            if (!audio.duration) return;
            var bar = document.getElementById('progBar');
            var rect = bar.getBoundingClientRect();
            var pct = (e.clientX - rect.left) / rect.width;
            audio.currentTime = pct * audio.duration;
        }

        function setVolume(val) {
            audio.volume = val / 100;
            if (gainNode) gainNode.gain.value = val / 100;
        }

        /* MODES */
        function toggleShuffle() {
            shuffleMode = !shuffleMode;
            document.getElementById('btnShuffle').classList.toggle('active', shuffleMode);
        }

        function toggleRepeat() {
            repeatMode = (repeatMode + 1) % 3;
            var btn = document.getElementById('btnRepeat');
            btn.classList.toggle('active', repeatMode > 0);
            btn.textContent = repeatMode === 1 ? '🔂' : '🔁';
            btn.title = ['Повтор выкл', 'Повтор трека', 'Повтор списка'][repeatMode];
        }

        /* PLAYLISTS */
        function loadPlaylists() {
            fetch('/api/playlists')
                .then(function(r){ return r.json(); })
                .then(function(list){
                    var el = document.getElementById('plList');
                    if (!list.length) {
                        el.innerHTML = '<li style="color:var(--muted);cursor:default;">Пусто</li>';
                        return;
                    }
                    var html = '';
                    list.forEach(function(p){
                        html += '<li onclick="loadPL(\''+esc(p.name)+'\')">'
                            + '<span>'+esc(p.name)+'</span>'
                            + '<span><span class="pl-count">'+p.tracks+'</span> '
                            + '<button class="pl-del" onclick="event.stopPropagation();delPL(\''+esc(p.name)+'\')" title="Удалить">&times;</button></span></li>';
                    });
                    el.innerHTML = html;
                });
        }

        function loadPL(name) {
            fetch('/api/playlist/'+encodeURIComponent(name))
                .then(function(r){ return r.json(); })
                .then(function(data){
                    if (data.error) return;
                    var indices = [];
                    data.tracks.forEach(function(file){
                        var idx = allTracks.findIndex(function(t){ return t.file === file; });
                        if (idx !== -1) indices.push(idx);
                    });
                    playlist = indices;
                    renderTracks();
                });
        }

        function savePL(name) {
            var files = playlist.map(function(i){ return allTracks[i] ? allTracks[i].file : ''; }).filter(Boolean);
            fetch('/api/playlist', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({name: name, tracks: files})
            }).then(function(){ loadPlaylists(); });
        }

        function delPL(name) {
            if (!confirm('Удалить плейлист "'+name+'"?')) return;
            fetch('/api/playlist/'+encodeURIComponent(name), {method:'DELETE'})
                .then(function(){ loadPlaylists(); });
        }

        function showNewPL() {
            document.getElementById('modalOverlay').classList.add('active');
            var inp = document.getElementById('plNameInput');
            inp.value = '';
            inp.focus();
        }

        function closeModal() {
            document.getElementById('modalOverlay').classList.remove('active');
        }

        function saveNewPL() {
            var name = document.getElementById('plNameInput').value.trim();
            if (!name) return;
            savePL(name);
            closeModal();
        }

        /* START */
        setVolume(80);
        init();
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5009)
    parser.add_argument('--log', action='store_true')
    args = parser.parse_args()

    if args.log:
        log_path = os.path.join(BASE_DIR, 'log_file.log')
        logging.basicConfig(filename=log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(message)s')
        logging.info('MP3 Player %s started', VERSION)

    print(f"MP3 Player {VERSION} - http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
