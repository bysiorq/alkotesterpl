import time
import threading
import cv2
from PyQt5 import QtCore, QtWidgets

from konfiguracja import konfig
from fs_pomoc import aktualnyCzas
from oknoPin import OknoPin
from komponenty import gui_helpery, wydarzenia, trening, sprzet
from komponenty.synchronizacja import synchronizuj_pracownikow

# Stany aplikacji - stałe
BEZCZYNNOSC = "BEZCZYNNOSC"
DETEKCJA = "DETEKCJA"
DETEKCJA_PONOWNA = "DETEKCJA_PONOWNA"
OCZEKIWANIE_POMIAR = "OCZEKIWANIE_POMIAR"
POMIAR = "POMIAR"
PONOW_POMIAR = "PONOW_POMIAR"
PIN_NIEUDANY_WYBOR = "PIN_NIEUDANY_WYBOR"
PIN_WPROWADZANIE = "PIN_WPROWADZANIE"
KALIBRACJA_MQ3 = "KALIBRACJA_MQ3"
DECYZJA_OK = "DECYZJA_OK"
DECYZJA_ODMOWA = "DECYZJA_ODMOWA"


def bezczynnosc(okno):
    okno.stan = BEZCZYNNOSC
    okno.id_pracownika_biezacego = None
    okno.nazwa_pracownika_biezacego = None
    okno.flaga_pin_zapasowy = False
    okno.czy_gosc = False

    okno.ostatni_obrys_twarzy = None
    okno.ostatnia_pewnosc = 0.0
    okno.licznik_nieudanych_detekcji = 0
    okno.licznik_prob_ponownej_detekcji = 0
    okno.stabilne_id_pracownika = None
    okno.licznik_stabilnych_probek = 0

    okno.kalibracja_dobra_twarz = False
    okno.kalibracja_widoczna_twarz = False

    okno.lista_probek_pomiarowych = []
    okno.czas_dmuchania = 0.0
    okno.licznik_ponownych_pomiarow = 0

    okno.pasek_postepu.hide()

    okno.timer_interfejsu.start(250)
    okno.timer_twarzy.start(konfig["co_ile_detekcja"])
    okno.zatrzymaj_timer(okno.timer_rozpoznany)
    okno.zatrzymaj_timer(okno.timer_pomiaru)

    okno.ustaw_komunikat(aktualnyCzas(), "Podejdź bliżej", color="white")
    okno.pokaz_guziki(primary_text=None, secondary_text="Wprowadź PIN")

    if hasattr(okno, "stos_srodek"):
        okno.stos_srodek.setCurrentWidget(okno.etykieta_srodek)


def tryb_detekcja(okno):
    okno.stan = DETEKCJA
    okno.licznik_nieudanych_detekcji = 0
    okno.stabilne_id_pracownika = None
    okno.licznik_stabilnych_probek = 0

    okno.timer_interfejsu.start(250)
    okno.timer_twarzy.start(konfig["co_ile_detekcja"])
    okno.zatrzymaj_timer(okno.timer_rozpoznany)
    okno.zatrzymaj_timer(okno.timer_pomiaru)

    okno.ustaw_komunikat(aktualnyCzas(), "Szukam twarzy…", color="white")
    okno.pokaz_guziki(primary_text=None, secondary_text="Wprowadź PIN")


def tryb_wpisywania_pinu(okno):
    okno.stan = PIN_WPROWADZANIE
    okno.zatrzymaj_timer(okno.timer_twarzy)
    okno.zatrzymaj_timer(okno.timer_interfejsu)
    okno.zatrzymaj_timer(okno.timer_rozpoznany)
    okno.zatrzymaj_timer(okno.timer_pomiaru)
    try:
        print("[SYNC] Ręczny sync przed wprowadzeniem PIN-u...")
        synchronizuj_pracownikow(okno.baza_twarzy)
    except Exception as e:
        print(f"[SYNC] Błąd sync przy wprowadzaniu PIN: {e}")

    dlg = OknoPin(okno, title="Wprowadź PIN")
    if dlg.exec_() == QtWidgets.QDialog.Accepted:
        pin = dlg.wezPin()
        try:
            okno.baza_twarzy.wczytajPracownikow()
        except Exception:
            pass
        wpis = okno.baza_twarzy.emp_by_pin.get(pin)
        if not wpis:
            okno.ustaw_komunikat("Zły PIN - brak danych", "", color="red")
            okno.pokaz_guziki(primary_text=None, secondary_text=None)
            QtCore.QTimer.singleShot(2000, lambda: bezczynnosc(okno))
            return

        okno.id_pracownika_biezacego = wpis.get("id")
        okno.nazwa_pracownika_biezacego = wpis.get("imie")
        okno.flaga_pin_zapasowy = False

        zbieranie_probek_pracownika(okno)
    else:
        bezczynnosc(okno)


