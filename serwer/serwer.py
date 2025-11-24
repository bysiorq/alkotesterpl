from flask import Flask, request, redirect, url_for, session, render_template_string, jsonify
from collections import deque
from datetime import datetime
import json
import os
from typing import Dict, List, Any

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

from config import config


appFlask = Flask(__name__)
appFlask.secret_key = "supersecretkey"

# Połączenie z MongoDB – nowa, polska wersja
if MongoClient is not None and config.get("mongo_uri"):
    try:
        _klient_mongo = MongoClient(config.get("mongo_uri"))
        _baza_mongo = _klient_mongo[config.get("baza_mongodb", "alkotester")]
        # NAZWA KOLEKCJI – tu załóżmy, że w SyncMongo robisz db["wejscia"]
        _kolekcja_wejsc = _baza_mongo["wejscia"]
    except Exception:
        _klient_mongo = None
        _baza_mongo = None
        _kolekcja_wejsc = None
else:
    _klient_mongo = None
    _baza_mongo = None
    _kolekcja_wejsc = None


katalog = os.path.dirname(os.path.abspath(__file__))


def sciezkaPracownicy() -> str:
    emp_path = config.get("pracownicyListajson", "dane/pracownicy.json")
    if not os.path.isabs(emp_path):
        emp_path = os.path.join(katalog, emp_path)
    return emp_path


def sciezkaLogow() -> str:
    log_dir = config.get("logi", "logi")
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(katalog, log_dir)
    return log_dir


def przydziel_PIN() -> str:
    import random

    istniejace_piny = set()
    emp_path = sciezkaPracownicy()
    try:
        with open(emp_path, "r", encoding="utf-8") as f:
            dane = json.load(f)
        lista = dane.get("pracownicy") or []
        for emp in lista:
            pin = emp.get("pin")
            if pin:
                istniejace_piny.add(str(pin))
    except Exception:
        pass

    while True:
        kandydat = f"{random.randint(0, 9999):04d}"
        if kandydat not in istniejace_piny:
            return kandydat


def pracownik_przydziel_ID() -> str:
    ids: List[int] = []
    emp_path = sciezkaPracownicy()
    try:
        with open(emp_path, "r", encoding="utf-8") as f:
            dane = json.load(f)
        lista = dane.get("pracownicy") or []
        for emp in lista:
            try:
                ids.append(int(emp.get("id")))
            except Exception:
                continue
    except Exception:
        pass
    return str(max(ids) + 1 if ids else 1)


def format_dt_iso_na_polski(dt_str: str) -> str:
    if not dt_str:
        return ""
    try:
        dt_obj = datetime.fromisoformat(dt_str)
        return dt_obj.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return dt_str


def opis_autoryzacji(pomiar_po_PIN: int | bool) -> str:
    try:
        flaga = int(pomiar_po_PIN)
    except Exception:
        flaga = 0
    return "PIN" if flaga else "SI"


def opis_wyniku(kod: str) -> str:
    if kod == "WEJSCIE_OK":
        return "Przepuszczony"
    if kod == "ODMOWA":
        return "Odmowa"
    return kod or ""


def wczytaj_wejscia_csv() -> List[Dict[str, Any]]:
    log_dir = sciezkaLogow()
    log_path = os.path.join(log_dir, "wejscia.csv")

    if not os.path.exists(log_path):
        return []

    try:
        from collections import deque
        with open(log_path, "r", encoding="utf-8") as f:
            linie = list(deque(f, maxlen=501))  # max 500 wpisów + nagłówek

        if len(linie) <= 1:
            return []

        wpisy: List[Dict[str, Any]] = []

        for wiersz in linie[1:]:
            kolumny = wiersz.strip().split(";")
            if len(kolumny) < 6:
                continue

            data_czas_raw = kolumny[0]
            nazwa = kolumny[1]
            prac_id = kolumny[2]
            pin = kolumny[3]
            prom_str = kolumny[4]
            pomiar_po_pin_str = kolumny[5]
            wynik_kod = kolumny[6] if len(kolumny) > 6 else ""

            try:
                prom = float(prom_str.replace(",", "."))
            except Exception:
                prom = 0.0

            data_czas = format_dt_iso_na_polski(data_czas_raw)
            zrodlo = opis_autoryzacji(pomiar_po_pin_str)
            werdykt = opis_wyniku(wynik_kod)

            wpisy.append(
                {
                    "pin_pracownika": pin,
                    "nazwa_pracownika": nazwa,
                    "promile": prom,
                    "data_czas": data_czas,
                    "werdykt": werdykt,
                    "zrodlo_weryfikacji": zrodlo,
                }
            )

        return wpisy
    except Exception:
        return []


