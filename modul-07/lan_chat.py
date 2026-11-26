"""Gateway browser LAN untuk chat TCP Modul 7 (Python standard library)."""
import argparse
import json
import queue
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

PAGE = '''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NETPRO | LAN Chat</title><style>
*{box-sizing:border-box}body{font:16px system-ui;background:#101827;color:#e8edf6;margin:0}main{max-width:650px;margin:auto;padding:24px}h1{margin-bottom:4px}p{color:#b2c1d5}input,button{font:inherit;padding:12px;border-radius:10px;border:1px solid #546479}input{min-width:0;flex:1;background:#1a293d;color:white}button{background:#79ddbd;color:#10251f;font-weight:bold;cursor:pointer}form{display:flex;gap:8px;margin:12px 0}#messages{height:45vh;overflow:auto;background:#182437;border:1px solid #34445a;border-radius:12px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere}#status{font-size:14px} [hidden]{display:none!important}</style><main><h1>NETPRO LAN Chat</h1><p>Modul 7 • TCP multi-client • Jaringan lokal</p><p id="status">Masukkan nickname untuk bergabung.</p><form id="join"><input id="nick" placeholder="Nickname" maxlength="24" required><button>Gabung</button></form><section id="room" hidden><div id="messages" role="log"></div><form id="send"><input id="message" placeholder="Tulis pesan" maxlength="1000" autocomplete="off" required><button>Kirim</button></form><button id="leave">Keluar</button></section></main><script>
const $=id=>document.getElementById(id);let token='',busy=false;
function line(s){const d=document.createElement('div');d.textContent=s;$('messages').append(d);while($('messages').children.length>300)$('messages').firstChild.remove();$('messages').scrollTop=$('messages').scrollHeight}
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const j=await r.json();if(!r.ok)throw Error(j.error||'Gagal');return j}
function reset(s){token='';$('join').hidden=false;$('room').hidden=true;$('status').textContent=s}
$('join').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;try{const j=await post('/join',{nick:$('nick').value});token=j.token;$('messages').replaceChildren();$('join').hidden=true;$('room').hidden=false;$('send').hidden=false;$('status').textContent='Terhubung sebagai '+j.nick;line('Anda bergabung.')}catch(e){$('status').textContent=e.message}finally{busy=false}};
$('send').onsubmit=async e=>{e.preventDefault();const m=$('message').value,t=token;if(!t||busy)return;busy=true;try{await post('/send',{token:t,message:m});if(token===t){line('[Saya] '+m);$('message').value=''}}catch(e){$('status').textContent=e.message}finally{busy=false}};
$('leave').onclick=async()=>{const t=token;reset('Anda keluar.');try{await post('/leave',{token:t})}catch(e){}};
async function poll(){const t=token;if(t){try{const r=await fetch('/poll?token='+encodeURIComponent(t),{cache:'no-store'});const j=await r.json();if(token===t){if(!r.ok)reset(j.error||'Terputus');else{j.messages.forEach(line);if(j.closed){token='';$('join').hidden=false;$('send').hidden=true;$('status').textContent='Server terputus. Buka ulang halaman untuk bergabung.'}}}}catch(e){if(token===t)$('status').textContent='Jaringan terputus; mencoba kembali...'}}setTimeout(poll,700)}poll();
</script></html>'''

sessions = {}
lock = threading.Lock()

