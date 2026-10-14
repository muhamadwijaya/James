@echo off
rem ==========================================================================
rem  Build FTP Photo Renamer menjadi 1 file .exe
rem    - backend C#  : dotnet publish (jika .NET SDK ada) atau csc.exe bawaan Windows
rem    - GUI PySide6 : PyInstaller --onefile (backend ikut dibundel di dalamnya)
rem  Hasil: dist\FtpPhotoRenamer.exe
rem ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Build FTP Photo Renamer

set "APP_NAME=FtpPhotoRenamer"
set "ROOT=%~dp0"
set "BUILD=%ROOT%build"
set "BACKEND_OUT=%BUILD%\backend"
set "DIST=%ROOT%dist"
set "VENV=%ROOT%.venv"
set "VPY=%VENV%\Scripts\python.exe"

echo ============================================================
echo   Build %APP_NAME% - FRT Cam  [GUI PySide6 + backend C#]
echo ============================================================
echo.

rem --------------------------------------------------------------------------
echo [1/4] Menyiapkan Python...
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :python_found
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :python_found
echo [GAGAL] Python 3.9 atau lebih baru tidak ditemukan.
echo         Install dari https://www.python.org/downloads/
echo         dan centang "Add python.exe to PATH" saat instalasi.
goto :fail

:python_found
echo       Python : %PY%
if exist "%VPY%" goto :venv_ready
echo       Membuat virtual environment .venv ...
%PY% -m venv "%VENV%"
if errorlevel 1 goto :fail

:venv_ready
echo       Install dependency: PySide6 dan PyInstaller ...
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip >nul 2>&1
"%VPY%" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt"
if errorlevel 1 goto :fail

rem --------------------------------------------------------------------------
echo.
echo [2/4] Build backend C# ...
if exist "%BACKEND_OUT%" rmdir /s /q "%BACKEND_OUT%" >nul 2>&1
mkdir "%BACKEND_OUT%" >nul 2>&1

where dotnet >nul 2>&1
if errorlevel 1 goto :use_csc
dotnet --list-sdks 2>nul | findstr /r "^[0-9]" >nul
if errorlevel 1 goto :use_csc

echo       Memakai .NET SDK - dotnet publish self-contained ...
dotnet publish "%ROOT%backend\FtpBackend.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=true -p:EnableCompressionInSingleFile=true -p:DebugType=none -o "%BACKEND_OUT%" --nologo
if not errorlevel 1 goto :backend_check
echo       [PERINGATAN] dotnet publish gagal, mencoba csc.exe bawaan Windows ...

:use_csc
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if exist "%CSC%" goto :csc_found
echo [GAGAL] .NET SDK maupun csc.exe .NET Framework 4.x tidak ditemukan.
echo         Install .NET 8 SDK dari https://dotnet.microsoft.com/download
goto :fail

:csc_found
echo       Memakai compiler bawaan Windows: %CSC%
"%CSC%" /nologo /optimize+ /target:exe /platform:anycpu /out:"%BACKEND_OUT%\FtpBackend.exe" /r:System.dll /r:System.Core.dll "%ROOT%backend\*.cs"
if errorlevel 1 goto :fail

:backend_check
if exist "%BACKEND_OUT%\FtpBackend.exe" goto :backend_done
echo [GAGAL] FtpBackend.exe tidak terbentuk.
goto :fail

:backend_done
echo       OK : %BACKEND_OUT%\FtpBackend.exe

rem --------------------------------------------------------------------------
echo.
echo [3/4] Build GUI menjadi .exe dengan PyInstaller ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed --log-level WARN ^
  --name "%APP_NAME%" ^
  --distpath "%DIST%" ^
  --workpath "%BUILD%\pyinstaller" ^
  --specpath "%BUILD%" ^
  --paths "%ROOT%gui" ^
  --add-binary "%BACKEND_OUT%\FtpBackend.exe;backend" ^
  --icon "%ROOT%assets\app.ico" ^
  "%ROOT%gui\main.py"
if errorlevel 1 goto :fail
if not exist "%DIST%\%APP_NAME%.exe" goto :fail

rem --------------------------------------------------------------------------
echo.
echo [4/4] SELESAI
echo.
echo   Aplikasi : %DIST%\%APP_NAME%.exe
echo.
echo   Jalankan aplikasi, isi IP, port, LINE-ID dan folder tujuan,
echo   lalu klik "Mulai Server". Saat pertama kali jalan, izinkan
echo   akses jaringan di jendela Windows Firewall.
echo.
if not defined NO_PAUSE pause
exit /b 0

:fail
echo.
echo ============================================================
echo   BUILD GAGAL - lihat pesan error di atas.
echo ============================================================
if not defined NO_PAUSE pause
exit /b 1
