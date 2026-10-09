
# ============================================================
# GENERATOR ORZECZEŃ TECHNICZNYCH
#
# Współpracuje z:
#     database_service.py
#
# Dane są pobierane wyłącznie z bazy ADMORA.
# DatabaseService działa w trybie READ ONLY.
# ============================================================

import re
import shutil
from pathlib import Path
from datetime import datetime

from odf.opendocument import load

from database import (
    DatabaseService,
    DatabaseServiceError,
    AssetNotFoundError,
)


# ============================================================
# KONFIGURACJA
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

TEMPLATE_PATH = (
    PROJECT_DIR / "szablon_orzeczenie.odt"
)

OUTPUT_DIR = (
    PROJECT_DIR / "orzeczenia"
)

CURRENT_YEAR = datetime.now().year


# ============================================================
# CZYSZCZENIE
# ============================================================

def clean(value):
    """
    Zamienia wartość na bezpieczny tekst.
    """

    if value is None:
        return ""

    value = str(value)

    value = value.replace(
        "\xa0",
        " "
    )

    value = value.replace(
        "\r\n",
        "\n"
    )

    value = value.replace(
        "\r",
        "\n"
    )

    value = re.sub(
        r"[ \t]+",
        " ",
        value
    )

    value = re.sub(
        r"\n[ \t]+",
        "\n",
        value
    )

    return value.strip()


# ============================================================
# BEZPIECZNA NAZWA PLIKU
# ============================================================

def safe_filename(value):

    value = clean(value)

    value = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        value
    )

    value = value.strip(" .")

    if not value:
        return "orzeczenie"

    return value


# ============================================================
# EKSPLOATACJA
# ============================================================

def calculate_exploitation(year):

    year = clean(year)

    if not year:
        return ""

    try:

        production_year = int(
            float(year)
        )

    except (
        ValueError,
        TypeError
    ):

        return ""

    if not (
        1900
        <= production_year
        <= CURRENT_YEAR
    ):

        return ""

    return str(
        CURRENT_YEAR
        - production_year
    )


# ============================================================
# PASZPORT
# ============================================================

def format_passport(value):

    value = clean(value)

    if not value:
        return ""

    if value.lower().startswith(
        "paszport"
    ):

        return " - " + value

    return " - Paszport " + value


# ============================================================
# KOMPONENTY - NAZWA DO {comp}
# ============================================================

def format_components_name(
    components
):

    if not components:
        return ""

    names = []

    for component in components:

        # ----------------------------------------------------
        # ComponentData
        # ----------------------------------------------------

        if hasattr(
            component,
            "name"
        ):

            name = clean(
                component.name
            )

        # ----------------------------------------------------
        # Dodatkowa obsługa słownika
        # ----------------------------------------------------

        elif isinstance(
            component,
            dict
        ):

            name = clean(
                component.get(
                    "name",
                    component.get(
                        "nazwa",
                        ""
                    )
                )
            )

        else:

            name = clean(
                component
            )

        if name:

            names.append(
                name
            )

    if not names:
        return ""

    return (
        " + "
        + " + ".join(names)
    )


# ============================================================
# KOMPONENTY - NAZWA + KOD
# ============================================================

def format_components_full(
    components
):

    if not components:
        return ""

    result = []

    for component in components:

        # ----------------------------------------------------
        # ComponentData
        # ----------------------------------------------------

        if hasattr(
            component,
            "name"
        ):

            name = clean(
                component.name
            )

            code = clean(
                component.code
            )

        # ----------------------------------------------------
        # Dodatkowa obsługa słownika
        # ----------------------------------------------------

        elif isinstance(
            component,
            dict
        ):

            name = clean(
                component.get(
                    "name",
                    component.get(
                        "nazwa",
                        ""
                    )
                )
            )

            code = clean(
                component.get(
                    "code",
                    component.get(
                        "kod",
                        component.get(
                            "st",
                            component.get(
                                "st_num_inv",
                                component.get(
                                    "kod_inwentarzowy",
                                    ""
                                )
                            )
                        )
                    )
                )
            )

        else:

            continue

        if not name:
            continue

        if code:

            result.append(
                f"{name} {code}"
            )

        else:

            result.append(
                name
            )

    if not result:
        return ""

    return "\n".join(
        result
    )


