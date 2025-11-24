import os
import glob
import json
import cv2
import numpy as np
from datetime import datetime

from konfiguracja import konfig

# Ścieżka do modelu YuNet
_SCIEZKA_YUNET = konfig.get("sciezka_modelu_yunet", "models/face_detection_yunet_2023mar.onnx")


class BazaTwarzy:
    """
    Baza pracowników wraz z ich zdjęciami twarzy i deskryptorami ORB.
    Implementacja wzorowana na sprawdzonej klasie FaceDB, dostosowana do polskiego nazewnictwa.
    """

    def __init__(self, folder_twarze: str, folder_indeks: str, plik_pracownicy: str):
        self.folder_twarze = folder_twarze
        self.folder_indeks = folder_indeks
        self.plik_pracownicy = plik_pracownicy

        # Załaduj bazę pracowników
        self.wczytajPracownikow()

        # Przygotuj detektory twarzy
        self._inicjalizuj_detektory()
        # Fallback Haar Cascade
        self.cascade = cv2.CascadeClassifier(self._znajdz_haar())

        # Ekstraktor cech ORB
        self.orb = cv2.ORB_create(nfeatures=1000)

        # Indeks deskryptorów w pamięci
        self.indeks = {}
        self.wczytajIndeks()

    # ----- Detektory twarzy -----
    def _inicjalizuj_detektory(self):
        """Przygotuj detektor YuNet, jeśli dostępny."""
        self._det_yunet = None
        try:
            if hasattr(cv2, "FaceDetectorYN_create") and os.path.exists(_SCIEZKA_YUNET):
                prog_score = float(konfig.get("prog_wykrycia_yunet", 0.85))
                prog_nms = float(konfig.get("prog_nms", 0.3))
                limit_top = int(konfig.get("limit_top_yunet", 5000))
                # Rozmiar wejścia ustawiony zostanie dynamicznie w detekcja
                self._det_yunet = cv2.FaceDetectorYN_create(
                    _SCIEZKA_YUNET, "", (320, 320), prog_score, prog_nms, limit_top
                )
        except Exception:
            self._det_yunet = None

    def detekcja(self, obraz_bgr):
        """
        Zwróć listę ramek (x,y,w,h) wykrytych twarzy w pikselach.
        Najpierw stosowany jest YuNet, a następnie Haar jako fallback.
        """
        wys, szer = obraz_bgr.shape[:2]
        # YuNet
        if self._det_yunet is not None:
            try:
                self._det_yunet.setInputSize((szer, wys))
                _, twarze = self._det_yunet.detect(obraz_bgr)
                ramki = []
                if twarze is not None and len(twarze) > 0:
                    for det in twarze:
                        x, y, ww, hh = det[:4]
                        ramki.append((int(x), int(y), int(ww), int(hh)))
                if ramki:
                    return ramki
            except Exception:
                pass
        # Haar fallback
        try:
            szary = cv2.cvtColor(obraz_bgr, cv2.COLOR_BGR2GRAY)
            twarze = self.cascade.detectMultiScale(szary, 1.2, 5)
            return [(int(x), int(y), int(ww), int(hh)) for (x, y, ww, hh) in twarze]
        except Exception:
            return []

    # ----- Init helpers -----
    def _znajdz_haar(self) -> str:
        """Zwróć ścieżkę do pliku haarcascade_frontalface_default.xml."""
        katalogi = []
        if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            katalogi.append(cv2.data.haarcascades)
        katalogi += [
            "/usr/share/opencv4/haarcascades/",
            "/usr/share/opencv/haarcascades/",
            "/usr/local/share/opencv4/haarcascades/",
            "./",
        ]
        nazwa = "haarcascade_frontalface_default.xml"
        for baza in katalogi:
            sciezka = os.path.join(baza, nazwa)
            if os.path.exists(sciezka):
                return sciezka
        return nazwa

    def wczytajPracownikow(self):
        """Wczytaj plik employees.json do struktur pomocniczych."""
        try:
            with open(self.plik_pracownicy, "r", encoding="utf-8") as f:
                dane = json.load(f)
        except Exception:
            dane = {}
        
        # Obsługa formatu {"pracownicy": [...]} oraz starego {"employees": [...]}
        self.pracownicy = dane.get("pracownicy") or dane.get("employees", [])
        if not isinstance(self.pracownicy, list):
            self.pracownicy = []

        # indeks pracowników po pinie i id
        self.emp_by_pin = {
            e["pin"]: e
            for e in self.pracownicy
            if "pin" in e
        }
        self.emp_by_id = {
            (e.get("id") or e.get("imie") or e.get("name")): e
            for e in self.pracownicy
        }

    def zapiszPracownikow(self):
        """Zapisz employees.json po modyfikacji i odśwież indeksy."""
        dane = {"pracownicy": self.pracownicy}
        with open(self.plik_pracownicy, "w", encoding="utf-8") as f:
            json.dump(dane, f, ensure_ascii=False, indent=2)
        self.wczytajPracownikow()

    def dodajNowego(self, id_prac: str, imie: str, pin: str):
        """Dopisz pracownika do bazy jeśli jeszcze go nie ma."""
        if not any((e.get("id") == id_prac) for e in self.pracownicy):
            self.pracownicy.append({"id": id_prac, "imie": imie, "pin": pin})
            self.zapiszPracownikow()
        os.makedirs(os.path.join(self.folder_twarze, id_prac), exist_ok=True)

    # ----- Zrzuty twarzy -----
    def zbierzProbki(self, id_prac: str, lista_obrazow_bgr):
        """Zapisz listę zrzutów twarzy (lista obrazów BGR) dla pracownika."""
        folder_prac = os.path.join(self.folder_twarze, id_prac)
        os.makedirs(folder_prac, exist_ok=True)
        for obraz in lista_obrazow_bgr:
            nazwa = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
            sciezka_wyj = os.path.join(folder_prac, nazwa)
            cv2.imwrite(sciezka_wyj, obraz, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    def usunNadmiar(self, id_prac: str, max_len: int):
        """Usuń najstarsze zrzuty twarzy jeśli jest ich zbyt dużo."""
        folder_prac = os.path.join(self.folder_twarze, id_prac)
        pliki = sorted(glob.glob(os.path.join(folder_prac, "*.jpg")))
        nadmiar = len(pliki) - max_len
        if nadmiar > 0:
            for sciezka in pliki[:nadmiar]:
                try:
                    os.remove(sciezka)
                except Exception:
                    pass

    def dodajProbke(self, id_prac: str, twarz_bgr_240):
        """
        Dodaj próbkę twarzy do indeksu i zapisz do katalogu faces.
        Zwraca True jeśli próbka została zaakceptowana.
        """
        szary = cv2.cvtColor(twarz_bgr_240, cv2.COLOR_BGR2GRAY)
        _, deskryptory = self.orb.detectAndCompute(szary, None)
        if deskryptory is None or len(deskryptory) == 0:
            return False
        if id_prac not in self.indeks:
            self.indeks[id_prac] = []
        self.indeks[id_prac].append(deskryptory)
        
        max_len = konfig.get("max_fotek_pracownika", 20)
        if len(self.indeks[id_prac]) > max_len:
            self.indeks[id_prac] = self.indeks[id_prac][-max_len:]
            
        folder_prac = os.path.join(self.folder_twarze, id_prac)
        os.makedirs(folder_prac, exist_ok=True)
        nazwa = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
        sciezka = os.path.join(folder_prac, nazwa)
        cv2.imwrite(sciezka, twarz_bgr_240, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        
        self.usunNadmiar(id_prac, max_len)
        self.zapiszIndeks(id_prac, self.indeks[id_prac])
        return True

    # ----- Indeks ORB -----
    def wczytajIndeks(self):
        """Załaduj deskryptory z plików .npz w index_dir."""
        self.indeks = {}
        for prac in self.pracownicy:
            id_prac = prac.get("id") or prac.get("imie") or prac.get("name")
            sciezka_npz = os.path.join(self.folder_indeks, f"{id_prac}.npz")
            if os.path.exists(sciezka_npz):
                try:
                    npz = np.load(sciezka_npz, allow_pickle=True)
                    self.indeks[id_prac] = list(npz.get("descriptors", []))
                except Exception:
                    self.indeks[id_prac] = []
            else:
                self.indeks[id_prac] = []

    def zapiszIndeks(self, id_prac: str, lista_deskryptorow):
        """Zapisz listę deskryptorów ORB dla danego pracownika."""
        os.makedirs(self.folder_indeks, exist_ok=True)
        np.savez_compressed(
            os.path.join(self.folder_indeks, f"{id_prac}.npz"),
            descriptors=np.array(lista_deskryptorow, dtype=object)
        )

    def trenuj(self, progress_callback=None):
        """
        Przebuduj indeks dla wszystkich pracowników na podstawie zrzutów twarzy.
        """
        pracownicy = self.pracownicy
        ile = len(pracownicy)
        for idx, prac in enumerate(pracownicy):
            id_prac = prac.get("id") or prac.get("imie") or prac.get("name")
            folder_prac = os.path.join(self.folder_twarze, id_prac)
            lista_desc = []
            for sciezka_obr in sorted(glob.glob(os.path.join(folder_prac, "*.jpg"))):
                obraz = cv2.imread(sciezka_obr)
                if obraz is None:
                    continue
                szary = cv2.cvtColor(obraz, cv2.COLOR_BGR2GRAY)
                # Używamy Haara do wycięcia twarzy ze zdjęć treningowych - tak jak w FaceDB
                twarze = self.cascade.detectMultiScale(szary, 1.2, 5)
                if len(twarze) > 0:
                    (x, y, w, h) = max(twarze, key=lambda r: r[2] * r[3])
                    roi = szary[y:y + h, x:x + w]
                else:
                    roi = szary
                roi = cv2.resize(roi, (240, 240), interpolation=cv2.INTER_LINEAR)
                _, desc = self.orb.detectAndCompute(roi, None)
                if desc is not None and len(desc) > 0:
                    lista_desc.append(desc)
            self.indeks[id_prac] = lista_desc
            self.zapiszIndeks(id_prac, lista_desc)
            if progress_callback:
                progress_callback(idx + 1, ile)

    # ----- Rozpoznawanie -----
    def rozpoznaj(self, img_bgr):
        """
        Rozpoznaj twarz w podanej klatce.
        :returns: (id_prac lub None, nazwa lub None, pewność%, bbox lub None)
        """
        szary = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        twarze = self.detekcja(img_bgr)
        if not twarze:
            return None, None, 0.0, None
        
        (x, y, w, h) = max(twarze, key=lambda r: r[2] * r[3])
        H, W = szary.shape[:2]
        x = int(max(0, x))
        y = int(max(0, y))
        w = int(max(0, w))
        h = int(max(0, h))
        x2 = min(x + w, W)
        y2 = min(y + h, H)
        
        if x2 <= x or y2 <= y:
            return None, None, 0.0, (x, y, max(0, x2 - x), max(0, y2 - y))
        
        roi_szary = szary[y:y2, x:x2]
        if roi_szary.size == 0:
            return None, None, 0.0, (x, y, max(0, x2 - x), max(0, y2 - y))
            
        try:
            roi_szary = cv2.resize(roi_szary, (240, 240), interpolation=cv2.INTER_LINEAR)
        except cv2.error:
            return None, None, 0.0, (x, y, max(0, x2 - x), max(0, y2 - y))
            
        _, desc = self.orb.detectAndCompute(roi_szary, None)
        if desc is None or len(desc) == 0:
            return None, None, 0.0, (x, y, max(0, x2 - x), max(0, y2 - y))
            
        prog_ratio = konfig.get("wspolczynnik_progu", 0.75)
        prog_min_match = konfig.get("min_dopasowan", 15)
        prog_margin = konfig.get("min_probek_podrzad", 5) # Uwaga: w FaceDB to recognition_min_margin
        
        knn = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        najlepszy_id = None
        najlepszy_wynik = 0
        drugi_wynik = 0
        
        for id_prac, lista_desc in self.indeks.items():
            wynik_emp = 0
            for dset in lista_desc:
                if dset is None or len(dset) == 0:
                    continue
                dopasowania = knn.knnMatch(desc, dset, k=2)
                for para in dopasowania:
                    if len(para) < 2:
                        continue
                    m1, m2 = para[0], para[1]
                    if m1.distance < prog_ratio * m2.distance:
                        wynik_emp += 1
            
            if wynik_emp > najlepszy_wynik:
                drugi_wynik, najlepszy_wynik, najlepszy_id = najlepszy_wynik, wynik_emp, id_prac
            elif wynik_emp > drugi_wynik:
                drugi_wynik = wynik_emp
                
        if najlepszy_wynik < prog_min_match:
            return None, None, 0.0, (x, y, max(0, x2 - x), max(0, y2 - y))
            
        if (najlepszy_wynik - drugi_wynik) < prog_margin:
            return None, None, 0.0, (x, y, max(0, x2 - x), max(0, y2 - y))
            
        suma = max(1, najlepszy_wynik + drugi_wynik)
        pewnosc = min(100.0, 100.0 * (najlepszy_wynik / suma))
        
        pokaz_nazwa = None
        if najlepszy_id:
            wpis = self.emp_by_id.get(najlepszy_id)
            pokaz_nazwa = wpis.get("imie") or wpis.get("name") or najlepszy_id if wpis else najlepszy_id
            
        bw = max(0, x2 - x)
        bh = max(0, y2 - y)
        return najlepszy_id, pokaz_nazwa, pewnosc, (x, y, bw, bh)
