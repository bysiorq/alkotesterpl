import cv2
import time
import threading
import numpy as np
from PyQt5 import QtCore
from konfiguracja import konfig


def jakosc_twarzy(szare_roi, config):
    ostrosc = cv2.Laplacian(szare_roi, cv2.CV_64F).var()
    jasnosc = float(np.mean(szare_roi))
    min_ostrosc = config["min_ostrosc"]
    min_jasnosc = config["min_jasnosc"]
    max_jasnosc = config["max_jasnosc"]
    ok = (
        ostrosc >= min_ostrosc
        and min_jasnosc <= jasnosc <= max_jasnosc
    )
    return ok, ostrosc, jasnosc


def doucz_twarz_logika(baza_twarzy, id_prac, ostatni_obrys, ostatnia_klatka_bgr, jakosc_twarzy_fn):
    try:
        if ostatni_obrys is None or ostatnia_klatka_bgr is None:
            return False

        (fx, fy, fw, fh) = ostatni_obrys
        fx = int(max(0, fx))
        fy = int(max(0, fy))
        fw = int(max(0, fw))
        fh = int(max(0, fh))

        h_img, w_img, _ = ostatnia_klatka_bgr.shape
        x2 = min(fx + fw, w_img)
        y2 = min(fy + fh, h_img)
        if x2 <= fx or y2 <= fy:
            return False

        twarz_bgr = ostatnia_klatka_bgr[fy:y2, fx:x2].copy()
        twarz_bgr = cv2.resize(twarz_bgr, (240, 240), interpolation=cv2.INTER_LINEAR)

        twarz_szara = cv2.cvtColor(twarz_bgr, cv2.COLOR_BGR2GRAY)
        ok_q, ostrosc, jasnosc = jakosc_twarzy_fn(twarz_szara)
        if not ok_q:
            return False

        baza_twarzy.dodajProbke(id_prac, twarz_bgr)
        return True
    except Exception:
        return False


def uruchom_trening_async(baza_twarzy, okno, callback_slot_name):
    def watek():
        baza_twarzy.trenuj()
        QtCore.QMetaObject.invokeMethod(
            okno,
            callback_slot_name,
            QtCore.Qt.QueuedConnection,
        )

    threading.Thread(target=watek, daemon=True).start()


def zbierz_probke_twarzy(klatka_bgr, twarze, config, jakosc_twarzy_fn):
    if not twarze:
        return False, None

    (x, y, w, h) = max(twarze, key=lambda r: r[2] * r[3])
    
    h_img, w_img = klatka_bgr.shape[:2]
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(int(x + w), w_img)
    y2 = min(int(y + h), h_img)

    if x2 <= x1 or y2 <= y1:
        return False, None

    min_rozmiar = config["min_rozmiar_twarzy"]
    if max(x2 - x1, y2 - y1) < min_rozmiar:
        return False, None

    roi_gray = cv2.cvtColor(klatka_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    if roi_gray.size == 0:
        return False, None

    roi_gray_resized = cv2.resize(roi_gray, (240, 240), interpolation=cv2.INTER_LINEAR)

    ok, ostrosc, jasnosc = jakosc_twarzy_fn(roi_gray_resized)
    if not ok:
        return False, (ostrosc, jasnosc)

    twarz_bgr = klatka_bgr[y1:y2, x1:x2].copy()
    twarz_bgr = cv2.resize(twarz_bgr, (240, 240), interpolation=cv2.INTER_LINEAR)
    
    return True, twarz_bgr
