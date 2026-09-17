@echo off
setlocal
title SHARKCODE - CSV Logger BY WIJAYA
color 0A

:: ============================================================
::  Konfigurasi DEFAULT IP dan Port Server
::  (dipakai hanya jika SHARKCODE-config.ini belum ada)
:: ============================================================
set "SERVER_IP=192.168.1.45"
set "SERVER_PORT=2002"

:: Folder tempat file .bat ini berada (untuk menyimpan config)
set "SHARK_DIR=%~dp0"

echo ==========================================
echo           SHARKCODE BY WIJAYA
echo            CSV LOGGER MODE
echo ==========================================
echo.

:: ------------------------------------------------------------
::  Jalankan bagian PowerShell yang tertanam di bawah (lihat penanda)
:: ------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$src=[IO.File]::ReadAllText('%~f0');" ^
 "$m=[char]35+'SHARK_PS';" ^
 "$i=$src.LastIndexOf($m);" ^
 "iex ($src.Substring($i))"

echo.
pause
exit /b

#SHARK_PS
# ============================================================
#  SHARKCODE - TCP Client + CSV Logger (PowerShell)
#
#  - Koneksi gagal  -> muncul kolom entry IP & Port, lalu config
#                      otomatis disimpan ke SHARKCODE-config.ini
#  - Minta nama file CSV (otomatis diawali 'Alb-', WAJIB diisi)
#  - Data dari server di-SAVE REALTIME ke CSV (flush tiap data masuk)
#  - Layar hanya menampilkan 1 baris data terakhir yang sudah
#    tersimpan (update di tempat) -> tidak ada bottleneck console
#  - Ketik 'x' lalu Enter -> tutup file ini, minta nama file baru
#  - Tutup jendela / Ctrl+C -> keluar
# ============================================================

$enc     = New-Object System.Text.UTF8Encoding($false)   # UTF-8 tanpa BOM
$buffer  = New-Object byte[] 65536
$nlChars = [char[]]@("`r", "`n")

# ------------------------------------------------------------
#  PROTEKSI EXCEL
#  File CSV selalu berisi nilai APA ADANYA dari server. Masalahnya
#  Excel meng-auto-convert angka panjang saat file CSV dibuka:
#    79381287487778932187877414214  ->  7.93813E+28
#  dan Excel hanya menyimpan 15 digit signifikan, sisanya jadi 0
#  (nilai RUSAK PERMANEN kalau file lalu di-save dari Excel).
#
#  $ExcelSafe = $true  -> kolom yang berbahaya ditulis sebagai ="..."
#                         supaya Excel menampilkannya PERSIS sebagai teks.
#                         Kolom pendek/biasa tidak diubah.
#  $ExcelSafe = $false -> file 100% byte-asli (pakai ini kalau CSV-nya
#                         dibaca program lain, bukan Excel).
# ------------------------------------------------------------
$ExcelSafe = $true

# ------------------------------------------------------------
#  PANJANG RECORD (hanya untuk server yang TIDAK mengirim newline)
#  Tanpa pemisah, batas antar-record tidak ada di dalam data, jadi
#  satu-satunya cara yang 100% pasti adalah panjang record yang tetap.
#    0  = deteksi otomatis (script belajar dari data yang masuk)
#    29 = misal record Anda selalu 29 karakter -> langsung pasti sejak
#         record pertama, tanpa fase belajar
#  Server yang mengirim newline tidak terpengaruh setelan ini.
# ------------------------------------------------------------
$RecordLength = 0

# Cocokkan 1 kolom penuh yang akan dirusak Excel:
#   - angka >= 16 digit          (presisi hilang)
#   - angka berawalan 0          (nol di depan dihapus Excel)
#   - angka/desimal sangat panjang
$rxRisk = [regex]::new('(?<=^|,)(0\d+|\d[\d.]{15,})(?=,|$)', 'Compiled')

# Lama menunggu data per putaran (mikrodetik). 20000us = 20ms: cukup
# responsif untuk tombol, dan Poll tetap bangun seketika saat data tiba.
$pollUs = 20000

