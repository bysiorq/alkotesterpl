import os
import json
import requests
from konfiguracja import konfig

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None


def synchronizuj_pracownikow(baza_twarzy):
    sciezka_prac = konfig.get("plik_pracownicy", "dane/pracownicy.json")
    if not os.path.isabs(sciezka_prac):
        katalog_biez = os.path.dirname(os.path.abspath(__file__))
        sciezka_prac = os.path.join(katalog_biez, "..", sciezka_prac)

    lista_prac_zdalna = []
    uzyto_mongo = False

    mongo_uri = konfig.get("mongo_uri")
    if MongoClient and mongo_uri:
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            nazwa_bazy = konfig.get("nazwa_bazy_mongo", "alkotester")
            db = client[nazwa_bazy]
            coll = db["pracownicy"]
            
            cursor = coll.find({}, {"_id": 0})
            lista_prac_zdalna = list(cursor)
            
            print(f"[SYNC] Pobrano {len(lista_prac_zdalna)} pracowników z MongoDB Atlas")
            uzyto_mongo = True
        except Exception as e:
            print(f"[SYNC] Błąd połączenia z MongoDB: {e}")
    
    if not uzyto_mongo:
        baza_url = konfig.get("url_bazy_render")
        token = konfig.get("haslo")
        if baza_url:
            url = f"{baza_url.rstrip('/')}/api/pracownicy_public"
        params = {"token": token} if token else {}

        try:
            print(f"[SYNC] Próba pobrania z serwera HTTP: {url}")
            odp = requests.get(url, params=params, timeout=10)
            odp.raise_for_status()
            dane = odp.json()
            lista_prac_zdalna = dane.get("pracownicy", [])
            print(f"[SYNC] Pobrano {len(lista_prac_zdalna)} pracowników z serwera HTTP")
        except Exception as e:
            print(f"[SYNC] Błąd synchronizacji HTTP: {e}")
            return

    try:
        dane_do_zapisu = {"pracownicy": lista_prac_zdalna}
        
        print(f"[SYNC] Zapisuję {len(lista_prac_zdalna)} pracowników do pliku (cache)")

        os.makedirs(os.path.dirname(sciezka_prac), exist_ok=True)
        with open(sciezka_prac, "w", encoding="utf-8") as f:
            json.dump(dane_do_zapisu, f, ensure_ascii=False, indent=2)

        baza_twarzy.wczytajPracownikow()
        print("[SYNC] Synchronizacja zakończona pomyślnie")
    except Exception as e:
        print(f"[SYNC] Błąd zapisu cache: {e}")
