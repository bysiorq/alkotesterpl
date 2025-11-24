import os
import json
import requests
from konfiguracja import konfig


def synchronizuj_pracownikow(baza_twarzy):
    baza_url = konfig.get("url_bazy_render")
    token = konfig.get("haslo")
    sciezka_prac = konfig.get("plik_pracownicy", "dane/pracownicy.json")

    if not os.path.isabs(sciezka_prac):
        katalog_biez = os.path.dirname(os.path.abspath(__file__))
        sciezka_prac = os.path.join(katalog_biez, "..", sciezka_prac)


    url = f"{baza_url.rstrip('/')}/api/pracownicy_public"
    params = {"token": token} if token else {}

    try:
        odp = requests.get(url, params=params, timeout=10)
        odp.raise_for_status()
        dane = odp.json()
        

        lista_prac_zdalna = dane.get("pracownicy")
        
        print(f"[SYNC] Pobrano {len(lista_prac_zdalna)} pracowników z serwera")

        dane_do_zapisu = {"pracownicy": lista_prac_zdalna}
        
        print(f"[SYNC] Zapisuję {len(lista_prac_zdalna)} pracowników do pliku (cache)")

        os.makedirs(os.path.dirname(sciezka_prac), exist_ok=True)
        with open(sciezka_prac, "w", encoding="utf-8") as f:
            json.dump(dane_do_zapisu, f, ensure_ascii=False, indent=2)

        baza_twarzy.wczytajPracownikow()
        print("[SYNC] Synchronizacja zakończona pomyślnie")
    except Exception as e:
        print(f"[SYNC] Błąd synchronizacji: {e}")
