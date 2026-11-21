# Verifica l'installazione di ConvertiTutto dopo la build.
# Uso (da PowerShell, nella cartella del progetto, dopo build\build.ps1):
#   powershell -ExecutionPolicy Bypass -File build\verifica.ps1
# Installa il setup in una cartella di prova, avvia l'app, controlla la finestra e il
# menu del tasto destro, poi esegue i test (con Python e con l'exe installato).
# Resoconti e schermata in build\verifica\.

param([string]$Work = "C:\tmp")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Out = Join-Path $PSScriptRoot "verifica"
New-Item -ItemType Directory -Force -Path $Out, $Work | Out-Null
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$problemi = @()

$setup = Get-ChildItem (Join-Path $PSScriptRoot "Output") -Filter "ConvertiTutto-Setup-*.exe" | Select-Object -First 1
if (-not $setup) { throw "Installazione non trovata in build\Output: esegui prima build\build.ps1" }
Write-Host "Setup: $($setup.FullName)  ($([math]::Round($setup.Length / 1MB)) MB)"

# ------------------------------------------------------------ 1. installazione silenziosa
$app = Join-Path $Work "ConvertiTutto_installato"
$p = Start-Process $setup.FullName -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /TASKS=`"contextmenu`" /DIR=`"$app`" /LOG=`"$Out\installazione.log`"" -Wait -PassThru
$exe = Join-Path $app "ConvertiTutto.exe"
if ($p.ExitCode -ne 0 -or -not (Test-Path $exe)) { throw "Installazione fallita (codice $($p.ExitCode))" }
Write-Host "Installato in $app"

# ------------------------------------------------------------ 2. menu del tasto destro
$key = "HKCU:\Software\Classes\*\shell\ConvertiTutto\command"
if (Test-Path -LiteralPath $key) {
    Write-Host "Menu del tasto destro: $((Get-ItemProperty -LiteralPath $key).'(default)')"
} else { $problemi += "menu del tasto destro non registrato" }

# ------------------------------------------------------------ 3. avvio dell'app e finestra
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing, System.Windows.Forms
$proc = Start-Process $exe -PassThru
$trovato = $false
for ($i = 0; $i -lt 60 -and -not $trovato; $i++) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) { break }
    $proc.Refresh()
    if ($proc.MainWindowHandle -eq 0) { continue }
    $win = [Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
    $cond = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty, "Trascina qui un file")
    if ($win.FindFirst([Windows.Automation.TreeScope]::Descendants, $cond)) { $trovato = $true }
}
Start-Sleep -Seconds 2
$b = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $b.Width, $b.Height
[Drawing.Graphics]::FromImage($bmp).CopyFromScreen($b.Location, [Drawing.Point]::Empty, $b.Size)
$bmp.Save((Join-Path $Out "avvio.png"), [Drawing.Imaging.ImageFormat]::Png)
if ($proc.HasExited) { $problemi += "l'app si è chiusa subito (codice $($proc.ExitCode))" }
elseif ($trovato) { Write-Host "Avvio OK: titolo '$($proc.MainWindowTitle)', testo 'Trascina qui un file' presente" }
else { $problemi += "finestra senza il testo 'Trascina qui un file'" }
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }

# ------------------------------------------------------------ 4. test con Python (tool di tools\ nel PATH)
$py = Join-Path $Root ".venv\Scripts\python.exe"
$t = Join-Path $Root "tools"
$env:Path = (@("$t\ffmpeg\bin", "$t\libreoffice\program", "$t\tesseract", "$t\7zip", "$t\libredwg", "$t\calibre") -join ";") + ";" + $env:Path
$env:TESSDATA_PREFIX = "$t\tesseract\tessdata"
$campioni = Join-Path $Work "campioni"
$ErrorActionPreference = "Continue"
& $py tests\make_samples.py $campioni 2>&1 | Tee-Object (Join-Path $Out "make_samples.log")
if ($LASTEXITCODE -ne 0) { $problemi += "make_samples.py fallito" }
& $py tests\run_all.py $campioni (Join-Path $Work "out") 2>&1 | Tee-Object (Join-Path $Out "run_all.log")
& $py tests\run_all.py tests\reali (Join-Path $Work "out_reali") 2>&1 | Tee-Object (Join-Path $Out "run_all_reali.log")
$ErrorActionPreference = "Stop"

# ------------------------------------------------------------ 5. stessi test con l'exe installato
Remove-Item Env:TESSDATA_PREFIX
foreach ($c in @(@($campioni, "out_exe", "autotest_exe.log"), @((Join-Path $Root "tests\reali"), "out_exe_reali", "autotest_exe_reali.log"))) {
    $rep = Join-Path $Out $c[2]
    $p = Start-Process $exe -ArgumentList "--autotest `"$($c[0])`" `"$(Join-Path $Work $c[1])`" `"$rep`"" -Wait -PassThru
    if (Test-Path $rep) { Get-Content $rep | Write-Host } else { $problemi += "autotest dell'exe senza resoconto ($($c[2]))" }
}

Write-Host ""
foreach ($f in "run_all.log", "run_all_reali.log", "autotest_exe.log", "autotest_exe_reali.log") {
    $l = Join-Path $Out $f
    if (Test-Path $l) { Write-Host ("{0,-24} {1}" -f $f, ((Get-Content $l | Select-String "Riuscite:") -join "")) }
}
if ($problemi) { Write-Host "PROBLEMI:"; $problemi | ForEach-Object { Write-Host "  - $_" } }
else { Write-Host "Avvio, menu e test eseguiti: vedi i resoconti in $Out" }
