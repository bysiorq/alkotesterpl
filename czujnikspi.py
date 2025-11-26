import spidev
import numpy as np

class Mcp3008:
    def __init__(self, magistrala: int = 0, urzadzenie: int = 0, max_czestotliwosc_hz: int = 1_000_000):
        self.spi = spidev.SpiDev()
        self.spi.open(magistrala, urzadzenie)
        self.spi.max_speed_hz = max_czestotliwosc_hz
        self.spi.mode = 0

    def czytaj(self, kanal: int) -> int:
        if kanal < 0 or kanal > 7:
            raise ValueError("MCP3008 obsługuje wyłącznie kanały 0..7")

        odpowiedz = self.spi.xfer2([1, (8 | kanal) << 4, 0])
        return ((odpowiedz[1] & 3) << 8) | odpowiedz[2]

    def zamknij(self):
        try:
            self.spi.close()
        except Exception:
            pass


class CzujnikMQ3:
    def __init__(self, adc: Mcp3008, kanal: int, promile_prog_probki: int, wspolczynnikPromile: float):
        self.adc = adc
        self.kanal = kanal
        self.promile_prog_probki = promile_prog_probki
        self.wspolczynnikPromile = wspolczynnikPromile
        self.bazowy_odczyt = None

    def kalibruj(self) -> float:
        probki = [self.adc.czytaj(self.kanal) for _ in range(self.promile_prog_probki)]
        self.bazowy_odczyt = float(np.median(probki))
        return self.bazowy_odczyt

    def pobierz(self) -> int:
        return self.adc.czytaj(self.kanal)

    def promile(self, probki):
        if probki:
            wartosc = float(np.mean(probki))
        else:
            wartosc = float(self.pobierz())

        if self.bazowy_odczyt is None:
            self.bazowy_odczyt = wartosc

        delta = max(0.0, wartosc - self.bazowy_odczyt)
        return delta / self.wspolczynnikPromile
