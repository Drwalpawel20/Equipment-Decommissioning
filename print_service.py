# ============================================================
# print_service.py
#
# SERWIS DRUKOWANIA - ADMORA
#
# Odpowiada wyłącznie za:
#   - wykrycie domyślnej drukarki Windows
#   - drukowanie PDF
#   - obsługę liczby kopii
#   - kontrolę błędów
#
# GUI nie zajmuje się bezpośrednio drukowaniem.
# ============================================================

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


# ============================================================
# WYJĄTEK
# ============================================================

class PrintServiceError(Exception):
    """Błąd związany z drukowaniem."""
    pass


# ============================================================
# SERWIS
# ============================================================

class PrintService:

    def __init__(self):
        self.system = os.name

    # ========================================================
    # DOMYŚLNA DRUKARKA
    # ========================================================

    def get_default_printer(self) -> str:

        if self.system != "nt":
            raise PrintServiceError(
                "Serwis drukowania obsługuje obecnie Windows."
            )

        try:

            import win32print

            printer = win32print.GetDefaultPrinter()

            if not printer:
                raise PrintServiceError(
                    "Nie ustawiono domyślnej drukarki Windows."
                )

            return printer

        except ImportError:

            # ------------------------------------------------
            # Fallback bez pywin32
            # ------------------------------------------------

            try:

                result = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        (
                            "Get-CimInstance Win32_Printer "
                            "| Where-Object {$_.Default -eq $true} "
                            "| Select-Object -ExpandProperty Name"
                        )
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15
                )

                printer = result.stdout.strip()

                if printer:
                    return printer

            except Exception:
                pass

            raise PrintServiceError(
                "Nie udało się wykryć domyślnej drukarki.\n\n"
                "Zainstaluj pywin32:\n"
                "pip install pywin32"
            )

        except Exception as e:

            raise PrintServiceError(
                "Nie udało się pobrać domyślnej drukarki:\n\n"
                + str(e)
            )

    # ========================================================
    # SPRAWDZENIE PLIKU
    # ========================================================

    def validate_pdf(self, pdf_path):

        pdf_path = Path(pdf_path)

        if not pdf_path.exists():

            raise PrintServiceError(
                "Plik PDF nie istnieje:\n\n"
                + str(pdf_path)
            )

        if not pdf_path.is_file():

            raise PrintServiceError(
                "Wskazana ścieżka nie jest plikiem:\n\n"
                + str(pdf_path)
            )

        if pdf_path.suffix.lower() != ".pdf":

            raise PrintServiceError(
                "Serwis drukowania obsługuje wyłącznie pliki PDF."
            )

        if pdf_path.stat().st_size == 0:

            raise PrintServiceError(
                "Plik PDF jest pusty."
            )

        return pdf_path

    # ========================================================
    # SPRAWDZENIE DRUKARKI
    # ========================================================

    def validate_printer(self, printer_name):

        if not printer_name:
            raise PrintServiceError(
                "Nie określono drukarki."
            )

        try:

            import win32print

            handle = win32print.OpenPrinter(
                printer_name
            )

            try:

                info = win32print.GetPrinter(
                    handle,
                    2
                )

                status = info.get(
                    "Status",
                    0
                )

                # Status nie musi być 0 — część sterowników
                # używa własnych flag.
                # Sam fakt możliwości otwarcia drukarki
                # traktujemy jako wystarczający.

                return True

            finally:

                win32print.ClosePrinter(
                    handle
                )

        except ImportError:

            return True

        except Exception as e:

            raise PrintServiceError(
                "Nie można uzyskać dostępu do drukarki:\n\n"
                + printer_name
                + "\n\n"
                + str(e)
            )

    # ========================================================
    # METODA 1
    #
    # Windows ShellExecute
    # ========================================================

    def _print_shell(
        self,
        pdf_path,
        copies
    ):

        import win32api

        pdf_path = str(
            Path(pdf_path).resolve()
        )

        # ----------------------------------------------------
        # ShellExecute "print" korzysta z aplikacji
        # skojarzonej z PDF.
        #
        # Jedno wywołanie = jedna kopia.
        # ----------------------------------------------------

        for _ in range(copies):

            result = win32api.ShellExecute(
                0,
                "print",
                pdf_path,
                None,
                str(Path(pdf_path).parent),
                0
            )

            # ShellExecute zwraca wartość <= 32 w przypadku
            # błędu uruchomienia.

            if result <= 32:

                raise PrintServiceError(
                    "Windows nie zdołał uruchomić "
                    "polecenia drukowania PDF.\n\n"
                    "Kod błędu: "
                    + str(result)
                )

            # Dajemy systemowi chwilę na przekazanie zadania
            # do spoolera.
            time.sleep(1.2)

    # ========================================================
    # METODA 2
    #
    # LibreOffice jako fallback
    # ========================================================

    def _find_libreoffice(self):

        candidates = [

            shutil.which(
                "soffice"
            ),

            shutil.which(
                "libreoffice"
            ),

            r"C:\Program Files\LibreOffice\program\soffice.exe",

            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",

        ]

        for candidate in candidates:

            if not candidate:
                continue

            path = Path(candidate)

            if path.exists():

                return str(path)

        return None

    def _print_libreoffice(
        self,
        pdf_path,
        printer_name,
        copies
    ):

        libreoffice = self._find_libreoffice()

        if not libreoffice:

            raise PrintServiceError(
                "Nie znaleziono LibreOffice."
            )

        pdf_path = str(
            Path(pdf_path).resolve()
        )

        # ----------------------------------------------------
        # LibreOffice:
        #
        # --pt "drukarka" plik
        #
        # Drukowanie wykonujemy osobno dla każdej kopii,
        # aby zachować działanie niezależnie od sterownika.
        # ----------------------------------------------------

        for _ in range(copies):

            command = [

                libreoffice,

                "--headless",

                "--pt",
                printer_name,

                pdf_path,

            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:

                raise PrintServiceError(
                    "LibreOffice nie zdołał wydrukować dokumentu.\n\n"
                    + result.stdout
                    + "\n"
                    + result.stderr
                )

            time.sleep(1)

    # ========================================================
    # GŁÓWNA METODA DRUKOWANIA
    # ========================================================

    def print_pdf(
        self,
        pdf_path,
        copies=2
    ):

        pdf_path = self.validate_pdf(
            pdf_path
        )

        try:

            copies = int(copies)

        except (
            ValueError,
            TypeError
        ):

            copies = 2

        copies = max(
            1,
            min(
                copies,
                99
            )
        )

        # ----------------------------------------------------
        # Domyślna drukarka
        # ----------------------------------------------------

        printer_name = (
            self.get_default_printer()
        )

        self.validate_printer(
            printer_name
        )

        # ----------------------------------------------------
        # Najpierw pywin32 / ShellExecute
        # ----------------------------------------------------

        try:

            import win32api

            self._print_shell(
                pdf_path,
                copies
            )

            return {
                "success": True,
                "printer": printer_name,
                "copies": copies,
                "method": "Windows ShellExecute"
            }

        except ImportError:

            pass

        except Exception as shell_error:

            # ------------------------------------------------
            # Jeżeli ShellExecute nie zadziała,
            # próbujemy LibreOffice.
            # ------------------------------------------------

            try:

                self._print_libreoffice(
                    pdf_path,
                    printer_name,
                    copies
                )

                return {
                    "success": True,
                    "printer": printer_name,
                    "copies": copies,
                    "method": "LibreOffice"
                }

            except Exception as libre_error:

                raise PrintServiceError(
                    "Nie udało się wydrukować dokumentu.\n\n"
                    "Drukarka:\n"
                    + printer_name
                    + "\n\n"
                    "Błąd Windows:\n"
                    + str(shell_error)
                    + "\n\n"
                    "Błąd LibreOffice:\n"
                    + str(libre_error)
                )

        # ----------------------------------------------------
        # Brak pywin32
        # ----------------------------------------------------

        try:

            self._print_libreoffice(
                pdf_path,
                printer_name,
                copies
            )

            return {
                "success": True,
                "printer": printer_name,
                "copies": copies,
                "method": "LibreOffice"
            }

        except Exception as e:

            raise PrintServiceError(
                "Nie udało się wydrukować dokumentu.\n\n"
                "Drukarka:\n"
                + printer_name
                + "\n\n"
                + str(e)
            )


# ============================================================
# FUNKCJA POMOCNICZA
# ============================================================

def print_pdf(
    pdf_path,
    copies=2
):

    service = PrintService()

    return service.print_pdf(
        pdf_path,
        copies
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "ADMORA - PRINT SERVICE"
    )

    print(
        "========================================"
    )

    try:

        service = PrintService()

        printer = (
            service.get_default_printer()
        )

        print(
            "Domyślna drukarka:"
        )

        print(
            printer
        )

    except Exception as e:

        print(
            "BŁĄD:"
        )

        print(
            e
        )