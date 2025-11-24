from PyQt5 import QtCore, QtWidgets


class Pin_okno(QtWidgets.QDialog):
    def __init__(self, parent=None, title="Wprowadź PIN"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)

        # brak ramki, ciemne tło
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog
        )
        self.setStyleSheet("background-color: rgba(0,0,0,210); color: white;")

        self.value = ""   # zapamiętany PIN

        # Layout główny
        uklad_glowny = QtWidgets.QVBoxLayout(self)
        uklad_glowny.setContentsMargins(16, 16, 16, 16)
        uklad_glowny.setSpacing(12)

        # Pasek tytułu + X
        pasek_gora = QtWidgets.QHBoxLayout()
        etykieta_tytul = QtWidgets.QLabel(title)
        etykieta_tytul.setAlignment(QtCore.Qt.AlignCenter)
        etykieta_tytul.setStyleSheet("font-size:28px; font-weight:600; color:white;")

        przycisk_zamknij = QtWidgets.QPushButton("X")
        przycisk_zamknij.setFixedSize(48, 48)
        przycisk_zamknij.setStyleSheet(
            "font-size:24px; font-weight:700; border-radius:12px; background:#550000; color:white;"
        )
        przycisk_zamknij.clicked.connect(self.zamknijOkno)

        pasek_gora.addWidget(etykieta_tytul, 1)
        pasek_gora.addWidget(przycisk_zamknij, 0, QtCore.Qt.AlignRight)
        uklad_glowny.addLayout(pasek_gora)

        # Pole PIN
        self.edit = QtWidgets.QLineEdit()
        self.edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.edit.setAlignment(QtCore.Qt.AlignCenter)
        self.edit.setFixedHeight(60)
        self.edit.setStyleSheet(
            "font-size:32px; padding:8px; border-radius:12px; background:#222; color:white;"
        )
        uklad_glowny.addWidget(self.edit)

        # Klawiatura numeryczna
        siatka = QtWidgets.QGridLayout()
        siatka.setSpacing(8)
        styl_przyc = (
            "font-size:26px; padding:16px; border-radius:16px; background:#333; color:white;"
        )

        klawisze = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("←", 3, 0), ("0", 3, 1), ("OK", 3, 2),
        ]

        for tekst, wiersz, kol in klawisze:
            przycisk = QtWidgets.QPushButton(tekst)
            przycisk.setStyleSheet(styl_przyc)
            przycisk.clicked.connect(lambda _, x=tekst: self.przycisk_klikniety(x))
            siatka.addWidget(przycisk, wiersz, kol)

        uklad_glowny.addLayout(siatka)

        self.resize(460, 640)


    def przycisk_klikniety(self, t: str):
        if t == "OK":
            self.accept()
        elif t == "←":
            self.edit.setText(self.edit.text()[:-1])
        else:
            self.edit.setText(self.edit.text() + t)

    def accept(self):
        self.value = self.edit.text()
        super().accept()

    def zamknijOkno(self):
        self.value = ""
        super().reject()

    def cyfryPin(self) -> str:
        return self.value
