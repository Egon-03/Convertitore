"""Crea file di prova di ogni tipo in una cartella."""
import os
import subprocess
import sys
import zipfile

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
P = lambda n: os.path.join(out, n)

from PIL import Image, ImageDraw, ImageFont

# immagini
img = Image.new("RGB", (1200, 800), (40, 120, 200))
d = ImageDraw.Draw(img)
d.ellipse((300, 150, 900, 650), fill=(250, 200, 60))
img.save(P("foto.jpg"), quality=92)
img.save(P("grafica.png"))
import pillow_heif
pillow_heif.register_heif_opener()
img.save(P("IMG_2041.heic"))

# video e audio
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", P("video_matrimonio.mov")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=5",
                P("intervista.wav")], check=True)

# documenti Office
from docx import Document
doc = Document()
doc.add_heading("Contratto di prova", 0)
doc.add_paragraph("Questo è un documento di prova per ConvertiTutto con lettere accentate: àèéìòù.")
t = doc.add_table(rows=3, cols=3)
for r in range(3):
    for c in range(3):
        t.cell(r, c).text = f"R{r}C{c}"
doc.save(P("contratto.docx"))

from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["Prodotto", "Prezzo", "Quantità"])
ws.append(["Mele", 2.5, 10]); ws.append(["Pere", 3.1, 4])
wb.save(P("listino.xlsx"))

from pptx import Presentation
prs = Presentation()
for i in range(2):
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = f"Diapositiva {i + 1}"
    s.placeholders[1].text = "Contenuto di prova"
prs.save(P("presentazione.pptx"))

# PDF con testo e tabella (da Word tramite LibreOffice)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", out, P("contratto.docx")],
               check=True, capture_output=True)

# PDF scansionato (solo immagine)
font = big = None
windir = os.environ.get("WINDIR", r"C:\Windows")
for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
          os.path.join(windir, "Fonts", "arial.ttf"), os.path.join(windir, "Fonts", "segoeui.ttf")]:
    if os.path.exists(f):
        font = ImageFont.truetype(f, 34); big = ImageFont.truetype(f, 54)
        break
if font is None:  # nessun font di sistema trovato: quello incorporato in Pillow
    font = ImageFont.load_default(34); big = ImageFont.load_default(54)
pages = []
for n in range(2):
    pg = Image.new("RGB", (1654, 2339), "white")
    dr = ImageDraw.Draw(pg)
    dr.text((160, 180), f"BOLLETTA ENERGIA - Pagina {n + 1}", font=big, fill="black")
    y = 360
    for line in ["Gentile cliente, la presente bolletta si riferisce", "al periodo di fornitura da gennaio a marzo.",
                 "Importo totale da pagare: 128,40 euro.", "Scadenza del pagamento: 15 aprile.",
                 "Grazie per aver scelto il nostro servizio."]:
        dr.text((160, y), line, font=font, fill="black"); y += 70
    pages.append(pg.rotate(0.6, fillcolor="white"))
pages[0].save(P("bolletta_scansionata.pdf"), "PDF", resolution=200, save_all=True, append_images=pages[1:])

# CAD
import ezdxf
dxf = ezdxf.new("R2018")
msp = dxf.modelspace()
msp.add_lwpolyline([(0, 0), (4000, 0), (4000, 3000), (0, 3000)], close=True)
msp.add_circle((2000, 1500), 600)
msp.add_line((0, 0), (4000, 3000))
msp.add_text("Cucina", dxfattribs={"height": 200}).set_placement((300, 2600))
dxf.saveas(P("progetto_cucina.dxf"))

# archivi
with zipfile.ZipFile(P("archivio.zip"), "w") as z:
    z.write(P("foto.jpg"), "foto.jpg"); z.write(P("contratto.docx"), "documenti/contratto.docx")
subprocess.run(["7z", "a", "-bd", "-y", P("archivio7.7z"), P("grafica.png")], check=True, capture_output=True)
os.makedirs(P("cartella_progetto"), exist_ok=True)
open(os.path.join(P("cartella_progetto"), "note.txt"), "w").write("note")

# e-book
subprocess.run(["ebook-convert", P("contratto.docx"), P("libro.epub")], check=True, capture_output=True)
print("ok")
