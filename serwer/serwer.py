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

from konfiguracja_serwer import konfig


aplikacja_flask = Flask(__name__)
aplikacja_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey-change-in-production")

# Połączenie z MongoDB – nowa, polska wersja
if MongoClient is not None and konfig.get("mongo_uri"):
    try:
        _klient_mongo = MongoClient(konfig.get("mongo_uri"))
        _baza_mongo = _klient_mongo[konfig.get("nazwa_bazy_mongo")]
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


def sciezka_pracownicy() -> str:
    emp_path = konfig.get("plik_pracownicy", "dane/pracownicy.json")
    if not os.path.isabs(emp_path):
        emp_path = os.path.join(katalog, emp_path)
    return emp_path


def sciezka_logow() -> str:
    log_dir = konfig.get("folder_logi", "logi")
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(katalog, log_dir)
    return log_dir


def przydziel_pin() -> str:
    import random

    istniejace_piny = set()
    emp_path = sciezka_pracownicy()
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


def przydziel_id_pracownika() -> str:
    ids: List[int] = []
    emp_path = sciezka_pracownicy()
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


def formatuj_date_czas(dt_str: str) -> str:
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
    log_dir = sciezka_logow()
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

            data_czas = formatuj_date_czas(data_czas_raw)
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


@aplikacja_flask.route("/")
def indeks():
    if session.get("zalogowany"):
        return redirect(url_for("tablica"))
    return redirect(url_for("logowanie"))


@aplikacja_flask.route("/logowanie", methods=["GET", "POST"])
def logowanie():
    blad = None
    if request.method == "POST":
        nazwa_uzytkownika = request.form.get("username", "").strip()
        haslo = request.form.get("password", "").strip()
        if (
            nazwa_uzytkownika == konfig.get("login_admina")
            and haslo == konfig.get("haslo_admina")
        ):
            session["zalogowany"] = True
            return redirect(url_for("tablica"))
        blad = "Zły login lub hasło"
    return render_template_string(szablon_logowania, blad=blad)


@aplikacja_flask.route("/wyloguj")
def wyloguj():
    session.pop("zalogowany", None)
    return redirect(url_for("logowanie"))


def czy_zalogowany() -> bool:
    return bool(session.get("zalogowany"))


@aplikacja_flask.route("/api/pracownicy_public", methods=["GET"])
def api_pracownicy_public():
    oczekiwany_token = konfig.get("haslo")
    if oczekiwany_token:
        token = request.args.get("token")
        if token != oczekiwany_token:
            return "Forbidden", 403

    emp_path = sciezka_pracownicy()
    try:
        with open(emp_path, "r", encoding="utf-8") as f:
            dane = json.load(f)
    except Exception:
        dane = {"pracownicy": []}
    return jsonify(dane)


@aplikacja_flask.route("/tablica", methods=["GET"])
def tablica():
    if not czy_zalogowany():
        return redirect(url_for("logowanie"))

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

                data_czas = formatuj_date_czas(czas_str)
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

    return render_template_string(szablon_tablicy, wpisy=wpisy, info=info)


@aplikacja_flask.route("/pracownicy", methods=["GET"])
def pracownicy():
    if not czy_zalogowany():
        return redirect(url_for("logowanie"))
    
    # Pobierz info po dodaniu pracownika
    nowy_pin = request.args.get("nowy_pin")
    nazwa_pracownika = request.args.get("nazwa_pracownika")
    if nowy_pin and nazwa_pracownika:
        info = f"✅ Dodano pracownika: {nazwa_pracownika}. Wygenerowany PIN: {nowy_pin}"
    else:
        info = None
    
    # Wczytaj listę pracowników
    emp_path = sciezka_pracownicy()
    try:
        with open(emp_path, "r", encoding="utf-8") as f:
            dane = json.load(f)
        lista_pracownikow = dane.get("pracownicy") or []
    except Exception:
        lista_pracownikow = []
    
    return render_template_string(szablon_pracownikow, pracownicy=lista_pracownikow, info=info)