# ============================================================
# PASZPORT
# ============================================================

def get_passport(asset):

    """
    database_service.py nie posiada obecnie pola passport
    w AssetData.

    Dlatego pozostawiamy puste pole, dopóki nie zostanie
    dodane pobieranie paszportu z bazy.
    """

    if hasattr(
        asset,
        "passport"
    ):

        return clean(
            asset.passport
        )

    return ""


# ============================================================
# PRZYGOTOWANIE DANYCH DO SZABLONU
# ============================================================

def prepare_template_data(
    asset
):

    # --------------------------------------------------------
    # MIEJSCE
    # --------------------------------------------------------

    miejsce = clean(
        getattr(
            asset,
            "location_name",
            ""
        )
    )

    # --------------------------------------------------------
    # NAZWA
    # --------------------------------------------------------

    nazwa = clean(
        getattr(
            asset,
            "name",
            ""
        )
    )

    # --------------------------------------------------------
    # NR FABRYCZNY
    # --------------------------------------------------------

    num_fab = clean(
        getattr(
            asset,
            "serial_number",
            ""
        )
    )

    # --------------------------------------------------------
    # NUMER INWENTARZOWY ST
    # --------------------------------------------------------

    st_num_inv = clean(
        getattr(
            asset,
            "code",
            ""
        )
    )

    # --------------------------------------------------------
    # PRODUCENT
    # --------------------------------------------------------

    brand = clean(
        getattr(
            asset,
            "manufacturer",
            ""
        )
    )

    # --------------------------------------------------------
    # MODEL
    #
    # Obecny szablon nie ma placeholdera {model},
    # ale pobieramy go z bazy i można go później dodać.
    # --------------------------------------------------------

    model = clean(
        getattr(
            asset,
            "model",
            ""
        )
    )

    # --------------------------------------------------------
    # ROK PRODUKCJI
    # --------------------------------------------------------

    production_year = getattr(
        asset,
        "production_year",
        None
    )

    time = clean(
        production_year
    )

    # --------------------------------------------------------
    # PASZPORT
    # --------------------------------------------------------

    passport = get_passport(
        asset
    )

    # --------------------------------------------------------
    # KOMPONENTY
    # --------------------------------------------------------

    components = getattr(
        asset,
        "components",
        []
    )

    # --------------------------------------------------------
    # FORMATOWANIE
    # --------------------------------------------------------

    passport_text = format_passport(
        passport
    )

    components_name = (
        format_components_name(
            components
        )
    )

    components_full = (
        format_components_full(
            components
        )
    )

    # --------------------------------------------------------
    # EKSPLOATACJA
    # --------------------------------------------------------

    exploitation = (
        calculate_exploitation(
            time
        )
    )

    # --------------------------------------------------------
    # WYNIK
    # --------------------------------------------------------

    return {

        "miejsce":
            miejsce,

        "nazwa":
            nazwa,

        "paszport":
            passport_text,

        "comp":
            components_name,

        "num_fab":
            num_fab,

        "st_num_inv":
            st_num_inv,

        "if_iscomp":
            components_full,

        "brand":
            brand,

        "model":
            model,

        "time":
            time,

        "curr_time-time":
            exploitation,

    }


# ============================================================
# PODMIANA PLACEHOLDERÓW W TEKŚCIE
# ============================================================

def replace_placeholders_in_text(
    text,
    replacements
):

    if not text:
        return text

    result = text

    for key, value in replacements.items():

        result = result.replace(
            "{" + key + "}",
            str(value)
        )

    return result


# ============================================================
# PODMIANA W WĘZŁACH XML
# ============================================================

