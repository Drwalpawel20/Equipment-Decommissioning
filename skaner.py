# scanner.py

import re
from typing import Callable, Optional


class BarcodeScanner:
    """
    Obsługa kodów kreskowych.

    Typowy skaner USB działa jak klawiatura:
        ST-000000787 + ENTER

    Dlatego moduł nie potrzebuje specjalnego sterownika.
    Odbiera tekst tak samo jak zwykłą klawiaturę.
    """

    def __init__(
        self,
        on_scan: Optional[Callable[[str], None]] = None
    ):
        self.on_scan = on_scan

        self._buffer = ""

    # ========================================================
    # ODBIÓR ZNAKU
    # ========================================================

    def add_char(self, char: str):
        """
        Dodaje pojedynczy znak otrzymany z klawiatury/skanera.
        """

        if not char:
            return

        # ----------------------------------------------------
        # ENTER = zakończenie skanowania
        # ----------------------------------------------------

        if char in ("\n", "\r"):

            self._finish_scan()

            return

        # ----------------------------------------------------
        # BACKSPACE
        # ----------------------------------------------------

        if char == "\b":

            self._buffer = self._buffer[:-1]

            return

        # ----------------------------------------------------
        # ZWYKŁY ZNAK
        # ----------------------------------------------------

        self._buffer += char

    # ========================================================
    # ZAKOŃCZENIE SKANU
    # ========================================================

    def _finish_scan(self):

        code = self._buffer.strip()

        self._buffer = ""

        if not code:
            return

        code = self.normalize_code(code)

        if not self.is_valid_code(code):

            print(
                f"[SCANNER] Nieprawidłowy kod: {code}"
            )

            return

        print(
            f"[SCANNER] Odczytano: {code}"
        )

        if self.on_scan:

            self.on_scan(code)

    # ========================================================
    # NORMALIZACJA
    # ========================================================

    @staticmethod
    def normalize_code(code: str) -> str:

        code = str(code)

        code = code.replace(
            "\r",
            ""
        )

        code = code.replace(
            "\n",
            ""
        )

        code = code.strip()

        return code.upper()

    # ========================================================
    # WALIDACJA
    # ========================================================

    @staticmethod
    def is_valid_code(code: str) -> bool:
        """
        Sprawdza obecny format numeru ST.

        Przykład:
            ST-000000787
        """

        return bool(
            re.fullmatch(
                r"ST-\d{9}",
                code
            )
        )


# ============================================================
# TEST MODUŁU
# ============================================================

if __name__ == "__main__":

    def scanned(code: str):

        print()
        print(
            "================================"
        )

        print(
            "ODEBRANO KOD:"
        )

        print(
            code
        )

        print(
            "================================"
        )

        print()

    scanner = BarcodeScanner(
        on_scan=scanned
    )

    print()
    print(
        "TEST SKANERA"
    )

    print(
        "Wpisz kod ST i Enter."
    )

    print(
        "Przykład: ST-000000787"
    )

    print()

    while True:

        try:

            char = input("> ")

            scanner.add_char(char)
            scanner.add_char("\n")

        except KeyboardInterrupt:

            print()
            print(
                "Zakończono."
            )

            break