class Client:
    """Setiap browser memiliki satu koneksi TCP tersendiri ke server praktikum."""
    def __init__(self, nick, port):
        self.nick = nick
        self.sock = socket.create_connection(('127.0.0.1', port), timeout=3)
        self.sock.settimeout(None)
        self.messages = queue.Queue(maxsize=200)
        self.last = time.monotonic()
        self.closed = False
        self.send_lock = threading.Lock()
        self.send('*** '+nick+' bergabung ***')
        threading.Thread(target=self.read, daemon=True).start()

    def send(self, text):
        with self.send_lock:
            self.sock.sendall((text+'\n').encode())

    def read(self):
        try:
            with self.sock.makefile('r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    try: self.messages.put_nowait(line.rstrip('\n'))
                    except queue.Full: break
        except OSError: pass
        finally: self.close(False)

    def close(self, announce=True):
        if self.closed: return
        self.closed = True
        if announce:
            try: self.send('*** '+self.nick+' keluar ***')
            except OSError: pass
        try: self.sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        self.sock.close()


def clean(value, limit):
    return ' '.join(str(value).split())[:limit]


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.respond(status, data, 'application/json; charset=utf-8')

    def respond(self, status, data, kind):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # Token sesi tidak ditulis ke log HTTP.

    def do_GET(self):
        u = urlsplit(self.path)
        if u.path == '/':
            return self.respond(200, PAGE.encode(), 'text/html; charset=utf-8')
        if u.path != '/poll': return self.reply(404, {'error':'Tidak ditemukan'})
        token = parse_qs(u.query).get('token', [''])[0]
        with lock:
            c = sessions.get(token)
            if c: c.last = time.monotonic()
        if not c: return self.reply(404, {'error':'Sesi berakhir; silakan gabung lagi.'})
        messages = []
        while True:
            try: messages.append(c.messages.get_nowait())
            except queue.Empty: break
        self.reply(200, {'messages':messages, 'closed':c.closed})

    def do_POST(self):
        if self.headers.get_content_type() != 'application/json':
            return self.reply(415, {'error':'JSON diperlukan'})
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 8192: raise ValueError()
            d = json.loads(self.rfile.read(n))
            if not isinstance(d, dict): raise ValueError()
        except (ValueError, OSError): return self.reply(400, {'error':'Request tidak valid'})
        if self.path == '/join':
            nick = clean(d.get('nick',''),24)
            if not nick: return self.reply(400, {'error':'Nickname wajib diisi'})
            with lock:
                if len(sessions) >= 40: return self.reply(503, {'error':'Ruang penuh'})
                try: c = Client(nick, self.server.tcp_port)
                except OSError: return self.reply(503, {'error':'Server TCP belum siap'})
                token = secrets.token_urlsafe(24)
                sessions[token] = c
            print(f'[WEB] {nick} bergabung dari {self.client_address[0]}', flush=True)
            return self.reply(200, {'token':token,'nick':nick})
        token = d.get('token')
        if not isinstance(token,str): return self.reply(400, {'error':'Token tidak valid'})
        with lock:
            c = sessions.get(token)
            if c: c.last = time.monotonic()
            if c and self.path == '/leave': sessions.pop(token,None)
        if not c: return self.reply(404, {'error':'Sesi berakhir'})
        if self.path == '/leave': c.close(); return self.reply(200, {'ok':True})
        if self.path != '/send': return self.reply(404, {'error':'Tidak ditemukan'})
        msg = clean(d.get('message',''),1000)
        if not msg: return self.reply(400, {'error':'Pesan kosong'})
        try:
            if c.closed: raise OSError()
            c.send('['+c.nick+'] '+msg)
        except OSError: return self.reply(503, {'error':'Server TCP terputus'})
        self.reply(200, {'ok':True})


def reap(stop):
    while not stop.wait(5):
        with lock:
            expired = [sessions.pop(t) for t,c in list(sessions.items()) if time.monotonic()-c.last > 90]
        for c in expired: c.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--web-port',type=int,default=8080)
    p.add_argument('--tcp-port',type=int,default=5050)
    p.add_argument('--ip',help='IP Wi-Fi/hotspot untuk link yang ditampilkan')
    p.add_argument('--mode',choices=['threading','select'],default='threading')
    p.add_argument('--scan-cidr',help='Subnet hotspot sendiri /24 sampai /30')
    p.add_argument('--authorized',action='store_true',help='Konfirmasi izin scan subnet')
    a = p.parse_args()
    if a.scan_cidr:
        from wifi_scan import validate, local_ip
        import shutil
        if not a.authorized: p.error('Scan membutuhkan --authorized dan izin pengelola jaringan.')
        if not shutil.which('ping'): p.error('Instal iputils terlebih dahulu.')
        try: local_ip(validate(a.scan_cidr))
        except (ValueError,OSError) as exc: p.error(str(exc))
    scanner = None
    http = ThreadingHTTPServer(('0.0.0.0',a.web_port),Handler)
    http.tcp_port = a.tcp_port
    script = 'chat_server_multiclient.py' if a.mode == 'threading' else 'chat_server_select.py'
    proc = subprocess.Popen([sys.executable,str(Path(__file__).with_name(script)),'--host','0.0.0.0','--port',str(a.tcp_port)],start_new_session=True)
    stop = threading.Event()
    try:
        for _ in range(50):
            if proc.poll() is not None: raise RuntimeError('Server TCP gagal dijalankan; periksa port.')
            try:
                with socket.create_connection(('127.0.0.1',a.tcp_port),timeout=.2): pass
                break
            except OSError: time.sleep(.1)
        else: raise RuntimeError('Server TCP tidak siap')
        ip = a.ip
        if not ip:
            try:
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
                    s.connect(('192.0.2.1',80)); ip = s.getsockname()[0]
            except OSError: ip = 'IP_WIFI_HP'
        print(f'Buka di browser teman: http://{ip}:{a.web_port}',flush=True)
        print('Jika IP salah, gunakan IP Wi-Fi/hotspot HP atau opsi --ip. Ctrl+C untuk berhenti.',flush=True)
        threading.Thread(target=reap,args=(stop,),daemon=True).start()
        if a.scan_cidr:
            scanner = subprocess.Popen([sys.executable,str(Path(__file__).with_name('wifi_scan.py')),'--cidr',a.scan_cidr,'--authorized'],start_new_session=True)
        http.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        stop.set(); http.server_close()
        if scanner is not None and scanner.poll() is None:
            scanner.send_signal(signal.SIGINT)
            try: scanner.wait(timeout=5)
            except subprocess.TimeoutExpired: scanner.terminate(); scanner.wait(timeout=5)
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired: proc.terminate(); proc.wait(timeout=5)
        with lock:
            remaining=list(sessions.values());sessions.clear()
        for c in remaining: c.close(False)

if __name__ == '__main__': main()
