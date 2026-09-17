@echo off
setlocal
title SHARKCODE - CSV Logger BY WIJAYA
color 0A

:: ============================================================
::  Konfigurasi IP dan Port Server
:: ============================================================
set "SERVER_IP=192.168.1.45"
set "SERVER_PORT=2002"

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
#  - Minta nama file CSV (otomatis diawali 'Alb-', WAJIB diisi)
#  - Data dari server disimpan ke file tsb (buffered = sangat cepat)
#  - Ketik 'x' lalu Enter  -> tutup file ini, minta nama file baru
#  - Tutup jendela / Ctrl+C -> keluar
# ============================================================

# --- Opsi: tampilkan data di layar? ($false = throughput maksimum) ---
$ShowData = $true

$IP   = $env:SERVER_IP
$Port = [int]$env:SERVER_PORT

$enc    = New-Object System.Text.UTF8Encoding($false)   # UTF-8 tanpa BOM
$buffer = New-Object byte[] 65536

# Warna sebagai enum (bukan string) + handle Console.Out => tampilan ~5x lebih cepat
$colorList = @(
    [ConsoleColor]::Cyan,        [ConsoleColor]::Yellow,
    [ConsoleColor]::Magenta,     [ConsoleColor]::Green,
    [ConsoleColor]::DarkCyan,    [ConsoleColor]::DarkYellow,
    [ConsoleColor]::DarkMagenta
)
$conOut = [Console]::Out

$client       = $null
$stream       = $null
$writer       = $null
$serverClosed = $false

try {
    # ---------------- Koneksi ke server ----------------
    Write-Host ("[INFO] Menghubungkan ke {0}:{1} ..." -f $IP, $Port) -ForegroundColor Cyan
    $client = New-Object System.Net.Sockets.TcpClient
    $client.NoDelay = $true
    $client.ReceiveBufferSize = 1048576
    $client.Connect($IP, $Port)
    $stream = $client.GetStream()
    Write-Host "[INFO] GO DATA - Terhubung ke server." -ForegroundColor Green

    # ================= Loop per-file (sesi penyimpanan) =================
    while (-not $serverClosed) {

        # ---------- Minta nama file CSV (WAJIB, prefiks 'Alb-') ----------
        $namePart = $null
        while ([string]::IsNullOrWhiteSpace($namePart)) {
            Write-Host ""
            Write-Host "Masukkan nama file CSV (otomatis diawali 'Alb-') :" -ForegroundColor Cyan
            Write-Host "Alb-" -NoNewline -ForegroundColor Green
            $namePart = Read-Host
            if ([string]::IsNullOrWhiteSpace($namePart)) {
                Write-Host "[PERINGATAN] Nama file WAJIB diisi, tidak boleh kosong!" -ForegroundColor Red
            }
        }

        # Bersihkan karakter ilegal untuk nama file
        $safe     = ($namePart.Trim() -replace '[\\/:*?"<>|]', '_')
        $fileName = "Alb-$safe.csv"
        $fullPath = Join-Path (Get-Location).Path $fileName

        # StreamWriter buffered (append) + AutoFlush off => penyimpanan sangat cepat
        $writer = New-Object System.IO.StreamWriter($fullPath, $true, $enc, 1048576)
        $writer.AutoFlush = $false

        Write-Host ""
        Write-Host ("[REC] Menyimpan data ke : {0}" -f $fullPath) -ForegroundColor Green
        Write-Host "[REC] Ketik 'x' lalu Enter untuk mengakhiri file ini & membuat file baru." -ForegroundColor Yellow
        Write-Host ""

        $knownData  = [System.Collections.Generic.Dictionary[string,int]]::new()
        $partial    = New-Object System.Text.StringBuilder
        $count      = 0
        $sinceFlush = 0

        # ---------- Loop terima data + pantau tombol 'x' ----------
        while ($true) {

            # (1) Cek keyboard: 'x' = akhiri sesi file ini
            $stop = $false
            while ([System.Console]::KeyAvailable) {
                $k = [System.Console]::ReadKey($true)   # $true = jangan tampilkan tombol
                if ($k.KeyChar -eq 'x' -or $k.KeyChar -eq 'X') { $stop = $true }
            }
            if ($stop) { break }

            # (2) Cek data dari server (non-blocking)
            if ($stream.DataAvailable) {
                $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
                if ($bytesRead -le 0) {
                    Write-Host "`n[INFO] Server menutup koneksi." -ForegroundColor Yellow
                    $serverClosed = $true
                    break
                }

                [void]$partial.Append($enc.GetString($buffer, 0, $bytesRead))

                # Pisahkan menjadi baris-baris lengkap (delimiter newline)
                $s      = $partial.ToString()
                $lastNL = $s.LastIndexOfAny([char[]]@("`n", "`r"))
                if ($lastNL -ge 0) {
                    $complete  = $s.Substring(0, $lastNL + 1)
                    $remainder = $s.Substring($lastNL + 1)
                    [void]$partial.Clear()
                    [void]$partial.Append($remainder)

                    foreach ($line in ($complete -split "`r?`n")) {
                        if ([string]::IsNullOrEmpty($line)) { continue }

                        # >>> Tulis ke file DULU (cepat, buffered) <<<
                        $writer.WriteLine($line)
                        $count++
                        $sinceFlush++

                        # Tampilan berwarna per data unik (opsional)
                        if ($ShowData) {
                            if (-not $knownData.ContainsKey($line)) {
                                $knownData[$line] = $knownData.Count + 1
                            }
                            $labelId = $knownData[$line]
                            [Console]::ForegroundColor = $colorList[($labelId - 1) % $colorList.Count]
                            $conOut.Write("[DATA " + $labelId + "] ")
                            [Console]::ResetColor()
                            $conOut.WriteLine($line)
                        }
                    }
                }

                # Flush: saat sudah tidak menumpuk (aman) atau tiap 1000 baris (tetap cepat)
                if (-not $stream.DataAvailable) {
                    $writer.Flush(); $sinceFlush = 0
                }
                elseif ($sinceFlush -ge 1000) {
                    $writer.Flush(); $sinceFlush = 0
                }
            }
            else {
                # Tidak ada data & tidak ada tombol => tidur singkat agar CPU rendah
                Start-Sleep -Milliseconds 5
            }
        }

        # ---------- Akhiri sesi file ini ----------
        # Tulis sisa data parsial (jika ada) sebagai satu baris terakhir
        $rem = $partial.ToString()
        if (-not [string]::IsNullOrWhiteSpace($rem)) {
            $writer.WriteLine($rem.Trim())
            $count++
        }
        $writer.Flush()
        $writer.Close()
        $writer = $null

        Write-Host ""
        Write-Host ("[OK] File ditutup : {0}  (total {1} baris data)" -f $fileName, $count) -ForegroundColor Green

        if ($serverClosed) {
            Write-Host "[INFO] Koneksi server berakhir. Program selesai." -ForegroundColor Yellow
        }
    }
}
catch {
    Write-Host ("`n[ERROR] Terjadi kesalahan: {0}" -f $_) -ForegroundColor Red
}
finally {
    if ($writer) { try { $writer.Flush(); $writer.Close() } catch {} }
    if ($stream) { try { $stream.Close() }                 catch {} }
    if ($client) { try { $client.Close() }                 catch {} }
    Write-Host "`n[INFO] Koneksi ditutup." -ForegroundColor Yellow
}
