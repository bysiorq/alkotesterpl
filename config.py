config = {
    # Wygląd aplikacji
    "UI_szerokosc": 720,
    "UI_wysokosc": 1280,
    "wysokoscUI": 240,
    "PelnyEkran": True,
    "SchowajKursor": True,

    # Kamera i obraz
    "rozdzielczoscKamery": (1280, 720),
    "fps": 10,
    "obrotKamera": "cw",

    # Rozpoznawanie twarzy (YuNet/ORB)
    "sciezkaYunet": "models/face_detection_yunet_2023mar.onnx",
    "yunet_prog_rozpoznania": 0.85,
    "prog_najlepszadetekcja": 0.3,
    "yunet_topwartosc": 5000,

    "czestotliwoscDetekcji": 1000,
    "minRozdzielczoscTwarz": 120,
    "prog_pewnosc_ok": 55.0,
    "prog_pewnosc_niska": 20.0,

    "limit": 5,
    "limitpowtorzen": 3,

    "ileZdjecTrening": 10,
    "CzasTrening": 15,

    "minOstroscProbki": 60.0,
    "minJasnoscProbki": 40.0,
    "maxJasnoscProbki": 210.0,

    "minIloscRozpoznan": 65,
    "prog_dopasowaniaTwarzy": 0.75,
    "minProbkipodrzad": 10,
    "ok_probki_podrzad": 2,

    "max_probekPracownik": 40,

    # MCP3008 / pomiar alkoholu
    "spi": 0,
    "spi_device": 0,
    "mq3_kanal": 0,
    "promile_prog_probki": 150,
    "wspolczynnikPromile": 220.0,
    "czas_pomiaru": 2.0,

    # Progowe decyzje (promil)
    "dolnyProgPromil": 0.2,
    "ProgPromilOdmowa": 0.5,

    # Sterowanie bramką i LED
    "PinFurtka": 18,
    "CzasOtwarciaFurtki": 5.0,

    "Pin_LED_otwarcie": 24,
    "Pin_LED_odmowa": 23,
    "Czas_trwaniaLED": 3.0,

    # Ścieżki i katalogi
    "katalog_dane": "dane",
    "katalogTwarze": "dane/twarze",
    "katalogIndex": "dane/indeks",
    "pracownicyListajson": "dane/pracownicy.json",
    "logi": "logi",
    "raportOdmowy": "logi/raporty_odmowy",
    "font": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    
    # Pracownik startowy
    "pracownikStartowy": {
        "id": "1",
        "imie": "Kamil Karolak",
        "pin": "0000",
    },

    # Uwierzytelnianie / serwer WWW
    "loginAdmin": "admin",
    "hasloAdmin": "admin123",
    "adminport": 5000,
    "urlrender": "https://inz-di1v.onrender.com",
    "token": "admin123",

    # Baza danych
    "mongo_uri": "",
    "baza_mongodb": "alkotester",

    # Czujniki odległości/mikrofon
    "odleglosc_kanal": 1,
    "mikrofon_kanal": 2,
    "minOdleglosc": 8.0,
    "maxOdleglosc": 20.0,
    "prog_mikrofonu": 150,
    "mikrofonAmpIloscProbek": 32,

    # Parametry logowania i maila
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "alkotesterinz@gmail.com",
    "smtp_password": "gnmqnptelfcitilt ",
    "smtp_use_tls": True,
    "alert_email_to": "s194553@student.pg.edu.pl",
}
