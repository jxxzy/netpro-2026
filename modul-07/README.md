# Modul 7 — Network Programming
Server Multi-Client: Threading dan I/O Multiplexing (select), D4 Teknik Informatika ULBI.

## Cara menjalankan
Python 3, tanpa pustaka eksternal. Buka empat terminal pada folder ini.

```bash
python chat_server_multiclient.py
```

Pada tiga terminal lainnya jalankan `python chat_client.py` dan gunakan nickname berbeda. Ketik pesan, lalu Enter; `/keluar` untuk mengakhiri client. Client di LAN: `python chat_client.py IP_SERVER 5050` (ganti IP_SERVER dengan IPv4 server). Jalankan hanya pada jaringan praktikum tepercaya: komunikasi TCP tidak terenkripsi dan tidak ada autentikasi. Untuk localhost saja, gunakan `--host 127.0.0.1`.

Hentikan server dengan Ctrl+C, kemudian uji pembanding:

```bash
python chat_server_select.py
```

## Latihan pengembangan
- Latihan 1: `python chat_server_multiclient.py --baseline` menonaktifkan graceful shutdown. Sambungkan dua client dan Ctrl+C. Ulangi tanpa `--baseline`.
- Latihan 2: versi normal mengumumkan `Server akan dimatikan` sebelum menutup socket.
- Latihan 3: `log_chat.txt` mencatat timestamp, client join/leave dan pesan.

## Uji integrasi
Di Linux, jalankan `python test_chat.py`. Script menggunakan proses server dan client asli pada loopback dengan port sementara, mengirim SIGINT, dan menyimpan hasil di `bukti/`. Uji manual Windows: Ctrl+C pada terminal server. Jangan menjalankan uji bersamaan dengan sesi praktikum yang menggunakan log yang sama (uji akan mereset log).

## Arsitektur
- Threading: accept loop → worker per client → recv dengan framing newline → snapshot daftar di bawah lock → sendall di luar lock. Lock per socket mencegah pencampuran pengiriman bersamaan. Worker daemon, shutdown normal menutup socket dan menunggu worker.
- Select: satu event loop memantau listener, socket siap baca/tulis dan error; buffer input/output per client menangani pesan TCP terpotong atau tergabung dan pengiriman parsial. Tidak membutuhkan lock antar-thread pada server.

## Batasan
Aplikasi pembelajaran, bukan layanan chat internet produksi. Server memakai timeout pengiriman atau batas antrean, tetapi tidak ada autentikasi, TLS, dan penyimpanan histori. Uji otomatis di Linux, bukan demonstrasi langsung di depan dosen. Video paket lokal adalah replay transkrip aktual, bukan rekaman desktop langsung.

## Mode browser LAN dan Wi-Fi discovery (opsional)

Di Termux:
```sh
pkg update -y
pkg install python git iputils -y
git clone https://github.com/jxxzy/netpro-2026.git
cd netpro-2026/modul-07
python lan_chat.py
```
Jika repo sudah ada: `cd ~/netpro-2026 && git pull --ff-only && cd modul-07`.

Teman bergabung ke hotspot yang sama, membuka link HTTP port 8080 yang ditampilkan server, lalu memasukkan nickname. Tidak perlu instal Python pada perangkat client browser. Jika IP otomatis salah, gunakan IP hotspot yang sebenarnya melalui `--ip`. Untuk backend select, tambahkan `--mode select`. Hentikan server lain di port 5050 sebelum menjalankan gateway.

Pemindaian opsional hanya pada hotspot sendiri atau subnet dengan izin pengelola. Contoh IP/subnet (ganti sesuai jaringan aktual):
```sh
python lan_chat.py --ip 192.168.43.1 --scan-cidr 192.168.43.0/24 --authorized
```
Atau jalankan scanner saja: `python wifi_scan.py --cidr 192.168.43.0/24 --authorized --once`.
Hasil ICMP tampil di terminal, bukan daftar lengkap perangkat Wi-Fi. Perangkat yang menolak ping atau terisolasi mungkin tidak terdeteksi; IP yang merespons belum tentu client chat. Browser yang bergabung tercatat di terminal gateway dengan nickname dan IP. Tidak ada pemaksaan koneksi, pemindaian port, pengambilan kredensial atau pemasangan aplikasi pada perangkat lain. Jangan aktifkan discovery di jaringan kampus tanpa izin. HTTP dan TCP tidak terenkripsi, gunakan hanya jaringan tepercaya dan jangan kirim informasi sensitif. ICMP dan konektivitas perangkat nyata harus diverifikasi pada Android/jaringan aktual.

## Heartbeat, timeout dan timestamp
Update semua server dan client dengan `git pull --ff-only`, lalu restart. Client terminal dan gateway otomatis mengirim PING setiap 10 detik; server membalas PONG khusus ke pengirim. Frame kontrol tidak muncul di chat. Jika tidak ada frame dari client selama 60 detik, server menutup koneksinya. Client mendeteksi server yang tidak membalas PONG selama 60 detik, serta berhenti otomatis saat menerima EOF. Pengguna yang diam tetapi koneksinya sehat tetap dapat menerima chat. Client lama tanpa heartbeat dapat terputus setelah 60 detik jika tidak mengirim pesan. Terminal dan browser menampilkan timestamp penerimaan lokal; HTTP fetch browser diberi batas 5 detik (browser modern). Server langsung mendukung opsi `--timeout`; default 60 detik, jangan gunakan nilai di bawah interval heartbeat 10 detik untuk chat normal. Uji regresi dan heartbeat dilakukan pada Linux; uji langsung Windows masih diperlukan.
