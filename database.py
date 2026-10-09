# ============================================================
# database_service.py
#
# Odczyt danych z bazy ADMORA.
#
# WAŻNE:
# Moduł jest przeznaczony WYŁĄCZNIE DO ODCZYTU.
#
# Nie wykonuje:
#   INSERT
#   UPDATE
#   DELETE
#   CREATE
#   DROP
#   ALTER
#   TRUNCATE
#
# Dodatkowo połączenie PostgreSQL jest ustawiane jako
# READ ONLY.
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import psycopg2
from psycopg2 import Error
import os
from dotenv import load_dotenv
load_dotenv()



# ============================================================
# KONFIGURACJA
# ============================================================

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ============================================================
# CZAS EKSPLOATACJI
# ============================================================

CURRENT_YEAR = 2026


# ============================================================
# MODELE DANYCH
# ============================================================

@dataclass
class ComponentData:

    code: str

    component_type: str

    name: str

    manufacturer: str = ""

    model: str = ""

    serial_number: str = ""

    version: str = ""

    additional_info: str = ""


@dataclass
class AssetData:

    code: str

    code_type: str

    name: str

    manufacturer: str = ""

    model: str = ""

    serial_number: str = ""

    production_year: Optional[int] = None

    location_code: str = ""

    location_name: str = ""

    active: bool = True

    components: list[ComponentData] = field(
        default_factory=list
    )

    @property
    def exploitation_years(self) -> Optional[int]:

        if self.production_year is None:
            return None

        if self.production_year < 1900:
            return None

        if self.production_year > CURRENT_YEAR:
            return None

        return (
            CURRENT_YEAR
            - self.production_year
        )


# ============================================================
# BŁĘDY
# ============================================================

class DatabaseServiceError(Exception):
    """
    Błąd związany z obsługą bazy danych.
    """
    pass


class AssetNotFoundError(DatabaseServiceError):
    """
    Nie znaleziono kodu.
    """
    pass


# ============================================================
# DATABASE SERVICE
# ============================================================

