"""Motore di conversione di ConvertiTutto.

Ogni conversione riceve: file sorgente, Target scelto, cartella di destinazione,
opzioni e una funzione di avanzamento progress(frazione 0..1, messaggio).
Restituisce l'elenco dei file (o cartelle) prodotti.
"""

from __future__ import annotations

import os
import re
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Callable

from . import tools
from .formats import Target, extension, pdf_is_scanned

Progress = Callable[[float, str], None]

OCR_LANGS = {"auto": "ita+eng+deu+fra", "ita": "ita", "deu": "deu", "fra": "fra", "eng": "eng", "spa": "spa"}


class ConversionError(RuntimeError):
    pass


@dataclass
class Job:
    src: str
    target: Target
    out_dir: str
    options: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- utilità

def _stem(path: str) -> str:
    name = os.path.basename(path.rstrip("/\\"))
    ext = extension(path)
    return name[: -(len(ext) + 1)] if ext and name.lower().endswith("." + ext) else name


def unique_path(folder: str, stem: str, ext: str) -> str:
    os.makedirs(folder, exist_ok=True)
    suffix = f".{ext}" if ext and ext != "folder" else ""
    cand = os.path.join(folder, stem + suffix)
    i = 2
    while os.path.exists(cand):
        cand = os.path.join(folder, f"{stem} ({i}){suffix}")
        i += 1
    return cand


def _variant(t: Target) -> str:
    return t.id.split(":", 1)[1] if ":" in t.id else ""


def _noop(p: float, m: str) -> None:
    pass


# --------------------------------------------------------------------------- immagini

