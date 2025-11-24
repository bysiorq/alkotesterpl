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

from PyQt5 import QtCore, QtGui, QtWidgets

from konfiguracja import konfig
from fs_pomoc import sprawdzKatalogi, aktualnyCzas, zapiszDoPlikuCsv
from czujnikspi import Mcp3008, CzujnikMQ3
from baza_twarzy import BazaTwarzy
from kamera import Kamera
from oknoPin import OknoPin

# Komponenty
from komponenty import sprzet, pomiary, wydarzenia, gui_helpery, trening, stany
from komponenty.baza_danych import loguj_do_mongo
from komponenty.poczta import synchronizuj_mail
from komponenty.raporty import generuj_raport_pdf
from komponenty.synchronizacja import synchronizuj_pracownikow


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

        # Inicjalizacja sprzętu (GPIO, diody, bramka)
        sprzet.inicjalizuj_gpio()

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
            synchronizuj_pracownikow(self.baza_twarzy)
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
        return gui_helpery.kadr_zoom_przyciecie(img, target_w, target_h)

    def doucz_twarz(self, id_prac: str):
        trening.doucz_twarz_logika(
            self.baza_twarzy, 
            id_prac, 
            self.ostatni_obrys_twarzy,
            self.ostatnia_klatka_bgr,
            jakosc_twarzy
        )

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
        gui_helpery.ustaw_komunikat(self, tekst_gora, tekst_srodek, color, use_center)

    def pokaz_guziki(self, primary_text=None, secondary_text=None):
        gui_helpery.pokaz_guziki(self, primary_text, secondary_text)


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
        trening.uruchom_trening_async(self.baza_twarzy, self, "koniec_treningu")

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
            wydarzenia.zapisz_zdarzenie_gosc(wejscie_ok)
            return
        
        migawka = None
        if not wejscie_ok:
            try:
                if self.ostatnia_klatka_detekcji_bgr is not None:
                    migawka = self.ostatnia_klatka_detekcji_bgr.copy()
                elif self.ostatnia_klatka_bgr is not None:
                    migawka = self.ostatnia_klatka_bgr.copy()
            except Exception:
                pass
        
        wydarzenia.zapisz_zdarzenie(
            wejscie_ok,
            self.nazwa_pracownika_biezacego or "<nieznany>",
            self.id_pracownika_biezacego or "<none>",
            promille,
            self.flaga_pin_zapasowy,
            self.baza_twarzy,
            migawka
        )



    def odczytaj_odleglosc(self) -> float:
        return pomiary.odczytaj_odleglosc(self.adc, self.kanal_odleglosc)

    def odczytaj_mikrofon(self, samples: int = 32):
        return pomiary.odczytaj_mikrofon(self.adc, self.kanal_mikrofon, samples)

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
