from PyQt5 import QtCore, QtWidgets
from konfiguracja import konfig
from fs_pomoc import sprawdzKatalogi, aktualnyCzas
from czujnikspi import Mcp3008, CzujnikMQ3
from baza_twarzy import BazaTwarzy
from kamera import Kamera
from komponenty import sprzet
from komponenty.synchronizacja import synchronizuj_pracownikow

def zainicjalizuj_aplikacje(okno):
    sprawdzKatalogi()

    # Inicjalizacja sprzętu (GPIO, diody, bramka)
    sprzet.inicjalizuj_gpio()

    okno.adc = Mcp3008(konfig["spi_kanal"], konfig["spi_urzadzenie"])
    okno.mq3 = CzujnikMQ3(
        okno.adc,
        konfig["kanal_mq3"],
        konfig["ile_probek_kalibracja"],
        konfig["przelicznik_promili"],
    )

    okno.baza_twarzy = BazaTwarzy(
        konfig["folder_twarze"],
        konfig["folder_indeks"],
        konfig["plik_pracownicy"],
    )

    try:
        synchronizuj_pracownikow(okno.baza_twarzy)
    except Exception as e:
        print(f"[SYNC] Błąd sync przy starcie: {e}")

    okno.setWindowTitle("Alkotester - Raspberry Pi")

    if konfig["ukryj_myszke"]:
        okno.setCursor(QtCore.Qt.BlankCursor)

    print(f"[MongoDebug] konfig['mongo_uri'] = {konfig.get('mongo_uri')}")
    print(f"[MongoDebug] konfig['nazwa_bazy_mongo'] = {konfig.get('nazwa_bazy_mongo')}")

    centralny = QtWidgets.QWidget()
    okno.setCentralWidget(centralny)
    uklad_zew = QtWidgets.QVBoxLayout(centralny)
    uklad_zew.setContentsMargins(0, 0, 0, 0)
    uklad_zew.setSpacing(0)

    okno.widok = QtWidgets.QLabel()
    okno.widok.setAlignment(QtCore.Qt.AlignCenter)
    okno.widok.setStyleSheet("background:black;")
    okno.widok.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Expanding,
    )
    uklad_zew.addWidget(okno.widok, 1)

    okno.nakladka = QtWidgets.QFrame()
    okno.nakladka.setFixedHeight(konfig["wysokosc_paska"])
    okno.nakladka.setStyleSheet("background: rgba(0,0,0,110); color:white;")

    uklad_overlay = QtWidgets.QVBoxLayout(okno.nakladka)
    uklad_overlay.setContentsMargins(16, 12, 16, 12)
    uklad_overlay.setSpacing(8)

    gorny_rzad = QtWidgets.QHBoxLayout()
    gorny_rzad.setContentsMargins(0, 0, 0, 0)
    gorny_rzad.setSpacing(8)
    okno.etykieta_gora = QtWidgets.QLabel("")
    okno.etykieta_gora.setStyleSheet("color:white; font-size:28px; font-weight:600;")
    gorny_rzad.addWidget(okno.etykieta_gora)
    gorny_rzad.addStretch(1)
    okno.guzik_gosc = QtWidgets.QPushButton("Gość")
    okno.guzik_gosc.setStyleSheet(
        "font-size:20px; padding:6px 12px; border-radius:12px; "
        "background:#6a1b9a; color:white;"
    )
    # Connect signals later or here if methods are available
    # okno.guzik_gosc.clicked.connect(okno.klik_gosc)
    gorny_rzad.addWidget(okno.guzik_gosc)
    uklad_overlay.addLayout(gorny_rzad)

    okno.stos_srodek = QtWidgets.QStackedLayout()
    okno.stos_srodek.setContentsMargins(0, 0, 0, 0)
    okno.stos_srodek.setSpacing(0)

    okno.etykieta_srodek = QtWidgets.QLabel("")
    okno.etykieta_srodek.setAlignment(QtCore.Qt.AlignCenter)
    okno.etykieta_srodek.setStyleSheet(
        "color:white; font-size:36px; font-weight:700;"
    )
    okno.stos_srodek.addWidget(okno.etykieta_srodek)  # index 0

    okno.pasek_postepu = QtWidgets.QProgressBar()
    okno.pasek_postepu.setRange(0, 100)
    okno.pasek_postepu.setValue(0)
    okno.pasek_postepu.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Fixed,
    )
    okno.pasek_postepu.setFixedHeight(40)
    okno.pasek_postepu.setStyleSheet(
        "QProgressBar {background-color: #444444; border-radius: 10px; "
        "color:white; font-size:24px;} "
        "QProgressBar::chunk { background-color: #00c853; }"
    )
    okno.pasek_postepu.hide()

    okno.kontener_postepu = QtWidgets.QWidget()
    uklad_postep = QtWidgets.QVBoxLayout(okno.kontener_postepu)
    uklad_postep.setContentsMargins(40, 0, 40, 0)
    uklad_postep.setSpacing(0)
    uklad_postep.addStretch(1)
    uklad_postep.addWidget(okno.pasek_postepu)
    uklad_postep.addStretch(1)

    okno.stos_srodek.addWidget(okno.kontener_postepu)

    uklad_overlay.addLayout(okno.stos_srodek, 1)
    okno.stos_srodek.setCurrentWidget(okno.etykieta_srodek)

    rzad_przyciski = QtWidgets.QHBoxLayout()
    rzad_przyciski.setSpacing(12)

    okno.guzik_glowny = QtWidgets.QPushButton("Ponów pomiar")
    okno.guzik_glowny.setStyleSheet(
        "font-size:24px; padding:12px 18px; border-radius:16px; "
        "background:#2e7d32; color:white;"
    )

    okno.guzik_pomocniczy = QtWidgets.QPushButton("Wprowadź PIN")
    okno.guzik_pomocniczy.setStyleSheet(
        "font-size:24px; padding:12px 18px; border-radius:16px; "
        "background:#1565c0; color:white;"
    )

    rzad_przyciski.addWidget(okno.guzik_glowny)
    rzad_przyciski.addWidget(okno.guzik_pomocniczy)
    uklad_overlay.addLayout(rzad_przyciski)

    uklad_zew.addWidget(okno.nakladka, 0)

    # STAN I ZMIENNE ROBOCZE
    okno.stan = "START"
    okno.id_pracownika_biezacego = None
    okno.nazwa_pracownika_biezacego = None

    okno.flaga_pin_zapasowy = False

    okno.ostatni_obrys_twarzy = None
    okno.ostatnia_pewnosc = 0.0
    okno.ostatni_wynik_promile = 0.0

    okno.ostatnia_klatka_bgr = None
    okno.ostatnia_klatka_detekcji_bgr = None

    okno.licznik_nieudanych_detekcji = 0
    okno.licznik_prob_ponownej_detekcji = 0

    okno.stabilne_id_pracownika = None
    okno.licznik_stabilnych_probek = 0

    okno.kalibracja_dobra_twarz = False
    okno.kalibracja_widoczna_twarz = False

    okno.lista_probek_pomiarowych = []
    okno.licznik_ponownych_pomiarow = 0

    okno.akcja_po_treningu = None

    okno.kanal_odleglosc = konfig.get("kanal_odleglosci")
    okno.kanal_mikrofon = konfig.get("kanal_mikrofonu")
    okno.odleglosc_min_cm = konfig.get("min_odleglosc")
    okno.odleglosc_max_cm = konfig.get("max_odleglosc")
    okno.prog_mikrofonu = konfig.get("prog_glosnosci")

    okno.czas_dmuchania = 0.0
    okno.czy_gosc = False

    okno.kamera = Kamera(
        konfig["rozdzialka_kamery"][0],
        konfig["rozdzialka_kamery"][1],
        konfig["kierunek_obrotu"],
    )

    okno.timer_kamery = QtCore.QTimer(okno)
    okno.timer_kamery.timeout.connect(okno.cykl_kamery)
    okno.timer_kamery.start(int(1000 / max(1, konfig["klatki_na_sekunde"])))

    okno.timer_twarzy = QtCore.QTimer(okno)

    okno.timer_interfejsu = QtCore.QTimer(okno)

    okno.timer_rozpoznany = QtCore.QTimer(okno)

    okno.timer_pomiaru = QtCore.QTimer(okno)

    okno.timer_sync = QtCore.QTimer(okno)
    okno.timer_sync.start(1 * 60 * 1000)