def _open_image(src: str):
    from PIL import Image
    ext = extension(src)
    if ext in ("heic", "heif"):
        import pillow_heif
        pillow_heif.register_heif_opener()
    if ext in ("cr2", "cr3", "nef", "arw", "dng", "orf", "rw2", "raf"):
        try:
            import rawpy
            with rawpy.imread(src) as raw:
                return Image.fromarray(raw.postprocess(use_camera_wb=True))
        except ImportError:
            pass  # Pillow apre almeno l'anteprima incorporata di alcuni RAW
    if ext == "svg":
        import pymupdf
        with pymupdf.open(src) as doc:
            pix = doc[0].get_pixmap(dpi=200, alpha=True)
            return Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    img = Image.open(src)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def convert_image(job: Job, progress: Progress) -> list[str]:
    from PIL import Image
    t = job.target
    v = _variant(t)
    progress(0.1, "Apro l'immagine…")
    img = _open_image(job.src)
    frames = getattr(img, "n_frames", 1)
    out = unique_path(job.out_dir, _stem(job.src), t.ext)
    progress(0.5, "Converto…")
    quality = int(job.options.get("quality", 90))
    exif = img.info.get("exif") if job.options.get("keep_exif", True) else None

    def flat(im):
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            return bg
        return im.convert("RGB")

    if t.ext in ("jpg", "jpeg"):
        im = flat(img)
        if v == "small":
            im.thumbnail((1920, 1920))
            quality = 75
        kw = {"quality": quality, "optimize": True}
        if exif:
            kw["exif"] = exif
        im.save(out, "JPEG", **kw)
    elif t.ext == "png":
        img.convert("RGBA" if "A" in img.mode or img.mode == "P" else "RGB").save(out, "PNG", optimize=True)
    elif t.ext == "webp":
        img.save(out, "WEBP", quality=quality, method=5)
    elif t.ext == "avif":
        img.save(out, "AVIF", quality=quality)
    elif t.ext in ("tif", "tiff"):
        img.save(out, "TIFF", compression="tiff_lzw")
    elif t.ext == "bmp":
        flat(img).save(out, "BMP")
    elif t.ext == "gif":
        if frames > 1:
            img.save(out, "GIF", save_all=True, loop=0)
        else:
            img.convert("RGBA").save(out, "GIF")
    elif t.ext == "ico":
        im = img.convert("RGBA")
        im.save(out, "ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    elif t.ext == "pdf":
        pages = []
        for i in range(frames):
            img.seek(i)
            pages.append(flat(img.copy()))
        pages[0].save(out, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    else:
        raise ConversionError(f"Formato immagine non supportato: {t.ext}")
    progress(1.0, "Fatto")
    return [out]


# --------------------------------------------------------------------------- audio e video (FFmpeg)

def media_duration(src: str) -> float:
    ffprobe = tools.find("ffprobe")
    if not ffprobe:
        return 0.0
    r = tools.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", src])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _ffmpeg(args: list[str], duration: float, progress: Progress, msg: str) -> None:
    ffmpeg = tools.require("ffmpeg")
    cmd = [ffmpeg, "-hide_banner", "-y", "-nostdin", "-progress", "pipe:1", "-nostats"] + args
    proc = tools.popen(cmd, stdout=tools.subprocess.PIPE, stderr=tools.subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    err_tail: list[str] = []

    import threading

    def read_err():
        for line in proc.stderr:
            err_tail.append(line)
            del err_tail[:-30]

    th = threading.Thread(target=read_err, daemon=True)
    th.start()
    for line in proc.stdout:
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                us = int(line.split("=", 1)[1])
                if duration > 0:
                    progress(min(0.99, us / 1e6 / duration), msg)
            except ValueError:
                pass
    proc.wait()
    th.join(timeout=2)
    if proc.returncode != 0:
        raise ConversionError("FFmpeg non è riuscito a convertire il file:\n" + "".join(err_tail[-8:]))


AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "320k"],
    "wav": ["-c:a", "pcm_s16le"],
    "m4a": ["-c:a", "aac", "-b:a", "256k"],
    "aac": ["-c:a", "aac", "-b:a", "256k", "-f", "adts"],
    "flac": ["-c:a", "flac"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "6"],
    "opus": ["-c:a", "libopus", "-b:a", "160k"],
    "wma": ["-c:a", "wmav2", "-b:a", "192k"],
    "aiff": ["-c:a", "pcm_s16be"],
}


def convert_media(job: Job, progress: Progress) -> list[str]:
    t = job.target
    v = _variant(t)
    src = job.src
    duration = media_duration(src)
    stem = _stem(src) + ("_whatsapp" if v == "whatsapp" else "")
    msg = "Converto…"

    if t.ext in AUDIO_CODECS:
        out = unique_path(job.out_dir, stem, t.ext)
        _ffmpeg(["-i", src, "-vn", "-map_metadata", "0"] + AUDIO_CODECS[t.ext] + [out], duration, progress, msg)
        return [out]

    if t.ext == "jpg":  # fotogrammi
        folder = unique_path(job.out_dir, stem + "_fotogrammi", "folder")
        os.makedirs(folder)
        fps = "1" if duration <= 600 else "1/10"
        _ffmpeg(["-i", src, "-vf", f"fps={fps}", "-q:v", "2", os.path.join(folder, "fotogramma_%05d.jpg")],
                duration, progress, "Estraggo i fotogrammi…")
        return [folder]

    out = unique_path(job.out_dir, stem, t.ext)
    if t.ext == "gif":
        vf = "fps=12,scale='min(480,iw)':-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer"
        _ffmpeg(["-i", src, "-filter_complex", vf, "-loop", "0", out], duration, progress, "Creo la GIF…")
        return [out]

    h264 = ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    if t.ext == "mp4" and v == "whatsapp":
        # obiettivo: meno di 16 MB
        target_kbps = (15 * 8 * 1024) / max(duration, 1) * 0.95
        a_kbps = 96 if target_kbps > 400 else 64
        v_kbps = max(120, int(target_kbps - a_kbps))
        args = ["-i", src, "-vf", "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
                "-c:v", "libx264", "-preset", "medium", "-b:v", f"{v_kbps}k", "-maxrate", f"{int(v_kbps * 1.2)}k",
                "-bufsize", f"{v_kbps * 2}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", f"{a_kbps}k",
                "-ac", "2", "-movflags", "+faststart", out]
    elif t.ext in ("mp4", "mov", "m4v"):
        crf = "26" if v == "small" else "20"
        args = ["-i", src] + h264 + ["-crf", crf, out]
    elif t.ext == "mkv":
        args = ["-i", src, "-map", "0", "-c", "copy", out]
        try:
            _ffmpeg(args, duration, progress, msg)
            return [out]
        except ConversionError:
            if os.path.exists(out):
                os.remove(out)
            args = ["-i", src] + h264[:-2] + ["-crf", "20", out]
    elif t.ext == "avi":
        args = ["-i", src, "-c:v", "mpeg4", "-q:v", "3", "-c:a", "libmp3lame", "-b:a", "192k", out]
    elif t.ext == "webm":
        args = ["-i", src, "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-deadline", "good", "-cpu-used", "4",
                "-row-mt", "1", "-c:a", "libopus", "-b:a", "128k", out]
    elif t.ext == "wmv":
        args = ["-i", src, "-c:v", "wmv2", "-q:v", "3", "-c:a", "wmav2", "-b:a", "192k", out]
    else:
        args = ["-i", src, out]
    _ffmpeg(args, duration, progress, msg)
    return [out]


# --------------------------------------------------------------------------- documenti (LibreOffice)

LO_FILTERS = {
    "txt": "txt:Text (encoded):UTF8",
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1",
    "doc": "doc:MS Word 97",
    "xls": "xls:MS Excel 97",
    "ppt": "ppt:MS PowerPoint 97",
    "html": "html",
}


def libreoffice_convert(src: str, ext: str, out_dir: str, infilter: str | None = None, timeout: int = 600) -> str:
    soffice = tools.require("soffice")
    with tempfile.TemporaryDirectory(prefix="ct_lo_") as tmp:
        profile = os.path.join(tmp, "profilo")
        outtmp = os.path.join(tmp, "out")
        os.makedirs(outtmp)
        url = "file:///" + profile.replace("\\", "/").lstrip("/")
        cmd = [soffice, f"-env:UserInstallation={url}", "--headless", "--norestore", "--nologo",
               "--nodefault", "--nolockcheck"]
        if infilter:
            cmd.append(f"--infilter={infilter}")
        src_in = src
        if extension(src) == "md":  # LibreOffice non legge il Markdown: lo tratta come testo
            src_in = os.path.join(tmp, _stem(src) + ".txt")
            shutil.copyfile(src, src_in)
        cmd += ["--convert-to", LO_FILTERS.get(ext, ext), "--outdir", outtmp, src_in]
        try:
            r = tools.run(cmd, timeout=timeout)
        except tools.subprocess.TimeoutExpired:
            raise ConversionError("La conversione del documento ha impiegato troppo tempo.")
        produced = [f for f in os.listdir(outtmp)]
        if not produced:
            raise ConversionError("LibreOffice non è riuscito a convertire il documento.\n" + (r.stderr or r.stdout)[-500:])
        final = unique_path(out_dir, _stem(src), ext)
        shutil.move(os.path.join(outtmp, produced[0]), final)
        return final


def _pdf_to_images(pdf: str, out_dir: str, stem: str, ext: str, progress: Progress, dpi: int = 200) -> list[str]:
    import pymupdf
    with pymupdf.open(pdf) as doc:
        n = len(doc)
        if n == 1:
            out = unique_path(out_dir, stem, ext)
            doc[0].get_pixmap(dpi=dpi).save(out, jpg_quality=90) if ext == "jpg" else doc[0].get_pixmap(dpi=dpi).save(out)
            return [out]
        folder = unique_path(out_dir, stem + "_pagine", "folder")
        os.makedirs(folder)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            p = os.path.join(folder, f"pagina_{i + 1:03d}.{ext}")
            pix.save(p, jpg_quality=90) if ext == "jpg" else pix.save(p)
            progress(0.3 + 0.7 * (i + 1) / n, f"Pagina {i + 1} di {n}…")
        return [folder]


def convert_document(job: Job, progress: Progress) -> list[str]:
    t = job.target
    progress(0.1, "Apro il documento…")
    if _variant(t) == "pages":  # presentazione -> immagini
        with tempfile.TemporaryDirectory(prefix="ct_") as tmp:
            pdf = libreoffice_convert(job.src, "pdf", tmp)
            progress(0.4, "Creo le immagini…")
            return _pdf_to_images(pdf, job.out_dir, _stem(job.src), t.ext, progress, dpi=150)
    out = libreoffice_convert(job.src, t.ext, job.out_dir)
    progress(1.0, "Fatto")
    return [out]


# --------------------------------------------------------------------------- PDF

def _ocr_lang(job: Job) -> str:
    return OCR_LANGS.get(job.options.get("ocr_lang", "auto"), "ita+eng+deu+fra")


def _ocr_textpage(page, lang: str, dpi: int = 300):
    td = os.path.join(tools.tools_dir(), "tesseract", "tessdata")
    kw = {"language": lang, "dpi": dpi, "full": True}
    if os.path.isdir(td):
        kw["tessdata"] = td
    return page.get_textpage_ocr(**kw)


def _ensure_tesseract():
    tess = tools.find("tesseract")
    if not tess:
        raise ConversionError("Il riconoscimento del testo (OCR) non è disponibile: manca Tesseract.")
    # PyMuPDF cerca tesseract nel PATH e i dati lingua in TESSDATA_PREFIX
    d = os.path.dirname(tess)
    if d not in os.environ.get("PATH", ""):
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    td = os.path.join(tools.tools_dir(), "tesseract", "tessdata")
    if os.path.isdir(td):
        os.environ["TESSDATA_PREFIX"] = td


def _page_needs_ocr(page) -> bool:
    return len(page.get_text("text").strip()) < 25


def pdf_ocr_to_docx(job: Job, out: str, progress: Progress) -> None:
    """PDF scansionato -> Word modificabile, ricostruendo paragrafi, dimensioni e grassetti.

    Le pagine che contengono già testo vengono lette direttamente; le altre con OCR."""
    import pymupdf
    from docx import Document
    from docx.enum.text import WD_BREAK, WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, Cm

    _ensure_tesseract()
    lang = _ocr_lang(job)
    docx = Document()
    sec = docx.sections[0]
    with pymupdf.open(job.src) as pdf:
        n = len(pdf)
        first = pdf[0].rect
        sec.page_width, sec.page_height = Pt(first.width), Pt(first.height)
        sec.left_margin = sec.right_margin = Cm(2)
        sec.top_margin = sec.bottom_margin = Cm(1.8)
        for i, page in enumerate(pdf):
            progress(0.05 + 0.9 * i / n, f"Leggo il testo: pagina {i + 1} di {n}…")
            tp = _ocr_textpage(page, lang) if (_page_needs_ocr(page) or job.options.get("force_ocr")) else None
            data = page.get_text("dict", textpage=tp, sort=True) if tp else page.get_text("dict", sort=True)
            width = page.rect.width
            paras: list[dict] = []
            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines = block.get("lines", [])
                if not lines:
                    continue
                text_parts, sizes, bold_chars, total_chars = [], [], 0, 0
                for ln in lines:
                    text_parts.append("".join(s.get("text", "") for s in ln.get("spans", [])))
                    for s in ln.get("spans", []):
                        c = len(s.get("text", "").strip())
                        total_chars += c
                        sizes.append((s.get("size", 11), c))
                        if s.get("flags", 0) & 16 or "bold" in s.get("font", "").lower():
                            bold_chars += c
                text = _join_lines(text_parts)
                if not text.strip():
                    continue
                size = sum(sz * c for sz, c in sizes) / max(1, sum(c for _, c in sizes))
                x0, y0, x1, y1 = block["bbox"]
                centre = (x0 + x1) / 2
                if abs(centre - width / 2) < width * 0.06 and (x1 - x0) < width * 0.7:
                    align = "center"
                elif x0 > width * 0.55:
                    align = "right"
                else:
                    align = "left"
                cur = {"text": text, "size": size, "bold": bold_chars > total_chars * 0.6,
                       "align": align, "x0": x0, "y0": y0, "y1": y1}
                prev = paras[-1] if paras else None
                # unisce le righe che appartengono allo stesso paragrafo
                if (prev and align == "left" and prev["align"] == "left"
                        and abs(prev["size"] - size) < 1.0 and abs(prev["x0"] - x0) < 18
                        and 0 <= y0 - prev["y1"] < size * 1.2 and prev["bold"] == cur["bold"]
                        and not prev["text"].rstrip().endswith((".", ":", "!", "?"))):
                    prev["text"] = _join_lines([prev["text"], text])
                    prev["y1"] = y1
                else:
                    paras.append(cur)
            for para in paras:
                p = docx.add_paragraph()
                run = p.add_run(para["text"])
                run.font.size = Pt(max(7, min(36, round(para["size"] * 2) / 2)))
                run.bold = para["bold"]
                if para["align"] == "center":
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif para["align"] == "right":
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p.paragraph_format.space_after = Pt(4)
            if i < n - 1:
                docx.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    docx.save(out)


def _join_lines(parts: list[str]) -> str:
    out = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if out.endswith("-") and part[:1].islower():
            out = out[:-1] + part
        elif out:
            out += " " + part
        else:
            out = part
    return re.sub(r"\s+", " ", out)


def pdf_to_docx(job: Job, out: str, progress: Progress) -> None:
    import pymupdf
    scanned = pdf_is_scanned(job.src) or job.options.get("force_ocr")
    if scanned:
        pdf_ocr_to_docx(job, out, progress)
        return
    with pymupdf.open(job.src) as d:
        mixed = any(_page_needs_ocr(p) and p.get_images() for p in d)
    if mixed and tools.find("tesseract") and job.options.get("ocr", True):
        # alcune pagine sono scansioni: ricostruzione con OCR pagina per pagina
        pdf_ocr_to_docx(job, out, progress)
        return
    from pdf2docx import Converter
    progress(0.1, "Analizzo l'impaginazione…")
    cv = Converter(job.src)
    try:
        cv.convert(out, multi_processing=False)
    finally:
        cv.close()
    progress(1.0, "Fatto")


def pdf_to_xlsx(job: Job, out: str, progress: Progress) -> None:
    import pdfplumber
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Tabelle"
    row = 1
    found = 0
    with pdfplumber.open(job.src) as pdf:
        n = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            progress(0.05 + 0.9 * i / max(1, n), f"Cerco le tabelle: pagina {i + 1} di {n}…")
            tables = page.extract_tables() or page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            for tb in tables:
                if not tb or len(tb) < 2:
                    continue
                found += 1
                ws.cell(row=row, column=1, value=f"Tabella {found} (pagina {i + 1})").font = Font(bold=True)
                row += 1
                for r_i, r in enumerate(tb):
                    for c_i, val in enumerate(r):
                        cell = ws.cell(row=row, column=c_i + 1, value=_num(val))
                        if r_i == 0:
                            cell.font = Font(bold=True)
                    row += 1
                row += 1
    if not found:
        # nessuna tabella: testo riga per riga, colonne separate da spazi ampi
        import pymupdf
        with pymupdf.open(job.src) as pdf:
            for page in pdf:
                text = page.get_text("text")
                if len(text.strip()) < 25 and tools.find("tesseract"):
                    _ensure_tesseract()
                    text = page.get_text("text", textpage=_ocr_textpage(page, _ocr_lang(job)))
                for line in text.splitlines():
                    if line.strip():
                        for c_i, val in enumerate(re.split(r"\s{2,}|\t", line.strip())):
                            ws.cell(row=row, column=c_i + 1, value=_num(val))
                        row += 1
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(60, max(8, width + 2))
    wb.save(out)


def _num(val):
    if val is None:
        return None
    s = str(val).strip()
    t = s.replace("€", "").replace("CHF", "").replace("'", "").strip()
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?", t):
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t) if "." in t else int(t)
    return s


