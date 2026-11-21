"""Riconoscimento del tipo di file e conversioni proposte per ciascun tipo."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Target:
    id: str            # identificativo interno, es. "pdf>docx"
    ext: str           # estensione del file prodotto (senza punto)
    title: str         # nome mostrato sulla scheda
    desc: str = ""     # breve spiegazione
    badge: str = ""    # etichetta piccola (formato)


@dataclass
class FileKind:
    key: str
    label: str                       # es. "PDF scansionato"
    color: tuple[str, str]           # (sfondo, testo) del badge
    recommended: list[Target] = field(default_factory=list)
    more: list[Target] = field(default_factory=list)


IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff", "ico", "heic", "heif",
             "avif", "jfif", "tga", "ppm", "psd", "cr2", "cr3", "nef", "arw", "dng", "orf", "rw2", "raf", "svg"}
VIDEO_EXT = {"mp4", "mov", "mkv", "avi", "wmv", "flv", "webm", "m4v", "mpg", "mpeg", "3gp", "ts", "mts", "m2ts", "vob", "ogv"}
AUDIO_EXT = {"mp3", "wav", "flac", "aac", "ogg", "oga", "m4a", "wma", "opus", "aiff", "aif", "amr", "ac3", "mka"}
WORD_EXT = {"doc", "docx", "odt", "rtf", "txt", "wpd", "docm", "dot", "dotx", "html", "htm", "md"}
SHEET_EXT = {"xls", "xlsx", "ods", "csv", "xlsm", "tsv"}
SLIDE_EXT = {"ppt", "pptx", "odp", "pps", "ppsx"}
APPLE_EXT = {"pages", "key", "numbers"}
CAD_EXT = {"dwg", "dxf"}
ARCHIVE_EXT = {"zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz", "iso", "cab"}
EBOOK_EXT = {"epub", "mobi", "azw", "azw3", "fb2", "lit", "pdb", "cbz", "cbr"}
RAW_EXT = {"cr2", "cr3", "nef", "arw", "dng", "orf", "rw2", "raf"}


def T(src: str, ext: str, title: str, desc: str = "", badge: str | None = None, variant: str = "") -> Target:
    tid = f"{src}>{ext}" + (f":{variant}" if variant else "")
    return Target(tid, ext, title, desc, (badge or ext).upper())


def _image(src: str) -> FileKind:
    k = FileKind("image", "Immagine", ("#E3EEFC", "#1A55A0"))
    k.recommended = [T("img", "jpg", "JPG", "Si apre ovunque"),
                     T("img", "png", "PNG", "Massima qualità"),
                     T("img", "pdf", "PDF", "Da stampare o inviare")]
    if src in ("jpg", "jpeg", "jfif"):
        k.recommended[0] = T("img", "webp", "WEBP", "Più leggero, per il web")
    if src == "png":
        k.recommended[1] = T("img", "webp", "WEBP", "Più leggero, per il web")
    k.more = [T("img", e, e.upper()) for e in ("webp", "tiff", "gif", "bmp", "ico", "avif") if e != src]
    k.more.append(T("img", "jpg", "JPG ridotto", "", "JPG", "small"))
    return k


def _video(src: str) -> FileKind:
    k = FileKind("video", "Video", ("#E2F4EC", "#13704A"))
    k.recommended = [T("vid", "mp4", "MP4", "Funziona su tutto"),
                     T("vid", "mp4", "Per WhatsApp", "Leggero da inviare", "MP4", "whatsapp"),
                     T("vid", "mp3", "Solo audio", "Estrae musica e voci")]
    if src == "mp4":
        k.recommended[0] = T("vid", "mp4", "MP4 compresso", "Stessa qualità visiva, meno spazio", "MP4", "small")
    k.more = [T("vid", e, e.upper()) for e in ("mkv", "avi", "webm", "mov", "wmv") if e != src]
    k.more += [T("vid", "gif", "GIF animata"), T("vid", "wav", "Audio WAV"), T("vid", "jpg", "Fotogrammi JPG")]
    return k


def _audio(src: str) -> FileKind:
    k = FileKind("audio", "Audio", ("#EEE8FB", "#5A33B0"))
    k.recommended = [T("aud", "mp3", "MP3", "Compatibile con tutto"),
                     T("aud", "wav", "WAV", "Senza perdite, per l'editing"),
                     T("aud", "m4a", "M4A", "Ideale per iPhone")]
    if src == "mp3":
        k.recommended[0] = T("aud", "flac", "FLAC", "Archivio senza perdite")
    k.more = [T("aud", e, e.upper()) for e in ("flac", "aac", "ogg", "opus", "wma", "aiff") if e != src]
    return k


def _document(src: str) -> FileKind:
    k = FileKind("document", "Documento", ("#E3EEFC", "#1A55A0"))
    k.recommended = [T("doc", "pdf", "PDF", "Identico all'originale"),
                     T("doc", "docx", "Word", "Modificabile", "DOCX"),
                     T("doc", "odt", "OpenOffice", "Per LibreOffice", "ODT")]
    if src == "docx":
        k.recommended[1] = T("doc", "doc", "Word 97-2003", "Per versioni vecchie di Office", "DOC")
    k.more = [T("doc", "rtf", "RTF"), T("doc", "txt", "Testo semplice", "", "TXT"),
              T("doc", "html", "Pagina web", "", "HTML"), T("doc", "epub", "E-book", "", "EPUB")]
    return k


def _sheet(src: str) -> FileKind:
    k = FileKind("sheet", "Foglio di calcolo", ("#E2F4EC", "#13704A"))
    k.recommended = [T("doc", "xlsx", "Excel", "Modificabile", "XLSX"),
                     T("doc", "pdf", "PDF", "Da stampare o inviare"),
                     T("doc", "csv", "CSV", "Dati semplici")]
    if src == "xlsx":
        k.recommended[0] = T("doc", "ods", "OpenOffice", "Per LibreOffice", "ODS")
    k.more = [T("doc", "xls", "Excel 97-2003", "", "XLS"), T("doc", "ods", "ODS"), T("doc", "html", "Pagina web", "", "HTML")]
    return k


def _slides(src: str) -> FileKind:
    k = FileKind("slides", "Presentazione", ("#FDEBE4", "#A63A12"))
    k.recommended = [T("doc", "pdf", "PDF", "Da condividere"),
                     T("doc", "pptx", "PowerPoint", "Modificabile", "PPTX"),
                     T("doc", "png", "Immagini", "Una per ogni diapositiva", "PNG", "pages")]
    if src == "pptx":
        k.recommended[1] = T("doc", "odp", "OpenOffice", "Per LibreOffice", "ODP")
    k.more = [T("doc", "ppt", "PowerPoint 97-2003", "", "PPT"), T("doc", "odp", "ODP"),
              T("doc", "jpg", "Immagini JPG", "", "JPG", "pages")]
    return k


def _apple(src: str) -> FileKind:
    if src == "numbers":
        k = _sheet(src); k.label = "Apple Numbers"
    elif src == "key":
        k = _slides(src); k.label = "Apple Keynote"
    else:
        k = _document(src); k.label = "Apple Pages"
        k.recommended = [T("doc", "docx", "Word", "Testo, immagini e stili", "DOCX"),
                         T("doc", "pdf", "PDF", "Identico all'originale"),
                         T("doc", "odt", "OpenOffice", "Per LibreOffice", "ODT")]
    return k


def _pdf(src: str, scanned: bool) -> FileKind:
    k = FileKind("pdf", "PDF scansionato" if scanned else "PDF", ("#FDEBE4", "#A63A12"))
    k.recommended = [T("pdf", "docx", "Word", "Modificabile" + (", con OCR" if scanned else ""), "DOCX"),
                     T("pdf", "xlsx", "Excel", "Estrae le tabelle", "XLSX"),
                     T("pdf", "jpg", "Immagini", "Una per ogni pagina", "JPG")]
    k.more = [T("pdf", "txt", "Testo semplice", "", "TXT"), T("pdf", "png", "Immagini PNG", "", "PNG"),
              T("pdf", "pptx", "PowerPoint", "", "PPTX"),
              T("pdf", "pdf", "PDF compresso", "", "PDF", "small"),
              T("pdf", "pdf", "PDF ricercabile (OCR)", "", "PDF", "ocr"),
              T("pdf", "epub", "E-book", "", "EPUB")]
    return k


def _cad(src: str) -> FileKind:
    k = FileKind("cad", "Disegno CAD", ("#FBF1D6", "#7A5300"))
    k.recommended = [T("cad", "pdf", "PDF", "Pronto da stampare"),
                     T("cad", "dxf" if src == "dwg" else "dwg", "DXF" if src == "dwg" else "DWG",
                       "Si apre in ogni CAD"),
                     T("cad", "png", "Immagine", "Anteprima ad alta qualità", "PNG")]
    k.more = [T("cad", "svg", "SVG"), T("cad", "jpg", "JPG")]
    if src == "dwg":
        k.more.append(T("cad", "dwg", "DWG versione 2000", "", "DWG", "r2000"))
    return k


def _archive(src: str) -> FileKind:
    k = FileKind("archive", "Archivio", ("#EFEFF3", "#3B3B46"))
    k.recommended = [T("arc", "folder", "Estrai", "Apre il contenuto in una cartella", "CARTELLA"),
                     T("arc", "zip", "ZIP", "Compatibile con Windows"),
                     T("arc", "7z", "7Z", "Il più compresso")]
    if src == "zip":
        k.recommended[1] = T("arc", "tar.gz", "TAR.GZ", "Per Linux e Mac", "TGZ")
    k.more = [T("arc", "tar", "TAR"), T("arc", "tar.gz", "TAR.GZ", "", "TGZ")]
    return k


def _ebook(src: str) -> FileKind:
    k = FileKind("ebook", "E-book", ("#F6E8F2", "#8A2A6E"))
    k.recommended = [T("ebk", "epub", "EPUB", "Per la maggior parte dei lettori"),
                     T("ebk", "azw3", "Kindle", "Per i lettori Kindle", "AZW3"),
                     T("ebk", "pdf", "PDF", "Da leggere al computer")]
    if src == "epub":
        k.recommended[0] = T("ebk", "mobi", "MOBI", "Kindle meno recenti")
    k.more = [T("ebk", e, e.upper()) for e in ("mobi", "fb2", "docx", "txt") if e != src]
    return k


def _folder_like(src: str) -> FileKind:
    k = FileKind("other", "File", ("#EFEFF3", "#3B3B46"))
    k.recommended = [T("arc", "zip", "ZIP", "Comprimi in un archivio")]
    return k


def extension(path: str) -> str:
    name = os.path.basename(path).lower()
    for multi in ("tar.gz", "tar.bz2", "tar.xz"):
        if name.endswith("." + multi):
            return multi
    return os.path.splitext(name)[1].lstrip(".")


def pdf_is_scanned(path: str, sample_pages: int = 5) -> bool:
    """Un PDF è considerato scansionato se quasi tutte le pagine non hanno testo."""
    try:
        import pymupdf
        with pymupdf.open(path) as doc:
            n = min(len(doc), sample_pages)
            if n == 0:
                return False
            empty = sum(1 for i in range(n) if len(doc[i].get_text("text").strip()) < 25)
            return empty >= max(1, n // 2 + (n % 2))
    except Exception:
        return False


def detect(path: str, generic: bool = False) -> FileKind:
    """generic=True: proposte valide per qualsiasi file della stessa famiglia (gruppi misti)."""
    k = _detect(path, generic)
    seen = {t.id for t in k.recommended}
    k.more = [t for t in k.more if not (t.id in seen or seen.add(t.id))]
    return k


def _detect(path: str, generic: bool = False) -> FileKind:
    if os.path.isdir(path):
        k = FileKind("folder", "Cartella", ("#FBF1D6", "#7A5300"))
        k.recommended = [T("arc", "zip", "ZIP", "Compatibile con Windows"),
                         T("arc", "7z", "7Z", "Il più compresso"),
                         T("arc", "tar.gz", "TAR.GZ", "Per Linux e Mac", "TGZ")]
        k.more = [T("arc", "tar", "TAR")]
        return k
    real = extension(path)
    src = "" if generic and real not in APPLE_EXT and real not in CAD_EXT and real != "pdf" else real
    if real == "pdf":
        return _pdf(src, pdf_is_scanned(path))
    if real in APPLE_EXT:
        return _apple(src)
    if real in CAD_EXT:
        return _cad(src)
    if real in IMAGE_EXT:
        return _image(src)
    if real in VIDEO_EXT:
        return _video(src)
    if real in AUDIO_EXT:
        return _audio(src)
    if real in SHEET_EXT:
        return _sheet(src)
    if real in SLIDE_EXT:
        return _slides(src)
    if real in WORD_EXT:
        return _document(src)
    if real in EBOOK_EXT:
        return _ebook(src)
    if real in ARCHIVE_EXT or real in ("tar.gz", "tar.bz2", "tar.xz"):
        return _archive(src)
    return _folder_like(src)


def human_size(n: float) -> str:
    for unit in ("byte", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return (f"{n:.0f} {unit}" if unit in ("byte", "KB") else f"{n:.1f} {unit}").replace(".", ",")
        n /= 1024
    return str(n)