@appFlask.route("/")
def index():
    if session.get("zalogowany"):
        return redirect(url_for("tablica"))
    return redirect(url_for("login"))


@appFlask.route("/login", methods=["GET", "POST"])
def login():
    blad = None
    if request.method == "POST":
        nazwa_uzytkownika = request.form.get("username", "").strip()
        haslo = request.form.get("password", "").strip()
        if (
            nazwa_uzytkownika == config.get("loginAdmin")
            and haslo == config.get("hasloAdmin")
        ):
            session["zalogowany"] = True
            return redirect(url_for("tablica"))
        blad = "Zły login lub hasło"
    return render_template_string(loginSzablon, blad=blad)


@appFlask.route("/logout")
def logout():
    session.pop("zalogowany", None)
    return redirect(url_for("login"))


def czy_zalogowany() -> bool:
    return bool(session.get("zalogowany"))


@appFlask.route("/api/pracownicy_public", methods=["GET"])
def api_pracownik_public():
    oczekiwany_token = config.get("token")
    if oczekiwany_token:
        token = request.args.get("token")
        if token != oczekiwany_token:
            return "Forbidden", 403

    emp_path = sciezkaPracownicy()
    try:
        with open(emp_path, "r", encoding="utf-8") as f:
            dane = json.load(f)
    except Exception:
        dane = {"pracownicy": []}
    return jsonify(dane)


@appFlask.route("/tablica", methods=["GET"])
def tablica():
    if not czy_zalogowany():
        return redirect(url_for("login"))

    # info po dodaniu pracownika (parametry GET)
    nowy_pin = request.args.get("nowy_pin")
    nazwa_pracownika = request.args.get("nazwa_pracownika")
    if nowy_pin and nazwa_pracownika:
        info = f"Dodano pracownika {nazwa_pracownika}. PIN: {nowy_pin}"
    else:
        info = session.pop("info", None)

    wpisy: List[Dict[str, Any]] = []

    # Preferencja: MongoDB, jeśli dostępne – UŻYWAMY TWOICH POLSKICH PÓL
    if _kolekcja_wejsc is not None:
        try:
            kursor = (
                _kolekcja_wejsc.find()
                .sort("data_czas", -1)
                .limit(500)
            )
            for doc in kursor:
                nazwa = doc.get("pracownik_nazwa", "")
                pin = doc.get("pracownik_pin", "")
                prom_val = doc.get("promile", 0.0)
                czas_str = doc.get("data_czas", "")
                flaga_pin = doc.get("pomiar_po_PIN", 0)
                wynik_kod = doc.get("wynik", "")

                try:
                    prom = float(prom_val)
                except Exception:
                    prom = 0.0

                data_czas = format_dt_iso_na_polski(czas_str)
                zrodlo = opis_autoryzacji(flaga_pin)
                werdykt = opis_wyniku(wynik_kod)

                wpisy.append(
                    {
                        "pin_pracownika": pin,
                        "nazwa_pracownika": nazwa,
                        "promile": prom,
                        "data_czas": data_czas,
                        "werdykt": werdykt,
                        "zrodlo_weryfikacji": zrodlo,
                    }
                )
        except Exception:
            wpisy = []

    # fallback: CSV, gdy brak Mongo albo brak danych – też w nowym, polskim formacie
    if not wpisy:
        wpisy = wczytaj_wejscia_csv()

    return render_template_string(tablicawejsc, wpisy=wpisy, info=info)