def replace_all_text_nodes(
    document,
    replacements
):

    changed = False

    def walk(element):

        nonlocal changed

        if not hasattr(
            element,
            "childNodes"
        ):

            return

        for child in list(
            element.childNodes
        ):

            # ------------------------------------------------
            # WĘZEŁ TEKSTOWY
            # ------------------------------------------------

            if getattr(
                child,
                "nodeType",
                None
            ) == child.TEXT_NODE:

                old_text = child.data

                new_text = (
                    replace_placeholders_in_text(
                        old_text,
                        replacements
                    )
                )

                if new_text != old_text:

                    child.data = new_text

                    changed = True

            else:

                walk(
                    child
                )

    # --------------------------------------------------------
    # TEKST DOKUMENTU
    # --------------------------------------------------------

    if hasattr(
        document,
        "text"
    ):

        walk(
            document.text
        )

    # --------------------------------------------------------
    # BODY
    # --------------------------------------------------------

    if hasattr(
        document,
        "body"
    ):

        walk(
            document.body
        )

    # --------------------------------------------------------
    # STYLES
    # --------------------------------------------------------

    if hasattr(
        document,
        "styles"
    ):

        walk(
            document.styles
        )

    return changed


# ============================================================
# GENEROWANIE DOKUMENTU
# ============================================================