def pdf_to_text(job: Job, out: str, progress: Progress) -> None:
    import pymupdf
    parts = []
    with pymupdf.open(job.src) as pdf:
        n = len(pdf)
        for i, page in enumerate(pdf):
            progress(0.05 + 0.9 * i / n, f"Pagina {i + 1} di {n}…")
            if _page_needs_ocr(page) and tools.find("tesseract"):
                _ensure_tesseract()
                parts.append(page.get_text("text", textpage=_ocr_textpage(page, _ocr_lang(job))))
            else:
                parts.append(page.get_text("text"))
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n\f\n".join(parts))


def pdf_make_searchable(job: Job, out: str, progress: Progress) -> None:
    import pymupdf
    _ensure_tesseract()
    lang = _ocr_lang(job)
    td = os.path.join(tools.tools_dir(), "tesseract", "tessdata")
    result = pymupdf.open()
    with pymupdf.open(job.src) as pdf:
        n = len(pdf)
        for i, page in enumerate(pdf):
            progress(0.05 + 0.9 * i / n, f"Riconosco il testo: pagina {i + 1} di {n}…")
            if not _page_needs_ocr(page):
                result.insert_pdf(pdf, from_page=i, to_page=i)
                continue
            pix = page.get_pixmap(dpi=300)
            kw = {"language": lang}
            if os.path.isdir(td):
                kw["tessdata"] = td
            data = pix.pdfocr_tobytes(**kw)
            with pymupdf.open("pdf", data) as one:
                result.insert_pdf(one)
    result.save(out, garbage=3, deflate=True)
    result.close()


