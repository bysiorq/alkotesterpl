import os
from datetime import datetime
from komponenty import sprzet
from komponenty.baza_danych import loguj_do_mongo
from komponenty.poczta import synchronizuj_mail
from fs_pomoc import zapiszDoPlikuCsv
from konfiguracja import konfig


def zapisz_zdarzenie(wejscie_ok, nazwa_prac, id_prac, promille, flaga_pin_zapasowy, baza_twarzy, migawka_bgr=None):
    """
    Główna funkcja obsługi zdarzeń: otwiera bramkę, loguje do CSV/Mongo, wysyła email przy odmowie.
    """
    znacznik_czas = datetime.now().isoformat()
    
    # Otwórz bramkę jeśli wejście OK
    if wejscie_ok:
        sprzet.otworz_bramke()
        zapiszDoPlikuCsv(
            os.path.join(konfig["folder_logi"], "zdarzenia.csv"),
            ["data_czas", "zdarzenie", "pracownik_nazwa", "pracownik_id"],
            [znacznik_czas, "otwarcie_bramki", nazwa_prac, id_prac],
        )
    else:
        zapiszDoPlikuCsv(
            os.path.join(konfig["folder_logi"], "zdarzenia.csv"),
            ["data_czas", "zdarzenie", "pracownik_nazwa", "pracownik_id"],
            [znacznik_czas, "odmowa_dostepu", nazwa_prac, id_prac],
        )
    
    zapiszDoPlikuCsv(
        os.path.join(konfig["folder_logi"], "pomiary.csv"),
        ["data_czas", "pracownik_nazwa", "pracownik_id", "promile", "pomiar_po_PIN"],
        [znacznik_czas, nazwa_prac, id_prac, f"{promille:.3f}", int(flaga_pin_zapasowy)],
    )
    
    pin_prac = None
    try:
        wpis = baza_twarzy.emp_by_id.get(id_prac or "")
        if wpis:
            pin_prac = wpis.get("pin")
    except Exception:
        pass
    
    try:
        loguj_do_mongo(znacznik_czas, id_prac, nazwa_prac, pin_prac, promille, wejscie_ok, flaga_pin_zapasowy)
    except Exception as e:
        print(f"[WYDARZENIA] Błąd Mongo: {e}")

    if not wejscie_ok and migawka_bgr is not None:
        try:
            synchronizuj_mail(znacznik_czas, id_prac, nazwa_prac, promille, migawka_bgr)
        except Exception as e:
            print(f"[WYDARZENIA] Błąd email: {e}")


def zapisz_zdarzenie_gosc(wejscie_ok):
    #Symulacja otwarcie furtki
    if wejscie_ok:
        sprzet.otworz_bramke()
