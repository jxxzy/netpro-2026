"""Heartbeat aplikasi; frame kontrol tidak diteruskan ke ruang chat."""
import socket
import threading
import time

PING = b'\x00PING'
PONG = b'\x00PONG'
INTERVAL = 10
TIMEOUT = 60


class Heartbeat:
    def __init__(self, send, disconnect, interval=INTERVAL, timeout=TIMEOUT):
        self.send = send
        self.disconnect = disconnect
        self.interval = interval
        self.timeout = timeout
        self.last = time.monotonic()
        self.stop = threading.Event()

    def received(self):
        self.last = time.monotonic()

    def run(self):
        while not self.stop.wait(self.interval):
            if time.monotonic() - self.last >= self.timeout:
                self.disconnect('Timeout: server tidak merespons.')
                return
            try:
                self.send(PING + b'\n')
            except OSError:
                self.disconnect('Koneksi ke server terputus.')
                return

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()


def keepalive(sock):
    """Aktifkan TCP keepalive sebagai cadangan untuk koneksi putus."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
