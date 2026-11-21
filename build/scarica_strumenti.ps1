# Scarica i programmi gratuiti usati da ConvertiTutto nella cartella "tools".
# Uso:  powershell -ExecutionPolicy Bypass -File build\scarica_strumenti.ps1
# Tutti i componenti sono software libero o gratuito da ridistribuire:
#   FFmpeg (GPL), LibreOffice (MPL), Tesseract OCR (Apache), 7-Zip (LGPL),
#   LibreDWG (GPL), Calibre (GPL).

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root  = Split-Path -Parent $PSScriptRoot
$Tools = Join-Path $Root "tools"
$Tmp   = Join-Path $env:TEMP "convertitutto_dl"
New-Item -ItemType Directory -Force -Path $Tools, $Tmp | Out-Null

function Get-File($url, $dest) {
    if (Test-Path $dest) { return }
    Write-Host "  scarico $url"
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -Headers @{ "User-Agent" = "ConvertiTutto-build" }
}

function Get-GitHubAsset($repo, $pattern) {
    $headers = @{ "User-Agent" = "ConvertiTutto-build" }
    if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN" }
    # l'ultima versione a volte non contiene ancora i file per Windows: guarda anche le precedenti
    $rels = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases?per_page=15" -Headers $headers
    foreach ($rel in $rels) {
        if ($rel.draft) { continue }
        $asset = $rel.assets | Where-Object { $_.name -match $pattern } | Select-Object -First 1
        if ($asset) { Write-Host "  $repo $($rel.tag_name): $($asset.name)"; return $asset.browser_download_url }
    }
    throw "Nessun file '$pattern' nelle versioni recenti di $repo"
}

function Expand-Msi($msi, $target) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $p = Start-Process msiexec.exe -ArgumentList "/a `"$msi`" /qn TARGETDIR=`"$target`"" -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Estrazione di $msi fallita ($($p.ExitCode))" }
}

# ---------------------------------------------------------------- 7-Zip (serve anche per estrarre gli altri)
Write-Host "7-Zip"
$sevenDir = Join-Path $Tools "7zip"
if (-not (Test-Path (Join-Path $sevenDir "7z.exe"))) {
    $zr = Join-Path $Tmp "7zr.exe"
    Get-File "https://www.7-zip.org/a/7zr.exe" $zr
    $page = (Invoke-WebRequest "https://www.7-zip.org/download.html" -UseBasicParsing).Content
    $ver = [regex]::Match($page, 'a/7z(\d{4})-x64\.exe').Groups[1].Value
    if (-not $ver) { $ver = "2409" }
    $inst = Join-Path $Tmp "7z-x64.exe"
    Get-File "https://www.7-zip.org/a/7z$ver-x64.exe" $inst
    & $zr x $inst "-o$sevenDir" -y | Out-Null
}
$7z = Join-Path $sevenDir "7z.exe"

# ---------------------------------------------------------------- FFmpeg
Write-Host "FFmpeg"
$ffDir = Join-Path $Tools "ffmpeg"
if (-not (Test-Path (Join-Path $ffDir "bin\ffmpeg.exe"))) {
    $zip = Join-Path $Tmp "ffmpeg.zip"
    Get-File "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" $zip
    $x = Join-Path $Tmp "ffmpeg_x"
    & $7z x $zip "-o$x" -y | Out-Null
    $inner = Get-ChildItem $x -Directory | Select-Object -First 1
    Move-Item $inner.FullName $ffDir
}

# ---------------------------------------------------------------- Tesseract OCR + lingue (modelli "best", più precisi)
Write-Host "Tesseract OCR"
$tessDir = Join-Path $Tools "tesseract"
if (-not (Test-Path (Join-Path $tessDir "tesseract.exe"))) {
    $url = Get-GitHubAsset "UB-Mannheim/tesseract" "w64-setup.*\.exe$"
    $inst = Join-Path $Tmp "tesseract-setup.exe"
    Get-File $url $inst
    & $7z x $inst "-o$tessDir" -y | Out-Null   # l'installer NSIS si estrae senza installare
    Remove-Item -Recurse -Force (Join-Path $tessDir '$PLUGINSDIR') -ErrorAction SilentlyContinue
    if (-not (Test-Path (Join-Path $tessDir "tesseract.exe"))) {
        $exe = Get-ChildItem $tessDir -Recurse -Filter "tesseract.exe" | Select-Object -First 1
        if (-not $exe) { throw "tesseract.exe non trovato nell'installer" }
        Get-ChildItem $exe.DirectoryName | Move-Item -Destination $tessDir -Force
    }
}
$tessdata = Join-Path $tessDir "tessdata"
New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
foreach ($lang in "ita", "deu", "fra", "eng", "spa", "osd") {
    $dest = Join-Path $tessdata "$lang.traineddata"
    $repo = if ($lang -eq "osd") { "tessdata" } else { "tessdata_best" }
    Get-File "https://github.com/tesseract-ocr/$repo/raw/main/$lang.traineddata" $dest
}

# ---------------------------------------------------------------- LibreDWG (DWG)
Write-Host "LibreDWG"
$dwgDir = Join-Path $Tools "libredwg"
if (-not (Test-Path (Join-Path $dwgDir "dwg2dxf.exe"))) {
    $url = Get-GitHubAsset "LibreDWG/libredwg" "win64\.zip$"
    $zip = Join-Path $Tmp "libredwg.zip"
    Get-File $url $zip
    $x = Join-Path $Tmp "libredwg_x"
    & $7z x $zip "-o$x" -y | Out-Null
    $exe = Get-ChildItem $x -Recurse -Filter "dwg2dxf.exe" | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path $dwgDir | Out-Null
    Copy-Item (Join-Path $exe.DirectoryName "*") $dwgDir -Recurse -Force
}

# ---------------------------------------------------------------- LibreOffice (documenti, Apple Pages/Keynote/Numbers)
Write-Host "LibreOffice"
$loDir = Join-Path $Tools "libreoffice"
if (-not (Test-Path (Join-Path $loDir "program\soffice.exe"))) {
    $base = "https://download.documentfoundation.org/libreoffice/stable/"
    $list = (Invoke-WebRequest $base -UseBasicParsing).Links.href | Where-Object { $_ -match '^\d+\.\d+\.\d+/$' }
    $ver = ($list | ForEach-Object { $_.TrimEnd('/') } | Sort-Object { [version]$_ } | Select-Object -Last 1)
    $msi = Join-Path $Tmp "libreoffice.msi"
    Get-File "$base$ver/win/x86_64/LibreOffice_${ver}_Win_x86-64.msi" $msi
    $x = Join-Path $Tmp "lo_x"
    Expand-Msi $msi $x
    $prog = Get-ChildItem $x -Recurse -Filter "soffice.exe" | Select-Object -First 1
    Move-Item $prog.Directory.Parent.FullName $loDir
}

# ---------------------------------------------------------------- Calibre (e-book)
Write-Host "Calibre"
$calDir = Join-Path $Tools "calibre"
if (-not (Test-Path (Join-Path $calDir "ebook-convert.exe"))) {
    $msi = Join-Path $Tmp "calibre.msi"
    Get-File "https://calibre-ebook.com/dist/win64" $msi
    $x = Join-Path $Tmp "calibre_x"
    Expand-Msi $msi $x
    $exe = Get-ChildItem $x -Recurse -Filter "ebook-convert.exe" | Select-Object -First 1
    Move-Item $exe.Directory.FullName $calDir
}

Write-Host ""
Write-Host "Strumenti pronti in $Tools"
Get-ChildItem $Tools -Directory | ForEach-Object { Write-Host "  - $($_.Name)" }
