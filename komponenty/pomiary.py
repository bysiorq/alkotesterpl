from konfiguracja import konfig


def odczytaj_odleglosc(adc, kanal_odleglosc):
    try:
        raw = adc.czytaj(kanal_odleglosc)
        napiecie = (raw / 1023.0) * 3.3
        if napiecie - 0.42 <= 0:
            return float("inf")
        odleglosc = 27.86 / (napiecie - 0.42)
        if odleglosc < 0 or odleglosc > 80:
            return float("inf")
        return odleglosc
    except Exception:
        return float("inf")


def odczytaj_mikrofon(adc, kanal_mikrofon, samples=32):
    try:
        n = max(1, int(samples))
        wartosci = [adc.czytaj(kanal_mikrofon) for _ in range(n)]
        min_v = min(wartosci)
        max_v = max(wartosci)
        avg = int(sum(wartosci) / len(wartosci))
        amp = max_v - min_v
        return amp, avg
    except Exception:
        return 0, 0
