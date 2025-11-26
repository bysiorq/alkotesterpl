import time
import threading
import RPi.GPIO as GPIO
from konfiguracja import konfig


def inicjalizuj_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    pin_furtki = konfig["pin_furtki"]
    pin_led_zielony = konfig["pin_led_zielony"]
    pin_led_czerwony = konfig["pin_led_czerwony"]
    
    GPIO.setup(pin_furtki, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(pin_led_zielony, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(pin_led_czerwony, GPIO.OUT, initial=GPIO.LOW)


def otworz_bramke():
    pin_furtki = konfig["pin_furtki"]
    GPIO.output(pin_furtki, GPIO.HIGH)

    def impuls():
        czas_otwarcia = konfig["czas_otwarcia"]
        time.sleep(czas_otwarcia)
        GPIO.output(pin_furtki, GPIO.LOW)

    threading.Thread(target=impuls, daemon=True).start()


def dioda_led(wejscie_ok: bool):
    try:
        pin_led_zielony = konfig["pin_led_zielony"]
        pin_led_czerwony = konfig["pin_led_czerwony"]
        pin = pin_led_zielony if wejscie_ok else pin_led_czerwony
        czas_impulsu = float(konfig.get("czas_swiecenia", 2.0))
        GPIO.output(pin, GPIO.HIGH)

        def watek():
            time.sleep(czas_impulsu)
            GPIO.output(pin, GPIO.LOW)

        threading.Thread(target=watek, daemon=True).start()
    except Exception as e:
        print(f"[SPRZET] Błąd sterowania diodą LED: {e}")


def zamknij_gpio():
    try:
        GPIO.cleanup()
    except Exception as e:
        print(f"[SPRZET] Błąd czyszczenia GPIO: {e}")
