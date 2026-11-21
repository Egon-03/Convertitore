# Crea l'installazione di ConvertiTutto per Windows.
# Requisiti sul PC di build: Python 3.12 o 3.13 (64 bit) e Inno Setup 6.
# Uso (da PowerShell, nella cartella del progetto):
#   powershell -ExecutionPolicy Bypass -File build\build.ps1
# Risultato: build\Output\ConvertiTutto-Setup-<versione>.exe

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Install-WithWinget($id) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return }
    Write-Host "  installo $id con winget"
    & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --scope user
    if ($LASTEXITCODE -ne 0) { & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements }
    # aggiorna il PATH della sessione corrente
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Find-Iscc {
    @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}

Write-Host "0/4  Requisiti (Python 3.12, Inno Setup 6)"
$hasPy = $false
try { & py -3.12 -c "import sys" *> $null; $hasPy = ($LASTEXITCODE -eq 0) } catch { }
if (-not $hasPy -and -not (Test-Path ".venv")) { Install-WithWinget "Python.Python.3.12" }
if (-not (Find-Iscc)) { Install-WithWinget "JRSoftware.InnoSetup" }

Write-Host "1/4  Ambiente Python"
if (-not (Test-Path ".venv")) {
    # preferisce Python 3.12 (3.13 come riserva) anche se sul PC ci sono altre versioni
    $made = $false
    $ErrorActionPreference = "Continue"
    foreach ($v in "-3.12", "-3.13") {
        try { & py $v -c "import sys" *> $null } catch { continue }
        if ($LASTEXITCODE -eq 0) { & py $v -m venv .venv; $made = $true; break }
    }
    if (-not $made) { try { & python -m venv .venv } catch { } }
    $ErrorActionPreference = "Stop"
    if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Python 3.12 non trovato: installalo con  winget install Python.Python.3.12" }
}
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
    --collect-submodules fontTools `
    --collect-data pdfminer `
    --hidden-import cv2 `
    --hidden-import py7zr `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallito" }
Copy-Item -Recurse -Force tools "dist\ConvertiTutto\tools"

Write-Host "4/4  Installazione (Inno Setup)"
$iscc = Find-Iscc
if (-not $iscc) { throw "Inno Setup 6 non trovato: installalo con  winget install JRSoftware.InnoSetup" }
$ver = (& $py -c "import convertitutto; print(convertitutto.__version__)").Trim()
& $iscc "/DAppVersion=$ver" (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallito" }
Write-Host ""
Write-Host "Fatto: build\Output\ConvertiTutto-Setup-$ver.exe"