def pdf_compress(job: Job, out: str, progress: Progress) -> None:
    gs = tools.find("gs")
    if gs:
        progress(0.2, "Comprimo il PDF…")
        r = tools.run([gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6", "-dPDFSETTINGS=/ebook",
                       "-dNOPAUSE", "-dQUIET", "-dBATCH", f"-sOutputFile={out}", job.src])
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) < os.path.getsize(job.src):
            return
    import pymupdf
    with pymupdf.open(job.src) as pdf:
        try:
            pdf.rewrite_images(dpi_threshold=160, dpi_target=150, quality=70)
        except Exception:
            pass
        pdf.save(out, garbage=4, deflate=True, clean=True)
    if os.path.getsize(out) >= os.path.getsize(job.src):
        shutil.copyfile(job.src, out)


def convert_pdf(job: Job, progress: Progress) -> list[str]:
    t = job.target
    v = _variant(t)
    stem = _stem(job.src)
    if t.ext in ("jpg", "png"):
        return _pdf_to_images(job.src, job.out_dir, stem, t.ext, progress)
    if t.ext == "pdf":
        out = unique_path(job.out_dir, stem + ("_ricercabile" if v == "ocr" else "_compresso"), "pdf")
        (pdf_make_searchable if v == "ocr" else pdf_compress)(job, out, progress)
        return [out]
    if t.ext == "epub":
        return convert_ebook(job, progress)
    out = unique_path(job.out_dir, stem, t.ext)
    if t.ext == "docx":
        pdf_to_docx(job, out, progress)
    elif t.ext == "xlsx":
        pdf_to_xlsx(job, out, progress)
    elif t.ext == "txt":
        pdf_to_text(job, out, progress)
    elif t.ext == "pptx":
        pdf_to_pptx(job, out, progress)
    else:
        raise ConversionError(f"Conversione da PDF a {t.ext} non supportata")
    return [out]