def tryb_ponowna_detekcja(okno):
    okno.stan = DETEKCJA_PONOWNA
    okno.licznik_prob_ponownej_detekcji = 0

    okno.timer_twarzy.start(konfig["co_ile_detekcja"])
    okno.zatrzymaj_timer(okno.timer_interfejsu)
    okno.zatrzymaj_timer(okno.timer_rozpoznany)
    okno.zatrzymaj_timer(okno.timer_pomiaru)

    okno.ustaw_komunikat(
        "Sprawdzam twarz…", okno.nazwa_pracownika_biezacego or "", color="white"
    )
    okno.pokaz_guziki(primary_text=None, secondary_text=None)


def tryb_rozpoznany(okno):
    okno.stan = OCZEKIWANIE_POMIAR

    okno.kalibracja_dobra_twarz = False
    okno.kalibracja_widoczna_twarz = False

    okno.timer_twarzy.start(konfig["co_ile_detekcja"])

    okno.zatrzymaj_timer(okno.timer_interfejsu)
    okno.zatrzymaj_timer(okno.timer_pomiaru)
    okno.zatrzymaj_timer(okno.timer_rozpoznany)

    okno.timer_rozpoznany.start(200)

    imie = okno.nazwa_pracownika_biezacego or ""
    odleglosc_cm = okno.odczytaj_odleglosc()
    if odleglosc_cm == float("inf"):
        tekst_odleglosc = "brak odczytu"
    elif odleglosc_cm > 80:
        tekst_odleglosc = ">80 cm"
    else:
        tekst_odleglosc = f"{odleglosc_cm:0.0f} cm"

    tekst_gora = "Podejdź bliżej"
    tekst_srodek = f"Cześć {imie}\nOdległość: {tekst_odleglosc}"
    okno.ustaw_komunikat(tekst_gora, tekst_srodek, color="white")
    okno.pokaz_guziki(primary_text=None, secondary_text=None)


def tryb_pomiaru(okno):
    okno.stan = POMIAR
    okno.lista_probek_pomiarowych = []
    okno.czas_dmuchania = 0.0

    okno.ostatni_obrys_twarzy = None
    okno.ostatnia_pewnosc = 0.0

    okno.zatrzymaj_timer(okno.timer_twarzy)
    okno.zatrzymaj_timer(okno.timer_interfejsu)
    okno.zatrzymaj_timer(okno.timer_rozpoznany)

    okno.pasek_postepu.setValue(0)
    okno.pasek_postepu.show()
    if hasattr(okno, "stos_srodek"):
        okno.stos_srodek.setCurrentWidget(okno.kontener_postepu)

    okno.timer_pomiaru.start(100)

    okno.ustaw_komunikat("Przeprowadzam pomiar…", "", color="white", use_center=False)
    okno.pokaz_guziki(primary_text=None, secondary_text=None)


def koniec_pomiaru(okno):
    promille = getattr(okno, "_oczekujace_promile", 0.0)
    werdykt(okno, promille)


def werdykt(okno, promille):
    okno.pasek_postepu.hide()
    if hasattr(okno, "stos_srodek"):
        okno.stos_srodek.setCurrentWidget(okno.etykieta_srodek)
        okno.etykieta_srodek.setWordWrap(True)

    okno.ostatni_wynik_promile = float(promille)

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
        f"[DECYZJA] promille={okno.ostatni_wynik_promile:.3f}, "
        f"OK <= {prog_ok:.3f}, odmowa >= {prog_odmowa:.3f}"
    )

    tekst_pomiar = f"Pomiar: {okno.ostatni_wynik_promile:.3f} [‰]"

    okno.zatrzymaj_timer(okno.timer_twarzy)
    okno.zatrzymaj_timer(okno.timer_interfejsu)
    okno.zatrzymaj_timer(okno.timer_rozpoznany)
    okno.zatrzymaj_timer(okno.timer_pomiaru)

    wynik_ok = False
    trzeba_powtorzyc = False

    if okno.ostatni_wynik_promile <= prog_ok:
        wynik_ok = True
    elif okno.ostatni_wynik_promile < prog_odmowa:
        if okno.licznik_ponownych_pomiarow >= 1:
            trzeba_powtorzyc = False
            wynik_ok = False
        else:
            trzeba_powtorzyc = True
    else:
        wynik_ok = False

    if wynik_ok and not trzeba_powtorzyc:
        okno.stan = DECYZJA_OK
        okno.ustaw_komunikat(tekst_pomiar, "Przejście otwarte", color="green")
        okno.pokaz_guziki(primary_text=None, secondary_text=None)
        okno.sygnal_bramka_mongo(True, okno.ostatni_wynik_promile)
        sprzet.dioda_led(True)
        QtCore.QTimer.singleShot(2500, lambda: bezczynnosc(okno))
        return

    if trzeba_powtorzyc:
        okno.stan = PONOW_POMIAR
        okno.ustaw_komunikat(
            tekst_pomiar,
            "Ponów pomiar",
            color="red",
        )
        okno.pokaz_guziki(
            primary_text="Ponów pomiar", secondary_text="Odmowa"
        )
        return

    okno.stan = DECYZJA_ODMOWA
    okno.ustaw_komunikat(tekst_pomiar, "Odmowa", color="red")
    okno.pokaz_guziki(primary_text=None, secondary_text=None)
    okno.sygnal_bramka_mongo(False, okno.ostatni_wynik_promile)
    sprzet.dioda_led(False)
    QtCore.QTimer.singleShot(3000, lambda: bezczynnosc(okno))