def generate_document(
    asset,
    number
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    data = prepare_template_data(
        asset
    )

    st_number = data[
        "st_num_inv"
    ]

    # --------------------------------------------------------
    # NAZWA PLIKU
    # --------------------------------------------------------

    if st_number:

        filename = (
            safe_filename(
                st_number
            )
            + "_orzeczenie.odt"
        )

    else:

        filename = (
            f"orzeczenie_{number:04d}.odt"
        )

    output_path = (
        OUTPUT_DIR / filename
    )

    # --------------------------------------------------------
    # KOPIA SZABLONU
    # --------------------------------------------------------

    shutil.copy2(
        TEMPLATE_PATH,
        output_path
    )

    # --------------------------------------------------------
    # OTWARCIE ODT
    # --------------------------------------------------------

    document = load(
        str(output_path)
    )

    # --------------------------------------------------------
    # PLACEHOLDERY
    # --------------------------------------------------------

    replacements = {

        "miejsce":
            data["miejsce"],

        "nazwa":
            data["nazwa"],

        "paszport":
            data["paszport"],

        "comp":
            data["comp"],

        "num_fab":
            data["num_fab"],

        "st_num_inv":
            data["st_num_inv"],

        "if_iscomp":
            data["if_iscomp"],

        "brand":
            data["brand"],

        "model":
            data["model"],

        "time":
            data["time"],

        "curr_time-time":
            data["curr_time-time"],

    }

    # --------------------------------------------------------
    # PODMIANA
    # --------------------------------------------------------

    replace_all_text_nodes(
        document,
        replacements
    )

    # --------------------------------------------------------
    # ZAPIS
    # --------------------------------------------------------

    document.save(
        str(output_path)
    )

    return (
        output_path,
        data
    )


# ============================================================
# WYŚWIETLANIE DANYCH
# ============================================================

def print_asset(
    asset,
    data
):

    print()
    print(
        "-" * 70
    )

    print(
        "Typ:",
        getattr(
            asset,
            "code_type",
            "ST"
        )
    )

    print(
        "ST:",
        data["st_num_inv"]
    )

    print(
        "Miejsce:",
        data["miejsce"]
    )

    print(
        "Nazwa:",
        data["nazwa"]
    )

    print(
        "Producent:",
        data["brand"]
    )

    print(
        "Model:",
        data["model"]
    )

    print(
        "Nr fabryczny:",
        data["num_fab"]
    )

    print(
        "Rok:",
        data["time"]
    )

    print(
        "Eksploatacja:",
        data["curr_time-time"]
    )

    print(
        "Paszport:",
        data["paszport"]
    )

    print()

    if data["if_iscomp"]:

        print(
            "KOMPONENTY:"
        )

        for line in data[
            "if_iscomp"
        ].splitlines():

            print(
                " ",
                line
            )

    else:

        print(
            "KOMPONENTY: brak"
        )

    print(
        "-" * 70
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "GENERATOR ORZECZEŃ TECHNICZNYCH"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # SZABLON
    # --------------------------------------------------------

    if not TEMPLATE_PATH.exists():

        print()
        print(
            "BŁĄD:"
        )

        print(
            "Nie znaleziono szablonu:"
        )

        print(
            TEMPLATE_PATH
        )

        input(
            "\nNaciśnij Enter..."
        )

        return

    # --------------------------------------------------------
    # DATABASE SERVICE
    # --------------------------------------------------------

    database = DatabaseService()

    # --------------------------------------------------------
    # POŁĄCZENIE
    # --------------------------------------------------------

    print()
    print(
        "Łączenie z bazą ADMORA..."
    )

    try:

        database.connect()

        if database.test_connection():

            print(
                "Połączenie z bazą: OK"
            )

            print(
                "Tryb: READ ONLY"
            )

        else:

            print(
                "BŁĄD: test połączenia nie powiódł się."
            )

            database.disconnect()

            input(
                "\nNaciśnij Enter..."
            )

            return

    except DatabaseServiceError as e:

        print()
        print(
            "BŁĄD POŁĄCZENIA:"
        )

        print(e)

        database.disconnect()

        input(
            "\nNaciśnij Enter..."
        )

        return

    # --------------------------------------------------------
    # TRYB GENEROWANIA
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )

    print(
        "TRYB GENEROWANIA"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "Wpisz kod ST."
    )

    print(
        "Możesz np. zeskanować:"
    )

    print(
        "ST-000000787"
    )

    print()

    code = input(
        "Kod: "
    ).strip()

    if not code:

        print(
            "Nie podano kodu."
        )

        database.disconnect()

        input(
            "\nNaciśnij Enter..."
        )

        return

    # --------------------------------------------------------
    # ODCZYT Z BAZY
    # --------------------------------------------------------

    try:

        asset = database.get_by_code(
            code
        )

    except AssetNotFoundError as e:

        print()
        print(
            "NIE ZNALEZIONO:"
        )

        print(e)

        database.disconnect()

        input(
            "\nNaciśnij Enter..."
        )

        return

    except DatabaseServiceError as e:

        print()
        print(
            "BŁĄD ODCZYTU BAZY:"
        )

        print(e)

        database.disconnect()

        input(
            "\nNaciśnij Enter..."
        )

        return

    except Exception as e:

        print()
        print(
            "NIEOCZEKIWANY BŁĄD:"
        )

        print(e)

        database.disconnect()

        input(
            "\nNaciśnij Enter..."
        )

        return

    # --------------------------------------------------------
    # PRZYGOTOWANIE DANYCH
    # --------------------------------------------------------

    data = prepare_template_data(
        asset
    )

    # --------------------------------------------------------
    # PODGLĄD
    # --------------------------------------------------------

    print_asset(
        asset,
        data
    )

    print()
    print(
        "=" * 70
    )

    print(
        "DANE DO SZABLONU"
    )

    print(
        "=" * 70
    )

    for key, value in data.items():

        print(
            f"{key:<20} = {value}"
        )

    # --------------------------------------------------------
    # GENEROWANIE
    # --------------------------------------------------------

    print()
    print(
        "Generowanie dokumentu..."
    )

    try:

        output_path, data = (
            generate_document(
                asset,
                1
            )
        )

    except Exception as e:

        print()
        print(
            "BŁĄD GENEROWANIA:"
        )

        print(e)

        database.disconnect()

        input(
            "\nNaciśnij Enter..."
        )

        return

    # --------------------------------------------------------
    # ROZŁĄCZENIE
    # --------------------------------------------------------

    database.disconnect()

    # --------------------------------------------------------
    # GOTOWE
    # --------------------------------------------------------

    print()
    print(
        "Dokument wygenerowany poprawnie."
    )

    print()
    print(
        "Plik:"
    )

    print(
        output_path
    )

    print()
    print(
        "=" * 70
    )

    print(
        "GOTOWE"
    )

    print(
        "=" * 70
    )

    input(
        "\nNaciśnij Enter..."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()