@aplikacja_flask.route("/dodaj_pracownika", methods=["POST"])
def dodaj_pracownika():
    if not czy_zalogowany():
        return redirect(url_for("pracownicy"))

    imie = request.form.get("first_name", "").strip()
    nazwisko = request.form.get("last_name", "").strip()
    if not imie or not nazwisko:
        return redirect(url_for("pracownicy"))

    pelne_imie = f"{imie} {nazwisko}"
    nowy_pin = przydziel_pin()
    nowe_id = przydziel_id_pracownika()

    emp_path = sciezka_pracownicy()
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

    return redirect(url_for("pracownicy", nowy_pin=nowy_pin, nazwa_pracownika=pelne_imie))


def uruchom_serwer():
    port = int(os.environ.get("PORT", konfig.get("port_admina", 8000)))
    aplikacja_flask.run(
        host="0.0.0.0",
        port=port,
        ssl_context=None,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


szablon_logowania = """
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
    <form method="post" action="{{ url_for('logowanie') }}">
        <label>Nazwa użytkownika:</label><br>
        <input type="text" name="username" placeholder="login" autofocus required><br>
        <label>Hasło:</label><br>
        <input type="password" name="password" placeholder="hasło" required><br>
        <button type="submit">Zaloguj</button>
    </form>
</body>
</html>
"""

szablon_tablicy = """
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
        .nav-buttons { margin-bottom: 1.5em; }
        .nav-buttons a { 
            display: inline-block;
            padding: 10px 20px; 
            background-color: #1565c0; 
            color: white; 
            text-decoration: none; 
            border-radius: 4px;
            margin-right: 10px;
        }
        .nav-buttons a:hover { background-color: #0d47a1; }
    </style>
</head>
<body>
    <h1>Harmonogram wejść pracowników</h1>
    
    <div class="nav-buttons">
        <a href="{{ url_for('pracownicy') }}">Zarządzaj pracownikami</a>
        <a href="{{ url_for('wyloguj') }}">Wyloguj</a>
    </div>
    
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
</body>
</html>
"""

szablon_pracownikow = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Zarządzanie pracownikami</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 2em; margin-top: 2em; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f2f2f2; font-weight: bold; }
        .form-container {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 2em;
        }
        .form-container input {
            padding: 8px;
            margin-right: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .form-container button {
            padding: 10px 20px;
            background-color: #2e7d32;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .form-container button:hover { background-color: #1b5e20; }
        .nav-buttons { margin-bottom: 1.5em; }
        .nav-buttons a {
            display: inline-block;
            padding: 10px 20px;
            background-color: #1565c0;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin-right: 10px;
        }
        .nav-buttons a:hover { background-color: #0d47a1; }
        .success { color: green; font-weight: bold; padding: 10px; background: #e8f5e9; border-radius: 4px; }
        .pin-display { font-family: monospace; font-size: 1.2em; font-weight: bold; color: #d32f2f; }
    </style>
</head>
<body>
    <h1>Zarządzanie pracownikami</h1>
    
    <div class="nav-buttons">
        <a href="{{ url_for('tablica') }}">Harmonogram wejść</a>
        <a href="{{ url_for('wyloguj') }}">Wyloguj</a>
    </div>
    
    {% if info %}
    <p class="success">{{ info }}</p>
    {% endif %}
    
    <div class="form-container">
        <h2>Dodaj nowego pracownika</h2>
        <form method="post" action="{{ url_for('dodaj_pracownika') }}">
            <input type="text" name="first_name" placeholder="Imię" required>
            <input type="text" name="last_name" placeholder="Nazwisko" required>
            <button type="submit">Dodaj pracownika</button>
        </form>
    </div>
    
    <h2>Lista pracowników</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Imię</th>
                <th>Nazwisko</th>
                <th>PIN</th>
            </tr>
        </thead>
        <tbody>
        {% for prac in pracownicy %}
            <tr>
                <td>{{ prac.id }}</td>
                <td>{{ (prac.imie.split(' ')[0] if prac.imie else '') }}</td>
                <td>{{ (prac.imie.split(' ', 1)[1] if prac.imie and ' ' in prac.imie else '') }}</td>
                <td class="pin-display">{{ prac.pin }}</td>
            </tr>
        {% else %}
            <tr>
                <td colspan="4" style="text-align: center; color: #999;">Brak pracowników. Dodaj pierwszego pracownika powyżej.</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

if __name__ == "__main__":
    uruchom_serwer()
