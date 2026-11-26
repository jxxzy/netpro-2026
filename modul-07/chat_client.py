import queue
import socket
import sys
import threading
from datetime import datetime
from heartbeat import Heartbeat, PONG, keepalive


def main():
    """Client terminal: input tidak menghalangi deteksi koneksi putus."""
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5050
    nick = ' '.join(input('Nickname: ').split())[:24] or 'anonim'
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except OSError as exc:
        print(f'[!] Tidak dapat terhubung: {exc}', flush=True)
        return 1
    sock.settimeout(None)
    keepalive(sock)
    stopped = threading.Event()
    send_lock = threading.Lock()
    messages = queue.Queue()

    def send(data):
        with send_lock:
            sock.sendall(data)

    def disconnect(reason):
        if not stopped.is_set():
            print('[!] '+reason, flush=True)
            stopped.set()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    beat = Heartbeat(send, disconnect)

    def receive():
        try:
            with sock.makefile('rb') as reader:
                for line in reader:
                    frame = line.rstrip(b'\n')
                    if frame == PONG:
                        beat.received()
                    else:
                        print(f'[{datetime.now():%H:%M:%S}] '+frame.decode('utf-8','replace'), flush=True)
        except OSError:
            pass
        finally:
            disconnect('Koneksi ke server terputus.')

    def keyboard():
        try:
            for line in sys.stdin:
                messages.put(line.strip())
        finally:
            messages.put(None)

    print(f'Terhubung ke {host}:{port}. Ketik /keluar untuk berhenti.', flush=True)
    receiver = threading.Thread(target=receive, daemon=True)
    receiver.start()
    try:
        send(f'*** {nick} bergabung ***\n'.encode())
        beat.start()
        threading.Thread(target=keyboard, daemon=True).start()
        while not stopped.is_set():
            try:
                msg = messages.get(timeout=.2)
            except queue.Empty:
                continue
            if msg is None or msg == '/keluar':
                break
            if msg and not stopped.is_set():
                send(f'[{nick}] {msg}\n'.encode())
    except (OSError, KeyboardInterrupt):
        pass
    finally:
        if not stopped.is_set():
            try:
                send(f'*** {nick} keluar ***\n'.encode())
            except OSError:
                pass
        stopped.set()
        beat.stop.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        receiver.join(timeout=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
