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

    if not baza_url:
        return

    url = f"{baza_url.rstrip('/')}/api/pracownicy_public"
    params = {"token": token} if token else {}

    try:
        odp = requests.get(url, params=params, timeout=10)
        odp.raise_for_status()
        dane = odp.json()
        
        if not isinstance(dane, dict):
            return

        lista_prac = dane.get("pracownicy") or dane.get("employees", [])
        if not isinstance(lista_prac, list):
            lista_prac = []

        dane_do_zapisu = {"pracownicy": lista_prac}

        os.makedirs(os.path.dirname(sciezka_prac), exist_ok=True)
        with open(sciezka_prac, "w", encoding="utf-8") as f:
            json.dump(dane_do_zapisu, f, ensure_ascii=False, indent=2)

        baza_twarzy.wczytajPracownikow()
    except Exception as e:
        print(f"[SYNC] Błąd: {e}")
