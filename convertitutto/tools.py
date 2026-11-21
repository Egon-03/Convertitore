"""Trova i programmi esterni: prima nella cartella 'tools' dell'app, poi nel PATH."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache

IS_WIN = os.name == "nt"


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tools_dir() -> str:
    return os.path.join(app_dir(), "tools")


# nome logico -> percorsi relativi possibili dentro tools/ (Windows) e nome nel PATH
_CANDIDATES = {
    "ffmpeg": (["ffmpeg/bin/ffmpeg.exe", "ffmpeg/ffmpeg.exe"], "ffmpeg"),
    "ffprobe": (["ffmpeg/bin/ffprobe.exe", "ffmpeg/ffprobe.exe"], "ffprobe"),
    "soffice": (["libreoffice/program/soffice.exe", "LibreOfficePortable/App/libreoffice/program/soffice.exe"], "soffice"),
    "tesseract": (["tesseract/tesseract.exe"], "tesseract"),
    "7z": (["7zip/7z.exe", "7zip/7za.exe"], "7z"),
    "dwg2dxf": (["libredwg/dwg2dxf.exe"], "dwg2dxf"),
    "dxf2dwg": (["libredwg/dxf2dwg.exe"], "dxf2dwg"),
    "dwgwrite": (["libredwg/dwgwrite.exe"], "dwgwrite"),
    "ebook-convert": (["calibre/ebook-convert.exe", "Calibre Portable/Calibre/ebook-convert.exe"], "ebook-convert"),
    "gs": (["ghostscript/bin/gswin64c.exe"], "gswin64c" if IS_WIN else "gs"),
}


@lru_cache(maxsize=None)
def find(name: str) -> str | None:
    rels, path_name = _CANDIDATES.get(name, ([], name))
    for rel in rels:
        p = os.path.join(tools_dir(), *rel.split("/"))
        if os.path.isfile(p):
            return p
    found = shutil.which(path_name)
    if found:
        return found
    if IS_WIN:
        pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        extra = {
            "soffice": [r"LibreOffice\program\soffice.exe"],
            "tesseract": [r"Tesseract-OCR\tesseract.exe"],
            "7z": [r"7-Zip\7z.exe"],
            "ebook-convert": [r"Calibre2\ebook-convert.exe"],
        }.get(name, [])
        for base in pf:
            for rel in extra:
                p = os.path.join(base, rel)
                if os.path.isfile(p):
                    return p
    return None


class ToolMissing(RuntimeError):
    pass


def require(name: str) -> str:
    p = find(name)
    if not p:
        raise ToolMissing(f"Manca il componente '{name}'. Reinstalla ConvertiTutto per ripristinarlo.")
    return p


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    if IS_WIN:
        kw.setdefault("creationflags", 0x08000000)  # CREATE_NO_WINDOW
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    return subprocess.run(cmd, **kw)


def popen(cmd: list[str], **kw) -> subprocess.Popen:
    if IS_WIN:
        kw.setdefault("creationflags", 0x08000000)
    return subprocess.Popen(cmd, **kw)


def tessdata_env() -> dict:
    env = dict(os.environ)
    td = os.path.join(tools_dir(), "tesseract", "tessdata")
    if os.path.isdir(td):
        env["TESSDATA_PREFIX"] = td
    return env