def cykl_rozpoznany(okno):
    if okno.stan != OCZEKIWANIE_POMIAR:
        okno.zatrzymaj_timer(okno.timer_rozpoznany)
        return

    odleglosc_cm = okno.odczytaj_odleglosc()
    imie = okno.nazwa_pracownika_biezacego or ""
    if odleglosc_cm > 70:
        tekst_odleglosc = ">1m"
    else:
        tekst_odleglosc = f"{odleglosc_cm:0.0f} cm"

    if okno.odleglosc_min_cm <= odleglosc_cm <= okno.odleglosc_max_cm:
        if okno.kalibracja_dobra_twarz or okno.flaga_pin_zapasowy:
            okno.zatrzymaj_timer(okno.timer_rozpoznany)
            tekst_gora = "Nie ruszaj się - start pomiaru"
            tekst_srodek = f"Cześć {imie}\nOdległość: {tekst_odleglosc}"
            okno.ustaw_komunikat(tekst_gora, tekst_srodek, color="white")
            tryb_pomiaru(okno)
            return
        else:
            okno.ustaw_komunikat(
                "Stań przodem do kamery",
                f"Cześć {imie}\nOdległość: {tekst_odleglosc}",
                color="white",
            )
            return

    okno.ustaw_komunikat(
        "Podejdź bliżej",
        f"Cześć {imie}\nOdległość: {tekst_odleglosc}",
        color="white",
    )


def pomiar(okno):
    if okno.stan != POMIAR:
        okno.zatrzymaj_timer(okno.timer_pomiaru)
        return

    try:
        dt = okno.timer_pomiaru.interval() / 1000.0
    except Exception:
        dt = 0.1

    odleglosc_cm = okno.odczytaj_odleglosc()
    amp, _ = okno.odczytaj_mikrofon(
        samples=konfig.get("probki_mikrofonu")
    )

    dmuchanie_wykryte = (
        okno.odleglosc_min_cm <= odleglosc_cm <= okno.odleglosc_max_cm
        and amp >= okno.prog_mikrofonu
    )

    if dmuchanie_wykryte:
        okno.czas_dmuchania += dt
        try:
            okno.lista_probek_pomiarowych.append(okno.mq3.pobierz())
        except Exception:
            pass

    postep = max(
        0.0, min(okno.czas_dmuchania / konfig["czas_dmuchania"], 1.0)
    )
    okno.pasek_postepu.setValue(int(postep * 100))
    okno.pasek_postepu.show()

    if hasattr(okno, "stos_srodek"):
        okno.stos_srodek.setCurrentWidget(okno.kontener_postepu)

    if dmuchanie_wykryte:
        okno.ustaw_komunikat(
            "Przeprowadzam pomiar…", "", color="white", use_center=False
        )
    else:
        if not (
            okno.odleglosc_min_cm <= odleglosc_cm <= okno.odleglosc_max_cm
        ):
            okno.ustaw_komunikat(
                "Podejdź bliżej", "", color="white", use_center=False
            )
        else:
            okno.ustaw_komunikat("Dmuchaj", "", color="white", use_center=False)

    if okno.czas_dmuchania >= konfig["czas_dmuchania"]:
        okno.zatrzymaj_timer(okno.timer_pomiaru)
        probki = list(okno.lista_probek_pomiarowych)

        def watek():
            try:
                promille = float(okno.mq3.promile(probki))
            except Exception as e:
                print(f"[POMIAR] błąd liczenia promili: {e}")
                promille = 0.0
            okno._oczekujace_promile = promille
            QtCore.QMetaObject.invokeMethod(
                okno,
                "koniec_pomiaru",
                QtCore.Qt.QueuedConnection,
            )

        threading.Thread(target=watek, daemon=True).start()