def pdf_to_pptx(job: Job, out: str, progress: Progress) -> None:
    """Ogni pagina diventa una diapositiva (immagine nitida a tutta pagina)."""
    import pymupdf
    from pptx import Presentation
    from pptx.util import Emu
    prs = Presentation()
    with pymupdf.open(job.src) as pdf, tempfile.TemporaryDirectory(prefix="ct_") as tmp:
        r = pdf[0].rect
        prs.slide_width = Emu(int(r.width * 12700))
        prs.slide_height = Emu(int(r.height * 12700))
        blank = prs.slide_layouts[6]
        n = len(pdf)
        for i, page in enumerate(pdf):
            progress(0.05 + 0.9 * i / n, f"Diapositiva {i + 1} di {n}…")
            img = os.path.join(tmp, f"p{i}.png")
            page.get_pixmap(dpi=200).save(img)
            s = prs.slides.add_slide(blank)
            s.shapes.add_picture(img, 0, 0, prs.slide_width, prs.slide_height)
            notes = page.get_text("text").strip()
            if notes:
                s.notes_slide.notes_text_frame.text = notes
        prs.save(out)


# --------------------------------------------------------------------------- CAD

def _dwg_to_dxf(src: str, out: str) -> None:
    exe = tools.find("dwg2dxf")
    if not exe:
        raise ConversionError("Per leggere i file DWG manca il componente LibreDWG.")
    r = tools.run([exe, "-y", "-o", out, src], timeout=600)
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        raise ConversionError("Non riesco a leggere questo DWG.\n" + (r.stderr or "")[-400:])


