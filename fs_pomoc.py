import os
import json
from datetime import datetime

from konfiguracja import konfig


def sprawdzKatalogi():
    for katalog in [
        konfig["folder_dane"],
        konfig["folder_twarze"],
        konfig["folder_indeks"],
        konfig["folder_logi"],
        konfig["folder_raporty"],
    ]:
        os.makedirs(katalog, exist_ok=True)

    if not os.path.exists(konfig["plik_pracownicy"]):
        os.makedirs(os.path.dirname(konfig["plik_pracownicy"]), exist_ok=True)
        with open(konfig["plik_pracownicy"], "w", encoding="utf-8") as f:
            json.dump({"pracownicy": []}, f, ensure_ascii=False, indent=2)


def aktualnyCzas() -> str:
    return datetime.now().strftime("%H:%M %d.%m.%Y")


def zapiszDoPlikuCsv(sciezka: str, naglowek: list, wiersz: list):
    istnialo = os.path.exists(sciezka)
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    with open(sciezka, "a", encoding="utf-8") as f:
        if not istnialo:
            f.write(";".join(naglowek) + "\n")
        f.write(";".join(map(str, wiersz)) + "\n")