def obsluz_guzik1(okno):
    if okno.stan == PONOW_POMIAR:
        if okno.licznik_ponownych_pomiarow >= 1:
            return
        okno.licznik_ponownych_pomiarow += 1
        tryb_pomiaru(okno)

    elif okno.stan == PIN_NIEUDANY_WYBOR:
        okno.flaga_pin_zapasowy = True
        tryb_rozpoznany(okno)


def obsluz_guzik2(okno):
    if okno.stan == PONOW_POMIAR:
        okno.ustaw_komunikat("Odmowa", "", color="red")
        okno.sygnal_bramka_mongo(False, okno.ostatni_wynik_promile)
        sprzet.dioda_led(False)
        okno.pokaz_guziki(primary_text=None, secondary_text=None)
        QtCore.QTimer.singleShot(2000, lambda: bezczynnosc(okno))
        return

    if okno.stan == PIN_NIEUDANY_WYBOR:
        bezczynnosc(okno)
        return

    if okno.stan in (BEZCZYNNOSC, DETEKCJA):
        tryb_wpisywania_pinu(okno)


def zbieranie_probek_pracownika(okno):
    id_prac = okno.id_pracownika_biezacego
    if not id_prac:
        bezczynnosc(okno)
        return

    ile_potrzeba = konfig["ile_fotek_trening"]
    timeout_s = konfig["czas_na_trening"]
    deadline = time.time() + timeout_s

    okno.ustaw_komunikat(
        "Przytrzymaj twarz w obwódce",
        f"Zbieram próbki 0/{ile_potrzeba}",
        color="white",
    )
    okno.pokaz_guziki(primary_text=None, secondary_text=None)

    zapisane = 0
    lista_obrazow = []

    def tik():
        nonlocal zapisane, lista_obrazow, deadline

        if time.time() > deadline:
            okno.ostatni_obrys_twarzy = None
            okno.stan = PIN_NIEUDANY_WYBOR
            okno.ustaw_komunikat(
                "Nie udało się zebrać próbek",
                "Przejście na podstawie PIN?",
                color="red",
            )
            okno.pokaz_guziki(
                primary_text="Przejdź do pomiaru",
                secondary_text="Anuluj",
            )
            return

        if okno.ostatnia_klatka_bgr is None:
            QtCore.QTimer.singleShot(80, tik)
            return

        klatka = okno.ostatnia_klatka_bgr
        szary = cv2.cvtColor(klatka, cv2.COLOR_BGR2GRAY)

        twarze = okno.baza_twarzy.detekcja(klatka)
        if not twarze:
            okno.ostatni_obrys_twarzy = None
            okno.ustaw_komunikat(
                "Przytrzymaj twarz w obwódce",
                f"Zbieram próbki {zapisane}/{ile_potrzeba}",
                color="white",
            )
            QtCore.QTimer.singleShot(80, tik)
            return

        (x, y, w, h) = max(twarze, key=lambda r: r[2] * r[3])
        okno.ostatni_obrys_twarzy = (x, y, w, h)
        okno.ostatnia_pewnosc = 100.0

        h_img, w_img = szary.shape[:2]
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(int(x + w), w_img)
        y2 = min(int(y + h), h_img)

        if x2 <= x1 or y2 <= y1:
            okno.ustaw_komunikat(
                "Przytrzymaj twarz w obwódce",
                f"Zbieram próbki {zapisane}/{ile_potrzeba}",
                color="white",
            )
            QtCore.QTimer.singleShot(80, tik)
            return

        if max(x2 - x1, y2 - y1) < konfig["min_rozmiar_twarzy"]:
            okno.ustaw_komunikat(
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

        # Import jakosc_twarzy z trening.py
        ok, ostrosc, jasnosc = trening.jakosc_twarzy(roi_gray_resized, konfig)
        if not ok:
            okno.ustaw_komunikat(
                "Stań prosto, popraw światło",
                f"ostrość {ostrosc:0.0f}, jasność {jasnosc:0.0f}  [{zapisane}/{ile_potrzeba}]",
                color="white",
            )
            QtCore.QTimer.singleShot(80, tik)
            return

        twarz_bgr = klatka[y1:y2, x1:x2].copy()
        twarz_bgr = cv2.resize(twarz_bgr, (240, 240), interpolation=cv2.INTER_LINEAR)
        lista_obrazow.append(twarz_bgr)
        zapisane += 1

        okno.ustaw_komunikat(
            "Próbka zapisana",
            f"Zbieram próbki {zapisane}/{ile_potrzeba}",
            color="green",
        )

        if zapisane >= ile_potrzeba:
            okno.baza_twarzy.zbierzProbki(id_prac, lista_obrazow)
            okno.start_treningu("DETEKCJA_PONOWNA")
            return

        QtCore.QTimer.singleShot(120, tik)

    QtCore.QTimer.singleShot(80, tik)

