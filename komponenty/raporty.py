import os
import io
import cv2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from konfiguracja import konfig


def generuj_raport_pdf(ts, id_prac, nazwa_prac, promille, klatka_bgr):
    pdfmetrics.registerFont(TTFont("DejaVuSans", konfig["czcionka"]))
    
    katalog_raporty = konfig.get("folder_raporty", "logi/raporty_odmowy")
    
    # Upewnij się że ścieżka jest relatywna do projektu, nie do roota systemu
    if not os.path.isabs(katalog_raporty):
        katalog_bazowy = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        katalog_raporty = os.path.join(katalog_bazowy, katalog_raporty)
    
    os.makedirs(katalog_raporty, exist_ok=True)
    print(f"[RAPORT] Katalog raportów: {katalog_raporty}")
    
    ts_bez = ts.replace(":", "-").replace(" ", "_")
    nazwa_pliku = f"odmowa_{ts_bez}_{id_prac or 'unknown'}.pdf"
    sciezka_pdf = os.path.join(katalog_raporty, nazwa_pliku)
    
    c = canvas.Canvas(sciezka_pdf, pagesize=A4)
    szerokosc, wysokosc = A4
    
    tekst = c.beginText(40, wysokosc - 40)
    tekst.setFont("DejaVuSans", 14)
    tekst.textLine("Odmowa wejścia na obiekt - raport")
    tekst.moveCursor(0, 20)
    tekst.setFont("DejaVuSans", 11)
    tekst.textLine(f"Data i czas: {ts}")
    tekst.textLine(f"Pracownik: {nazwa_prac} (ID: {id_prac})")
    tekst.textLine(f"Wynik pomiaru: {promille:.3f} [‰]")
    c.drawText(tekst)
    
    if klatka_bgr is not None:
        ok, buf = cv2.imencode(".jpg", klatka_bgr)
        if ok:
            bajty = io.BytesIO(buf.tobytes())
            obraz = ImageReader(bajty)
            img_w, img_h = obraz.getSize()
            
            max_w = szerokosc - 80
            max_h = wysokosc - 200
            
            skala = min(max_w / img_w, max_h / img_h, 1.0)
            rys_w = img_w * skala
            rys_h = img_h * skala
            
            x = (szerokosc - rys_w) / 2.0
            y = max(40, (wysokosc - rys_h) / 2.0 - 20)
            
            c.drawImage(obraz, x, y, width=rys_w, height=rys_h, preserveAspectRatio=True)
    
    c.save()
    return sciezka_pdf
