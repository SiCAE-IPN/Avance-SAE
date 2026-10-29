@echo off
chcp 65001 >nul
echo =========================================================
echo  Compilando Instalador_SiCAE.exe (Nativo Windows 10/11)
echo =========================================================
cd /d "%~dp0"

set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    set "CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

"%CSC%" /target:winexe /out:"Instalador_SiCAE.exe" /win32icon:"sicae_icon.ico" /resource:"sicae_header.png",sicae_header.png /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll "src\InstaladorSiCAE.cs"

if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la compilacion del instalador.
    pause
    exit /b 1
)

echo.
echo [OK] Instalador_SiCAE.exe generado exitosamente en: %cd%\Instalador_SiCAE.exe

