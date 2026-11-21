# ConvertiTutto – note per Claude Code

App desktop per Windows (Python 3.12 + PySide6) che converte file di ogni tipo.
Interfaccia in italiano, minimal, in 3 passaggi: trascina → scegli la conversione → fatto.

## Stato
- Motore e interfaccia completi e testati su Linux: 105/106 conversioni riuscite (`tests/run_all.py`).
- NON ancora provati: lettura/scrittura DWG (serve LibreDWG, scaricato da `build/scarica_strumenti.ps1`),
  file Apple Pages/Keynote/Numbers (convertiti da LibreOffice), la build Windows stessa.

## Obiettivo
Produrre `build\Output\ConvertiTutto-Setup-<versione>.exe` funzionante su Windows 10/11 x64.

## Come si crea l'installazione
- Locale (Windows): `powershell -ExecutionPolicy Bypass -File build\build.ps1`
  (serve Python 3.12 e Inno Setup 6: `winget install Python.Python.3.12 JRSoftware.InnoSetup`).
- GitHub: push su `main` → workflow `.github/workflows/build-windows.yml` → artifact `ConvertiTutto-Setup`.

`build/scarica_strumenti.ps1` mette in `tools/` FFmpeg, LibreOffice, Tesseract (+ lingue ita/deu/fra/eng/spa),
7-Zip, LibreDWG, Calibre. `convertitutto/tools.py` li cerca prima in `tools/` accanto all'exe, poi nel PATH.

## Cosa verificare dopo la build
1. L'exe parte e la finestra mostra "Trascina qui un file".
2. `python tests\make_samples.py C:\tmp\campioni` e `python tests\run_all.py C:\tmp\campioni C:\tmp\out`
   usando i tool in `tools\` (aggiungerli al PATH o eseguire dalla cartella dell'app).
3. Provare a mano un DWG reale → PDF/DXF e un file .pages → DOCX.
4. Menu del tasto destro "Converti con ConvertiTutto" dopo l'installazione.
5. Se PyInstaller dimentica moduli (cv2 per pdf2docx, fontTools, template di python-docx/pptx),
   aggiungere `--collect-*` / `--hidden-import` in `build/build.ps1`.

## Struttura
- `main.py` avvio (file come argomenti dal menu contestuale)
- `convertitutto/formats.py` riconoscimento file + conversioni proposte (consigliate / altre)
- `convertitutto/engine.py` conversioni (Pillow, FFmpeg, LibreOffice, PyMuPDF+Tesseract OCR, pdf2docx, ezdxf, py7zr, Calibre)
- `convertitutto/ui.py` interfaccia Qt; `settings.py` impostazioni in %APPDATA%; `winutil.py` registro/menu contestuale
- `build/` script di build e installer Inno Setup; `tests/` campioni e test

## Regole
- Testi dell'interfaccia in italiano semplice.
- Non aggiungere rimozione DRM. Non creare archivi RAR (solo estrazione).
