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
        print("[SYNC] Brak URL bazy - pomijam synchronizację")
        return

    url = f"{baza_url.rstrip('/')}/api/pracownicy_public"
    params = {"token": token} if token else {}

    try:
        # Wczytaj istniejących pracowników lokalnych
        pracownicy_lokalni = []
        if os.path.exists(sciezka_prac):
            try:
                with open(sciezka_prac, "r", encoding="utf-8") as f:
                    dane_lokalne = json.load(f)
                pracownicy_lokalni = dane_lokalne.get("pracownicy", [])
                print(f"[SYNC] Wczytano {len(pracownicy_lokalni)} lokalnych pracowników")
            except Exception as e:
                print(f"[SYNC] Błąd wczytywania lokalnych pracowników: {e}")
        
        # Pobierz pracowników ze zdalnego serwera
        odp = requests.get(url, params=params, timeout=10)
        odp.raise_for_status()
        dane = odp.json()
        
        if not isinstance(dane, dict):
            print("[SYNC] Błędny format danych z serwera")
            return

        lista_prac_zdalna = dane.get("pracownicy") or dane.get("employees", [])
        if not isinstance(lista_prac_zdalna, list):
            lista_prac_zdalna = []
        
        print(f"[SYNC] Pobrano {len(lista_prac_zdalna)} pracowników z serwera")
        
        # Jeśli serwer zwraca pustą listę i mamy lokalnych pracowników, nie nadpisuj!
        if len(lista_prac_zdalna) == 0 and len(pracownicy_lokalni) > 0:
            print("[SYNC] Serwer zwrócił pustą listę - zachowuję lokalnych pracowników")
            return
        
        # Scal pracowników: zdalni + lokalni (bez duplikatów po ID)
        pracownicy_scaleni = {}
        
        # Najpierw dodaj zdalnych
        for prac in lista_prac_zdalna:
            prac_id = prac.get("id")
            if prac_id:
                pracownicy_scaleni[prac_id] = prac
        
        # Następnie dodaj lokalnych (jeśli nie ma już w zdalnych)
        for prac in pracownicy_lokalni:
            prac_id = prac.get("id")
            if prac_id and prac_id not in pracownicy_scaleni:
                print(f"[SYNC] Zachowuję lokalnego pracownika: {prac.get('imie', prac_id)}")
                pracownicy_scaleni[prac_id] = prac
        
        lista_finalna = list(pracownicy_scaleni.values())
        dane_do_zapisu = {"pracownicy": lista_finalna}
        
        print(f"[SYNC] Zapisuję {len(lista_finalna)} pracowników do pliku")

        os.makedirs(os.path.dirname(sciezka_prac), exist_ok=True)
        with open(sciezka_prac, "w", encoding="utf-8") as f:
            json.dump(dane_do_zapisu, f, ensure_ascii=False, indent=2)

        baza_twarzy.wczytajPracownikow()
        print("[SYNC] Synchronizacja zakończona pomyślnie")
    except Exception as e:
        print(f"[SYNC] Błąd synchronizacji: {e}")