@appFlask.route("/dodajPracownika", methods=["POST"])
def dodajPracownika():
    if not czy_zalogowany():
        return redirect(url_for("tablica"))

    imie = request.form.get("first_name", "").strip()
    nazwisko = request.form.get("last_name", "").strip()
    if not imie or not nazwisko:
        return redirect(url_for("tablica"))

    pelne_imie = f"{imie} {nazwisko}"
    nowy_pin = przydziel_PIN()
    nowe_id = pracownik_przydziel_ID()

    emp_path = sciezkaPracownicy()
    try:
        with open(emp_path, "r", encoding="utf-8") as f:
            dane = json.load(f)
        lista = dane.get("pracownicy") or []
    except Exception:
        dane = {}
        lista = []

    # TUTAJ TEŻ JEST POLSKO: "imie", nie "name"
    lista.append({"id": nowe_id, "imie": pelne_imie, "pin": nowy_pin})
    dane["pracownicy"] = lista

    dirpath = os.path.dirname(emp_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    try:
        with open(emp_path, "w", encoding="utf-8") as f:
            json.dump(dane, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return redirect(url_for("tablica", nowy_pin=nowy_pin, nazwa_pracownika=pelne_imie))


def run_server():
    port = int(os.environ.get("PORT", config.get("adminport", 8000)))
    appFlask.run(
        host="0.0.0.0",
        port=port,
        ssl_context=None,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


loginSzablon = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Logowanie administratora</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
        form { max-width: 300px; }
        input { width: 100%; padding: 8px; margin-top: 8px; }
        button { padding: 8px 16px; margin-top: 12px; width: 100%; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>Logowanie administratora</h1>
    {% if blad %}
    <p class="error">{{ blad }}</p>
    {% endif %}
    <form method="post" action="{{ url_for('login') }}">
        <label>Nazwa użytkownika:</label><br>
        <input type="text" name="username" placeholder="login" autofocus required><br>
        <label>Hasło:</label><br>
        <input type="password" name="password" placeholder="hasło" required><br>
        <button type="submit">Zaloguj</button>
    </form>
</body>
</html>
"""

tablicawejsc = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Harmonogram wejść</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        form input { margin-right: 8px; }
    </style>
</head>
<body>
    <h1>Harmonogram wejść pracowników</h1>
    {% if info %}
    <p style="color: green; font-weight: bold;">{{ info }}</p>
    {% endif %}
    <table>
        <thead>
            <tr>
                <th>PIN</th>
                <th>Imię</th>
                <th>Nazwisko</th>
                <th>Promil [‰]</th>
                <th>Data i godzina</th>
                <th>Wynik</th>
                <th>Weryfikacja</th>
            </tr>
        </thead>
        <tbody>
        {% for wpis in wpisy %}
            <tr>
                <td>{{ wpis.pin_pracownika }}</td>
                <td>{{ (wpis.nazwa_pracownika.split(' ')[0] if wpis.nazwa_pracownika else '') }}</td>
                <td>{{ (wpis.nazwa_pracownika.split(' ', 1)[1] if wpis.nazwa_pracownika and ' ' in wpis.nazwa_pracownika else '') }}</td>
                <td>{{ '%.3f'|format(wpis.promile) }}</td>
                <td>{{ wpis.data_czas }}</td>
                <td>{{ wpis.werdykt }}</td>
                <td>{{ wpis.zrodlo_weryfikacji }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    <h2>Dodaj nowego pracownika</h2>
    <form method="post" action="{{ url_for('dodajPracownika') }}">
        <input type="text" name="first_name" placeholder="Imię" required>
        <input type="text" name="last_name" placeholder="Nazwisko" required>
        <button type="submit">Dodaj</button>
    </form>
    <p><a href="{{ url_for('logout') }}">Wyloguj</a></p>
</body>
</html>
"""

if __name__ == "__main__":
    run_server()
