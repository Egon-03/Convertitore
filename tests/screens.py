"""Cattura le schermate dell'interfaccia (senza schermo) e prova un ciclo completo."""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
from convertitutto import ui

samples, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(ui.QSS)
w = ui.MainWindow()
w.settings.output_mode = "custom"
w.settings.custom_dir = os.path.join(out, "risultati")
w.resize(1040, 760)
w.show()


def snap(name):
    for _ in range(5):
        app.processEvents()
    w.grab().save(os.path.join(out, name))


snap("1_vuoto.png")
w.load_files([os.path.join(samples, "bolletta_scansionata.pdf")])
snap("2_scegli_pdf.png")
w.choose._toggle_more()
snap("2b_altri_formati.png")
w.load_files([os.path.join(samples, "video_matrimonio.mov")])
snap("2c_scegli_video.png")
w.load_files([os.path.join(samples, "bolletta_scansionata.pdf")])
w.start(w.choose.current())
snap("3_in_corso.png")
t0 = time.time()
while w.stack.currentWidget() is not w.done and time.time() - t0 < 120:
    app.processEvents()
    time.sleep(0.05)
snap("4_fatto.png")
print("risultati:", w.all_results, "errori:", w.all_errors)
