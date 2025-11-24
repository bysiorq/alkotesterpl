import threading
from konfiguracja import konfig

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

_KLIENT_MONGO = None


def loguj_do_mongo(znacznik_czasu, id_prac, nazwa_prac, pin_prac, promille, wejscie_ok: bool, flaga_pin_zapasowy: bool):
    if MongoClient is None or not konfig.get("mongo_uri"):
        return

    def watek():
        global _KLIENT_MONGO
        try:
            if _KLIENT_MONGO is None:
                _KLIENT_MONGO = MongoClient(
                    konfig["mongo_uri"],
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000,
                )

            baza = _KLIENT_MONGO[konfig.get("nazwa_bazy_mongo", "alkotester")]
            kolekcja = baza["wejscia"]
            
            dokument = {
                "data_czas": znacznik_czasu,
                "pracownik_id": id_prac,
                "pracownik_nazwa": nazwa_prac,
                "pracownik_pin": pin_prac,
                "promile": float(promille),
                "wynik": "WEJSCIE_OK" if wejscie_ok else "ODMOWA",
                "pomiar_po_PIN": bool(flaga_pin_zapasowy),
            }
            
            kolekcja.insert_one(dokument)
        except Exception as e:
            print(f"[Mongo] Błąd logowania: {e}")

    threading.Thread(target=watek, daemon=True).start()
    
synchronizuj_mongo_z_flaga = loguj_do_mongo