class DatabaseService:

    def __init__(
        self,
        host: str = DB_HOST,
        port: int = DB_PORT,
        database: str = DB_NAME,
        user: str = DB_USER,
        password: str = DB_PASSWORD,
    ):

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

        self.connection = None

    # ========================================================
    # POŁĄCZENIE
    # ========================================================

    def connect(self):

        if self.connection is not None:

            if not self.connection.closed:
                return

        try:

            self.connection = psycopg2.connect(

                host=self.host,

                port=self.port,

                database=self.database,

                user=self.user,

                password=self.password,

            )

            # ------------------------------------------------
            # NAJWAŻNIEJSZE ZABEZPIECZENIE
            # ------------------------------------------------

            cursor = self.connection.cursor()

            cursor.execute(
                "SET SESSION CHARACTERISTICS "
                "AS TRANSACTION READ ONLY"
            )

            cursor.close()

            self.connection.commit()

        except Error as e:

            self.connection = None

            raise DatabaseServiceError(
                "Nie można połączyć się z bazą ADMORA.\n"
                f"Szczegóły: {e}"
            ) from e

    # ========================================================
    # ROZŁĄCZENIE
    # ========================================================

    def disconnect(self):

        if self.connection is not None:

            try:

                self.connection.close()

            finally:

                self.connection = None

    # ========================================================
    # SPRAWDZENIE POŁĄCZENIA
    # ========================================================

    def is_connected(self) -> bool:

        return (
            self.connection is not None
            and not self.connection.closed
        )

    # ========================================================
    # ROZPOZNANIE TYPU KODU
    # ========================================================

    @staticmethod
    def detect_code_type(code: str) -> str:

        code = code.strip().upper()

        # ----------------------------------------------
        # ST-K
        # ----------------------------------------------

        if re.fullmatch(
            r"ST-K-\d+",
            code
        ):

            return "ST-K"

        # ----------------------------------------------
        # STW
        # ----------------------------------------------

        if re.fullmatch(
            r"STW-\d+",
            code
        ):

            return "STW"

        # ----------------------------------------------
        # ST
        # ----------------------------------------------

        if re.fullmatch(
            r"ST-\d+",
            code
        ):

            return "ST"

        return "UNKNOWN"

    # ========================================================
    # NORMALIZACJA KODU
    # ========================================================

    @staticmethod
    def normalize_code(code: str) -> str:

        if code is None:
            return ""

        code = str(code)

        code = code.replace(
            "\r",
            ""
        )

        code = code.replace(
            "\n",
            ""
        )

        return code.strip().upper()

    # ========================================================
    # POBRANIE ŚRODKA TRWAŁEGO
    # ========================================================

    def _get_fixed_asset(
        self,
        code: str
    ) -> AssetData:

        if not self.is_connected:
            self.connect()

        cursor = self.connection.cursor()

        try:

            cursor.execute(
                """
                SELECT

                    fa.inventory_number,

                    fa.name,

                    fa.manufacturer,

                    fa.model,

                    fa.serial_number,

                    fa.production_year,

                    fa.active,

                    l.code,

                    l.name

                FROM fixed_assets fa

                LEFT JOIN locations l
                    ON l.id = fa.location_id

                WHERE
                    fa.inventory_number = %s

                LIMIT 1
                """,

                (code,)
            )

            row = cursor.fetchone()

        except Error as e:

            raise DatabaseServiceError(
                "Błąd podczas pobierania środka trwałego.\n"
                f"Szczegóły: {e}"
            ) from e

        finally:

            cursor.close()

        if row is None:

            raise AssetNotFoundError(
                f"Nie znaleziono środka trwałego: {code}"
            )

        (
            inventory_number,
            name,
            manufacturer,
            model,
            serial_number,
            production_year,
            active,
            location_code,
            location_name,

        ) = row

        return AssetData(

            code=inventory_number,

            code_type="ST",

            name=name or "",

            manufacturer=manufacturer or "",

            model=model or "",

            serial_number=serial_number or "",

            production_year=production_year,

            location_code=location_code or "",

            location_name=location_name or "",

            active=bool(active),

        )

    # ========================================================
    # KOMPONENTY ŚRODKA TRWAŁEGO
    # ========================================================

    def _get_components(
        self,
        asset_code: str
    ) -> list[ComponentData]:

        cursor = self.connection.cursor()

        try:

            cursor.execute(
                """
                SELECT

                    c.inventory_number,

                    c.component_type,

                    c.name,

                    c.manufacturer,

                    c.model,

                    c.serial_number,

                    c.version,

                    c.additional_info

                FROM components c

                INNER JOIN asset_components ac
                    ON ac.component_id = c.id

                INNER JOIN fixed_assets fa
                    ON fa.id = ac.asset_id

                WHERE

                    fa.inventory_number = %s

                    AND c.active = TRUE

                ORDER BY
                    c.inventory_number
                """,

                (asset_code,)
            )

            rows = cursor.fetchall()

        except Error as e:

            raise DatabaseServiceError(
                "Błąd podczas pobierania komponentów.\n"
                f"Szczegóły: {e}"
            ) from e

        finally:

            cursor.close()

        components = []

        for row in rows:

            (
                code,
                component_type,
                name,
                manufacturer,
                model,
                serial_number,
                version,
                additional_info,

            ) = row

            components.append(

                ComponentData(

                    code=code or "",

                    component_type=(
                        component_type or ""
                    ),

                    name=name or "",

                    manufacturer=(
                        manufacturer or ""
                    ),

                    model=model or "",

                    serial_number=(
                        serial_number or ""
                    ),

                    version=version or "",

                    additional_info=(
                        additional_info or ""
                    ),
                )
            )

        return components

    # ========================================================
    # POBRANIE DANYCH PO KODZIE
    # ========================================================

    def get_by_code(
        self,
        code: str
    ) -> AssetData:

        code = self.normalize_code(code)

        if not code:

            raise DatabaseServiceError(
                "Kod jest pusty."
            )

        code_type = self.detect_code_type(
            code
        )

        # ----------------------------------------------------
        # ST
        # ----------------------------------------------------

        if code_type == "ST":

            asset = self._get_fixed_asset(
                code
            )

            asset.components = (
                self._get_components(
                    code
                )
            )

            return asset

        # ----------------------------------------------------
        # ST-K
        # ----------------------------------------------------

        if code_type == "ST-K":

            raise DatabaseServiceError(
                "Zeskanowano komponent "
                f"{code}.\n\n"
                "Na tym etapie moduł oczekuje "
                "głównego środka trwałego ST."
            )

        # ----------------------------------------------------
        # STW
        # ----------------------------------------------------

        if code_type == "STW":

            raise DatabaseServiceError(
                "Rozpoznano kod STW:\n"
                f"{code}\n\n"
                "Obsługa tabeli STW zostanie "
                "dodana po określeniu jej struktury."
            )

        # ----------------------------------------------------
        # NIEZNANY
        # ----------------------------------------------------

        raise DatabaseServiceError(
            "Nieznany typ kodu:\n"
            f"{code}"
        )

    # ========================================================
    # TEST POŁĄCZENIA
    # ========================================================

    def test_connection(self) -> bool:

        self.connect()

        cursor = self.connection.cursor()

        try:

            cursor.execute(
                "SELECT 1"
            )

            result = cursor.fetchone()

            return (
                result is not None
                and result[0] == 1
            )

        except Error as e:

            raise DatabaseServiceError(
                "Test połączenia nie powiódł się.\n"
                f"Szczegóły: {e}"
            ) from e

        finally:

            cursor.close()


