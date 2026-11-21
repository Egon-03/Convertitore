# ConvertiTutto

Convertitore di file per Windows: trascini un file, l'app lo riconosce e propone
le conversioni adatte, premi **Converti**. Tutto avviene sul PC, senza internet.

## Cosa converte

| Tipo | Esempi di formati |
|---|---|
| Immagini | JPG, PNG, HEIC (iPhone), WEBP, AVIF, TIFF, BMP, GIF, ICO, SVG, PSD, RAW delle fotocamere → JPG, PNG, WEBP, AVIF, TIFF, BMP, GIF, ICO, PDF |
| Video | MP4, MOV, MKV, AVI, WMV, WEBM, FLV, 3GP… → MP4, MP4 per WhatsApp (< 16 MB), MKV, AVI, WEBM, MOV, WMV, GIF, MP3, fotogrammi JPG |
| Audio | MP3, WAV, FLAC, AAC, M4A, OGG, OPUS, WMA, AIFF… → tutti questi |
| Documenti | Word, Excel, PowerPoint (anche 97-2003), OpenOffice, RTF, TXT, HTML → PDF, DOCX, DOC, ODT, XLSX, XLS, ODS, CSV, PPTX, PPT, ODP, immagini |
| Apple | Pages, Keynote, Numbers → Word, PowerPoint, Excel, PDF, OpenOffice |
| PDF | → Word modificabile (con OCR per le scansioni), Excel (tabelle), immagini, testo, PowerPoint, PDF compresso, PDF ricercabile, EPUB |
| CAD | DWG, DXF → PDF (A3/A4), DXF, DWG (anche versione 2000), PNG, JPG, SVG |
| Archivi | ZIP, 7Z, RAR, TAR, GZ, ISO, cartelle → estrazione, ZIP, 7Z, TAR, TAR.GZ |
| E-book | EPUB, MOBI, AZW3, FB2… → EPUB, Kindle (AZW3), MOBI, PDF, DOCX, TXT |

## PDF in Word

* PDF "normali": impaginazione, tabelle, immagini e stili ricostruiti (pdf2docx).
* PDF scansionati o foto di documenti: il testo viene letto con l'OCR (Tesseract,
  modelli di alta precisione per italiano, tedesco, francese, inglese, spagnolo) e
  ricostruito in paragrafi modificabili, con dimensioni del testo, grassetti e
  allineamenti. Le pagine miste (alcune scansionate, altre no) vengono gestite pagina per pagina.

## Creare l'installazione (.exe)

**Su un PC Windows** (serve Python 3.12 e Inno Setup 6):

```powershell
winget install Python.Python.3.12 JRSoftware.InnoSetup
powershell -ExecutionPolicy Bypass -File build\build.ps1
```

(se Python 3.12 o Inno Setup 6 mancano, `build.ps1` li installa da solo con winget).

Il file `build\Output\ConvertiTutto-Setup-1.0.0.exe` è l'installazione completa.
Per controllarla: `powershell -ExecutionPolicy Bypass -File build\verifica.ps1`
(installa in `C:\tmp`, avvia l'app, controlla il menu del tasto destro ed esegue
tutti i test, anche con i DWG e i file Pages/Keynote/Numbers reali di `tests\reali`).
Lo script scarica da solo i componenti gratuiti (FFmpeg, LibreOffice, Tesseract,
7-Zip, LibreDWG, Calibre) e li mette dentro l'installazione: chi installa
ConvertiTutto non deve installare nient'altro.

**Con GitHub**: carica questa cartella in un repository; il workflow
`.github/workflows/build-windows.yml` crea l'installazione e la mette tra gli
*Artifacts* della build.

## Provare senza installare

```powershell
pip install -r requirements.txt
python main.py
```

(serve avere FFmpeg, LibreOffice, ecc. nel PATH oppure nella cartella `tools`).

## Struttura

* `main.py` – avvio (accetta file come argomenti, usato dal menu del tasto destro)
* `convertitutto/formats.py` – riconoscimento dei file e conversioni proposte
* `convertitutto/engine.py` – motore di conversione
* `convertitutto/ui.py` – interfaccia (trascina → scegli → fatto)
* `convertitutto/settings.py` – impostazioni
* `convertitutto/winutil.py` – menu del tasto destro, apertura file
* `build/` – script per creare l'installazione
* `tests/` – file di prova e test di tutte le conversioni

## Limiti

* Non rimuove protezioni DRM.
* Non crea archivi RAR (licenza chiusa): li apre e li converte in ZIP/7Z.
* PDF con impaginazioni molto complesse (riviste, moduli grafici) possono richiedere qualche ritocco in Word.
