import os
from dotenv import load_dotenv

load_dotenv()

import os
from dotenv import load_dotenv

load_dotenv()

konfig = {
    # Wyglad apki
    "szerokosc_ekranu": 720,
    "wysokosc_ekranu": 1280,
    "wysokosc_paska": 240,
    "czy_pelny_ekran": True,
    "ukryj_myszke": True,

    # Kamera
    "rozdzialka_kamery": (1280, 720),
    "klatki_na_sekunde": 10,
    "kierunek_obrotu": "cw",

    # Twarze (YuNet)
    "sciezka_modelu_yunet": "models/face_detection_yunet_2023mar.onnx",
    "prog_wykrycia_yunet": 0.85,
    "prog_nms": 0.3,
    "limit_top_yunet": 5000,

    "co_ile_detekcja": 1000,
    "min_rozmiar_twarzy": 120,
    "pewnosc_dobra": 55.0,
    "pewnosc_slaba": 20.0,

    "limit_prob_detekcji": 5,
    "limit_powtorzen_detekcji": 3,

    "ile_fotek_trening": 10,
    "czas_na_trening": 15,

    "min_ostrosc": 60.0,
    "min_jasnosc": 40.0,
    "max_jasnosc": 210.0,

    "min_dopasowan": 65,
    "wspolczynnik_progu": 0.75,
    "min_probek_podrzad": 10,
    "ile_ok_podrzad": 2,

    "max_fotek_pracownika": 40,

    # Alkohol
    "spi_kanal": 0,
    "spi_urzadzenie": 0,
    "kanal_mq3": 0,
    "ile_probek_kalibracja": 150,
    "przelicznik_promili": 220.0,
    "czas_dmuchania": 2.0,

    # Progi
    "prog_trzezwosci": 0.2,
    "prog_pijany": 0.5,

    # Bramka i swiatelka
    "pin_furtki": 18,
    "czas_otwarcia": 5.0,

    "pin_led_zielony": 24,
    "pin_led_czerwony": 23,
    "czas_swiecenia": 3.0,

    # Sciezki
    "folder_dane": "dane",
    "folder_twarze": "dane/twarze",
    "folder_indeks": "dane/indeks",
    "plik_pracownicy": "dane/pracownicy.json",
    "folder_logi": "logi",
    "folder_raporty": "logi/raporty_odmowy",
    "czcionka": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    
    # Startowy ziomek
    "pracownik_startowy": {
        "id": "1",
        "imie": "Kamil Karolak",
        "pin": "0000",
    },

    # Admin
    "login_admina": os.getenv("ADMIN_LOGIN", "admin"),
    "haslo_admina": os.getenv("ADMIN_PASSWORD", "admin123"),
    "port_admina": 5000,
    "url_bazy_render": "https://inz-di1v.onrender.com",
    "haslo": os.getenv("TOKEN", "admin123"),

    # Baza
    "mongo_uri": os.getenv("MONGO_URI", ""),
    "nazwa_bazy_mongo": "alkotester",
    "uzytkownik_mongo": os.getenv("MONGODB_USERNAME", ""),

    # Odleglosc i mikrofon
    "kanal_odleglosci": 1,
    "kanal_mikrofonu": 2,
    "min_odleglosc": 8.0,
    "max_odleglosc": 20.0,
    "prog_glosnosci": 500,
    "probki_mikrofonu": 64,

    # Mail
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": os.getenv("SMTP_USER", "alkotesterinz@gmail.com"),
    "smtp_password": os.getenv("SMTP_PASSWORD", "gnmqnptelfcitilt "),
    "uzywaj_tls": True,
    "mail_alertowy": "s194553@student.pg.edu.pl",
}