# ============================================================
# TEST MODUŁU
# ============================================================

if __name__ == "__main__":

    database = DatabaseService()

    try:

        print()
        print("=" * 60)
        print("TEST DATABASE SERVICE")
        print("=" * 60)

        # ----------------------------------------------------
        # POŁĄCZENIE
        # ----------------------------------------------------

        database.connect()

        print(
            "Połączenie z bazą: OK"
        )

        # ----------------------------------------------------
        # TEST KODU
        # ----------------------------------------------------

        test_code = "ST-000000787"

        print()
        print(
            "Szukam:",
            test_code
        )

        data = database.get_by_code(
            test_code
        )

        print()
        print(
            "ZNALEZIONO"
        )

        print(
            "-" * 60
        )

        print(
            "Typ:",
            data.code_type
        )

        print(
            "ST:",
            data.code
        )

        print(
            "Nazwa:",
            data.name
        )

        print(
            "Producent:",
            data.manufacturer
        )

        print(
            "Model:",
            data.model
        )

        print(
            "Nr fabryczny:",
            data.serial_number
        )

        print(
            "Miejsce:",
            data.location_name
        )

        print(
            "Rok produkcji:",
            data.production_year
        )

        print(
            "Czas eksploatacji:",
            data.exploitation_years
        )

        print()
        print(
            "KOMPONENTY:"
        )

        for component in data.components:

            print()
            print(
                "  Kod:",
                component.code
            )

            print(
                "  Typ:",
                component.component_type
            )

            print(
                "  Nazwa:",
                component.name
            )

            print(
                "  Producent:",
                component.manufacturer
            )

            print(
                "  Model:",
                component.model
            )

            print(
                "  Wersja:",
                component.version
            )

        print()
        print("=" * 60)

    except AssetNotFoundError as e:

        print(
            "NIE ZNALEZIONO:"
        )

        print(e)

    except DatabaseServiceError as e:

        print(
            "BŁĄD:"
        )

        print(e)

    finally:

        database.disconnect()


