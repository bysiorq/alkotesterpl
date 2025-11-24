import numpy as np
from picamera2 import Picamera2


class Kamera:

    def __init__(self, szer: int, wys: int, kierunekObrotu: str):
        import cv2 

        self.kierunekObrotu = kierunekObrotu
        self.probkiKamera = Picamera2()

        cfg = self.probkiKamera.create_preview_configuration(
            main={"size": (szer, wys), "format": "RGB888"}
        )
        self.probkiKamera.configure(cfg)
        self.probkiKamera.start()

    def wez_klatke(self):
        klatka = self.probkiKamera.capture_array("main")

        if self.kierunekObrotu == "cw":
            klatka = np.rot90(klatka, 3)
        elif self.kierunekObrotu == "ccw":
            klatka = np.rot90(klatka, 1)
        elif self.kierunekObrotu == "180":
            klatka = np.rot90(klatka, 2)
        return klatka

    def stop(self):
        try:
            self.probkiKamera.stop()
        except Exception:
            pass
