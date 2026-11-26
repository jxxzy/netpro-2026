import socket
import sys
import threading


def terima_pesan(sock, berhenti):
    """Terima baris lengkap secara independen dari input keyboard."""
    try:
        with sock.makefile('r', encoding='utf-8', errors='replace') as reader:
            for pesan in reader:
                print(pesan, end='', flush=True)
    except OSError:
        pass
    finally:
        if not berhenti.is_set():
            print('[!] Koneksi ke server terputus. Tekan Enter untuk keluar.', flush=True)
        berhenti.set()


def main():
    """Hubungkan client, kirim nickname dan pesan, lalu tutup koneksi."""
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5050
    nick = input('Nickname: ').strip() or 'anonim'
    berhenti = threading.Event()
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except OSError as exc:
        print(f'[!] Tidak dapat terhubung: {exc}')
        return 1
    sock.settimeout(None)
    print(f'Terhubung ke {host}:{port}. Ketik /keluar untuk berhenti.', flush=True)
    penerima = threading.Thread(target=terima_pesan, args=(sock, berhenti), daemon=True)
    penerima.start()
    try:
        sock.sendall(f'*** {nick} bergabung ***\n'.encode())
        while not berhenti.is_set():
            pesan = input()
            if berhenti.is_set() or pesan.strip() == '/keluar':
                break
            if pesan.strip():
                sock.sendall(f'[{nick}] {pesan}\n'.encode())
    except (EOFError, KeyboardInterrupt, OSError):
        pass
    finally:
        if not berhenti.is_set():
            try:
                sock.sendall(f'*** {nick} keluar ***\n'.encode())
            except OSError:
                pass
        berhenti.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        penerima.join(timeout=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
