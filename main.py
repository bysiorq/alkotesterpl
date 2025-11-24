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
from komponenty import sprzet, pomiary, wydarzenia, gui_helpery, trening, stany, inicjalizacja
from komponenty.baza_danych import loguj_do_mongo
from komponenty.poczta import synchronizuj_mail
from komponenty.raporty import generuj_raport_pdf
from komponenty.synchronizacja import synchronizuj_pracownikow





class GlowneOkno(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        inicjalizacja.zainicjalizuj_aplikacje(self)
        
        # Connect signals that might need local methods or were not connected in init
        self.guzik_gosc.clicked.connect(self.klik_gosc)
        self.timer_twarzy.timeout.connect(self.cykl_twarzy)
        self.timer_interfejsu.timeout.connect(self.cykl_interfejsu)
        self.timer_rozpoznany.timeout.connect(self.cykl_rozpoznany)
        self.timer_pomiaru.timeout.connect(self.pomiar)
        self.timer_sync.timeout.connect(self.cykl_synchronizacji)

        self.ustaw_komunikat(
            "Proszę czekać…",
            "Kalibracja czujnika MQ-3 w toku",
            color="white",
        )
        self.pokaz_guziki(primary_text=None, secondary_text=None)

        self.stan_kalibracjamq3()

        self.stan_kalibracjamq3()


    def kadr_zoom_przyciecie(self, img, target_w, target_h):
        return gui_helpery.kadr_zoom_przyciecie(img, target_w, target_h)

    def doucz_twarz(self, id_prac: str):
        trening.doucz_twarz_logika(
            self.baza_twarzy, 
            id_prac, 
            self.ostatni_obrys_twarzy,
            self.ostatnia_klatka_bgr,
            lambda img: trening.jakosc_twarzy(img, konfig)
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
        stany.bezczynnosc(self)

    def tryb_detekcja(self):
        stany.tryb_detekcja(self)

    def tryb_wpisywania_pinu(self):
        stany.tryb_wpisywania_pinu(self)

    def tryb_ponowna_detekcja(self):
        stany.tryb_ponowna_detekcja(self)

    def tryb_rozpoznany(self):
        stany.tryb_rozpoznany(self)

    def tryb_pomiaru(self):
        stany.tryb_pomiaru(self)

    @QtCore.pyqtSlot()
    def koniec_pomiaru(self):
        stany.koniec_pomiaru(self)

    def werdykt(self, promille):
        stany.werdykt(self, promille)

    def cykl_rozpoznany(self):
        stany.cykl_rozpoznany(self)

    def pomiar(self):
        stany.pomiar(self)

    def klik_guzik1(self):
        stany.obsluz_guzik1(self)

    def klik_guzik2(self):
        stany.obsluz_guzik2(self)

    def zbieranie_probek_pracownika(self):
        stany.zbieranie_probek_pracownika(self)

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

    def odczytaj_mikrofon(self, samples):
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


    def stan_kalibracjamq3(self):
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
