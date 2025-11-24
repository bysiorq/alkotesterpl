import cv2


def kadr_zoom_przyciecie(img, target_w, target_h):
    """Przycina i skaluje obraz do docelowych wymiarów zachowując proporcje."""
    if img is None or target_w <= 0 or target_h <= 0:
        return None

    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return None

    proporcja_zrodlo = w / float(h)
    proporcja_cel = target_w / float(target_h)

    if proporcja_zrodlo > proporcja_cel:
        nowe_w = int(h * proporcja_cel)
        if nowe_w <= 0:
            return None
        x1 = max(0, (w - nowe_w) // 2)
        x2 = x1 + nowe_w
        przyciete = img[:, x1:x2]
    else:
        nowe_h = int(w / proporcja_cel)
        if nowe_h <= 0:
            return None
        y1 = max(0, (h - nowe_h) // 2)
        y2 = y1 + nowe_h
        przyciete = img[y1:y2, :]

    if przyciete.size == 0:
        return None

    zmienione = cv2.resize(
        przyciete, (int(target_w), int(target_h)), interpolation=cv2.INTER_AREA
    )
    return zmienione


def ustaw_komunikat(okno, tekst_gora, tekst_srodek=None, color="white", use_center=True):
    """Ustawia tekst komunikatu w interfejsie."""
    if color == "green":
        kolor_css = "#00ff00"
    elif color == "red":
        kolor_css = "#ff4444"
    else:
        kolor_css = "white"

    okno.etykieta_gora.setText(tekst_gora)
    okno.etykieta_gora.setStyleSheet(
        f"color:{kolor_css}; font-size:28px; font-weight:600;"
    )
    if use_center:
        okno.etykieta_srodek.setText(tekst_srodek or "")
        okno.etykieta_srodek.setStyleSheet(
            f"color:{kolor_css}; font-size:36px; font-weight:700;"
        )
        if hasattr(okno, "stos_srodek"):
            okno.stos_srodek.setCurrentWidget(okno.etykieta_srodek)


def pokaz_guziki(okno, primary_text=None, secondary_text=None):
    """Pokazuje/ukrywa przyciski interfejsu."""
    if primary_text is None:
        okno.guzik_glowny.hide()
    else:
        okno.guzik_glowny.setText(primary_text)
        okno.guzik_glowny.show()

    if secondary_text is None:
        okno.guzik_pomocniczy.hide()
    else:
        okno.guzik_pomocniczy.setText(secondary_text)
        okno.guzik_pomocniczy.show()
