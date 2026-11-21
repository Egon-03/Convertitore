# Crea l'installazione di ConvertiTutto per Windows.
# Requisiti sul PC di build: Python 3.12 o 3.13 (64 bit) e Inno Setup 6.
# Uso (da PowerShell, nella cartella del progetto):
#   powershell -ExecutionPolicy Bypass -File build\build.ps1
# Risultato: build\Output\ConvertiTutto-Setup-<versione>.exe

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "1/4  Ambiente Python"
if (-not (Test-Path ".venv")) { py -3 -m venv .venv }
$py = Join-Path $Root ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Installazione dei pacchetti Python fallita" }

Write-Host "2/4  Componenti di conversione"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "scarica_strumenti.ps1")
if ($LASTEXITCODE -ne 0) { throw "Download dei componenti fallito" }

Write-Host "3/4  Programma (PyInstaller)"
& $py -m PyInstaller --noconfirm --clean --windowed `
    --name ConvertiTutto `
    --icon assets\icon.ico `
    --add-data "assets;assets" `
    --collect-all pymupdf `
    --collect-all pillow_heif `
    --collect-data docx `
    --collect-data pptx `
    --collect-submodules ezdxf `
    --collect-submodules pdf2docx `
    --collect-submodules rawpy `
    --hidden-import py7zr `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallito" }
Copy-Item -Recurse -Force tools "dist\ConvertiTutto\tools"

Write-Host "4/4  Installazione (Inno Setup)"
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 non trovato: installalo con  winget install JRSoftware.InnoSetup" }
$ver = (& $py -c "import convertitutto; print(convertitutto.__version__)").Trim()
& $iscc "/DAppVersion=$ver" (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallito" }
Write-Host ""
Write-Host "Fatto: build\Output\ConvertiTutto-Setup-$ver.exe"
