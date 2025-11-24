import os
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from konfiguracja import konfig
from komponenty.raporty import generuj_raport_pdf


def wyslij_mail_odmowa(ts, id_prac, nazwa_prac, promille, klatka_bgr):
    pdf_path = generuj_raport_pdf(ts, id_prac, nazwa_prac, promille, klatka_bgr)
    
    temat = f"Odmowa wejścia - {nazwa_prac} ({promille:.3f} ‰)"
    tresc = (
        "System Alkotester - odmowa wejścia na obiekt.\\n\\n"
        f"Data i czas: {ts}\\n"
        f"Pracownik: {nazwa_prac} (ID: {id_prac})\\n"
        f"Wynik pomiaru: {promille:.3f} [‰]\\n"
    )
    
    wiadomosc = MIMEMultipart()
    wiadomosc["Subject"] = temat
    wiadomosc["From"] = konfig["smtp_user"]
    wiadomosc["To"] = konfig["mail_alertowy"]
    wiadomosc.attach(MIMEText(tresc, "plain", "utf-8"))
    
    with open(pdf_path, "rb") as f:
        zal = MIMEBase("application", "pdf")
        zal.set_payload(f.read())
    encoders.encode_base64(zal)
    zal.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(pdf_path)}"')
    wiadomosc.attach(zal)
    
    with smtplib.SMTP(konfig["smtp_host"], konfig["smtp_port"], timeout=10) as serwer:
        serwer.starttls()
        serwer.login(konfig["smtp_user"], konfig["smtp_password"])
        serwer.send_message(wiadomosc)


def synchronizuj_mail(ts, id_prac, nazwa_prac, promille, klatka_bgr):
    def watek():
        try:
            wyslij_mail_odmowa(ts, id_prac, nazwa_prac, promille, klatka_bgr)
        except Exception as e:
            print(f"[EMAIL] Błąd: {e}")
    
    threading.Thread(target=watek, daemon=True).start()
