"""Discovery IP terbatas untuk hotspot/jaringan LAN yang diizinkan."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import shutil
import socket
import subprocess
import time

PRIVATE = tuple(ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def validate(cidr):
    """Batasi ke subnet IPv4 privat paling banyak 256 alamat."""
    net = ipaddress.ip_network(cidr, strict=True)
    if net.version != 4 or not 24 <= net.prefixlen <= 30 or not any(net.subnet_of(p) for p in PRIVATE):
        raise ValueError('Gunakan subnet IPv4 privat /24 sampai /30.')
    return net


def local_ip(net):
    """Periksa sumber rute lokal; tidak mengirim paket UDP."""
    target = next(net.hosts())
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((str(target), 9))
        ip = ipaddress.ip_address(s.getsockname()[0])
    if ip not in net:
        raise ValueError(f'Rute lokal ({ip}) bukan bagian dari {net}. Periksa IP hotspot.')
    return ip


def probe(ip):
    """Satu ICMP echo, tanpa pemeriksaan port atau layanan."""
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '1', str(ip)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        return str(ip) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def scan(net, own, check=probe):
    """Probe paralel terbatas; hasil bukan daftar lengkap klien Wi-Fi."""
    with ThreadPoolExecutor(max_workers=12) as pool:
        return [ip for ip in pool.map(check, (ip for ip in net.hosts() if ip != own)) if ip]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cidr', required=True, help='Contoh 192.168.43.0/24')
    parser.add_argument('--authorized', action='store_true', help='Konfirmasi izin pemindaian subnet')
    parser.add_argument('--interval', type=int, default=45)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not args.authorized:
        parser.error('Gunakan hanya hotspot sendiri atau jaringan dengan izin pengelola; konfirmasi --authorized.')
    if not shutil.which('ping'):
        parser.error('Perintah ping tidak tersedia; instal iputils di Termux.')
    try:
        net = validate(args.cidr)
        own = local_ip(net)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if probe(own) is None:
        parser.error('Ping ke IP sendiri gagal. ICMP mungkin diblokir atau rute tidak benar.')
    print(f'[SCAN] Subnet {net} | IP lokal {own} | ICMP saja', flush=True)
    try:
        while True:
            found = scan(net, own)
            print(f'[SCAN {time.strftime("%H:%M:%S")}] {len(found)} alamat merespons (di luar HP sendiri): '+(', '.join(found) or '-'), flush=True)
            if args.once:
                break
            time.sleep(max(30, args.interval))
    except KeyboardInterrupt:
        print('[SCAN] Berhenti.', flush=True)


if __name__ == '__main__':
    main()
