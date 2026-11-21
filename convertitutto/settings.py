"""Impostazioni salvate in %APPDATA%\\ConvertiTutto\\impostazioni.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from . import APP_NAME


def _config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def default_output_dir() -> str:
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    if os.name == "nt":
        try:
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL
            if buf.value:
                docs = buf.value
        except Exception:
            pass
    return os.path.join(docs, APP_NAME)


@dataclass
class Settings:
    output_mode: str = "documents"      # "documents" | "same" | "custom"
    custom_dir: str = ""
    open_folder_after: bool = False
    ocr_lang: str = "auto"
    quality: int = 90
    keep_exif: bool = True
    cad_paper: str = "a3"
    cad_mono: bool = False

    def output_dir_for(self, src: str) -> str:
        if self.output_mode == "same":
            return os.path.dirname(os.path.abspath(src.rstrip("/\\")))
        if self.output_mode == "custom" and self.custom_dir:
            return self.custom_dir
        return default_output_dir()

    def engine_options(self) -> dict:
        return {"ocr_lang": self.ocr_lang, "quality": self.quality, "keep_exif": self.keep_exif,
                "paper": self.cad_paper, "mono": self.cad_mono}

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(os.path.join(_config_dir(), "impostazioni.json"), encoding="utf-8") as f:
                data = json.load(f)
            s = cls()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
        except Exception:
            return cls()

    def save(self) -> None:
        with open(os.path.join(_config_dir(), "impostazioni.json"), "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