def _load_dxf(path: str):
    import ezdxf
    from ezdxf import recover
    try:
        return ezdxf.readfile(path)
    except Exception:
        doc, _ = recover.readfile(path)
        return doc


def _render_cad(doc, out: str, ext: str, progress: Progress, paper: str = "auto", mono: bool = False) -> None:
    from ezdxf.addons.drawing import Frontend, RenderContext, config, layout
    from ezdxf.addons.drawing import pymupdf as mbackend
    from ezdxf.addons.drawing import svg as svgbackend

    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.BLACK if mono else config.ColorPolicy.COLOR,
        lineweight_scaling=1.0,
    )
    # layout da disegnare: modello + layout carta non vuoti
    targets = [doc.modelspace()] + [l for l in doc.layouts if l.name != "Model" and len(l) > 0]
    if ext != "pdf":
        targets = targets[:1]
    # formato carta: A3/A4 nell'orientamento del disegno, con il disegno adattato al foglio
    landscape = True
    try:
        from ezdxf import bbox
        ext_box = bbox.extents(doc.modelspace(), fast=True)
        if ext_box.has_data:
            landscape = ext_box.size.x >= ext_box.size.y
    except Exception:
        pass
    w, h = (297, 210) if paper == "a4" else (420, 297)
    if not landscape:
        w, h = h, w
    page_def = layout.Page(w, h, layout.Units.mm, margins=layout.Margins.all(10))
    settings = layout.Settings(fit_page=True)

    if ext == "svg":
        backend = svgbackend.SVGBackend()
        Frontend(RenderContext(doc), backend, config=cfg).draw_layout(targets[0], finalize=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(backend.get_string(page_def, settings=settings))
        return

    import pymupdf
    merged = pymupdf.open()
    for i, lay in enumerate(targets):
        progress(0.3 + 0.6 * i / len(targets), f"Disegno il layout {i + 1} di {len(targets)}…")
        backend = mbackend.PyMuPdfBackend()
        Frontend(RenderContext(doc), backend, config=cfg).draw_layout(lay, finalize=True)
        if ext == "pdf":
            data = backend.get_pdf_bytes(page_def, settings=settings)
            with pymupdf.open("pdf", data) as one:
                merged.insert_pdf(one)
        else:
            data = backend.get_pixmap_bytes(page_def, fmt="png", dpi=200, settings=settings)
            if ext in ("jpg", "jpeg"):
                import io
                from PIL import Image
                Image.open(io.BytesIO(data)).convert("RGB").save(out, "JPEG", quality=92)
            else:
                with open(out, "wb") as f:
                    f.write(data)
            merged.close()
            return
    merged.save(out, garbage=3, deflate=True)
    merged.close()


def convert_cad(job: Job, progress: Progress) -> list[str]:
    t = job.target
    v = _variant(t)
    src_ext = extension(job.src)
    stem = _stem(job.src)
    with tempfile.TemporaryDirectory(prefix="ct_cad_") as tmp:
        dxf = job.src
        if src_ext == "dwg":
            progress(0.1, "Leggo il disegno DWG…")
            dxf = os.path.join(tmp, "disegno.dxf")
            _dwg_to_dxf(job.src, dxf)
        if t.ext == "dxf":
            out = unique_path(job.out_dir, stem, "dxf")
            if src_ext == "dwg":
                shutil.move(dxf, out)
            else:
                _load_dxf(dxf).saveas(out)
            return [out]
        if t.ext == "dwg":
            exe = tools.find("dxf2dwg")
            if not exe:
                raise ConversionError("Per creare file DWG manca il componente LibreDWG.")
            src_dxf = dxf
            if v == "r2000" or src_ext == "dwg":
                doc = _load_dxf(dxf)
                doc.dxfversion = "AC1015"  # AutoCAD 2000: la più compatibile
                src_dxf = os.path.join(tmp, "r2000.dxf")
                doc.saveas(src_dxf)
            out = unique_path(job.out_dir, stem + ("_R2000" if v == "r2000" else ""), "dwg")
            r = tools.run([exe, "-y", "-o", out, src_dxf], timeout=600)
            if not os.path.exists(out):
                raise ConversionError("Non è stato possibile creare il DWG.\n" + (r.stderr or "")[-400:])
            return [out]
        progress(0.25, "Preparo il disegno…")
        doc = _load_dxf(dxf)
        out = unique_path(job.out_dir, stem, t.ext)
        _render_cad(doc, out, t.ext, progress, job.options.get("paper", "auto"), job.options.get("mono", False))
        return [out]


# --------------------------------------------------------------------------- archivi

def _extract_any(src: str, dest: str, progress: Progress) -> None:
    ext = extension(src)
    progress(0.1, "Estraggo…")
    if ext == "zip" and zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            _safe_members_zip(z, dest)
        return
    if ext in ("tar", "tar.gz", "tgz", "tar.bz2", "tar.xz") and tarfile.is_tarfile(src):
        with tarfile.open(src) as tf:
            tf.extractall(dest, filter="data")
        return
    if ext == "7z":
        import py7zr
        with py7zr.SevenZipFile(src) as z:
            z.extractall(dest)
        return
    exe = tools.find("7z")
    if not exe:
        raise ConversionError("Per aprire questo archivio manca il componente 7-Zip.")
    r = tools.run([exe, "x", "-y", f"-o{dest}", src])
    if r.returncode not in (0, 1):
        raise ConversionError("Non riesco ad aprire l'archivio (forse è protetto da password).")


def _safe_members_zip(z: zipfile.ZipFile, dest: str) -> None:
    root = os.path.realpath(dest)
    for m in z.infolist():
        target = os.path.realpath(os.path.join(dest, m.filename))
        if not target.startswith(root + os.sep) and target != root:
            continue  # ignora percorsi pericolosi
        z.extract(m, dest)


def _pack(folder_or_file: str, out: str, ext: str, progress: Progress) -> None:
    progress(0.5, "Comprimo…")
    base = os.path.basename(folder_or_file.rstrip("/\\"))
    if ext == "zip":
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            if os.path.isdir(folder_or_file):
                for root, _, files in os.walk(folder_or_file):
                    for f in files:
                        full = os.path.join(root, f)
                        z.write(full, os.path.relpath(full, os.path.dirname(folder_or_file)))
            else:
                z.write(folder_or_file, base)
    elif ext == "7z":
        import py7zr
        with py7zr.SevenZipFile(out, "w") as z:
            if os.path.isdir(folder_or_file):
                z.writeall(folder_or_file, base)
            else:
                z.write(folder_or_file, base)
    elif ext in ("tar", "tar.gz"):
        with tarfile.open(out, "w:gz" if ext == "tar.gz" else "w") as tf:
            tf.add(folder_or_file, arcname=base)
    else:
        raise ConversionError(f"Formato di archivio non supportato: {ext}")


def convert_archive(job: Job, progress: Progress) -> list[str]:
    t = job.target
    src = job.src
    stem = _stem(src)
    src_ext = extension(src)
    is_archive = not os.path.isdir(src) and src_ext in {"zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz", "iso", "cab", "tar.gz", "tar.bz2", "tar.xz"}
    if t.ext == "folder":
        dest = unique_path(job.out_dir, stem, "folder")
        os.makedirs(dest)
        _extract_any(src, dest, progress)
        return [dest]
    out = unique_path(job.out_dir, stem, t.ext)
    if is_archive:
        with tempfile.TemporaryDirectory(prefix="ct_arc_") as tmp:
            inner = os.path.join(tmp, stem)
            os.makedirs(inner)
            _extract_any(src, inner, progress)
            _pack(inner, out, t.ext, progress)
    else:
        _pack(src, out, t.ext, progress)
    return [out]


# --------------------------------------------------------------------------- e-book

def convert_ebook(job: Job, progress: Progress) -> list[str]:
    try:
        return _calibre(job, progress)
    except ConversionError:
        if job.target.ext != "pdf" or extension(job.src) == "pdf":
            raise
        # piano B per e-book -> PDF: passa da Word e poi LibreOffice
        with tempfile.TemporaryDirectory(prefix="ct_ebk_") as tmp:
            mid = Job(job.src, Target("ebk>docx", "docx", "DOCX"), tmp, job.options)
            docx = _calibre(mid, progress)[0]
            pdf = libreoffice_convert(docx, "pdf", job.out_dir)
            final = unique_path(job.out_dir, _stem(job.src), "pdf")
            if os.path.basename(pdf) != os.path.basename(final):
                shutil.move(pdf, final)
            return [final]


def _calibre(job: Job, progress: Progress) -> list[str]:
    exe = tools.find("ebook-convert")
    if not exe:
        raise ConversionError("Per gli e-book manca il componente Calibre.")
    out = unique_path(job.out_dir, _stem(job.src), job.target.ext)
    progress(0.1, "Converto l'e-book…")
    proc = tools.popen([exe, job.src, out], stdout=tools.subprocess.PIPE, stderr=tools.subprocess.STDOUT,
                       text=True, encoding="utf-8", errors="replace")
    tail = []
    for line in proc.stdout:
        tail.append(line)
        del tail[:-20]
        m = re.match(r"\s*(\d+)%", line)
        if m:
            progress(min(0.99, int(m.group(1)) / 100), "Converto l'e-book…")
    proc.wait()
    if proc.returncode != 0 or not os.path.exists(out):
        raise ConversionError("Non riesco a convertire l'e-book (potrebbe essere protetto).\n" + "".join(tail[-5:]))
    return [out]


# --------------------------------------------------------------------------- smistamento

HANDLERS = {
    "img": convert_image,
    "vid": convert_media,
    "aud": convert_media,
    "doc": convert_document,
    "pdf": convert_pdf,
    "cad": convert_cad,
    "arc": convert_archive,
    "ebk": convert_ebook,
}


def convert(job: Job, progress: Progress | None = None) -> list[str]:
    progress = progress or _noop
    if not os.path.exists(job.src):
        raise ConversionError("Il file non esiste più.")
    family = job.target.id.split(">", 1)[0]
    handler = HANDLERS.get(family)
    if not handler:
        raise ConversionError("Conversione non supportata.")
    os.makedirs(job.out_dir, exist_ok=True)
    try:
        result = handler(job, progress)
    except tools.ToolMissing as e:
        raise ConversionError(str(e))
    progress(1.0, "Fatto")
    return result
