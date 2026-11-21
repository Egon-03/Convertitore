"""Integrazione con Windows: menu del tasto destro, apertura file e cartelle."""

from __future__ import annotations

import os
import subprocess
import sys

IS_WIN = os.name == "nt"
MENU_KEYS = [r"Software\Classes\*\shell\ConvertiTutto", r"Software\Classes\Directory\shell\ConvertiTutto"]


def exe_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"'
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}" "%1"'


def context_menu_enabled() -> bool:
    if not IS_WIN:
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, MENU_KEYS[0]))
        return True
    except OSError:
        return False


def set_context_menu(enabled: bool) -> None:
    if not IS_WIN:
        return
    import winreg
    for key in MENU_KEYS:
        if enabled:
            k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key)
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Converti con ConvertiTutto")
            icon = sys.executable if getattr(sys, "frozen", False) else ""
            if icon:
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
            winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
            c = winreg.CreateKey(k, "command")
            winreg.SetValueEx(c, "", 0, winreg.REG_SZ, exe_command())
            winreg.CloseKey(c)
            winreg.CloseKey(k)
        else:
            for sub in (key + r"\command", key):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
                except OSError:
                    pass


def open_path(path: str) -> None:
    if IS_WIN:
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def show_in_folder(path: str) -> None:
    if IS_WIN:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        open_path(os.path.dirname(path) if os.path.isfile(path) else path)
