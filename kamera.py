import numpy as np
from picamera2 import Picamera2


class camera:

    def __init__(self, szer: int, wys: int, rotate_dir: str):
        import cv2 

        self.obrot = rotate_dir
        self.probkiKamera = Picamera2()

        cfg = self.probkiKamera.create_preview_configuration(
            main={"size": (szer, wys), "format": "RGB888"}
        )
        self.probkiKamera.configure(cfg)
        self.probkiKamera.start()

    def loadklatka_cam(self):
        klatka = self.probkiKamera.capture_array("main")

        if self.obrot == "cw":
            klatka = np.rot90(klatka, 3)
        elif self.obrot == "ccw":
            klatka = np.rot90(klatka, 1)
        elif self.obrot == "180":
            klatka = np.rot90(klatka, 2)
        return klatka

    def stop(self):
        try:
            self.probkiKamera.stop()
        except Exception:
            pass