# Klep pengaman ukuran buffer (byte) untuk server TANPA pemisah. Kalau data
# mengalir tanpa jeda sama sekali, socket tak pernah kosong sehingga batas
# record dari timing tak pernah muncul; buffer dipaksa ditulis di ukuran ini
# supaya data tidak menumpuk di memori. Untuk kasus itu, set $RecordLength
# agar pemisahan tetap tepat.
$capB = 32768
$conOut  = [Console]::Out

# Lebar console (untuk memotong baris status agar tidak wrap)
try   { $wide = [Console]::WindowWidth - 2 }
catch { $wide = 78 }
if ($wide -lt 40) { $wide = 78 }

# ------------------------------------------------------------
#  Config IP / Port  (SHARKCODE-config.ini di folder .bat)
# ------------------------------------------------------------
$cfgDir = $env:SHARK_DIR
if ([string]::IsNullOrWhiteSpace($cfgDir)) { $cfgDir = (Get-Location).Path }
$cfgPath = Join-Path $cfgDir 'SHARKCODE-config.ini'

function Save-Config([string]$ip, [int]$port) {
    try {
        Set-Content -LiteralPath $cfgPath -Encoding ASCII -Value @(
            "; SHARKCODE - konfigurasi koneksi (otomatis dibuat)",
            "IP=$ip",
            "PORT=$port"
        )
        Write-Host ("[CONFIG] Tersimpan -> {0}" -f $cfgPath) -ForegroundColor DarkGray
    }
    catch {
        Write-Host ("[CONFIG] Gagal menyimpan config: {0}" -f $_.Exception.Message) -ForegroundColor Red
    }
}

function Load-Config {
    if (-not (Test-Path -LiteralPath $cfgPath)) { return $null }
    try {
        $ip = $null; $port = 0
        foreach ($raw in (Get-Content -LiteralPath $cfgPath)) {
            $l = $raw.Trim()
            if ($l.Length -eq 0 -or $l.StartsWith(';')) { continue }
            $kv = $l.Split('=', 2)
            if ($kv.Count -ne 2) { continue }
            switch ($kv[0].Trim().ToUpper()) {
                'IP'   { $ip = $kv[1].Trim() }
                'PORT' { [void][int]::TryParse($kv[1].Trim(), [ref]$port) }
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($ip) -and $port -gt 0) {
            return @{ IP = $ip; PORT = $port }
        }
    }
    catch { }
    return $null
}

# Coba connect dengan timeout; $null = gagal (pesan di $script:connErr)
function Connect-Server([string]$ip, [int]$port, [int]$timeoutMs) {
    $script:connErr = ''
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $c.NoDelay           = $true
        $c.ReceiveBufferSize = 1048576
        $t = $c.ConnectAsync($ip, $port)
        if (-not $t.Wait($timeoutMs)) {
            $script:connErr = "Timeout ${timeoutMs}ms - server tidak merespon"
            try { $c.Close() } catch { }
            return $null
        }
        if ($t.IsFaulted) {
            $script:connErr = $t.Exception.GetBaseException().Message
            try { $c.Close() } catch { }
            return $null
        }
        return $c
    }
    catch {
        $script:connErr = $_.Exception.Message
        try { $c.Close() } catch { }
        return $null
    }
}

# ------------------------------------------------------------
#  Helper tampilan & penutup sesi file
# ------------------------------------------------------------
function Show-NamePrompt {
    Write-Host ""
    Write-Host "Masukkan nama file CSV (otomatis diawali 'Alb-') :" -ForegroundColor Cyan
    Write-Host "Alb-" -NoNewline -ForegroundColor Green
}

# Render 1 baris status = data terakhir yang SUDAH tersimpan (update di tempat)
function Show-Live {
    $txt = "[SAVED $count] $latest"
    if ($txt.Length -gt $wide) { $txt = $txt.Substring(0, $wide) }
    $pad = ''
    if ($prevLen -gt $txt.Length) { $pad = ' ' * ($prevLen - $txt.Length) }
    [Console]::ForegroundColor = [ConsoleColor]::Cyan
    $conOut.Write("`r" + $txt + $pad)
    [Console]::ResetColor()
    $script:prevLen  = $txt.Length
    $script:liveLine = $true
}

