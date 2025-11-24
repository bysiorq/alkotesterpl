import os
import sys
import cv2
import time
import signal
import threading
import json
import requests
import numpy as np
from datetime import datetime

import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from PyQt5 import QtCore, QtGui, QtWidgets
import RPi.GPIO as GPIO

from konfiguracja import konfig
from fs_pomoc import sprawdzKatalogi, aktualnyCzas, zapiszDoPlikuCsv
from czujnikspi import Mcp3008, CzujnikMQ3
from baza_twarzy import BazaTwarzy
from kamera import Kamera
from oknoPin import OknoPin

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

_KLIENT_MONGO = None


def jakosc_twarzy(szare_roi):
    ostrosc = cv2.Laplacian(szare_roi, cv2.CV_64F).var()
    jasnosc = float(np.mean(szare_roi))
    ok = (
        ostrosc >= konfig["min_ostrosc"]
        and konfig["min_jasnosc"] <= jasnosc <= konfig["max_jasnosc"]
    )
    return ok, ostrosc, jasnosc


class GlowneOkno(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        sprawdzKatalogi()

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(konfig["pin_furtki"], GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(konfig["pin_led_zielony"], GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(konfig["pin_led_czerwony"], GPIO.OUT, initial=GPIO.LOW)

        self.adc = Mcp3008(konfig["spi_kanal"], konfig["spi_urzadzenie"])
        self.mq3 = CzujnikMQ3(
            self.adc,
            konfig["kanal_mq3"],
            konfig["ile_probek_kalibracja"],
            konfig["przelicznik_promili"],
        )

        self.baza_twarzy = BazaTwarzy(
            konfig["folder_twarze"],
            konfig["folder_indeks"],
            konfig["plik_pracownicy"],
        )
        prac_start = konfig["pracownik_startowy"]
        self.baza_twarzy.dodajNowego(
            prac_start["id"], prac_start["imie"], prac_start["pin"]
        )

        try:
            self.synchronizuj_pracownikow()
        except Exception as e:
            print(f"[SYNC] Błąd sync przy starcie: {e}")

        self.setWindowTitle("Alkotester - Raspberry Pi")

        if konfig["ukryj_myszke"]:
            self.setCursor(QtCore.Qt.BlankCursor)

        print(f"[MongoDebug] konfig['mongo_uri'] = {konfig.get('mongo_uri')}")
        print(f"[MongoDebug] konfig['nazwa_bazy_mongo'] = {konfig.get('nazwa_bazy_mongo')}")

        centralny = QtWidgets.QWidget()
        self.setCentralWidget(centralny)
        uklad_zew = QtWidgets.QVBoxLayout(centralny)
        uklad_zew.setContentsMargins(0, 0, 0, 0)
        uklad_zew.setSpacing(0)

        self.widok = QtWidgets.QLabel()
        self.widok.setAlignment(QtCore.Qt.AlignCenter)
        self.widok.setStyleSheet("background:black;")
        self.widok.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        uklad_zew.addWidget(self.widok, 1)

        self.nakladka = QtWidgets.QFrame()
        self.nakladka.setFixedHeight(konfig["wysokosc_paska"])
        self.nakladka.setStyleSheet("background: rgba(0,0,0,110); color:white;")

        uklad_overlay = QtWidgets.QVBoxLayout(self.nakladka)
        uklad_overlay.setContentsMargins(16, 12, 16, 12)
        uklad_overlay.setSpacing(8)

        gorny_rzad = QtWidgets.QHBoxLayout()
        gorny_rzad.setContentsMargins(0, 0, 0, 0)
        gorny_rzad.setSpacing(8)
        self.etykieta_gora = QtWidgets.QLabel("")
        self.etykieta_gora.setStyleSheet("color:white; font-size:28px; font-weight:600;")
        gorny_rzad.addWidget(self.etykieta_gora)
        gorny_rzad.addStretch(1)
        self.guzik_gosc = QtWidgets.QPushButton("Gość")
        self.guzik_gosc.setStyleSheet(
            "font-size:20px; padding:6px 12px; border-radius:12px; "
            "background:#6a1b9a; color:white;"
        )
        self.guzik_gosc.clicked.connect(self.klik_gosc)
        gorny_rzad.addWidget(self.guzik_gosc)
        uklad_overlay.addLayout(gorny_rzad)

        self.stos_srodek = QtWidgets.QStackedLayout()
        self.stos_srodek.setContentsMargins(0, 0, 0, 0)
        self.stos_srodek.setSpacing(0)

        self.etykieta_srodek = QtWidgets.QLabel("")
        self.etykieta_srodek.setAlignment(QtCore.Qt.AlignCenter)
        self.etykieta_srodek.setStyleSheet(
            "color:white; font-size:36px; font-weight:700;"
        )
        self.stos_srodek.addWidget(self.etykieta_srodek)  # index 0

        self.pasek_postepu = QtWidgets.QProgressBar()
        self.pasek_postepu.setRange(0, 100)
        self.pasek_postepu.setValue(0)
        self.pasek_postepu.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.pasek_postepu.setFixedHeight(40)
        self.pasek_postepu.setStyleSheet(
            "QProgressBar {background-color: #444444; border-radius: 10px; "
            "color:white; font-size:24px;} "
            "QProgressBar::chunk { background-color: #00c853; }"
        )
        self.pasek_postepu.hide()

        self.kontener_postepu = QtWidgets.QWidget()
        uklad_postep = QtWidgets.QVBoxLayout(self.kontener_postepu)
        uklad_postep.setContentsMargins(40, 0, 40, 0)
        uklad_postep.setSpacing(0)
        uklad_postep.addStretch(1)
        uklad_postep.addWidget(self.pasek_postepu)
        uklad_postep.addStretch(1)

        self.stos_srodek.addWidget(self.kontener_postepu)

        uklad_overlay.addLayout(self.stos_srodek, 1)
        self.stos_srodek.setCurrentWidget(self.etykieta_srodek)

        rzad_przyciski = QtWidgets.QHBoxLayout()
        rzad_przyciski.setSpacing(12)

        self.guzik_glowny = QtWidgets.QPushButton("Ponów pomiar")
        self.guzik_glowny.setStyleSheet(
            "font-size:24px; padding:12px 18px; border-radius:16px; "
            "background:#2e7d32; color:white;"
        )

        self.guzik_pomocniczy = QtWidgets.QPushButton("Wprowadź PIN")
        self.guzik_pomocniczy.setStyleSheet(
            "font-size:24px; padding:12px 18px; border-radius:16px; "
            "background:#1565c0; color:white;"
        )

        rzad_przyciski.addWidget(self.guzik_glowny)
        rzad_przyciski.addWidget(self.guzik_pomocniczy)
        uklad_overlay.addLayout(rzad_przyciski)

        uklad_zew.addWidget(self.nakladka, 0)

        # STAN I ZMIENNE ROBOCZE
        self.stan = "START"
        self.id_pracownika_biezacego = None
        self.nazwa_pracownika_biezacego = None

        self.flaga_pin_zapasowy = False

        self.ostatni_obrys_twarzy = None
        self.ostatnia_pewnosc = 0.0
        self.ostatni_wynik_promile = 0.0

        self.ostatnia_klatka_bgr = None
        self.ostatnia_klatka_detekcji_bgr = None

        self.licznik_nieudanych_detekcji = 0
        self.licznik_prob_ponownej_detekcji = 0

        self.stabilne_id_pracownika = None
        self.licznik_stabilnych_probek = 0

        self.kalibracja_dobra_twarz = False
        self.kalibracja_widoczna_twarz = False

        self.lista_probek_pomiarowych = []
        self.licznik_ponownych_pomiarow = 0

        self.akcja_po_treningu = None

        self.kanal_odleglosc = konfig.get("kanal_odleglosci")
        self.kanal_mikrofon = konfig.get("kanal_mikrofonu")
        self.odleglosc_min_cm = konfig.get("min_odleglosc")
        self.odleglosc_max_cm = konfig.get("max_odleglosc")
        self.prog_mikrofonu = konfig.get("prog_glosnosci")

        self.czas_dmuchania = 0.0
        self.czy_gosc = False

        self.kamera = Kamera(
            konfig["rozdzialka_kamery"][0],
            konfig["rozdzialka_kamery"][1],
            konfig["kierunek_obrotu"],
        )

        self.timer_kamery = QtCore.QTimer(self)
        self.timer_kamery.timeout.connect(self.cykl_kamery)
        self.timer_kamery.start(int(1000 / max(1, konfig["klatki_na_sekunde"])))

        self.timer_twarzy = QtCore.QTimer(self)
        self.timer_twarzy.timeout.connect(self.cykl_twarzy)

        self.timer_interfejsu = QtCore.QTimer(self)
        self.timer_interfejsu.timeout.connect(self.cykl_interfejsu)

        self.timer_rozpoznany = QtCore.QTimer(self)
        self.timer_rozpoznany.timeout.connect(self.cykl_rozpoznany)

        self.timer_pomiaru = QtCore.QTimer(self)
        self.timer_pomiaru.timeout.connect(self.pomiar)

        self.timer_sync = QtCore.QTimer(self)
        self.timer_sync.timeout.connect(self.cykl_synchronizacji)
        self.timer_sync.start(1 * 60 * 1000)

        self.guzik_glowny.clicked.connect(self.klik_guzik1)
        self.guzik_pomocniczy.clicked.connect(self.klik_guzik2)

        self.ustaw_komunikat(
            "Proszę czekać…",
            "Kalibracja czujnika MQ-3 w toku",
            color="white",
        )
        self.pokaz_guziki(primary_text=None, secondary_text=None)

        self.stan_kalibracjamq3()


    def kadr_zoom_przyciecie(self, img, target_w, target_h):
        if img is None or target_w <= 0 or target_h <= 0:
            return None

        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return None

        proporcja_zrodlo = w / float(h)
        proporcja_cel = target_w / float(target_h)

        if proporcja_zrodlo > proporcja_cel:
            nowe_w = int(h * proporcja_cel)
            if nowe_w <= 0:
                return None
            x1 = max(0, (w - nowe_w) // 2)
            x2 = x1 + nowe_w
            przyciete = img[:, x1:x2]
        else:
            nowe_h = int(w / proporcja_cel)
            if nowe_h <= 0:
                return None
            y1 = max(0, (h - nowe_h) // 2)
            y2 = y1 + nowe_h
            przyciete = img[y1:y2, :]

        if przyciete.size == 0:
            return None

        zmienione = cv2.resize(
            przyciete, (int(target_w), int(target_h)), interpolation=cv2.INTER_AREA
        )
        return zmienione

    def synchronizuj_pracownikow(self):
        baza_url = konfig.get("url_bazy_render")
        token = konfig.get("haslo")
        sciezka_prac = konfig.get("plik_pracownicy", "dane/pracownicy.json")

        if not os.path.isabs(sciezka_prac):
            katalog_biez = os.path.dirname(os.path.abspath(__file__))
            sciezka_prac = os.path.join(katalog_biez, sciezka_prac)

        if not baza_url:
            print("[SYNC] Brak url_bazy_render w config - pomijam sync.")
            return

        url = f"{baza_url.rstrip('/')}/api/pracownicy_public"
        params = {}
        if token:
            params["token"] = token

        try:
            print(f"[SYNC] Pobieram pracowników z {url} ...")
            odp = requests.get(url, params=params, timeout=3)
            odp.raise_for_status()
            dane = odp.json()
            if not isinstance(dane, dict):
                print("[SYNC] Odpowiedź nie jest dict-em - pomijam.")
                return

            lista_prac = dane.get("pracownicy")
            if lista_prac is None:
                lista_prac = dane.get("employees", [])
            if not isinstance(lista_prac, list):
                lista_prac = []

            dane_do_zapisu = {"pracownicy": lista_prac}

            os.makedirs(os.path.dirname(sciezka_prac), exist_ok=True)
            with open(sciezka_prac, "w", encoding="utf-8") as f:
                json.dump(dane_do_zapisu, f, ensure_ascii=False, indent=2)

            print(f"[SYNC] Zapisano {len(lista_prac)} pracowników do {sciezka_prac}")

            try:
                self.baza_twarzy.wczytajPracownikow()
                print("[SYNC] FaceDB przeładowany.")
            except Exception as e:
                print(f"[SYNC] Błąd przeładowania FaceDB: {e}")

        except Exception as e:
            print(f"[SYNC] Błąd pobierania z serwera: {e}")

    def doucz_twarz(self, id_prac: str):
        try:
            if self.ostatni_obrys_twarzy is None:
                return
            if self.ostatnia_klatka_bgr is None:
                return

            (fx, fy, fw, fh) = self.ostatni_obrys_twarzy
            fx = int(max(0, fx))
            fy = int(max(0, fy))
            fw = int(max(0, fw))
            fh = int(max(0, fh))

            h_img, w_img, _ = self.ostatnia_klatka_bgr.shape
            x2 = min(fx + fw, w_img)
            y2 = min(fy + fh, h_img)
            if x2 <= fx or y2 <= fy:
                return

            twarz_bgr = self.ostatnia_klatka_bgr[fy:y2, fx:x2].copy()
            twarz_bgr = cv2.resize(
                twarz_bgr,
                (240, 240),
                interpolation=cv2.INTER_LINEAR,
            )

            twarz_szara = cv2.cvtColor(twarz_bgr, cv2.COLOR_BGR2GRAY)
            ok_q, ostrosc, jasnosc = jakosc_twarzy(twarz_szara)
            if not ok_q:
                return

            self.baza_twarzy.dodajProbke(id_prac, twarz_bgr)
        except Exception:
            pass

    def cykl_synchronizacji(self):
        try:
            self.synchronizuj_pracownikow()
        except Exception as e:
            print(f"[SYNC] Błąd okresowego sync-a: {e}")

    def zatrzymaj_timer(self, obiekt_timera: QtCore.QTimer):
        try:
            if obiekt_timera.isActive():
                obiekt_timera.stop()
        except Exception:
            pass

    def ustaw_komunikat(self, tekst_gora, tekst_srodek=None, color="white", use_center=True):
        if color == "green":
            kolor_css = "#00ff00"
        elif color == "red":
            kolor_css = "#ff4444"
        else:
            kolor_css = "white"

        self.etykieta_gora.setText(tekst_gora)
        self.etykieta_gora.setStyleSheet(
            f"color:{kolor_css}; font-size:28px; font-weight:600;"
        )
        if use_center:
            self.etykieta_srodek.setText(tekst_srodek or "")
            self.etykieta_srodek.setStyleSheet(
                f"color:{kolor_css}; font-size:36px; font-weight:700;"
            )
            if hasattr(self, "stos_srodek"):
                self.stos_srodek.setCurrentWidget(self.etykieta_srodek)

    def pokaz_guziki(self, primary_text=None, secondary_text=None):
        if primary_text is None:
            self.guzik_glowny.hide()
        else:
            self.guzik_glowny.setText(primary_text)
            self.guzik_glowny.show()

        if secondary_text is None:
            self.guzik_pomocniczy.hide()
        else:
            self.guzik_pomocniczy.setText(secondary_text)
            self.guzik_pomocniczy.show()


    def bezczynnosc(self):
        self.stan = "BEZCZYNNOSC"
        self.id_pracownika_biezacego = None
        self.nazwa_pracownika_biezacego = None
        self.flaga_pin_zapasowy = False
        self.czy_gosc = False

        self.ostatni_obrys_twarzy = None
        self.ostatnia_pewnosc = 0.0
        self.licznik_nieudanych_detekcji = 0
        self.licznik_prob_ponownej_detekcji = 0
        self.stabilne_id_pracownika = None
        self.licznik_stabilnych_probek = 0

        self.kalibracja_dobra_twarz = False
        self.kalibracja_widoczna_twarz = False

        self.lista_probek_pomiarowych = []
        self.czas_dmuchania = 0.0
        self.licznik_ponownych_pomiarow = 0

        self.pasek_postepu.hide()

        self.timer_interfejsu.start(250)
        self.timer_twarzy.start(konfig["co_ile_detekcja"])
        self.zatrzymaj_timer(self.timer_rozpoznany)
        self.zatrzymaj_timer(self.timer_pomiaru)

        self.ustaw_komunikat(aktualnyCzas(), "Podejdź bliżej", color="white")
        self.pokaz_guziki(primary_text=None, secondary_text="Wprowadź PIN")

        if hasattr(self, "stos_srodek"):
            self.stos_srodek.setCurrentWidget(self.etykieta_srodek)

    def tryb_detekcja(self):
        self.stan = "DETEKCJA"
        self.licznik_nieudanych_detekcji = 0
        self.stabilne_id_pracownika = None
        self.licznik_stabilnych_probek = 0

        self.timer_interfejsu.start(250)
        self.timer_twarzy.start(konfig["co_ile_detekcja"])
        self.zatrzymaj_timer(self.timer_rozpoznany)
        self.zatrzymaj_timer(self.timer_pomiaru)

        self.ustaw_komunikat(aktualnyCzas(), "Szukam twarzy…", color="white")
        self.pokaz_guziki(primary_text=None, secondary_text="Wprowadź PIN")

    def tryb_wpisywania_pinu(self):
        self.stan = "PIN_WPROWADZANIE"
        self.zatrzymaj_timer(self.timer_twarzy)
        self.zatrzymaj_timer(self.timer_interfejsu)
        self.zatrzymaj_timer(self.timer_rozpoznany)
        self.zatrzymaj_timer(self.timer_pomiaru)
        try:
            print("[SYNC] Ręczny sync przed wprowadzeniem PIN-u...")
            self.synchronizuj_pracownikow()
        except Exception as e:
            print(f"[SYNC] Błąd sync przy wprowadzaniu PIN: {e}")

        dlg = OknoPin(self, title="Wprowadź PIN")
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            pin = dlg.wezPin()
            try:
                self.baza_twarzy.wczytajPracownikow()
            except Exception:
                pass
            wpis = self.baza_twarzy.emp_by_pin.get(pin)
            if not wpis:
                self.ustaw_komunikat("Zły PIN - brak danych", "", color="red")
                self.pokaz_guziki(primary_text=None, secondary_text=None)
                QtCore.QTimer.singleShot(2000, self.bezczynnosc)
                return

            self.id_pracownika_biezacego = wpis.get("id")
            self.nazwa_pracownika_biezacego = wpis.get("imie")
            self.flaga_pin_zapasowy = False

            self.zbieranieprobek_dla_pracownika()
        else:
            self.bezczynnosc()

    def tryb_ponowna_detekcja(self):
        self.stan = "DETEKCJA_PONOWNA"
        self.licznik_prob_ponownej_detekcji = 0

        self.timer_twarzy.start(konfig["co_ile_detekcja"])
        self.zatrzymaj_timer(self.timer_interfejsu)
        self.zatrzymaj_timer(self.timer_rozpoznany)
        self.zatrzymaj_timer(self.timer_pomiaru)

        self.ustaw_komunikat(
            "Sprawdzam twarz…", self.nazwa_pracownika_biezacego or "", color="white"
        )
        self.pokaz_guziki(primary_text=None, secondary_text=None)

    def tryb_rozpoznany(self):
        self.stan = "OCZEKIWANIE_POMIAR"

        self.kalibracja_dobra_twarz = False
        self.kalibracja_widoczna_twarz = False

        self.timer_twarzy.start(konfig["co_ile_detekcja"])

        self.zatrzymaj_timer(self.timer_interfejsu)
        self.zatrzymaj_timer(self.timer_pomiaru)
        self.zatrzymaj_timer(self.timer_rozpoznany)

        self.timer_rozpoznany.start(200)

        imie = self.nazwa_pracownika_biezacego or ""
        odleglosc_cm = self.odczytaj_odleglosc()
        if odleglosc_cm == float("inf"):
            tekst_odleglosc = "brak odczytu"
        elif odleglosc_cm > 80:
            tekst_odleglosc = ">80 cm"
        else:
            tekst_odleglosc = f"{odleglosc_cm:0.0f} cm"

        tekst_gora = "Podejdź bliżej"
        tekst_srodek = f"Cześć {imie}\nOdległość: {tekst_odleglosc}"
        self.ustaw_komunikat(tekst_gora, tekst_srodek, color="white")
        self.pokaz_guziki(primary_text=None, secondary_text=None)

    def tryb_pomiaru(self):
        self.stan = "POMIAR"
        self.lista_probek_pomiarowych = []
        self.czas_dmuchania = 0.0

        self.ostatni_obrys_twarzy = None
        self.ostatnia_pewnosc = 0.0

        self.zatrzymaj_timer(self.timer_twarzy)
        self.zatrzymaj_timer(self.timer_interfejsu)
        self.zatrzymaj_timer(self.timer_rozpoznany)

        self.pasek_postepu.setValue(0)
        self.pasek_postepu.show()
        if hasattr(self, "stos_srodek"):
            self.stos_srodek.setCurrentWidget(self.kontener_postepu)

        self.timer_pomiaru.start(100)

        self.ustaw_komunikat("Przeprowadzam pomiar…", "", color="white", use_center=False)
        self.pokaz_guziki(primary_text=None, secondary_text=None)

    @QtCore.pyqtSlot()
    def koniec_pomiaru(self):
        promille = getattr(self, "_oczekujace_promile", 0.0)
        self.werdykt(promille)

    def werdykt(self, promille):
        self.pasek_postepu.hide()
        if hasattr(self, "stos_srodek"):
            self.stos_srodek.setCurrentWidget(self.etykieta_srodek)
            self.etykieta_srodek.setWordWrap(True)

        self.ostatni_wynik_promile = float(promille)

        try:
            prog_ok = float(konfig.get("prog_trzezwosci", 0.0))
        except Exception:
            prog_ok = 0.0
        try:
            prog_odmowa = float(konfig.get("prog_pijany", 0.5))
        except Exception:
            prog_odmowa = 0.5

        if prog_ok > prog_odmowa:
            print(
                f"[WARN] prog_trzezwosci ({prog_ok}) > prog_pijany ({prog_odmowa})"
            )
            prog_ok, prog_odmowa = prog_odmowa, prog_ok

        print(
            f"[DECYZJA] promille={self.ostatni_wynik_promile:.3f}, "
            f"OK <= {prog_ok:.3f}, odmowa >= {prog_odmowa:.3f}"
        )

        tekst_pomiar = f"Pomiar: {self.ostatni_wynik_promile:.3f} [‰]"

        self.zatrzymaj_timer(self.timer_twarzy)
        self.zatrzymaj_timer(self.timer_interfejsu)
        self.zatrzymaj_timer(self.timer_rozpoznany)
        self.zatrzymaj_timer(self.timer_pomiaru)

        wynik_ok = False
        trzeba_powtorzyc = False

        if self.ostatni_wynik_promile <= prog_ok:
            wynik_ok = True
        elif self.ostatni_wynik_promile < prog_odmowa:
            if self.licznik_ponownych_pomiarow >= 1:
                trzeba_powtorzyc = False
                wynik_ok = False
            else:
                trzeba_powtorzyc = True
        else:
            wynik_ok = False

        if wynik_ok and not trzeba_powtorzyc:
            self.stan = "DECYZJA_OK"
            self.ustaw_komunikat(tekst_pomiar, "Przejście otwarte", color="green")
            self.pokaz_guziki(primary_text=None, secondary_text=None)
            self.sygnal_bramka_mongo(True, self.ostatni_wynik_promile)
            self.dioda_led(True)
            QtCore.QTimer.singleShot(2500, self.bezczynnosc)
            return

        if trzeba_powtorzyc:
            self.stan = "PONOW_POMIAR"
            self.ustaw_komunikat(
                tekst_pomiar,
                "Ponów pomiar",
                color="red",
            )
            self.pokaz_guziki(
                primary_text="Ponów pomiar", secondary_text="Odmowa"
            )
            return

        self.stan = "DECYZJA_ODMOWA"
        self.ustaw_komunikat(tekst_pomiar, "Odmowa", color="red")
        self.pokaz_guziki(primary_text=None, secondary_text=None)
        self.sygnal_bramka_mongo(False, self.ostatni_wynik_promile)
        self.dioda_led(False)
        QtCore.QTimer.singleShot(3000, self.bezczynnosc)

    def cykl_rozpoznany(self):
        if self.stan != "OCZEKIWANIE_POMIAR":
            self.zatrzymaj_timer(self.timer_rozpoznany)
            return

        odleglosc_cm = self.odczytaj_odleglosc()
        imie = self.nazwa_pracownika_biezacego or ""
        if odleglosc_cm > 70:
            tekst_odleglosc = ">1m"
        else:
            tekst_odleglosc = f"{odleglosc_cm:0.0f} cm"

        if self.odleglosc_min_cm <= odleglosc_cm <= self.odleglosc_max_cm:
            if self.kalibracja_dobra_twarz or self.flaga_pin_zapasowy:
                self.zatrzymaj_timer(self.timer_rozpoznany)
                tekst_gora = "Nie ruszaj się - start pomiaru"
                tekst_srodek = f"Cześć {imie}\nOdległość: {tekst_odleglosc}"
                self.ustaw_komunikat(tekst_gora, tekst_srodek, color="white")
                self.tryb_pomiaru()
                return
            else:
                self.ustaw_komunikat(
                    "Stań przodem do kamery",
                    f"Cześć {imie}\nOdległość: {tekst_odleglosc}",
                    color="white",
                )
                return

        self.ustaw_komunikat(
            "Podejdź bliżej",
            f"Cześć {imie}\nOdległość: {tekst_odleglosc}",
            color="white",
        )

    def pomiar(self):
        if self.stan != "POMIAR":
            self.zatrzymaj_timer(self.timer_pomiaru)
            return

        try:
            dt = self.timer_pomiaru.interval() / 1000.0
        except Exception:
            dt = 0.1

        odleglosc_cm = self.odczytaj_odleglosc()
        amp, _ = self.odczytaj_mikrofon(
            samples=konfig.get("probki_mikrofonu", 32)
        )

        dmuchanie_wykryte = (
            self.odleglosc_min_cm <= odleglosc_cm <= self.odleglosc_max_cm
            and amp >= self.prog_mikrofonu
        )

        if dmuchanie_wykryte:
            self.czas_dmuchania += dt
            try:
                self.lista_probek_pomiarowych.append(self.mq3.pobierz())
            except Exception:
                pass

        postep = max(
            0.0, min(self.czas_dmuchania / konfig["czas_dmuchania"], 1.0)
        )
        self.pasek_postepu.setValue(int(postep * 100))
        self.pasek_postepu.show()

        if hasattr(self, "stos_srodek"):
            self.stos_srodek.setCurrentWidget(self.kontener_postepu)

        if dmuchanie_wykryte:
            self.ustaw_komunikat(
                "Przeprowadzam pomiar…", "", color="white", use_center=False
            )
        else:
            if not (
                self.odleglosc_min_cm <= odleglosc_cm <= self.odleglosc_max_cm
            ):
                self.ustaw_komunikat(
                    "Podejdź bliżej", "", color="white", use_center=False
                )
            else:
                self.ustaw_komunikat("Dmuchaj", "", color="white", use_center=False)

        if self.czas_dmuchania >= konfig["czas_dmuchania"]:
            self.zatrzymaj_timer(self.timer_pomiaru)
            probki = list(self.lista_probek_pomiarowych)

            def watek():
                try:
                    promille = float(self.mq3.promile(probki))
                except Exception as e:
                    print(f"[POMIAR] błąd liczenia promili: {e}")
                    promille = 0.0
                self._oczekujace_promile = promille
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "koniec_pomiaru",
                    QtCore.Qt.QueuedConnection,
                )

            threading.Thread(target=watek, daemon=True).start()

    def klik_guzik1(self):
        if self.stan == "PONOW_POMIAR":
            if self.licznik_ponownych_pomiarow >= 1:
                return
            self.licznik_ponownych_pomiarow += 1
            self.tryb_pomiaru()

        elif self.stan == "PIN_NIEUDANY_WYBOR":
            self.flaga_pin_zapasowy = True
            self.tryb_rozpoznany()

    def klik_guzik2(self):
        if self.stan == "PONOW_POMIAR":
            self.ustaw_komunikat("Odmowa", "", color="red")
            self.sygnal_bramka_mongo(False, self.ostatni_wynik_promile)
            self.dioda_led(False)
            self.pokaz_guziki(primary_text=None, secondary_text=None)
            QtCore.QTimer.singleShot(2000, self.bezczynnosc)
            return

        if self.stan == "PIN_NIEUDANY_WYBOR":
            self.bezczynnosc()
            return

        if self.stan in ("BEZCZYNNOSC", "DETEKCJA"):
            self.tryb_wpisywania_pinu()

    def zbieranie_probek_pracownika(self):
        id_prac = self.id_pracownika_biezacego
        if not id_prac:
            self.bezczynnosc()
            return

        ile_potrzeba = konfig["ile_fotek_trening"]
        timeout_s = konfig["czas_na_trening"]
        deadline = time.time() + timeout_s

        self.ustaw_komunikat(
            "Przytrzymaj twarz w obwódce",
            f"Zbieram próbki 0/{ile_potrzeba}",
            color="white",
        )
        self.pokaz_guziki(primary_text=None, secondary_text=None)

        zapisane = 0
        lista_obrazow = []

        def tik():
            nonlocal zapisane, lista_obrazow, deadline

            if time.time() > deadline:
                self.ostatni_obrys_twarzy = None
                self.stan = "PIN_NIEUDANY_WYBOR"
                self.ustaw_komunikat(
                    "Nie udało się zebrać próbek",
                    "Przejść do pomiaru na podstawie PIN?",
                    color="red",
                )
                self.pokaz_guziki(
                    primary_text="Przejdź do pomiaru",
                    secondary_text="Anuluj",
                )
                return

            if self.ostatnia_klatka_bgr is None:
                QtCore.QTimer.singleShot(80, tik)
                return

            klatka = self.ostatnia_klatka_bgr
            szary = cv2.cvtColor(klatka, cv2.COLOR_BGR2GRAY)

            twarze = self.baza_twarzy.detekcja(klatka)
            if not twarze:
                self.ostatni_obrys_twarzy = None
                self.ustaw_komunikat(
                    "Przytrzymaj twarz w obwódce",
                    f"Zbieram próbki {zapisane}/{ile_potrzeba}",
                    color="white",
                )
                QtCore.QTimer.singleShot(80, tik)
                return

            (x, y, w, h) = max(twarze, key=lambda r: r[2] * r[3])
            self.ostatni_obrys_twarzy = (x, y, w, h)
            self.ostatnia_pewnosc = 100.0

            h_img, w_img = szary.shape[:2]
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(int(x + w), w_img)
            y2 = min(int(y + h), h_img)

            if x2 <= x1 or y2 <= y1:
                self.ustaw_komunikat(
                    "Przytrzymaj twarz w obwódce",
                    f"Zbieram próbki {zapisane}/{ile_potrzeba}",
                    color="white",
                )
                QtCore.QTimer.singleShot(80, tik)
                return

            if max(x2 - x1, y2 - y1) < konfig["min_rozmiar_twarzy"]:
                self.ustaw_komunikat(
                    "Podejdź bliżej",
                    f"Zbieram próbki {zapisane}/{ile_potrzeba}",
                    color="white",
                )
                QtCore.QTimer.singleShot(80, tik)
                return

            roi_gray = szary[y1:y2, x1:x2]
            if roi_gray.size == 0:
                QtCore.QTimer.singleShot(80, tik)
                return

            roi_gray_resized = cv2.resize(
                roi_gray,
                (240, 240),
                interpolation=cv2.INTER_LINEAR,
            )

            ok, ostrosc, jasnosc = jakosc_twarzy(roi_gray_resized)
            if not ok:
                self.ustaw_komunikat(
                    "Stań prosto, popraw światło",
                    f"ostrość {ostrosc:0.0f}, jasność {jasnosc:0.0f}  [{zapisane}/{ile_potrzeba}]",
                    color="white",
                )
                QtCore.QTimer.singleShot(80, tik)
                return

            twarz_bgr = klatka[y1:y2, x1:x2].copy()
            twarz_bgr = cv2.resize(
                twarz_bgr, (240, 240), interpolation=cv2.INTER_LINEAR
            )
            lista_obrazow.append(twarz_bgr)
            zapisane += 1

            self.ustaw_komunikat(
                "Próbka zapisana",
                f"Zbieram próbki {zapisane}/{ile_potrzeba}",
                color="green",
            )

            if zapisane >= ile_potrzeba:
                self.baza_twarzy.zbierzProbki(id_prac, lista_obrazow)
                self.start_treningu(akcja_po="DETEKCJA_PONOWNA")
                return

            QtCore.QTimer.singleShot(120, tik)

        QtCore.QTimer.singleShot(80, tik)

    def start_treningu(self, akcja_po):
        self.akcja_po_treningu = akcja_po

        self.ustaw_komunikat("Proszę czekać…", "Trening AI", color="white")
        self.pokaz_guziki(primary_text=None, secondary_text=None)

        def watek():
            self.baza_twarzy.trenuj()
            QtCore.QMetaObject.invokeMethod(
                self,
                "koniec_treningu",
                QtCore.Qt.QueuedConnection,
            )

        threading.Thread(target=watek, daemon=True).start()

    @QtCore.pyqtSlot()
    def koniec_treningu(self):
        akcja = self.akcja_po_treningu
        self.akcja_po_treningu = None

        if akcja == "DETEKCJA_PONOWNA":
            self.tryb_ponowna_detekcja()
        else:
            self.tryb_detekcja()

    def sygnal_bramka_mongo(self, wejscie_ok: bool, promille: float):
        if self.czy_gosc:
            if wejscie_ok:
                GPIO.output(konfig["pin_furtki"], GPIO.HIGH)

                def impuls():
                    time.sleep(konfig["czas_otwarcia"])
                    GPIO.output(konfig["pin_furtki"], GPIO.LOW)

                threading.Thread(target=impuls, daemon=True).start()
            return

        nazwa_prac = self.nazwa_pracownika_biezacego or "<nieznany>"
        id_prac = self.id_pracownika_biezacego or "<none>"
        znacznik_czasu = datetime.now().isoformat()

        if wejscie_ok:
            GPIO.output(konfig["pin_furtki"], GPIO.HIGH)

            def impuls():
                time.sleep(konfig["czas_otwarcia"])
                GPIO.output(konfig["pin_furtki"], GPIO.LOW)

            threading.Thread(target=impuls, daemon=True).start()

            zapiszDoPlikuCsv(
                os.path.join(konfig["folder_logi"], "zdarzenia.csv"),
                ["data_czas", "zdarzenie", "pracownik_nazwa", "pracownik_id"],
                [znacznik_czasu, "otwarcie_bramki", nazwa_prac, id_prac],
            )
        else:
            zapiszDoPlikuCsv(
                os.path.join(konfig["folder_logi"], "zdarzenia.csv"),
                ["data_czas", "zdarzenie", "pracownik_nazwa", "pracownik_id"],
                [znacznik_czasu, "odmowa_dostepu", nazwa_prac, id_prac],
            )

        zapiszDoPlikuCsv(
            os.path.join(konfig["folder_logi"], "pomiary.csv"),
            ["data_czas", "pracownik_nazwa", "pracownik_id", "promile", "pomiar_po_PIN"],
            [
                znacznik_czasu,
                nazwa_prac,
                id_prac,
                f"{promille:.3f}",
                int(self.flaga_pin_zapasowy),
            ],
        )

        pin_prac = None
        try:
            wpis = self.baza_twarzy.emp_by_id.get(self.id_pracownika_biezacego or "")
            if wpis:
                pin_prac = wpis.get("pin")
        except Exception:
            pin_prac = None

        try:
            self.synchronizuj_mongo(
                znacznik_czasu, id_prac, nazwa_prac, pin_prac, promille, wejscie_ok
            )
        except Exception as e:
            print(f"[MongoDebug] Błąd przy uruchamianiu logu do Mongo: {e}")
        if not wejscie_ok:
            migawka = None
            try:
                if self.ostatnia_klatka_detekcji_bgr is not None:
                    migawka = self.ostatnia_klatka_detekcji_bgr.copy()
                elif self.ostatnia_klatka_bgr is not None:
                    migawka = self.ostatnia_klatka_bgr.copy()
            except Exception:
                migawka = None

            try:
                self.synchronizuj_mail(
                    znacznik_czasu, id_prac, nazwa_prac, promille, migawka
                )
            except Exception as e:
                print(f"[EMAIL] Błąd przy uruchamianiu wysyłki maila: {e}")

    def synchronizuj_mongo(
        self, znacznik_czasu, id_prac, nazwa_prac, pin_prac, promille, wejscie_ok: bool
    ):
        if MongoClient is None:
            print("[MongoDebug] Brak biblioteki pymongo – pomijam logowanie do Mongo.")
            return

        mongo_uri = konfig.get("mongo_uri") or ""
        nazwa_bazy = konfig.get("nazwa_bazy_mongo") or "alkotester"

        print(
            f"[MongoDebug] Kolejkuję log do Mongo, uri ustawione={bool(mongo_uri)}, "
            f"baza={nazwa_bazy!r}"
        )

        if not mongo_uri:
            print("[MongoDebug] Brak mongo_uri w konfiguracji – zapis tylko do CSV.")
            return

        def watek():
            global _KLIENT_MONGO
            try:
                print("[MongoDebug] Worker start")

                if _KLIENT_MONGO is None:
                    print("[MongoDebug] Tworzę nowy MongoClient...")
                    _KLIENT_MONGO = MongoClient(
                        mongo_uri,
                        serverSelectionTimeoutMS=5000,
                        connectTimeoutMS=5000,
                        socketTimeoutMS=5000,
                    )
                    _KLIENT_MONGO.admin.command("ping")
                    print("[MongoDebug] Połączenie z Mongo OK")

                baza = _KLIENT_MONGO[nazwa_bazy]
                kolekcja = baza["wejscia"]
                dokument = {
                    "data_czas": znacznik_czasu,
                    "pracownik_id": id_prac,
                    "pracownik_nazwa": nazwa_prac,
                    "pracownik_pin": pin_prac,
                    "promile": float(promille),
                    "wynik": "WEJSCIE_OK" if wejscie_ok else "ODMOWA",
                    "pomiar_po_PIN": bool(self.flaga_pin_zapasowy),
                }
                wynik = kolekcja.insert_one(dokument)
                print(f"[MongoDebug] insert_one OK, _id={wynik.inserted_id}")
            except Exception:
                import traceback

                print("[Mongo] Błąd logowania do Mongo:")
                traceback.print_exc()

        threading.Thread(target=watek, daemon=True).start()

    def synchronizuj_mail(self, ts, id_prac, nazwa_prac, promille, klatka_bgr):
        def watek():
            try:
                self.wyslij_mail_odmowa(ts, id_prac, nazwa_prac, promille, klatka_bgr)
            except Exception as e:
                print(f"[EMAIL] Błąd wysyłki maila: {e}")

        threading.Thread(target=watek, daemon=True).start()

    def wyslij_mail_odmowa(self, ts, id_prac, nazwa_prac, promille, klatka_bgr):
        smtp_host = konfig.get("smtp_host")
        if not smtp_host:
            print("[EMAIL] Brak smtp_host w config - pomijam wysyłkę maila.")
            return

        smtp_port = int(konfig.get("smtp_port", 587))
        smtp_user = konfig.get("smtp_user") or ""
        smtp_password = konfig.get("smtp_password") or ""
        smtp_use_tls = bool(konfig.get("uzywaj_tls", True))
        from_addr = konfig.get("smtp_from") or smtp_user or "alkotester@localhost"
        to_addr = konfig.get("mail_alertowy")

        if not to_addr:
            print("[EMAIL] Brak mail_alertowy w config - pomijam wysyłkę maila.")
            return

        pdf_path = self.generuj_raport(ts, id_prac, nazwa_prac, promille, klatka_bgr)
        if pdf_path is None:
            print("[EMAIL] Nie udało się wygenerować PDF - nie wysyłam maila.")
            return

        temat = f"Odmowa wejścia - {nazwa_prac} ({promille:.3f} ‰)"
        tresc = (
            "System Alkotester - odmowa wejścia na obiekt.\n\n"
            f"Data i czas: {ts}\n"
            f"Pracownik: {nazwa_prac} (ID: {id_prac})\n"
            f"Wynik pomiaru: {promille:.3f} [‰]\n"
        )

        wiadomosc = MIMEMultipart()
        wiadomosc["Subject"] = temat
        wiadomosc["From"] = from_addr
        wiadomosc["To"] = to_addr
        wiadomosc.attach(MIMEText(tresc, "plain", "utf-8"))

        try:
            with open(pdf_path, "rb") as f:
                zal = MIMEBase("application", "pdf")
                zal.set_payload(f.read())
            encoders.encode_base64(zal)
            zal.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(pdf_path)}"',
            )
            wiadomosc.attach(zal)
        except Exception as e:
            print(f"[EMAIL] Nie udało się dołączyć PDF-a: {e}")
            return

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as serwer:
                if smtp_use_tls:
                    serwer.starttls()
                if smtp_user and smtp_password:
                    serwer.login(smtp_user, smtp_password)
                serwer.send_message(wiadomosc)
            print(f"[EMAIL] Wysłano mail o odmowie na {to_addr} z PDF-em {pdf_path}")
        except Exception as e:
            print(f"[EMAIL] Błąd SMTP: {e}")

    def generuj_raport(self, ts, id_prac, nazwa_prac, promille, klatka_bgr):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            print(
                "[PDF] Brak biblioteki reportlab (pip install reportlab) - pomijam PDF."
            )
            return None

        nazwa_czcionki = "DejaVuSans"
        sciezka_czcionki = konfig.get(
            "czcionka", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        try:
            pdfmetrics.registerFont(TTFont(nazwa_czcionki, sciezka_czcionki))
        except Exception as e:
            print(
                f"[PDF] Nie udało się zarejestrować fontu '{sciezka_czcionki}': {e}"
            )
            nazwa_czcionki = "Helvetica"

        katalog_raporty = konfig.get("folder_raporty") or konfig.get("folder_logi") or "logi"
        try:
            os.makedirs(katalog_raporty, exist_ok=True)
        except Exception as e:
            print(f"[PDF] Nie mogę utworzyć katalogu na raporty: {e}")
            return None

        ts_bez = ts.replace(":", "-").replace(" ", "_")
        nazwa_pliku = f"odmowa_{ts_bez}_{id_prac or 'unknown'}.pdf"
        sciezka_pdf = os.path.join(katalog_raporty, nazwa_pliku)

        try:
            c = canvas.Canvas(sciezka_pdf, pagesize=A4)
            szerokosc, wysokosc = A4
            tekst = c.beginText(40, wysokosc - 40)
            tekst.setFont(nazwa_czcionki, 14)
            tekst.textLine("Odmowa wejścia na obiekt - raport")
            tekst.moveCursor(0, 20)
            tekst.setFont(nazwa_czcionki, 11)
            tekst.textLine(f"Data i czas: {ts}")
            tekst.textLine(f"Pracownik: {nazwa_prac} (ID: {id_prac})")
            tekst.textLine(f"Wynik pomiaru: {promille:.3f} [‰]")
            c.drawText(tekst)

            if klatka_bgr is not None:
                try:
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

                        c.drawImage(
                            obraz,
                            x,
                            y,
                            width=rys_w,
                            height=rys_h,
                            preserveAspectRatio=True,
                            mask=None,
                        )
                except Exception as e:
                    print(f"[PDF] Błąd osadzania zdjęcia w PDF: {e}")

            c.showPage()
            c.save()
            print(f"[PDF] Zapisano raport odmowy do {sciezka_pdf}")
            return sciezka_pdf
        except Exception as e:
            print(f"[PDF] Błąd generowania PDF: {e}")
            return None

    def dioda_led(self, wejscie_ok: bool):
        try:
            pin = (
                konfig["pin_led_zielony"]
                if wejscie_ok
                else konfig["pin_led_czerwony"]
            )
            czas_impulsu = float(konfig.get("czas_swiecenia", 2.0))
            GPIO.output(pin, GPIO.HIGH)

            def watek():
                try:
                    time.sleep(czas_impulsu)
                finally:
                    GPIO.output(pin, GPIO.LOW)

            threading.Thread(target=watek, daemon=True).start()
        except Exception as e:
            print(f"[LED] Błąd sterowania diodą: {e}")

    def odczytaj_odleglosc(self) -> float:
        try:
            raw = self.adc.czytaj(self.kanal_odleglosc)
            napiecie = (raw / 1023.0) * 3.3
            if napiecie - 0.42 <= 0:
                return float("inf")
            odleglosc = 27.86 / (napiecie - 0.42)
            if odleglosc < 0 or odleglosc > 80:
                return float("inf")
            return odleglosc
        except Exception:
            return float("inf")

    def odczytaj_mikrofon(self, samples: int = 32):
        try:
            n = max(1, int(samples))
            wartosci = [self.adc.czytaj(self.kanal_mikrofon) for _ in range(n)]
            min_v = min(wartosci)
            max_v = max(wartosci)
            avg = int(sum(wartosci) / len(wartosci))
            amp = max_v - min_v
            return amp, avg
        except Exception as e:
            print(f"[MIKROFON] błąd odczytu: {e}")
            return 0, 0

    def klik_gosc(self):
        self.czy_gosc = True
        self.id_pracownika_biezacego = "<gosc>"
        self.nazwa_pracownika_biezacego = "Gość"
        self.flaga_pin_zapasowy = True
        self.tryb_rozpoznany()

    def cykl_kamery(self):
        klatka_bgr = self.kamera.wez_klatke()
        if klatka_bgr is None:
            return

        self.ostatnia_klatka_bgr = klatka_bgr

        obraz_do_wysw = klatka_bgr.copy()

        if self.ostatni_obrys_twarzy is not None:
            (x, y, w, h) = self.ostatni_obrys_twarzy
            x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)

            if self.ostatnia_pewnosc >= konfig["pewnosc_dobra"]:
                kolor = (0, 255, 0)
            elif self.ostatnia_pewnosc <= konfig["pewnosc_slaba"]:
                kolor = (0, 255, 255)
            else:
                kolor = (255, 255, 0)

            cv2.rectangle(obraz_do_wysw, (x1, y1), (x2, y2), kolor, 2)
            napis = f"{self.ostatnia_pewnosc:.0f}%"
            cv2.putText(
                obraz_do_wysw,
                napis,
                (x2 - 10, y2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                kolor,
                2,
                cv2.LINE_AA,
            )

        obraz_rgb = cv2.cvtColor(obraz_do_wysw, cv2.COLOR_BGR2RGB)

        cel_szer = self.widok.width()
        cel_wys = self.widok.height()
        dopasowany = self.kadr_zoom_przyciecie(obraz_rgb, cel_szer, cel_wys)
        if dopasowany is None:
            return

        h, w, _ = dopasowany.shape
        qimg = QtGui.QImage(
            dopasowany.data, w, h, 3 * w, QtGui.QImage.Format_RGB888
        )
        self.widok.setPixmap(QtGui.QPixmap.fromImage(qimg))

    def cykl_twarzy(self):
        if self.ostatnia_klatka_bgr is None:
            return

        id_prac, nazwa_prac, pewnosc, obrys = self.baza_twarzy.rozpoznaj(
            self.ostatnia_klatka_bgr
        )

        self.ostatni_obrys_twarzy = obrys
        self.ostatnia_pewnosc = pewnosc or 0.0
        if obrys is not None and self.stan in (
            "DETEKCJA",
            "DETEKCJA_PONOWNA",
            "OCZEKIWANIE_POMIAR",
        ):
            try:
                self.ostatnia_klatka_detekcji_bgr = self.ostatnia_klatka_bgr.copy()
            except Exception:
                pass

        if self.stan == "BEZCZYNNOSC":
            if obrys is not None:
                self.tryb_detekcja()
            return

        if self.stan == "DETEKCJA":
            if obrys is None:
                self.licznik_nieudanych_detekcji = 0
                self.stabilne_id_pracownika = None
                self.licznik_stabilnych_probek = 0
                self.ustaw_komunikat(aktualnyCzas(), "Szukam twarzy…", color="white")
                return

            cel_id = id_prac if id_prac else None
            if cel_id is not None:
                if self.stabilne_id_pracownika == cel_id:
                    self.licznik_stabilnych_probek += 1
                else:
                    self.stabilne_id_pracownika = cel_id
                    self.licznik_stabilnych_probek = 1
            else:
                self.stabilne_id_pracownika = None
                self.licznik_stabilnych_probek = 0

            if (
                nazwa_prac
                and pewnosc >= konfig["pewnosc_dobra"]
                and self.stabilne_id_pracownika == id_prac
                and self.licznik_stabilnych_probek >= konfig["ile_ok_podrzad"]
            ):
                self.id_pracownika_biezacego = id_prac
                self.nazwa_pracownika_biezacego = nazwa_prac
                self.flaga_pin_zapasowy = False

                self.doucz_twarz(id_prac)

                self.tryb_rozpoznany()
                return

            self.licznik_nieudanych_detekcji += 1
            if self.licznik_nieudanych_detekcji >= konfig["limit_prob_detekcji"]:
                self.tryb_wpisywania_pinu()
                return

            if pewnosc <= konfig["pewnosc_slaba"]:
                self.ustaw_komunikat(aktualnyCzas(), "Nie rozpoznaję…", color="white")
            else:
                self.ustaw_komunikat(aktualnyCzas(), f"pewność: {pewnosc:.0f}%", color="white")
            return

        if self.stan == "DETEKCJA_PONOWNA":
            self.licznik_prob_ponownej_detekcji += 1
            if (
                id_prac == self.id_pracownika_biezacego
                and pewnosc >= konfig["pewnosc_dobra"]
            ):
                self.flaga_pin_zapasowy = False
                self.doucz_twarz(id_prac)
                self.tryb_rozpoznany()
                return

            if self.licznik_prob_ponownej_detekcji >= konfig["limit_powtorzen_detekcji"]:
                self.flaga_pin_zapasowy = True
                self.tryb_rozpoznany()
                return

            txt_conf = f"{pewnosc:.0f}%" if pewnosc is not None else ""
            self.ustaw_komunikat(
                "Sprawdzam twarz…",
                f"{self.nazwa_pracownika_biezacego or ''} {txt_conf}",
                color="white",
            )
            return

        if self.stan == "OCZEKIWANIE_POMIAR":
            if self.ostatni_obrys_twarzy is not None:
                self.kalibracja_widoczna_twarz = True
                (_, _, w, h) = self.ostatni_obrys_twarzy
                if max(w, h) >= konfig["min_rozmiar_twarzy"]:
                    self.kalibracja_dobra_twarz = True
            return

        return

    def cykl_interfejsu(self):
        if self.stan in ("BEZCZYNNOSC", "DETEKCJA"):
            self.etykieta_gora.setText(aktualnyCzas())
            self.etykieta_gora.setStyleSheet(
                "color:white; font-size:28px; font-weight:600;"
            )


    def stan_kalibracja_mq3(self):
        def watek():
            self.mq3.kalibruj()
            QtCore.QMetaObject.invokeMethod(
                self,
                "po_kalibracji",
                QtCore.Qt.QueuedConnection,
            )

        threading.Thread(target=watek, daemon=True).start()

    @QtCore.pyqtSlot()
    def po_kalibracji(self):
        self.bezczynnosc()

    def zamknij_aplikacje(self, e: QtGui.QCloseEvent):
        for t in [
            getattr(self, "timer_pomiaru", None),
            getattr(self, "timer_kalibracji", None),
            getattr(self, "timer_rozpoznany", None),
            getattr(self, "timer_twarzy", None),
            getattr(self, "timer_interfejsu", None),
            getattr(self, "timer_kamery", None),
            getattr(self, "timer_sync", None),
        ]:
            try:
                if t and t.isActive():
                    t.stop()
            except Exception:
                pass

        try:
            self.kamera.stop()
        except Exception:
            pass

        try:
            self.adc.zamknij()
        except Exception:
            pass

        try:
            GPIO.cleanup()
        except Exception:
            pass

        for okno in QtWidgets.QApplication.topLevelWidgets():
            if okno is not self:
                try:
                    okno.close()
                except Exception:
                    pass

        return super().closeEvent(e)

    def closeEvent(self, e: QtGui.QCloseEvent):
        return self.zamknij_aplikacje(e)


def konfiguruj_qt():
    os.environ.setdefault("DISPLAY", ":0")
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")


def uruchom():
    konfiguruj_qt()

    app = QtWidgets.QApplication(sys.argv)
    okno = GlowneOkno()

    if konfig["czy_pelny_ekran"]:
        okno.showFullScreen()
    else:
        okno.resize(konfig["szerokosc_ekranu"], konfig["wysokosc_ekranu"])
        okno.show()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    sys.exit(app.exec_())


if __name__ == "__main__":
    uruchom()
