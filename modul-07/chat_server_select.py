import argparse
import logging
import select
import socket
import time
from heartbeat import PING, PONG, TIMEOUT, keepalive


def main():
    """Satu event loop, socket nonblocking, buffer input dan output per client."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--timeout', type=int, default=TIMEOUT, help='Detik tanpa frame dari client')
    args = parser.parse_args()
    if args.timeout < 2:
        parser.error('Timeout minimum 2 detik')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler('log_chat.txt', encoding='utf-8')])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen()
    server.setblocking(False)
    clients = {}

    def hapus(conn):
        """Bersihkan socket dan buffer client."""
        info = clients.pop(conn, None)
        if info:
            logging.info('[-] %s keluar. Total client: %d', info[0], len(clients))
        conn.close()

    def broadcast(data, pengirim=None):
        """Antrekan pesan, tanpa menahan event loop pada client lambat."""
        for conn, info in list(clients.items()):
            if conn is not pengirim:
                info[2].extend(data)
                if len(info[2]) > 262144:
                    hapus(conn)

    def kirim(conn):
        """Kirim bagian yang siap; simpan sisa byte untuk putaran berikutnya."""
        try:
            buf = clients[conn][2]
            n = conn.send(buf)
            if n == 0:
                hapus(conn)
            else:
                del buf[:n]
        except BlockingIOError:
            pass
        except OSError:
            hapus(conn)

    logging.info('Chat server berjalan di port %d ... (select)', args.port)
    try:
        while True:
            for conn, info in list(clients.items()):
                if time.monotonic() - info[3] >= args.timeout:
                    logging.info('Timeout client: %s', info[0])
                    hapus(conn)
            baca, tulis, gagal = select.select([server, *clients],
                [c for c in clients if clients[c][2]], list(clients), 0.5)
            for conn in gagal:
                if conn in clients:
                    hapus(conn)
            for conn in baca:
                if conn is server:
                    try:
                        c, addr = server.accept()
                    except BlockingIOError:
                        continue
                    c.setblocking(False)
                    keepalive(c)
                    clients[c] = [addr, bytearray(), bytearray(), time.monotonic()]
                    logging.info('[+] %s bergabung. Total client: %d', addr, len(clients))
                elif conn in clients:
                    try:
                        data = conn.recv(1024)
                    except BlockingIOError:
                        continue
                    except OSError:
                        hapus(conn)
                        continue
                    if not data:
                        hapus(conn)
                        continue
                    buf = clients[conn][1]
                    buf.extend(data)
                    while b'\n' in buf:
                        pesan, sisa = buf.split(b'\n', 1)
                        buf[:] = sisa
                        clients[conn][3] = time.monotonic()
                        if pesan == PING:
                            clients[conn][2].extend(PONG + b'\n')
                            if len(clients[conn][2]) > 262144:
                                hapus(conn)
                                break
                            continue
                        logging.info('Pesan: %s', pesan.decode('utf-8', 'replace'))
                        broadcast(pesan + b'\n', conn)
                    if len(buf) > 65536:
                        hapus(conn)
            for conn in tulis:
                if conn in clients:
                    kirim(conn)
    except KeyboardInterrupt:
        logging.info('[!] Sinyal berhenti diterima, menutup seluruh koneksi client...')
        server.close()
        broadcast(b'*** Server akan dimatikan ***\n')
        batas = time.monotonic() + 2
        while time.monotonic() < batas:
            pending = [c for c in clients if clients[c][2]]
            if not pending:
                break
            _, siap, _ = select.select([], pending, [], 0.1)
            for conn in siap:
                if conn in clients:
                    kirim(conn)
    finally:
        for conn in list(clients):
            hapus(conn)
        server.close()
        logging.info('Server berhenti normal.')


if __name__ == '__main__':
    main()
