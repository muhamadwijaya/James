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

# Cocokkan 1 kolom penuh yang akan dirusak Excel:
#   - angka >= 16 digit          (presisi hilang)
#   - angka berawalan 0          (nol di depan dihapus Excel)
#   - angka/desimal sangat panjang
$rxRisk = [regex]::new('(?<=^|,)(0\d+|\d[\d.]{15,})(?=,|$)', 'Compiled')
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
    $rem     = $partial.ToString()
    $carried = $false

    if ($rem.Trim().Length -gt 0) {
        if (-not $sawNL) {
            # server tanpa pemisah: sisa ini record utuh
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

        if ($stream.DataAvailable) {
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
            elseif (-not $sawNL -and -not $stream.DataAvailable) {
                # --- Framing B: server TIDAK pakai newline ---
                # Satu burst = satu record (seperti SHARKCODE versi awal).
                # Syarat -not DataAvailable: kalau masih ada lanjutan menunggu,
                # data digabung dulu supaya record tidak terpotong.
                $rec = $s.Trim()
                [void]$partial.Clear()
                if ($rec.Length -gt 0) {
                    if ($writer) {
                        $o = $rec
                        if ($ExcelSafe) { $o = $rxRisk.Replace($o, '="$1"') }
                        $writer.WriteLine($o); $count++; $latest = $rec; $wrote = $true
                    } else {
                        $pending.Add($rec)
                    }
                }
            }
            # else: belum ada newline tapi masih ada data menunggu ->
            #       biarkan menumpuk (menyatukan record yang terpotong)
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
        elseif (-not $stream.DataAvailable) {
            Start-Sleep -Milliseconds 2
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
