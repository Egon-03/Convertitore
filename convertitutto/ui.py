"""Interfaccia di ConvertiTutto: tre passaggi (trascina, scegli, fatto)."""

from __future__ import annotations

import os
from collections import OrderedDict

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLayout, QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget, QLineEdit,
)

from . import APP_NAME, __version__, engine, formats, winutil
from .settings import Settings

ACCENT = "#2259E8"
TEXT = "#111114"
MUTED = "#5B5B66"
SURFACE = "#F7F7F9"
BORDER = "#E4E4E9"

QSS = f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", Inter, sans-serif; color: {TEXT}; }}
QMainWindow, #root {{ background: #FFFFFF; }}
QLabel#appName {{ font-size: 14px; font-weight: 700; }}
QLabel#h1 {{ font-size: 26px; font-weight: 800; }}
QLabel#big {{ font-size: 64px; font-weight: 800; }}
QLabel#muted {{ color: {MUTED}; font-size: 14px; }}
QLabel#fileName {{ font-size: 16px; font-weight: 700; }}
QLabel#fileMeta {{ color: {MUTED}; font-size: 13px; }}
QPushButton {{ font-size: 14px; }}
QPushButton#drop {{ background: {SURFACE}; border: 2px dashed #CFCFD8; border-radius: 28px; }}
QPushButton#drop[dragging="true"] {{ background: #EEF3FF; border-color: {ACCENT}; }}
QPushButton#drop:hover {{ border-color: #A9A9B6; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: 0; border-radius: 16px; font-size: 17px; font-weight: 700; min-height: 58px; padding: 0 28px; }}
QPushButton#primary:hover {{ background: #1A4BCB; }}
QPushButton#primary:disabled {{ background: #A9B9EC; }}
QPushButton#secondary {{ background: #F0F0F4; border: 0; border-radius: 14px; font-size: 15px; font-weight: 600; min-height: 50px; padding: 0 22px; }}
QPushButton#secondary:hover {{ background: #E6E6EC; }}
QPushButton#link {{ background: transparent; border: 0; color: {ACCENT}; font-weight: 600; min-height: 40px; padding: 0 6px; }}
QPushButton#link:hover {{ color: #1A45B5; }}
QPushButton#icon {{ background: transparent; border: 0; border-radius: 8px; min-width: 40px; min-height: 40px; }}
QPushButton#icon:hover {{ background: #F0F0F4; }}
QPushButton#card {{ background: white; border: 2px solid {BORDER}; border-radius: 18px; text-align: left; }}
QPushButton#card:hover {{ border-color: #C4C4CF; }}
QPushButton#card:checked {{ background: #F1F5FF; border-color: {ACCENT}; }}
QPushButton#chip {{ background: white; border: 1px solid #D9D9E0; border-radius: 20px; min-height: 38px; padding: 0 16px; font-weight: 600; }}
QPushButton#chip:hover {{ border-color: #A9A9B6; }}
QPushButton#chip:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QFrame#fileBox {{ background: {SURFACE}; border-radius: 18px; }}
QProgressBar {{ background: #EDEDF1; border: 0; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QScrollArea {{ border: 0; background: transparent; }}
QDialog {{ background: white; }}
QLabel#section {{ font-size: 13px; font-weight: 700; color: {MUTED}; margin-top: 12px; }}
QComboBox, QLineEdit {{ min-height: 34px; border: 1px solid #D0D0D8; border-radius: 6px; padding: 0 10px; background: white; }}
"""


# --------------------------------------------------------------------------- grafica disegnata

def _icon(kind: str, color: str = MUTED, size: int = 20) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2 * size / 24, 2 * size / 24)
    pen = QPen(QColor(color), 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    if kind == "settings":
        for x, y1, y2, k in ((4, 21, 3, 14), (12, 21, 3, 8), (20, 21, 3, 16)):
            p.drawLine(x, y1, x, y2)
            p.drawLine(x - 3, k, x + 3, k)
    elif kind == "close":
        p.drawLine(6, 6, 18, 18)
        p.drawLine(18, 6, 6, 18)
    p.end()
    return QIcon(pm)


class Circle(QWidget):
    """Cerchio pieno con un simbolo (più o spunta)."""

    def __init__(self, symbol: str, bg: str, fg: str, d: int, parent=None):
        super().__init__(parent)
        self.symbol, self.bg, self.fg, self.d = symbol, QColor(bg), QColor(fg), d
        self.setFixedSize(d, d)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.bg)
        p.drawEllipse(0, 0, self.d, self.d)
        p.setPen(QPen(self.fg, self.d * 0.07, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        s = self.d
        if self.symbol == "plus":
            p.drawLine(int(s * .5), int(s * .3), int(s * .5), int(s * .7))
            p.drawLine(int(s * .3), int(s * .5), int(s * .7), int(s * .5))
        else:
            path = QPainterPath()
            path.moveTo(s * .3, s * .52)
            path.lineTo(s * .44, s * .66)
            path.lineTo(s * .72, s * .36)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)


def app_icon() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ACCENT))
    p.drawRoundedRect(8, 8, 240, 240, 56, 56)
    p.setPen(QPen(QColor("white"), 22, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(64, 96, 180, 96); p.drawLine(180, 96, 146, 62)
    p.drawLine(192, 160, 76, 160); p.drawLine(76, 160, 110, 194)
    p.end()
    return QIcon(pm)


class Badge(QLabel):
    def __init__(self, text: str, colors: tuple[str, str], size: int = 52, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(size, size)
        self.set_colors(colors, size)

    def set_colors(self, colors, size=52):
        self.setStyleSheet(f"background:{colors[0]};color:{colors[1]};border-radius:{size // 4}px;"
                           f"font-size:{11 if size >= 48 else 10}px;font-weight:800;")


# --------------------------------------------------------------------------- layout a capo automatico

class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self._items = []
        self._sp = spacing

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QRect(0, 0, w, 0), True)
    def setGeometry(self, r): super().setGeometry(r); self._do(r, False)
    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, lh = rect.x(), rect.y(), 0
        for it in self._items:
            w = it.sizeHint()
            if x + w.width() > rect.right() and lh > 0:
                x, y, lh = rect.x(), y + lh + self._sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), w))
            x += w.width() + self._sp
            lh = max(lh, w.height())
        return y + lh - rect.y()

    def clear(self):
        while self._items:
            it = self._items.pop()
            if it.widget():
                it.widget().deleteLater()


# --------------------------------------------------------------------------- lavoratore in background

class Worker(QObject):
    progress = Signal(float, str)
    finished = Signal(list, list)  # risultati, errori [(file, messaggio)]

    def __init__(self, files, target, settings: Settings):
        super().__init__()
        self.files, self.target, self.settings = files, target, settings

    def run(self):
        results, errors = [], []
        n = len(self.files)
        for i, src in enumerate(self.files):
            name = os.path.basename(src)

            def cb(frac, msg, i=i, name=name):
                prefix = f"{name}: " if n > 1 else ""
                self.progress.emit((i + max(0.0, min(1.0, frac))) / n, prefix + msg)

            try:
                job = engine.Job(src, self.target, self.settings.output_dir_for(src), self.settings.engine_options())
                results.extend(engine.convert(job, cb))
            except Exception as e:  # noqa: BLE001 - mostriamo l'errore all'utente
                errors.append((name, str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__))
        self.finished.emit(results, errors)


# --------------------------------------------------------------------------- pagine

def _wrap(widget: QWidget, max_w: int) -> QWidget:
    outer = QWidget()
    lay = QHBoxLayout(outer)
    lay.setContentsMargins(24, 0, 24, 0)
    lay.addStretch(1)
    widget.setMaximumWidth(max_w)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    lay.addWidget(widget, 100)
    lay.addStretch(1)
    return outer


class EmptyPage(QWidget):
    def __init__(self, on_click):
        super().__init__()
        col = QVBoxLayout(self)
        col.addStretch(1)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setSpacing(24)
        self.drop = QPushButton(objectName="drop")
        self.drop.setCursor(Qt.PointingHandCursor)
        self.drop.setMinimumHeight(360)
        self.drop.setAccessibleName("Scegli i file da convertire")
        self.drop.clicked.connect(on_click)
        dv = QVBoxLayout(self.drop)
        dv.setSpacing(16)
        dv.addStretch(1)
        c = Circle("plus", ACCENT, "#FFFFFF", 72)
        dv.addWidget(c, 0, Qt.AlignHCenter)
        t = QLabel("Trascina qui un file", objectName="h1")
        t.setAlignment(Qt.AlignCenter)
        t.setAttribute(Qt.WA_TransparentForMouseEvents)
        s = QLabel("oppure clicca per sceglierlo", objectName="muted")
        s.setAlignment(Qt.AlignCenter)
        s.setAttribute(Qt.WA_TransparentForMouseEvents)
        dv.addWidget(t)
        dv.addWidget(s)
        dv.addStretch(1)
        v.addWidget(self.drop)
        foot = QLabel("Foto, video, audio, documenti, PDF, disegni CAD, file Apple ed e-book.\n"
                      "Tutto sul tuo PC, anche senza internet.", objectName="muted")
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet("font-size:13px;")
        v.addWidget(foot)
        col.addWidget(_wrap(inner, 680))
        col.addStretch(1)

    def set_dragging(self, on: bool):
        self.drop.setProperty("dragging", "true" if on else "false")
        self.drop.style().unpolish(self.drop)
        self.drop.style().polish(self.drop)


class TargetCard(QPushButton):
    def __init__(self, target: formats.Target):
        super().__init__(objectName="card")
        self.target = target
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(128)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName(f"{target.title} ({target.badge}). {target.desc}")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        top = QHBoxLayout()
        b = QLabel(target.badge)
        b.setStyleSheet(f"font-size:12px;font-weight:800;color:{MUTED};background:transparent;")
        top.addWidget(b)
        top.addStretch(1)
        self.tick = Circle("check", ACCENT, "#FFFFFF", 22)
        self.tick.hide()
        top.addWidget(self.tick)
        v.addLayout(top)
        v.addStretch(1)
        ti = QLabel(target.title)
        ti.setStyleSheet("font-size:18px;font-weight:700;background:transparent;")
        de = QLabel(target.desc)
        de.setWordWrap(True)
        de.setStyleSheet(f"font-size:13px;color:{MUTED};background:transparent;")
        for w in (b, ti, de):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        v.addWidget(ti)
        v.addWidget(de)
        self.toggled.connect(self.tick.setVisible)


class ChoosePage(QWidget):
    convert_requested = Signal(object)
    reset_requested = Signal()
    change_requested = Signal()

    def __init__(self):
        super().__init__()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        host = QWidget(objectName="root")
        scroll.setWidget(host)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: #FFFFFF; }")
        col = QVBoxLayout(host)
        col.addStretch(1)
        inner = QWidget()
        self.v = QVBoxLayout(inner)
        self.v.setSpacing(24)

        # riquadro del file
        box = QFrame(objectName="fileBox")
        h = QHBoxLayout(box)
        h.setContentsMargins(18, 16, 12, 16)
        h.setSpacing(16)
        self.badge = Badge("", ("#EEE", "#333"))
        h.addWidget(self.badge)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        self.name = QLabel(objectName="fileName")
        self.meta = QLabel(objectName="fileMeta")
        tv.addWidget(self.name)
        tv.addWidget(self.meta)
        h.addLayout(tv, 1)
        ch = QPushButton("Cambia file", objectName="link")
        ch.setCursor(Qt.PointingHandCursor)
        ch.clicked.connect(self.change_requested)
        h.addWidget(ch)
        x = QPushButton(objectName="icon")
        x.setIcon(_icon("close"))
        x.setToolTip("Rimuovi")
        x.setAccessibleName("Rimuovi file")
        x.clicked.connect(self.reset_requested)
        h.addWidget(x)
        self.v.addWidget(box)

        self.title = QLabel("Trasformalo in…", objectName="h1")
        self.v.addWidget(self.title)
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.v.addLayout(self.grid)
        self.more_btn = QPushButton(objectName="link")
        self.more_btn.setCursor(Qt.PointingHandCursor)
        self.more_btn.clicked.connect(self._toggle_more)
        hb = QHBoxLayout()
        hb.addWidget(self.more_btn)
        hb.addStretch(1)
        self.v.addLayout(hb)
        self.more_box = QWidget()
        self.flow = FlowLayout(self.more_box)
        self.more_box.hide()
        self.v.addWidget(self.more_box)

        self.go = QPushButton(objectName="primary")
        self.go.setCursor(Qt.PointingHandCursor)
        self.go.clicked.connect(lambda: self.convert_requested.emit(self.current()))
        self.v.addWidget(self.go)
        col.addWidget(_wrap(inner, 720))
        col.addStretch(1)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.buttonToggled.connect(self._update_go)

    def show_files(self, kind: formats.FileKind, files: list[str], group_info: str = ""):
        self.kind = kind
        self.badge.setText(formats.extension(files[0]).upper()[:5] or "FILE")
        self.badge.set_colors(kind.color)
        if len(files) == 1:
            f = files[0]
            self.name.setText(os.path.basename(f.rstrip("/\\")))
            size = "" if os.path.isdir(f) else " · " + formats.human_size(os.path.getsize(f))
            self.meta.setText(kind.label + size)
        else:
            total = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
            self.name.setText(f"{len(files)} file: " + ", ".join(os.path.basename(f) for f in files[:3])
                              + ("…" if len(files) > 3 else ""))
            self.meta.setText(f"{kind.label} · {formats.human_size(total)}")
        self.title.setText("Trasformalo in…" if len(files) == 1 else "Trasformali in…")
        if group_info:
            self.meta.setText(self.meta.text() + " · " + group_info)
        for b in self.group.buttons():
            self.group.removeButton(b)
            b.deleteLater()
        self.flow.clear()
        cols = 3
        for i, t in enumerate(kind.recommended):
            card = TargetCard(t)
            self.group.addButton(card)
            self.grid.addWidget(card, i // cols, i % cols)
        for t in kind.more:
            chip = QPushButton(t.title, objectName="chip")
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.target = t
            self.group.addButton(chip)
            self.flow.addWidget(chip)
        self.more_box.setVisible(False)
        self.more_btn.setVisible(bool(kind.more))
        self._set_more_label()
        if self.group.buttons():
            self.group.buttons()[0].setChecked(True)
        self._update_go()

    def current(self):
        b = self.group.checkedButton()
        return b.target if b else None

    def _toggle_more(self):
        self.more_box.setVisible(not self.more_box.isVisible())
        self._set_more_label()

    def _set_more_label(self):
        n = len(getattr(self, "kind", None).more) if hasattr(self, "kind") else 0
        self.more_btn.setText("Meno formati" if self.more_box.isVisible() else f"Altri formati ({n})")

    def _update_go(self, *_):
        t = self.current()
        self.go.setEnabled(t is not None)
        self.go.setText(f"Converti in {t.title}" if t else "Scegli un formato")


class WorkPage(QWidget):
    def __init__(self):
        super().__init__()
        col = QVBoxLayout(self)
        col.addStretch(1)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setSpacing(22)
        self.pct = QLabel("0%", objectName="big")
        self.pct.setAlignment(Qt.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.msg = QLabel("", objectName="muted")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        v.addWidget(self.pct)
        v.addWidget(self.bar)
        v.addWidget(self.msg)
        col.addWidget(_wrap(inner, 560))
        col.addStretch(1)

    def set_progress(self, frac: float, msg: str):
        self.pct.setText(f"{int(frac * 100)}%")
        self.bar.setValue(int(frac * 1000))
        if msg:
            self.msg.setText(msg)


class DonePage(QWidget):
    again = Signal()

    def __init__(self):
        super().__init__()
        col = QVBoxLayout(self)
        col.addStretch(1)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setSpacing(18)
        self.circle_ok = Circle("check", "#E5F6EC", "#1C7C46", 88)
        v.addWidget(self.circle_ok, 0, Qt.AlignHCenter)
        self.title = QLabel("Fatto!", objectName="h1")
        self.title.setStyleSheet("font-size:32px;font-weight:800;")
        self.title.setAlignment(Qt.AlignCenter)
        self.info = QLabel("", objectName="muted")
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.title)
        v.addWidget(self.info)
        row = QHBoxLayout()
        row.addStretch(1)
        self.open_btn = QPushButton("Apri", objectName="primary")
        self.open_btn.setStyleSheet("min-height:50px;border-radius:14px;font-size:15px;")
        self.folder_btn = QPushButton("Mostra nella cartella", objectName="secondary")
        for b in (self.open_btn, self.folder_btn):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        again = QPushButton("Converti un altro file", objectName="link")
        again.setCursor(Qt.PointingHandCursor)
        again.clicked.connect(self.again)
        v.addWidget(again, 0, Qt.AlignHCenter)
        self.open_btn.clicked.connect(lambda: self.results and winutil.open_path(self.results[0]))
        self.folder_btn.clicked.connect(lambda: self.results and winutil.show_in_folder(self.results[0]))
        col.addWidget(_wrap(inner, 600))
        col.addStretch(1)
        self.results: list[str] = []

    def show_result(self, results: list[str], errors: list[tuple[str, str]]):
        self.results = results
        ok = bool(results)
        self.circle_ok.setVisible(ok)
        self.open_btn.setVisible(ok)
        self.folder_btn.setVisible(ok)
        if ok and not errors:
            self.title.setText("Fatto!")
        elif ok:
            self.title.setText("Fatto, con qualche problema")
        else:
            self.title.setText("Non è stato possibile convertire")
        lines = []
        if len(results) == 1:
            r = results[0]
            size = "" if os.path.isdir(r) else " · " + formats.human_size(os.path.getsize(r))
            lines.append(os.path.basename(r) + size)
        elif results:
            lines.append(f"{len(results)} file pronti in {os.path.dirname(results[0])}")
        for name, msg in errors[:4]:
            lines.append(f"{name}: {msg}")
        if len(errors) > 4:
            lines.append(f"…e altri {len(errors) - 4} file")
        self.info.setText("\n".join(lines))
        self.open_btn.setText("Apri" if len(results) == 1 and not os.path.isdir(results[0]) else "Apri cartella")
        self.folder_btn.setVisible(ok and len(results) == 1 and not os.path.isdir(results[0]))


# --------------------------------------------------------------------------- impostazioni

class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle("Impostazioni")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(8)
        title = QLabel("Impostazioni", objectName="h1")
        v.addWidget(title)

        v.addWidget(QLabel("DOVE SALVARE I FILE CONVERTITI", objectName="section"))
        self.r_docs = QRadioButton(f"Nella cartella Documenti\\{APP_NAME}")
        self.r_same = QRadioButton("Nella stessa cartella del file originale")
        self.r_custom = QRadioButton("In un'altra cartella:")
        for r in (self.r_docs, self.r_same, self.r_custom):
            v.addWidget(r)
        row = QHBoxLayout()
        self.custom = QLineEdit(settings.custom_dir)
        self.custom.setPlaceholderText("Scegli una cartella…")
        browse = QPushButton("Sfoglia…", objectName="secondary")
        browse.setStyleSheet("min-height:34px;border-radius:6px;font-size:13px;")
        browse.clicked.connect(self._browse)
        row.addWidget(self.custom, 1)
        row.addWidget(browse)
        v.addLayout(row)
        {"same": self.r_same, "custom": self.r_custom}.get(settings.output_mode, self.r_docs).setChecked(True)
        self.open_after = QCheckBox("Apri la cartella al termine della conversione")
        self.open_after.setChecked(settings.open_folder_after)
        v.addWidget(self.open_after)

        v.addWidget(QLabel("PDF SCANSIONATI (OCR)", objectName="section"))
        self.lang = QComboBox()
        for code, label in (("auto", "Automatica (italiano, tedesco, francese, inglese)"), ("ita", "Italiano"),
                            ("deu", "Tedesco"), ("fra", "Francese"), ("eng", "Inglese"), ("spa", "Spagnolo")):
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(settings.ocr_lang)))
        v.addWidget(QLabel("Lingua del testo"))
        v.addWidget(self.lang)

        v.addWidget(QLabel("IMMAGINI", objectName="section"))
        self.quality = QComboBox()
        for q, label in ((95, "Massima"), (90, "Alta (consigliata)"), (75, "File leggeri")):
            self.quality.addItem(label, q)
        self.quality.setCurrentIndex(max(0, self.quality.findData(settings.quality)))
        v.addWidget(self.quality)
        self.exif = QCheckBox("Mantieni data, luogo e dati della fotocamera")
        self.exif.setChecked(settings.keep_exif)
        v.addWidget(self.exif)

        v.addWidget(QLabel("DISEGNI CAD", objectName="section"))
        self.paper = QComboBox()
        self.paper.addItem("Foglio A3", "a3")
        self.paper.addItem("Foglio A4", "a4")
        self.paper.setCurrentIndex(max(0, self.paper.findData(settings.cad_paper)))
        v.addWidget(self.paper)
        self.mono = QCheckBox("Stampa in bianco e nero")
        self.mono.setChecked(settings.cad_mono)
        v.addWidget(self.mono)

        if winutil.IS_WIN:
            v.addWidget(QLabel("WINDOWS", objectName="section"))
            self.menu = QCheckBox("Mostra \"Converti con ConvertiTutto\" nel menu del tasto destro")
            self.menu.setChecked(winutil.context_menu_enabled())
            v.addWidget(self.menu)

        v.addSpacing(12)
        ver = QLabel(f"{APP_NAME} {__version__}", objectName="muted")
        ver.setStyleSheet("font-size:12px;")
        btns = QHBoxLayout()
        btns.addWidget(ver)
        btns.addStretch(1)
        cancel = QPushButton("Annulla", objectName="secondary")
        save = QPushButton("Salva", objectName="primary")
        save.setStyleSheet("min-height:44px;border-radius:12px;font-size:14px;")
        cancel.setStyleSheet("min-height:44px;border-radius:12px;font-size:14px;")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Scegli la cartella", self.custom.text() or os.path.expanduser("~"))
        if d:
            self.custom.setText(d)
            self.r_custom.setChecked(True)

    def _save(self):
        s = self.s
        s.output_mode = "same" if self.r_same.isChecked() else ("custom" if self.r_custom.isChecked() and self.custom.text() else "documents")
        s.custom_dir = self.custom.text()
        s.open_folder_after = self.open_after.isChecked()
        s.ocr_lang = self.lang.currentData()
        s.quality = self.quality.currentData()
        s.keep_exif = self.exif.isChecked()
        s.cad_paper = self.paper.currentData()
        s.cad_mono = self.mono.isChecked()
        s.save()
        if winutil.IS_WIN:
            try:
                winutil.set_context_menu(self.menu.isChecked())
            except OSError:
                pass
        self.accept()


# --------------------------------------------------------------------------- finestra principale

class MainWindow(QMainWindow):
    def __init__(self, files: list[str] | None = None):
        super().__init__()
        self.settings = Settings.load()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1040, 760)
        self.setMinimumSize(760, 600)
        self.setAcceptDrops(True)

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.setContentsMargins(22, 10, 14, 0)
        top.addWidget(QLabel(APP_NAME, objectName="appName"))
        top.addStretch(1)
        gear = QPushButton(objectName="icon")
        gear.setIcon(_icon("settings"))
        gear.setIconSize(QSize(20, 20))
        gear.setToolTip("Impostazioni")
        gear.setAccessibleName("Impostazioni")
        gear.clicked.connect(self.open_settings)
        top.addWidget(gear)
        v.addLayout(top)

        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        self.empty = EmptyPage(self.pick_files)
        self.choose = ChoosePage()
        self.work = WorkPage()
        self.done = DonePage()
        for p in (self.empty, self.choose, self.work, self.done):
            self.stack.addWidget(p)
        self.choose.reset_requested.connect(self.reset)
        self.choose.change_requested.connect(self.pick_files)
        self.choose.convert_requested.connect(self.start)
        self.done.again.connect(self.reset)

        self.groups: list[tuple[formats.FileKind, list[str]]] = []
        self.all_results: list[str] = []
        self.all_errors: list[tuple[str, str]] = []
        self.thread: QThread | None = None
        if files:
            self.load_files(files)

    # ---- file
    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Scegli i file da convertire", os.path.expanduser("~"))
        if files:
            self.load_files(files)

    def load_files(self, files: list[str]):
        files = [os.path.abspath(f) for f in files if os.path.exists(f)]
        if not files:
            return
        if self.stack.currentWidget() is self.work:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            groups: OrderedDict = OrderedDict()
            for f in files:
                k = formats.detect(f)
                key = k.key + ("|" + formats.extension(f) if k.key in ("document", "sheet", "slides", "cad") else "")
                groups.setdefault(key, [k, []])[1].append(f)
            for g in groups.values():
                if len({formats.extension(f) for f in g[1]}) > 1:
                    g[0] = formats.detect(g[1][0], generic=True)
        finally:
            QApplication.restoreOverrideCursor()
        self.groups = [(k, fs) for k, fs in groups.values()]
        self.all_results, self.all_errors = [], []
        self._show_group()

    def _show_group(self):
        kind, files = self.groups[0]
        info = f"gruppo 1 di {len(self.groups)}" if len(self.groups) > 1 else ""
        self.choose.show_files(kind, files, info)
        self.stack.setCurrentWidget(self.choose)

    def reset(self):
        self.groups = []
        self.stack.setCurrentWidget(self.empty)

    # ---- conversione
    def start(self, target):
        if not target or not self.groups:
            return
        _, files = self.groups[0]
        self.work.set_progress(0, "Preparo…")
        self.stack.setCurrentWidget(self.work)
        self.thread = QThread(self)
        self.worker = Worker(files, target, self.settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.work.set_progress)
        self.worker.finished.connect(self._finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def _finished(self, results, errors):
        self.all_results += results
        self.all_errors += errors
        self.groups.pop(0)
        if self.groups:
            self._show_group()
            return
        self.done.show_result(self.all_results, self.all_errors)
        self.stack.setCurrentWidget(self.done)
        if self.settings.open_folder_after and self.all_results:
            winutil.show_in_folder(self.all_results[0])
        QApplication.alert(self)

    def open_settings(self):
        SettingsDialog(self.settings, self).exec()

    # ---- trascinamento
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and self.stack.currentWidget() is not self.work:
            e.acceptProposedAction()
            self.empty.set_dragging(True)

    def dragLeaveEvent(self, e):
        self.empty.set_dragging(False)

    def dropEvent(self, e):
        self.empty.set_dragging(False)
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        self.load_files(files)

    def closeEvent(self, e):
        if self.thread and self.thread.isRunning():
            if QMessageBox.question(self, APP_NAME, "Una conversione è in corso. Vuoi chiudere comunque?") != QMessageBox.Yes:
                e.ignore()
                return
        e.accept()


def run(argv: list[str]) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    f = QFont("Segoe UI", 10)
    app.setFont(f)
    files = [a for a in argv[1:] if not a.startswith("-")]
    w = MainWindow(files)
    w.show()
    return app.exec()
