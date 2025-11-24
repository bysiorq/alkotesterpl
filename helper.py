import os
import json
from datetime import datetime

from config import config


def katalogiverify():
    for katalog in [
        config["katalog_dane"],
        config["katalogTwarze"],
        config["katalogIndex"],
        config["logi"],
        config["raportOdmowy"],
    ]:
        os.makedirs(katalog, exist_ok=True)

    if not os.path.exists(config["pracownicyListajson"]):
        os.makedirs(os.path.dirname(config["pracownicyListajson"]), exist_ok=True)
        with open(config["pracownicyListajson"], "w", encoding="utf-8") as f:
            json.dump({"pracownicy": []}, f, ensure_ascii=False, indent=2)


def czas() -> str:
    return datetime.now().strftime("%H:%M %d.%m.%Y")


def dopiszCsv(path: str, header: list, row_values: list):
    istnialo = os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        if not istnialo:
            f.write(";".join(header) + "\n")
        f.write(";".join(map(str, row_values)) + "\n")
