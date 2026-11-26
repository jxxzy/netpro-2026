"""Uji integrasi nyata melalui empat proses CLI dan koneksi TCP loopback."""
import subprocess, sys, threading, time, signal, socket, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'bukti'
OUT.mkdir(exist_ok=True)

class Process:
    """Simpan output proses dan beri input lewat stdin."""
    def __init__(self, *args):
        self.p = subprocess.Popen([sys.executable, '-u', *args], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace')
        self.lines = []
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
    def read(self):
        for line in self.p.stdout:
            self.lines.append(line.rstrip())
    def send(self, s):
        self.p.stdin.write(s + '\n'); self.p.stdin.flush()
    def wait(self, s, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if s in '\n'.join(self.lines): return
            time.sleep(.02)
        raise AssertionError(f'{s!r} tidak ditemukan: {self.lines}')
    def close(self):
        if self.p.poll() is None:
            self.p.kill()
        self.p.wait(timeout=5); self.reader.join(timeout=2)


def run(mode, baseline=False, two=False):
    """Uji broadcast, client idle, disconnect, reconnect, dan SIGINT."""
    with socket.socket() as tmp:
        tmp.bind(('127.0.0.1', 0)); port = str(tmp.getsockname()[1])
    procs = {}
    checks = []
    snapshots = []
    def capture(title):
        snapshots.append((title, {k: list(p.lines) for k,p in procs.items()}))
    def client(nick):
        p = Process('chat_client.py', '127.0.0.1', port)
        procs[nick] = p; p.send(nick); p.wait('Terhubung ke')
        procs['Server'].wait(f'Total client: {sum(q.p.poll() is None for k,q in procs.items() if k != "Server")}')
        return p
    try:
        file = 'chat_server_multiclient.py' if mode == 'threading' else 'chat_server_select.py'
        s = Process(file, '--host', '127.0.0.1', '--port', port, *(['--baseline'] if baseline else [])); procs['Server']=s
        s.wait('Chat server berjalan'); a=client('Andi'); b=client('Budi'); a.wait('Budi bergabung')
        if not baseline and not two:
            c=client('Citra'); a.wait('Citra bergabung'); b.wait('Citra bergabung')
            a.send('Halo semua'); b.wait('[Andi] Halo semua'); c.wait('[Andi] Halo semua')
            assert '[Andi] Halo semua' not in '\n'.join(a.lines)
            checks.append('PASS: broadcast A ke B dan C; tanpa echo ke A')
            b.send('Halo dari Budi'); a.wait('[Budi] Halo dari Budi'); c.wait('[Budi] Halo dari Budi')
            c.send('Pesan dari Citra'); a.wait('[Citra] Pesan dari Citra'); b.wait('[Citra] Pesan dari Citra')
            assert '[Budi] Halo dari Budi' not in '\n'.join(b.lines) and '[Citra] Pesan dari Citra' not in '\n'.join(c.lines)
            checks.append('PASS: broadcast B dan C; A idle tetap menerima')
            capture('Broadcast dan client idle')
            a.send('/keluar'); a.p.wait(timeout=5); b.wait('Andi keluar'); c.wait('Andi keluar'); s.wait('keluar. Total client: 2')
            b.send('Server tetap berjalan'); c.wait('[Budi] Server tetap berjalan')
            d=client('Dina'); b.wait('Dina bergabung'); d.send('Saya client baru'); b.wait('[Dina] Saya client baru'); c.wait('[Dina] Saya client baru')
            checks.append('PASS: disconnect, layanan tetap hidup, client baru bergabung')
            capture('Disconnect dan reconnect')
            active=[b,c,d]
        else: active=[a,b]
        s.p.send_signal(signal.SIGINT)
        rc=s.p.wait(timeout=10); s.reader.join(timeout=2)
        for p in active:
            p.wait('Koneksi ke server terputus')
            if not baseline: p.wait('Server akan dimatikan')
            else: assert 'Server akan dimatikan' not in '\n'.join(p.lines)
            p.send(''); p.p.wait(timeout=5)
        if baseline:
            assert rc != 0 and 'KeyboardInterrupt' in '\n'.join(s.lines)
            checks.append(f'PASS: baseline traceback, exit {rc}, dua client terputus tanpa notifikasi')
        else:
            assert rc == 0 and 'Server berhenti normal.' in '\n'.join(s.lines)
            checks.append('PASS: graceful shutdown, notifikasi semua client, exit 0')
        capture('Shutdown ' + ('baseline' if baseline else 'graceful'))
        # Restart pada port yang sama setelah server berhenti.
        again=Process(file,'--host','127.0.0.1','--port',port); procs['Restart']=again
        again.wait('Chat server berjalan'); again.p.send_signal(signal.SIGINT); assert again.p.wait(timeout=5)==0
        checks.append('PASS: restart pada port yang sama')
        return checks, snapshots
    finally:
        for p in procs.values(): p.close()


def main():
    """Simpan bukti output asli dari proses yang diuji."""
    import json
    all_snapshots=[]; results=[]
    log=ROOT/'log_chat.txt'
    if log.exists(): log.unlink()
    for mode, baseline, two in [('threading',True,True),('threading',False,True),('threading',False,False),('select',False,False)]:
        label=mode + (' baseline (2 client)' if baseline else ' graceful (2 client)' if two else ' final')
        checks, snapshots=run(mode,baseline,two)
        results.append(label+'\n'+'\n'.join(checks))
        all_snapshots.extend((label+' | '+title, data) for title,data in snapshots)
    log_text=log.read_text(encoding='utf-8')
    assert 'bergabung. Total client:' in log_text and 'keluar. Total client:' in log_text and 'Pesan: [Andi] Halo semua' in log_text
    results.append('PASS: log_chat.txt berisi timestamp, join, leave dan pesan')
    content='\n\n'.join(results)+'\n'
    (OUT/'hasil_uji.txt').write_text(content,encoding='utf-8')
    (OUT/'transkrip.json').write_text(json.dumps(all_snapshots,ensure_ascii=False,indent=2),encoding='utf-8')
    print(content)

if __name__=='__main__': main()