# Tutup file sesi ini: flush, close, lapor.
#  $final = $true  -> program berakhir (server menutup koneksi)
#  $final = $false -> sekedar ganti file (perintah 'x')
#
# Penanganan sisa data yang BELUM lengkap (belum ketemu newline):
#  - server pakai newline + ganti file -> potongan DIBAWA ke file berikutnya
#    supaya record tetap utuh (tidak ditulis terpotong di file ini)
#  - server pakai newline + program berakhir -> potongan TIDAK ditulis,
#    hanya diberitahukan; menulis angka terpotong lebih berbahaya daripada
#    tidak menulisnya (kelihatan valid padahal nilainya salah)
#  - server TANPA newline -> sisa itu memang 1 record utuh, jadi ditulis
function Close-Session([bool]$final) {
    # data yang masih ditahan fase belajar jangan sampai hilang
    if ($learnChunk -and $learnChunk.Count -gt 0) {
        foreach ($c in $learnChunk) {
            if ($recLen -gt 0 -and ($c.Length % $recLen) -eq 0) {
                for ($i = 0; $i -lt $c.Length; $i += $recLen) {
                    $o = $c.Substring($i, $recLen)
                    if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                    $writer.WriteLine($o); $script:count = $count + 1; $script:latest = $c.Substring($i, $recLen)
                }
            }
            else {
                $o = $c
                if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                $writer.WriteLine($o); $script:count = $count + 1; $script:latest = $c
            }
        }
        $learnChunk.Clear()
    }

    $rem     = $partial.ToString()
    $carried = $false

    if ($rem.Trim().Length -gt 0) {
        if (-not $sawNL -and $recLen -gt 0) {
            # MODE PANJANG TETAP: tulis hanya record yang LENGKAP.
            # Sisa yang kurang dari 1 record adalah record belum utuh -> tidak
            # ditulis (menulis nilai terpotong lebih berbahaya daripada tidak
            # menulisnya, karena kelihatan valid padahal salah).
            $k = [int][Math]::Floor($rem.Length / $recLen)
            for ($i = 0; $i -lt $k; $i++) {
                $piece = $rem.Substring($i * $recLen, $recLen)
                $o = $piece
                if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                $writer.WriteLine($o)
                $script:count  = $count + 1
                $script:latest = $piece
            }
            $left = $rem.Length - ($k * $recLen)
            if ($left -gt 0) {
                Write-Host ("`n[PERINGATAN] {0} karakter terakhir belum menjadi record lengkap dan TIDAK ditulis." -f $left) -ForegroundColor Yellow
            }
            [void]$partial.Clear()
        }
        elseif (-not $sawNL) {
            # panjang record tidak tetap: sisa ini dianggap 1 record utuh
            $o = $rem.Trim()
            if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
            $writer.WriteLine($o)
            $script:count  = $count + 1
            $script:latest = $rem.Trim()
            [void]$partial.Clear()
        }
        elseif ($final) {
            Write-Host ("`n[PERINGATAN] Potongan data terakhir belum lengkap dan TIDAK ditulis (agar tidak ada nilai terpotong di CSV): {0}" -f $rem.Trim()) -ForegroundColor Yellow
            [void]$partial.Clear()
        }
        else {
            # dibawa ke file berikutnya -> $partial sengaja TIDAK dibersihkan
            $carried = $true
        }
    }
    else {
        [void]$partial.Clear()
    }

    $writer.Flush()
    $writer.Close()
    $script:writer = $null

    if ($liveLine) {
        $txt = "[SAVED $count] $latest"
        if ($txt.Length -gt $wide) { $txt = $txt.Substring(0, $wide) }
        $pad = ''
        if ($prevLen -gt $txt.Length) { $pad = ' ' * ($prevLen - $txt.Length) }
        $conOut.WriteLine("`r" + $txt + $pad)
        $script:liveLine = $false
    }
    Write-Host ""
    Write-Host ("[OK] File ditutup : {0}  (total {1} baris data)" -f $fileName, $count) -ForegroundColor Green
    if ($carried) {
        Write-Host "[INFO] Potongan record terakhir dibawa ke file berikutnya agar tetap utuh." -ForegroundColor DarkGray
    }
}

