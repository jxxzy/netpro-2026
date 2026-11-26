import argparse
import logging
import socket
import threading

clients = {}
lock = threading.Lock()


def hapus(conn):
    """Hapus koneksi sekali saja dan tutup socket."""
    with lock:  # LOCK: daftar client bersama
        info = clients.pop(conn, None)
        total = len(clients)
    if info:
        logging.info('[-] %s keluar. Total client: %d', info[0], total)
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    conn.close()


def broadcast(data, pengirim=None):
    """Salin daftar di bawah lock, lalu kirim di luar lock."""
    with lock:  # LOCK: snapshot daftar client
        daftar = list(clients.items())
    for conn, (_, send_lock) in daftar:
        if conn is pengirim:
            continue
        try:
            with send_lock:  # LOCK: pengiriman per socket
                conn.sendall(data)
        except OSError:
            hapus(conn)


def tangani_client(conn):
    """Baca pesan TCP dengan pembatas newline, kemudian broadcast."""
    buffer = b''
    try:
        while True:
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue
            if not data:
                break
            buffer += data
            while b'\n' in buffer:
                pesan, buffer = buffer.split(b'\n', 1)
                logging.info('Pesan: %s', pesan.decode('utf-8', 'replace'))
                broadcast(pesan + b'\n', conn)
            if len(buffer) > 65536:
                break
    except OSError:
        pass
    finally:
        hapus(conn)


def matikan_server_dengan_rapi(server, workers):
    """Hentikan penerimaan, umumkan shutdown, tutup koneksi dan tunggu worker."""
    logging.info('[!] Sinyal berhenti diterima, menutup seluruh koneksi client...')
    server.close()
    broadcast(b'*** Server akan dimatikan ***\n')
    with lock:  # LOCK: snapshot untuk cleanup
        daftar = list(clients)
    for conn in daftar:
        hapus(conn)
    for worker in workers:
        worker.join(timeout=2)
    logging.info('Server berhenti normal.')


def main():
    """Jalankan accept loop; opsi baseline untuk Latihan 1."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler('log_chat.txt', encoding='utf-8')])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen()
    server.settimeout(0.5)
    workers = []
    logging.info('Chat server berjalan di port %d ... (threading)', args.port)
    try:
        while True:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            conn.settimeout(1)
            with lock:  # LOCK: registrasi client
                clients[conn] = (addr, threading.Lock())
                total = len(clients)
            logging.info('[+] %s bergabung. Total client: %d', addr, total)
            workers = [w for w in workers if w.is_alive()]
            worker = threading.Thread(target=tangani_client, args=(conn,), daemon=True)
            workers.append(worker)
            worker.start()
    except KeyboardInterrupt:
        if args.baseline:
            raise
        matikan_server_dengan_rapi(server, workers)


if __name__ == '__main__':
    main()