$client       = $null
$stream       = $null
$writer       = $null
$serverClosed = $false

try {
    # ---------------- Tentukan IP/Port awal ----------------
    $cfg = Load-Config
    if ($cfg) {
        $IP = $cfg.IP; $Port = $cfg.PORT
        Write-Host ("[CONFIG] Memakai config tersimpan: {0}:{1}" -f $IP, $Port) -ForegroundColor DarkGray
    }
    else {
        $IP = $env:SERVER_IP; $Port = [int]$env:SERVER_PORT
        Write-Host ("[CONFIG] Memakai default: {0}:{1}" -f $IP, $Port) -ForegroundColor DarkGray
    }

    # ---------------- Loop koneksi (entry IP/Port bila gagal) ----------------
    while (-not $client) {
        Write-Host ("[INFO] Menghubungkan ke {0}:{1} ..." -f $IP, $Port) -ForegroundColor Cyan
        $client = Connect-Server $IP $Port 5000
        if ($client) { break }

        Write-Host ("[ERROR] Koneksi GAGAL: {0}" -f $script:connErr) -ForegroundColor Red
        Write-Host ""
        Write-Host "===== ENTRY KONFIGURASI SERVER =====" -ForegroundColor Yellow
        Write-Host ("  (Enter = pakai nilai sekarang)") -ForegroundColor DarkGray

        # --- kolom entry IP ---
        Write-Host ("  IP Server   [{0}] : " -f $IP) -NoNewline -ForegroundColor Cyan
        $inIP = Read-Host
        if (-not [string]::IsNullOrWhiteSpace($inIP)) { $IP = $inIP.Trim() }

        # --- kolom entry Port ---
        while ($true) {
            Write-Host ("  Port Server [{0}] : " -f $Port) -NoNewline -ForegroundColor Cyan
            $inPort = Read-Host
            if ([string]::IsNullOrWhiteSpace($inPort)) { break }
            $tmp = 0
            if ([int]::TryParse($inPort.Trim(), [ref]$tmp) -and $tmp -ge 1 -and $tmp -le 65535) {
                $Port = $tmp; break
            }
            Write-Host "  [PERINGATAN] Port harus angka 1-65535!" -ForegroundColor Red
        }

        # --- otomatis simpan config ---
        Save-Config $IP $Port
        Write-Host ""
    }

    $stream = $client.GetStream()
    $sock   = $client.Client
    Write-Host "[INFO] GO DATA - Terhubung ke server." -ForegroundColor Green
    if (-not (Test-Path -LiteralPath $cfgPath)) { Save-Config $IP $Port }

    # ================= Loop utama (satu state machine) =================
    #  mode NAME = sedang minta nama file  -> record ditampung di $pending
    #  mode REC  = sedang merekam ke file  -> record langsung ditulis
    #  Socket TETAP dibaca di kedua mode, sehingga batas antar-record tidak
    #  pernah hilang walau user sedang mengetik nama file.
    $pending  = New-Object 'System.Collections.Generic.List[string]'
    $partial  = New-Object System.Text.StringBuilder
    $nameBuf  = New-Object System.Text.StringBuilder
    $mode      = 'NAME'
    $skipEnter = $false
    $fileName = ''
    $count    = 0
    $latest   = ''
    $prevLen  = 0
    $liveLine = $false
    $sawNL    = $false

    # state framing untuk server tanpa pemisah
    $recLen     = $RecordLength
    $learnChunk = New-Object 'System.Collections.Generic.List[string]'
    $learnMs    = [Diagnostics.Stopwatch]::StartNew()
    $learnDone  = $false
    $showSw   = [Diagnostics.Stopwatch]::StartNew()

    Show-NamePrompt

    while (-not $serverClosed) {

        # ---------------- (1) Keyboard ----------------
        while ([System.Console]::KeyAvailable) {
            $k = [System.Console]::ReadKey($true)

            if ($mode -eq 'NAME') {
                if ($k.Key -eq [ConsoleKey]::Enter -or $k.KeyChar -eq "`r" -or $k.KeyChar -eq "`n") {
                    # Enter sisa dari perintah "x + Enter" -> abaikan sekali,
                    # supaya tidak dianggap nama file kosong.
                    if ($skipEnter) { $skipEnter = $false; continue }

                    $np = $nameBuf.ToString().Trim()
                    [void]$nameBuf.Clear()
                    $conOut.WriteLine()
                    if ($np.Length -eq 0) {
                        Write-Host "[PERINGATAN] Nama file WAJIB diisi, tidak boleh kosong!" -ForegroundColor Red
                        Show-NamePrompt
                    }
                    else {
                        $safe     = ($np -replace '[\\/:*?"<>|]', '_')
                        $fileName = "Alb-$safe.csv"
                        $fullPath = Join-Path (Get-Location).Path $fileName

                        # buffer kecil + flush tiap data masuk => REALTIME
                        $writer = New-Object System.IO.StreamWriter($fullPath, $true, $enc, 8192)
                        $writer.AutoFlush = $false

                        $count = 0; $latest = ''; $prevLen = 0; $liveLine = $false

                        Write-Host ""
                        Write-Host ("[REC] Menyimpan REALTIME ke : {0}" -f $fullPath) -ForegroundColor Green
                        Write-Host "[REC] Ketik 'x' lalu Enter untuk mengakhiri file ini & membuat file baru." -ForegroundColor Yellow

                        # record yang masuk saat mengetik nama -> tulis sekarang
                        if ($pending.Count -gt 0) {
                            foreach ($r in $pending) {
                                $o = $r
                                if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                                $writer.WriteLine($o); $count++; $latest = $r
                            }
                            $pending.Clear()
                            $writer.Flush()
                            Write-Host ("[REC] {0} record yang masuk saat input nama sudah ikut tersimpan." -f $count) -ForegroundColor DarkGray
                        }
                        Write-Host ""
                        $mode = 'REC'
                    }
                }
                elseif ($k.Key -eq [ConsoleKey]::Backspace -or [int]$k.KeyChar -eq 8 -or [int]$k.KeyChar -eq 127) {
                    if ($nameBuf.Length -gt 0) {
                        [void]$nameBuf.Remove($nameBuf.Length - 1, 1)
                        $conOut.Write("`b `b")
                    }
                }
                elseif ([int]$k.KeyChar -ge 32) {
                    $skipEnter = $false          # user sudah mulai mengetik
                    [void]$nameBuf.Append($k.KeyChar)
                    $conOut.Write($k.KeyChar)
                }
            }
            else {
                # mode REC: 'x' = akhiri file ini, minta nama baru
                if ($k.KeyChar -eq 'x' -or $k.KeyChar -eq 'X') {
                    Close-Session $false
                    $mode      = 'NAME'
                    $skipEnter = $true           # buang Enter yang mengikuti 'x'
                    [void]$nameBuf.Clear()
                    Show-NamePrompt
                }
            }
        }

        # ---------------- (2) Socket: baca + framing ----------------
        $wrote = $false

        # Tunggu data dengan Socket.Poll: langsung bangun begitu byte
        # pertama tiba. (Start-Sleep TIDAK dipakai: di Windows sleep
        # sependek 2ms tetap jadi ~15ms, sehingga pada data 10ms dua
        # record menumpuk di buffer dan terbaca sebagai satu record.)
        if ($sock.Poll($pollUs, [System.Net.Sockets.SelectMode]::SelectRead)) {
            $n = $stream.Read($buffer, 0, $buffer.Length)
            if ($n -le 0) { $serverClosed = $true; break }
            [void]$partial.Append($enc.GetString($buffer, 0, $n))

            $s      = $partial.ToString()
            $lastNL = $s.LastIndexOfAny($nlChars)

            if ($lastNL -ge 0) {
                # --- Framing A: server pakai newline -> potong per baris ---
                # Mode paling akurat. Sisa baris yang belum lengkap ditahan
                # sampai newline-nya datang, jadi record tidak pernah terpotong.
                $sawNL    = $true
                $complete = $s.Substring(0, $lastNL + 1)
                $rest     = $s.Substring($lastNL + 1)
                [void]$partial.Clear()
                [void]$partial.Append($rest)

                foreach ($line in ($complete -split '[\r\n]+')) {
                    if ($line.Length -eq 0) { continue }
                    if ($writer) {
                        $o = $line
                        if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                        $writer.WriteLine($o); $count++; $latest = $line; $wrote = $true
                    } else {
                        $pending.Add($line)
                    }
                }
            }
            elseif (-not $sawNL) {
                # =========== Framing B: server TIDAK pakai newline ===========
                # Tanpa pemisah, batas record TIDAK ada di dalam data. Timing
                # saja tidak cukup: sekali proses tersendat, dua record sudah
                # menumpuk dan batasnya hilang. Jadi begitu panjang record
                # diketahui tetap, pemisahan memakai panjang (deterministik).
                $emit = $null

                if ($recLen -gt 0) {
                    # ---- MODE PANJANG TETAP (tidak bergantung timing) ----
                    $k = [int][Math]::Floor($s.Length / $recLen)
                    if ($k -gt 0) {
                        $emit = New-Object 'System.Collections.Generic.List[string]'
                        for ($i = 0; $i -lt $k; $i++) {
                            [void]$emit.Add($s.Substring($i * $recLen, $recLen))
                        }
                        [void]$partial.Clear()
                        [void]$partial.Append($s.Substring($k * $recLen))
                    }
                }
                elseif ($learnDone) {
                    # ---- panjang TIDAK tetap: batas record hanya dari timing ----
                    # $capB = klep pengaman: kalau data mengalir terus tanpa
                    # jeda, socket tidak pernah kosong, jadi batas dari timing
                    # tidak pernah muncul. Tanpa klep ini buffer numpuk terus
                    # dan tidak ada yang tertulis.
                    if ((-not $stream.DataAvailable -or $s.Length -ge $capB) -and $s.Length -gt 0) {
                        [void]$partial.Clear()
                        $emit = New-Object 'System.Collections.Generic.List[string]'
                        [void]$emit.Add($s)
                    }
                }
                elseif ((-not $stream.DataAvailable) -or ($s.Length -ge $capB)) {
                    # ---- MODE BELAJAR ----
                    # Batas sementara dari timing, TAPI data ditahan dulu (maks
                    # ~300ms). Kalau ternyata panjangnya tetap, potongan yang
                    # sudah menumpuk dibelah ulang dengan benar SEBELUM ditulis,
                    # jadi tidak ada baris numpuk di file - termasuk baris awal.
                    # Catatan: TIDAK di-Trim, supaya byte & perataan tetap utuh.
                    if ($s.Length -gt 0) { [void]$learnChunk.Add($s) }
                    [void]$partial.Clear()

                    $decide = $false
                    if ($learnChunk.Count -ge 12) { $decide = $true }
                    elseif ($learnMs.ElapsedMilliseconds -ge 300) {
                        if ($learnChunk.Count -ge 4) { $decide = $true }
                        elseif ($learnChunk.Count -gt 0) {
                            # server lambat -> tidak ada risiko numpuk,
                            # tulis apa adanya biar tetap realtime
                            $emit = New-Object 'System.Collections.Generic.List[string]'
                            foreach ($c in $learnChunk) { [void]$emit.Add($c) }
                            $learnChunk.Clear(); $learnMs.Restart()
                        }
                        else { $learnMs.Restart() }
                    }

                    if ($decide) {
                        # Panjang record = panjang yang PALING SERING muncul
                        # (modus), BUKAN yang terpendek: potongan tidak lengkap
                        # akibat koneksi masuk di tengah stream tidak boleh
                        # dianggap sebagai panjang record.
                        $freq = @{}
                        foreach ($c in $learnChunk) { $freq[$c.Length] = 1 + [int]$freq[$c.Length] }
                        $L = [int]::MaxValue; $best = 0
                        foreach ($kv in $freq.GetEnumerator()) {
                            if ($kv.Value -gt $best -or ($kv.Value -eq $best -and $kv.Key -lt $L)) {
                                $best = $kv.Value; $L = $kv.Key
                            }
                        }
                        $mult = 0
                        foreach ($c in $learnChunk) { if (($c.Length % $L) -eq 0) { $mult++ } }

                        # Syarat sengaja ketat, supaya data yang panjangnya
                        # memang bervariasi TIDAK ikut dibelah:
                        #   >=60% chunk panjangnya TEPAT $L, dan
                        #   >=80% chunk kelipatan pas dari $L
                        $isFixed = ($L -gt 0) -and
                                   (($best * 100) -ge ($learnChunk.Count * 60)) -and
                                   (($mult * 100) -ge ($learnChunk.Count * 80))

                        $emit = New-Object 'System.Collections.Generic.List[string]'
                        if ($isFixed) {
                            $recLen = $L
                            # Chunk berurutan = potongan stream yang bersambung,
                            # jadi gabung semua lalu belah per $L. Sisa di DEPAN
                            # (r) adalah record tidak lengkap karena koneksi
                            # masuk di tengah record - tidak bisa dilengkapi.
                            $all = -join $learnChunk
                            $r   = $learnChunk[0].Length % $L
                            if ($r -gt 0) {
                                Write-Host ("`n[INFO] {0} karakter pertama dibuang: record tidak lengkap (koneksi masuk di tengah record)." -f $r) -ForegroundColor DarkGray
                            }
                            $rest = $all.Substring($r)
                            $k2   = [int][Math]::Floor($rest.Length / $L)
                            for ($i = 0; $i -lt $k2; $i++) {
                                [void]$emit.Add($rest.Substring($i * $L, $L))
                            }
                            [void]$partial.Clear()
                            [void]$partial.Append($rest.Substring($k2 * $L))
                            Write-Host ("[INFO] Data tanpa pemisah: panjang record TETAP {0} karakter -> pemisahan deterministik, tidak akan menumpuk lagi." -f $L) -ForegroundColor DarkGray
                        }
                        else {
                            foreach ($c in $learnChunk) { [void]$emit.Add($c) }
                            Write-Host "`n[PERINGATAN] Data tanpa pemisah dan panjangnya TIDAK tetap. Batas record hanya bisa dari timing, jadi saat data sangat cepat masih mungkin menumpuk. Solusi pasti: minta server mengirim newline, atau set `$RecordLength di script." -ForegroundColor Yellow
                        }
                        $learnChunk.Clear()
                        $learnDone = $true
                    }
                }

                if ($emit) {
                    foreach ($rec in $emit) {
                        if ($rec.Length -eq 0) { continue }
                        if ($writer) {
                            $o = $rec
                            if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                            $writer.WriteLine($o); $count++; $latest = $rec; $wrote = $true
                        } else {
                            $pending.Add($rec)
                        }
                    }
                }
            }
        }

        # ---------------- (3) Save realtime + tampilkan 1 baris ----------------
        if ($wrote) {
            # >>> SAVE REALTIME: data langsung masuk file <<<
            $writer.Flush()

            # Tampilkan HANYA 1 data terakhir yang SUDAH tersimpan, update di
            # tempat. Di-throttle ~120ms supaya console tidak jadi bottleneck.
            if ($showSw.ElapsedMilliseconds -ge 120) {
                Show-Live
                $showSw.Restart()
            }
        }
    }

    # ---------------- Server menutup koneksi ----------------
    if ($writer) { Close-Session $true }
    if ($serverClosed) {
        Write-Host "[INFO] Server menutup koneksi. Program selesai." -ForegroundColor Yellow
    }
}
catch {
    Write-Host ("`n[ERROR] Terjadi kesalahan: {0}" -f $_) -ForegroundColor Red
}
finally {
    if ($writer) { try { $writer.Flush(); $writer.Close() } catch { } }
    if ($stream) { try { $stream.Close() }                 catch { } }
    if ($client) { try { $client.Close() }                 catch { } }
    Write-Host "`n[INFO] Koneksi ditutup." -ForegroundColor Yellow
}
