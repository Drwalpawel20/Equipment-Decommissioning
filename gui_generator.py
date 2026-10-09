# ============================================================
# gui_generator.py
#
# ADMORA
# GENERATOR ORZECZEŃ TECHNICZNYCH
#
# GUI:
#   - Tkinter
#   - logowanie
#   - fullscreen
#   - minimalizowanie
#   - zamykanie przez X
#   - skanowanie kodów ST
#   - ręczne wpisywanie kodu
#   - READ ONLY
#   - pobieranie danych z ADMORA
#   - automatyczna klasyfikacja urządzenia
#   - automatyczny wybór szablonu
#   - własne obiekty do kasacji z własnym szablonem
#   - edycja szablonu bezpośrednio w GUI
#   - dodawanie szablonów
#   - generowanie ODT
#   - konwersja ODT -> PDF
#   - podgląd PDF
#   - drukowanie na drukarce domyślnej
#   - domyślnie 2 kopie
#
# ============================================================

from __future__ import annotations
# Obsługa własnych obiektów do kasacji.
# Funkcje są wywoływane przez bezpieczne wrappery niżej, dzięki czemu
# gui_generator.py działa również wtedy, gdy sygnatury modułu zostały rozszerzone.
try:
    from disposal_objects import (
        load_objects,
        add_object,
        delete_object,
        get_matching_template,
    )
except ImportError:
    load_objects = None
    add_object = None
    delete_object = None
    get_matching_template = None

import inspect

import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk,
    Toplevel,
    StringVar,
    IntVar,
    END,
    filedialog,
    messagebox,
)
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


# ============================================================
# PDF / PIL
# ============================================================

try:
    import pymupdf
except ImportError:
    pymupdf = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


# ============================================================
# ODT
# ============================================================

from odf.opendocument import load
from odf import text as odf_text
from odf import teletype
from rich_odt_editor import RichODTEditor


# ============================================================
# DATABASE
# ============================================================

from database import (
    DatabaseService,
    DatabaseServiceError,
    AssetNotFoundError,
)

from print_service import (
    PrintService,
    PrintServiceError,
)


# ============================================================
# KONFIGURACJA
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = (
    PROJECT_DIR / "orzeczenia"
)

TEMPLATES_DIR = (
    PROJECT_DIR / "szablony"
)

DEFAULT_TEMPLATE = (
    PROJECT_DIR / "szablon_orzeczenie.odt"
)

LAST_TEMPLATE_FILE = (
    PROJECT_DIR / "ostatni_szablon.json"
)

CURRENT_YEAR = datetime.now().year


# ============================================================
# LOGOWANIE
# ============================================================

LOGIN_USERNAME = "admin"
LOGIN_PASSWORD = "1234"


# ============================================================
# KOLORY
# ============================================================

COLORS = {

    "background":
        "#EEF1F5",

    "surface":
        "#F8FAFC",

    "surface_alt":
        "#E7EBF0",

    "border":
        "#D3D9E1",

    "border_dark":
        "#BEC7D2",

    "text":
        "#202A35",

    "text_secondary":
        "#687585",

    "blue":
        "#316BEA",

    "blue_dark":
        "#2457C7",

    "blue_light":
        "#E7EEFF",

    "green":
        "#218653",

    "green_light":
        "#E4F5EC",

    "red":
        "#C93636",

    "red_light":
        "#FBE9E9",

    "white":
        "#FFFFFF",

}


# ============================================================
# FONTY
# ============================================================

FONT_MAIN = "Segoe UI"
FONT_MONO = "Consolas"


# ============================================================
# CZYSZCZENIE
# ============================================================

def clean(value):

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
# BEZPIECZNA NAZWA
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

    return (
        " - Paszport "
        + value
    )


# ============================================================
# KOMPONENTY
# ============================================================

def format_components_name(
    components
):

    if not components:
        return ""

    names = []

    for component in components:

        if hasattr(
            component,
            "name"
        ):

            name = clean(
                component.name
            )

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


def format_components_full(
    components
):

    if not components:
        return ""

    result = []

    for component in components:

        if hasattr(
            component,
            "name"
        ):

            name = clean(
                component.name
            )

            code = clean(
                getattr(
                    component,
                    "code",
                    ""
                )
            )

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
                        ""
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
# KLASYFIKACJA URZĄDZENIA
# ============================================================

def classify_asset(asset):

    """
    Klasyfikacja używana do automatycznego wyboru szablonu.

    Przykładowe klasy:
        komputer
        drukarka
        łóżko
        monitor
        telefon
        tablet
        skaner
        serwer
        kserokopiarka
        urządzenie medyczne
        domyślny
    """

    name = clean(
        getattr(
            asset,
            "name",
            ""
        )
    ).lower()

    manufacturer = clean(
        getattr(
            asset,
            "manufacturer",
            ""
        )
    ).lower()

    model = clean(
        getattr(
            asset,
            "model",
            ""
        )
    ).lower()

    text = (
        name
        + " "
        + manufacturer
        + " "
        + model
    )

    # --------------------------------------------------------
    # DRUKARKA
    # --------------------------------------------------------

    printer_words = [

        "drukarka",
        "drukarki",
        "printer",
        "laserjet",
        "deskjet",
        "officejet",
        "druk.",

    ]

    for word in printer_words:

        if word in text:

            return "drukarka"

    # --------------------------------------------------------
    # KOMPUTER
    # --------------------------------------------------------

    computer_words = [

        "komputer",
        "komputera",
        "pc",
        "desktop",
        "stacja robocza",
        "workstation",
        "laptop",
        "notebook",
        "all in one",
        "all-in-one",

    ]

    for word in computer_words:

        if word in text:

            return "komputer"

    # --------------------------------------------------------
    # ŁÓŻKO
    # --------------------------------------------------------

    bed_words = [

        "łóżko",
        "lozko",
        "łóżka",
        "lozka",
        "łóżko szpitalne",
        "lozko szpitalne",
        "bed",
        "hospital bed",

    ]

    for word in bed_words:

        if word in text:

            return "łóżko"

    # --------------------------------------------------------
    # MONITOR
    # --------------------------------------------------------

    monitor_words = [

        "monitor",
        "monitor lcd",
        "monitor led",

    ]

    for word in monitor_words:

        if word in text:

            return "monitor"

    # --------------------------------------------------------
    # TELEFON
    # --------------------------------------------------------

    phone_words = [

        "telefon",
        "smartfon",
        "smartphone",
        "telephone",

    ]

    for word in phone_words:

        if word in text:

            return "telefon"

    # --------------------------------------------------------
    # TABLET
    # --------------------------------------------------------

    tablet_words = [

        "tablet",

    ]

    for word in tablet_words:

        if word in text:

            return "tablet"

    # --------------------------------------------------------
    # SKANER
    # --------------------------------------------------------

    scanner_words = [

        "skaner",
        "scanner",

    ]

    for word in scanner_words:

        if word in text:

            return "skaner"

    # --------------------------------------------------------
    # SERWER
    # --------------------------------------------------------

    server_words = [

        "serwer",
        "server",

    ]

    for word in server_words:

        if word in text:

            return "serwer"

    # --------------------------------------------------------
    # KSEROKOPIARKA
    # --------------------------------------------------------

    copier_words = [

        "kserokopiarka",
        "ksero",
        "kopiarka",
        "copier",

    ]

    for word in copier_words:

        if word in text:

            return "kserokopiarka"

    # --------------------------------------------------------
    # URZĄDZENIE MEDYCZNE
    # --------------------------------------------------------

    medical_words = [

        "holter",
        "ekg",
        "eeg",
        "usg",
        "ultrasonograf",
        "defibrylator",
        "respirator",
        "pompa infuzyjna",
        "pompa",
        "ssak",
        "aparatura medyczna",

    ]

    for word in medical_words:

        if word in text:

            return "urządzenie_medyczne"

    return "domyślny"


# ============================================================
# SZABLONY
# ============================================================

def ensure_directories():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    TEMPLATES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def normalize_template_category(
    category
):

    category = clean(
        category
    ).lower()

    replacements = {

        "lozko":
            "łóżko",

        "łóżko":
            "łóżko",

        "komputer":
            "komputer",

        "drukarka":
            "drukarka",

        "monitor":
            "monitor",

        "telefon":
            "telefon",

        "tablet":
            "tablet",

        "skaner":
            "skaner",

        "serwer":
            "serwer",

        "kserokopiarka":
            "kserokopiarka",

        "urządzenie medyczne":
            "urządzenie_medyczne",

        "urządzenie_medyczne":
            "urządzenie_medyczne",

        "domyślny":
            "domyślny",

    }

    return replacements.get(
        category,
        category
    )


def category_template_path(
    category
):

    category = normalize_template_category(
        category
    )

    mapping = {

        "komputer":
            "komputer.odt",

        "drukarka":
            "drukarka.odt",

        "łóżko":
            "lozko.odt",

        "monitor":
            "monitor.odt",

        "telefon":
            "telefon.odt",

        "tablet":
            "tablet.odt",

        "skaner":
            "skaner.odt",

        "serwer":
            "serwer.odt",

        "kserokopiarka":
            "kserokopiarka.odt",

        "urządzenie_medyczne":
            "urzadzenie_medyczne.odt",

    }

    filename = mapping.get(
        category
    )

    if not filename:
        return None

    return (
        TEMPLATES_DIR
        / filename
    )


def load_last_template():

    if not LAST_TEMPLATE_FILE.exists():
        return ""

    try:

        with open(
            LAST_TEMPLATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

        path = data.get(
            "path",
            ""
        )

        if path:

            template = Path(
                path
            )

            if template.exists():

                return str(
                    template
                )

    except Exception:
        pass

    return ""


def save_last_template(
    template_path
):

    try:

        with open(
            LAST_TEMPLATE_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                {
                    "path":
                        str(
                            template_path
                        )
                },
                file,
                ensure_ascii=False,
                indent=4
            )

    except Exception:
        pass


def get_templates():

    ensure_directories()

    templates = []

    for path in sorted(
        TEMPLATES_DIR.glob("*.odt")
    ):

        templates.append(
            path
        )

    if DEFAULT_TEMPLATE.exists():

        if DEFAULT_TEMPLATE not in templates:

            templates.append(
                DEFAULT_TEMPLATE
            )

    return templates


def choose_template(
    classification
):

    ensure_directories()

    classification = (
        normalize_template_category(
            classification
        )
    )

    # --------------------------------------------------------
    # 1. SZABLON PRZYPISANY DO KLASY
    # --------------------------------------------------------

    specific = category_template_path(
        classification
    )

    if (
        specific
        and specific.exists()
    ):

        return specific

    # --------------------------------------------------------
    # 2. OSTATNI UŻYWANY SZABLON
    # --------------------------------------------------------

    last = load_last_template()

    if last:

        path = Path(
            last
        )

        if path.exists():

            return path

    # --------------------------------------------------------
    # 3. SZABLON DOMYŚLNY
    # --------------------------------------------------------

    if DEFAULT_TEMPLATE.exists():

        return DEFAULT_TEMPLATE

    # --------------------------------------------------------
    # 4. PIERWSZY DOSTĘPNY
    # --------------------------------------------------------

    templates = get_templates()

    if templates:

        return templates[0]

    return None


# ============================================================
# PLACEHOLDERY
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

    if hasattr(
        document,
        "text"
    ):

        walk(
            document.text
        )

    if hasattr(
        document,
        "body"
    ):

        walk(
            document.body
        )

    if hasattr(
        document,
        "styles"
    ):

        walk(
            document.styles
        )

    return changed


# ============================================================
# DANE ASSET
# ============================================================

def prepare_template_data(
    asset
):

    miejsce = clean(
        getattr(
            asset,
            "location_name",
            ""
        )
    )

    nazwa = clean(
        getattr(
            asset,
            "name",
            ""
        )
    )

    num_fab = clean(
        getattr(
            asset,
            "serial_number",
            ""
        )
    )

    st_num_inv = clean(
        getattr(
            asset,
            "code",
            ""
        )
    )

    brand = clean(
        getattr(
            asset,
            "manufacturer",
            ""
        )
    )

    model = clean(
        getattr(
            asset,
            "model",
            ""
        )
    )

    production_year = getattr(
        asset,
        "production_year",
        None
    )

    time_value = clean(
        production_year
    )

    components = getattr(
        asset,
        "components",
        []
    )

    passport = ""

    if hasattr(
        asset,
        "passport"
    ):

        passport = clean(
            asset.passport
        )

    return {

        "miejsce":
            miejsce,

        "nazwa":
            nazwa,

        "paszport":
            format_passport(
                passport
            ),

        "comp":
            format_components_name(
                components
            ),

        "num_fab":
            num_fab,

        "st_num_inv":
            st_num_inv,

        "if_iscomp":
            format_components_full(
                components
            ),

        "brand":
            brand,

        "model":
            model,

        "time":
            time_value,

        "curr_time-time":
            calculate_exploitation(
                time_value
            ),

    }


# ============================================================
# GENEROWANIE ODT
# ============================================================

def generate_document(
    asset,
    template_path,
    number=1
):

    ensure_directories()

    template_path = Path(
        template_path
    )

    if not template_path.exists():

        raise FileNotFoundError(
            "Nie znaleziono szablonu:\n"
            + str(template_path)
        )

    data = prepare_template_data(
        asset
    )

    st_number = data[
        "st_num_inv"
    ]

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

    if output_path.exists():

        try:

            output_path.unlink()

        except PermissionError:

            filename = (
                safe_filename(
                    st_number
                )
                + "_"
                + datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                )
                + "_orzeczenie.odt"
            )

            output_path = (
                OUTPUT_DIR / filename
            )

    shutil.copy2(
        template_path,
        output_path
    )

    document = load(
        str(output_path)
    )

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

    replace_all_text_nodes(
        document,
        replacements
    )

    document.save(
        str(output_path)
    )

    save_last_template(
        template_path
    )

    return (
        output_path,
        data
    )


# ============================================================
# LIBREOFFICE
# ============================================================

def find_libreoffice():

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

        if candidate:

            path = Path(
                candidate
            )

            if path.exists():

                return str(
                    path
                )

    return None


def convert_odt_to_pdf(
    odt_path
):

    odt_path = Path(
        odt_path
    )

    libreoffice = find_libreoffice()

    if not libreoffice:

        raise RuntimeError(
            "Nie znaleziono LibreOffice.\n\n"
            "LibreOffice jest wymagany do "
            "generowania PDF."
        )

    pdf_dir = odt_path.parent

    command = [

        libreoffice,

        "--headless",

        "--convert-to",
        "pdf",

        "--outdir",
        str(pdf_dir),

        str(odt_path),

    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120
    )

    pdf_path = (
        odt_path.with_suffix(
            ".pdf"
        )
    )

    if not pdf_path.exists():

        raise RuntimeError(
            "Nie udało się utworzyć PDF.\n\n"
            + result.stdout
            + "\n"
            + result.stderr
        )

    return pdf_path


# ============================================================
# SUMATRA PDF
# ============================================================

def find_sumatra():

    candidates = [

        shutil.which(
            "SumatraPDF"
        ),

        shutil.which(
            "SumatraPDF.exe"
        ),

        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",

        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",

        os.path.expandvars(
            r"%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe"
        ),

    ]

    for candidate in candidates:

        if not candidate:
            continue

        path = Path(
            candidate
        )

        if path.exists():

            return str(
                path
            )

    return None


# ============================================================
# DRUKOWANIE PDF
# ============================================================




# ============================================================
# WŁASNE OBIEKTY DO KASACJI
# ============================================================

OBJECT_TEMPLATES_DIR = TEMPLATES_DIR / "obiekty"
OBJECT_REGISTRY_FILE = TEMPLATES_DIR / "obiekty.json"


def ensure_object_templates_directory():
    OBJECT_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def get_custom_template(asset_name):
    """Zwraca szablon własnego obiektu, jeśli moduł disposal_objects go znajdzie."""
    if get_matching_template is None:
        return None

    local = _local_matching_template(asset_name)
    if local is not None:
        return local
    if get_matching_template is None:
        return None
    try:
        result = get_matching_template(clean(asset_name))
        if not result:
            return None
        path = Path(result)
        return path if path.exists() else None
    except Exception:
        return None


def _read_object_registry():
    try:
        if not OBJECT_REGISTRY_FILE.exists():
            return {}
        data = json.loads(OBJECT_REGISTRY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_object_registry(data):
    OBJECT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OBJECT_REGISTRY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.replace(tmp, OBJECT_REGISTRY_FILE)
    except PermissionError:
        # Jeżeli plik rejestru jest chwilowo zablokowany, zachowujemy dane
        # w alternatywnym pliku zamiast blokować tworzenie obiektu.
        fallback = OBJECT_REGISTRY_FILE.with_name("obiekty_local.json")
        fallback.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _register_local_object(name, template_path):
    data = _read_object_registry()
    data[clean(name).lower()] = {
        "name": clean(name),
        "keywords": [clean(name)],
        "template": str(Path(template_path)),
    }
    _write_object_registry(data)


def _remove_local_object(name):
    data = _read_object_registry()
    data.pop(clean(name).lower(), None)
    _write_object_registry(data)


def _local_matching_template(asset_name):
    value = clean(asset_name).lower()
    for item in _read_object_registry().values():
        keywords = item.get("keywords", [])
        for keyword in keywords:
            if clean(keyword).lower() and clean(keyword).lower() in value:
                path = Path(item.get("template", ""))
                if path.exists():
                    return path
    return None


def _call_add_object(object_name, template_path, keywords=None):
    """Rejestruje obiekt. Lokalny rejestr jest źródłem awaryjnym, więc
    blokada pliku disposal_objects nie może uniemożliwić utworzenia obiektu."""
    name = clean(object_name)
    path = Path(template_path)
    words = keywords or [name]

    # Najpierw zapisujemy własny rejestr ADMORA.
    _register_local_object(name, path)

    if add_object is None:
        return True

    try:
        return add_object(name, str(path), words)
    except PermissionError:
        return True
    except OSError as error:
        if getattr(error, "winerror", None) == 5 or "access is denied" in str(error).lower():
            return True
        raise


def _call_delete_object(object_name, template_path=None):
    _remove_local_object(object_name)
    if delete_object is None:
        return None
    name = clean(object_name)
    path = str(Path(template_path)) if template_path else ""
    try:
        signature = inspect.signature(delete_object)
        kwargs = {}
        for parameter_name, parameter in signature.parameters.items():
            if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            key = parameter_name.lower()
            if key in {"name", "nazwa", "object_name", "nazwa_obiektu"}:
                kwargs[parameter_name] = name
            elif "template" in key or key in {"path", "template_path", "odt_path", "szablon"}:
                kwargs[parameter_name] = path
            elif "keyword" in key or key in {"keywords", "slowa", "slowa_kluczowe"}:
                kwargs[parameter_name] = [name]
        if all(
            p.default is not inspect.Parameter.empty or n in kwargs
            for n, p in signature.parameters.items()
            if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ):
            try:
                return delete_object(**kwargs)
            except (PermissionError, OSError):
                return None
    except Exception:
        pass
    return None


def _load_custom_objects():
    result = []
    registry = _read_object_registry()
    result.extend(registry.values())
    if load_objects is not None:
        try:
            external = load_objects() or []
            if isinstance(external, dict):
                external = list(external.values())
            result.extend(external)
        except Exception:
            pass
    return result


def _object_display_name(item):
    if isinstance(item, dict):
        return clean(item.get("name") or item.get("nazwa") or item.get("object_name") or "")
    return clean(getattr(item, "name", getattr(item, "nazwa", str(item))))


# ============================================================
# APLIKACJA
# ============================================================

class Application:

    def __init__(
        self,
        root
    ):

        self.root = root

        self.database = None
        self.print_service = PrintService()

        self.asset = None

        self.current_data = None

        self.current_odt = None

        self.current_pdf = None

        self.preview_image = None

        self.editor = None

        self.login_frame = None

        self.main_frame = None

        self.closing = False

        self.status_var = StringVar(
            value="Gotowy"
        )

        self.code_var = StringVar()

        self.copies_var = IntVar(
            value=2
        )

        self.classification_var = StringVar(
            value="—"
        )

        self.template_var = StringVar(
            value="—"
        )

        self.info_vars = {

            "ST":
                StringVar(),

            "Nazwa":
                StringVar(),

            "Producent":
                StringVar(),

            "Model":
                StringVar(),

            "Nr fabryczny":
                StringVar(),

            "Miejsce":
                StringVar(),

            "Rok produkcji":
                StringVar(),

            "Eksploatacja":
                StringVar(),

        }

        ensure_directories()

        self.setup_style()

        self.show_login()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )


    # ========================================================
    # STYLE
    # ========================================================

    def setup_style(self):

        style = ttk.Style()

        try:

            style.theme_use(
                "clam"
            )

        except Exception:
            pass

        style.configure(

            "TFrame",

            background=
                COLORS["background"]

        )

        style.configure(

            "TLabel",

            background=
                COLORS["background"],

            foreground=
                COLORS["text"],

        )

        style.configure(

            "TEntry",

            padding=(
                10,
                9
            ),

            font=(
                FONT_MAIN,
                11
            ),

            fieldbackground=
                COLORS["surface"],

        )

        style.configure(

            "TSpinbox",

            padding=(
                8,
                8
            ),

            font=(
                FONT_MAIN,
                10
            ),

        )

        style.configure(

            "TCombobox",

            padding=(
                8,
                8
            ),

            fieldbackground=
                COLORS["surface"],

            background=
                COLORS["surface"],

            foreground=
                COLORS["text"],

            arrowcolor=
                COLORS["blue"],

        )

        style.configure(

            "Blue.TButton",

            font=(
                FONT_MAIN,
                10,
                "bold"
            ),

            padding=(
                18,
                10
            ),

            foreground=
                COLORS["white"],

            background=
                COLORS["blue"],

            borderwidth=0,

            relief="flat",

        )

        style.map(

            "Blue.TButton",

            background=[

                (
                    "active",
                    COLORS["blue_dark"]
                ),

                (
                    "pressed",
                    COLORS["blue_dark"]
                ),

            ]

        )

        style.configure(

            "Secondary.TButton",

            font=(
                FONT_MAIN,
                10
            ),

            padding=(
                15,
                9
            ),

            foreground=
                COLORS["text"],

            background=
                COLORS["surface"],

            borderwidth=1,

            relief="solid",

        )

        style.map(

            "Secondary.TButton",

            background=[

                (
                    "active",
                    COLORS["surface_alt"]
                ),

            ]

        )


    # ========================================================
    # LOGIN
    # ========================================================

    def show_login(self):

        if self.main_frame:

            self.main_frame.destroy()

            self.main_frame = None

        if self.login_frame:

            self.login_frame.destroy()

        self.login_frame = ttk.Frame(
            self.root
        )

        self.login_frame.pack(
            fill="both",
            expand=True
        )

        outer = ttk.Frame(
            self.login_frame
        )

        outer.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        card = ttk.Frame(
            outer,
            padding=(
                55,
                45
            )
        )

        card.pack()

        ttk.Label(
            card,
            text="ADMORA",
            font=(
                FONT_MAIN,
                30,
                "bold"
            ),
            foreground=
                COLORS["blue"]
        ).pack(
            pady=(
                0,
                5
            )
        )

        ttk.Label(
            card,
            text="Generator orzeczeń technicznych",
            font=(
                FONT_MAIN,
                11
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            pady=(
                0,
                35
            )
        )

        ttk.Label(
            card,
            text="Login",
            font=(
                FONT_MAIN,
                10,
                "bold"
            )
        ).pack(
            anchor="w"
        )

        self.login_entry = ttk.Entry(
            card,
            width=35
        )

        self.login_entry.pack(
            pady=(
                6,
                18
            )
        )

        ttk.Label(
            card,
            text="Hasło",
            font=(
                FONT_MAIN,
                10,
                "bold"
            )
        ).pack(
            anchor="w"
        )

        self.password_entry = ttk.Entry(
            card,
            width=35,
            show="●"
        )

        self.password_entry.pack(
            pady=(
                6,
                25
            )
        )

        self.login_button = ttk.Button(
            card,
            text="ZALOGUJ",
            style="Blue.TButton",
            command=self.login
        )

        self.login_button.pack(
            fill="x"
        )

        self.login_status = ttk.Label(
            card,
            text="",
            foreground=
                COLORS["red"],
            font=(
                FONT_MAIN,
                9
            )
        )

        self.login_status.pack(
            pady=(
                12,
                0
            )
        )

        ttk.Label(
            card,
            text=(
                "© "
                + str(CURRENT_YEAR)
                + " Paweł Drwal • Wszelkie prawa zastrzeżone"
            ),
            font=(
                FONT_MAIN,
                8
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            pady=(
                35,
                3
            )
        )

        ttk.Label(
            card,
            text="LICENCJA NIE AKTYWNA",
            font=(
                FONT_MAIN,
                9,
                "bold"
            ),
            foreground=
                COLORS["red"]
        ).pack()

        self.login_entry.focus_set()

        self.login_entry.bind(
            "<Return>",
            lambda event:
                self.password_entry.focus_set()
        )

        self.password_entry.bind(
            "<Return>",
            lambda event:
                self.login()
        )


    def login(self):

        login = (
            self.login_entry
            .get()
            .strip()
        )

        password = (
            self.password_entry
            .get()
        )

        if (
            login == LOGIN_USERNAME
            and password == LOGIN_PASSWORD
        ):

            self.login_frame.destroy()

            self.login_frame = None

            self.show_main()

        else:

            self.login_status.config(
                text="Nieprawidłowy login lub hasło."
            )

            self.password_entry.delete(
                0,
                END
            )

            self.password_entry.focus_set()


    # ========================================================
    # MAIN
    # ========================================================

    def show_main(self):

        self.root.title(
            "ADMORA — Generator orzeczeń technicznych"
        )

        self.main_frame = ttk.Frame(
            self.root
        )

        self.main_frame.pack(
            fill="both",
            expand=True
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = ttk.Frame(
            self.main_frame,
            padding=(
                25,
                18
            )
        )

        header.pack(
            fill="x"
        )

        title_frame = ttk.Frame(
            header
        )

        title_frame.pack(
            side="left"
        )

        ttk.Label(
            title_frame,
            text="ADMORA",
            font=(
                FONT_MAIN,
                22,
                "bold"
            ),
            foreground=
                COLORS["blue"]
        ).pack(
            anchor="w"
        )

        ttk.Label(
            title_frame,
            text="Generator orzeczeń technicznych",
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            anchor="w"
        )

        right_header = ttk.Frame(
            header
        )

        right_header.pack(
            side="right"
        )

        ttk.Label(
            right_header,
            text="READ ONLY",
            font=(
                FONT_MAIN,
                9,
                "bold"
            ),
            foreground=
                COLORS["green"]
        ).pack(
            side="left",
            padx=(
                0,
                25
            )
        )

        ttk.Label(
            right_header,
            text="Paweł Drwal",
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            side="left"
        )

        separator = ttk.Separator(
            self.main_frame,
            orient="horizontal"
        )

        separator.pack(
            fill="x"
        )

        # ====================================================
        # BODY
        # ====================================================

        body = ttk.Frame(
            self.main_frame,
            padding=(
                20,
                15
            )
        )

        body.pack(
            fill="both",
            expand=True
        )

        body.columnconfigure(
            0,
            weight=4
        )

        body.columnconfigure(
            1,
            weight=5
        )

        body.rowconfigure(
            0,
            weight=1
        )

        # ====================================================
        # LEWA
        # ====================================================

        left = ttk.Frame(
            body
        )

        left.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(
                0,
                10
            )
        )

        left.rowconfigure(
            2,
            weight=1
        )

        left.columnconfigure(
            0,
            weight=1
        )

        # ====================================================
        # SEARCH
        # ====================================================

        scan_card = ttk.Frame(
            left,
            padding=(
                20,
                18
            )
        )

        scan_card.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(
                0,
                12
            )
        )

        ttk.Label(
            scan_card,
            text="Wyszukiwanie środka trwałego",
            font=(
                FONT_MAIN,
                13,
                "bold"
            )
        ).pack(
            anchor="w"
        )

        ttk.Label(
            scan_card,
            text=(
                "Wpisz kod ręcznie lub zeskanuj kod ST "
                "czytnikiem."
            ),
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(
                3,
                12
            )
        )

        search_row = ttk.Frame(
            scan_card
        )

        search_row.pack(
            fill="x"
        )

        self.code_entry = ttk.Entry(
            search_row,
            textvariable=self.code_var,
            font=(
                FONT_MAIN,
                12
            )
        )

        self.code_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(
                0,
                10
            )
        )

        ttk.Button(
            search_row,
            text="POBIERZ",
            style="Blue.TButton",
            command=self.search_asset
        ).pack(
            side="right"
        )

        self.code_entry.bind(
            "<Return>",
            lambda event:
                self.search_asset()
        )

        status_frame = ttk.Frame(
            scan_card
        )

        status_frame.pack(
            fill="x",
            pady=(
                12,
                0
            )
        )

        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        )

        self.status_label.pack(
            side="left"
        )

        # ====================================================
        # SPECYFIKACJA
        # ====================================================

        info_card = ttk.Frame(
            left,
            padding=(
                20,
                18
            )
        )

        info_card.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(
                0,
                12
            )
        )

        ttk.Label(
            info_card,
            text="Specyfikacja",
            font=(
                FONT_MAIN,
                13,
                "bold"
            )
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(
                0,
                12
            )
        )

        row = 1

        for label, variable in self.info_vars.items():

            ttk.Label(
                info_card,
                text=label,
                font=(
                    FONT_MAIN,
                    9,
                    "bold"
                ),
                foreground=
                    COLORS["text_secondary"]
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=3,
                padx=(
                    0,
                    20
                )
            )

            ttk.Label(
                info_card,
                textvariable=variable,
                font=(
                    FONT_MAIN,
                    10
                ),
                foreground=
                    COLORS["text"]
            ).grid(
                row=row,
                column=1,
                sticky="w",
                pady=3
            )

            row += 1

        info_card.columnconfigure(
            1,
            weight=1
        )

        # ====================================================
        # KOMPONENTY
        # ====================================================

        components_card = ttk.Frame(
            left,
            padding=(
                20,
                18
            )
        )

        components_card.grid(
            row=2,
            column=0,
            sticky="nsew"
        )

        components_card.rowconfigure(
            1,
            weight=1
        )

        components_card.columnconfigure(
            0,
            weight=1
        )

        ttk.Label(
            components_card,
            text="Komponenty",
            font=(
                FONT_MAIN,
                13,
                "bold"
            )
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(
                0,
                10
            )
        )

        self.components_text = ScrolledText(
            components_card,
            height=8,
            font=(
                FONT_MAIN,
                9
            ),
            bg=COLORS["surface"],
            fg=COLORS["text"],
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
            wrap="word"
        )

        self.components_text.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        self.components_text.insert(
            "1.0",
            "Brak danych."
        )

        self.components_text.config(
            state="disabled"
        )

        # ====================================================
        # PRAWA
        # ====================================================

        right = ttk.Frame(
            body
        )

        right.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(
                10,
                0
            )
        )

        right.rowconfigure(
            1,
            weight=1
        )

        right.columnconfigure(
            0,
            weight=1
        )

        # ====================================================
        # PREVIEW HEADER
        # ====================================================

        preview_header = ttk.Frame(
            right,
            padding=(
                20,
                18
            )
        )

        preview_header.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        ttk.Label(
            preview_header,
            text="Podgląd dokumentu",
            font=(
                FONT_MAIN,
                13,
                "bold"
            )
        ).pack(
            side="left"
        )

        ttk.Label(
            preview_header,
            textvariable=
                self.classification_var,
            font=(
                FONT_MAIN,
                9,
                "bold"
            ),
            foreground=
                COLORS["blue"]
        ).pack(
            side="right"
        )

        # ====================================================
        # PREVIEW
        # ====================================================

        preview_card = ttk.Frame(
            right,
            padding=(
                20,
                12
            )
        )

        preview_card.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        preview_card.rowconfigure(
            0,
            weight=1
        )

        preview_card.columnconfigure(
            0,
            weight=1
        )

        self.preview_canvas = ttk.Label(
            preview_card,
            text=(
                "Brak dokumentu do podglądu.\n\n"
                "Zeskanuj lub wpisz kod ST."
            ),
            anchor="center",
            justify="center",
            font=(
                FONT_MAIN,
                11
            ),
            foreground=
                COLORS["text_secondary"]
        )

        self.preview_canvas.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=25
        )

        # ====================================================
        # ACTIONS
        # ====================================================

        actions = ttk.Frame(
            right,
            padding=(
                12,
                15
            )
        )

        actions.grid(
            row=2,
            column=0,
            sticky="ew"
        )

        template_frame = ttk.Frame(
            actions
        )

        template_frame.pack(
            fill="x",
            pady=(
                0,
                10
            )
        )

        ttk.Label(
            template_frame,
            text="Szablon:",
            font=(
                FONT_MAIN,
                9,
                "bold"
            )
        ).pack(
            side="left"
        )

        ttk.Label(
            template_frame,
            textvariable=
                self.template_var,
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            side="left",
            padx=(
                8,
                0
            )
        )

        buttons = ttk.Frame(
            actions
        )

        buttons.pack(
            fill="x"
        )

        ttk.Button(
            buttons,
            text="EDYTUJ",
            style="Secondary.TButton",
            command=self.edit_document
        ).pack(
            side="left",
            padx=(0, 6)
        )

        ttk.Button(
            buttons,
            text="EDYTUJ SZABLON",
            style="Secondary.TButton",
            command=self.edit_template
        ).pack(
            side="left",
            padx=(0, 6)
        )

        ttk.Button(
            buttons,
            text="ODŚWIEŻ PODGLĄD",
            style="Secondary.TButton",
            command=self.refresh_current_pdf
        ).pack(
            side="left",
            padx=(0, 6)
        )

        ttk.Button(
            buttons,
            text="DODAJ OBIEKT",
            style="Secondary.TButton",
            command=self.add_disposal_object
        ).pack(
            side="left",
            padx=(0, 6)
        )

        ttk.Button(
            buttons,
            text="DODAJ SZABLON",
            style="Secondary.TButton",
            command=self.add_template
        ).pack(
            side="left",
            padx=(0, 12)
        )

        ttk.Label(
            buttons,
            text="Kopie:",
            font=(
                FONT_MAIN,
                9,
                "bold"
            )
        ).pack(
            side="left",
            padx=(
                25,
                7
            )
        )

        self.copies_spin = ttk.Spinbox(
            buttons,
            from_=1,
            to=99,
            textvariable=
                self.copies_var,
            width=5
        )

        self.copies_spin.pack(
            side="left"
        )

        ttk.Button(
            buttons,
            text="DRUKUJ",
            style="Blue.TButton",
            command=self.print_document
        ).pack(
            side="right"
        )

        # ====================================================
        # FOOTER
        # ====================================================

        footer = ttk.Frame(
            self.main_frame,
            padding=(
                20,
                8
            )
        )

        footer.pack(
            fill="x"
        )

        ttk.Label(
            footer,
            text=(
                "© "
                + str(CURRENT_YEAR)
                + " Paweł Drwal • Wszelkie prawa zastrzeżone"
            ),
            font=(
                FONT_MAIN,
                8
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            side="left"
        )

        ttk.Label(
            footer,
            text="LICENCJA NIE AKTYWNA",
            font=(
                FONT_MAIN,
                8,
                "bold"
            ),
            foreground=
                COLORS["red"]
        ).pack(
            side="right"
        )

        # ====================================================
        # DATABASE
        # ====================================================

        self.database = DatabaseService()

        self.set_status(
            "Łączenie z bazą ADMORA..."
        )

        self.root.after(
            100,
            self.connect_database
        )


    # ========================================================
    # DATABASE
    # ========================================================

    def connect_database(self):

        def worker():

            try:

                self.database.connect()

                success = (
                    self.database.test_connection()
                )

                self.root.after(
                    0,
                    lambda success=success:
                        self.database_connected(
                            success
                        )
                )

            except Exception as error:

                error_text = str(
                    error
                )

                self.root.after(
                    0,
                    lambda error_text=error_text:
                        self.database_error(
                            error_text
                        )
                )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()


    def database_connected(
        self,
        success
    ):

        if success:

            self.set_status(
                "Połączenie z bazą ADMORA: OK — READ ONLY"
            )

        else:

            self.set_status(
                "Błąd testu połączenia."
            )


    def database_error(
        self,
        error
    ):

        self.set_status(
            "Błąd połączenia z bazą."
        )

        messagebox.showerror(
            "Baza ADMORA",
            str(error)
        )


    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        text
    ):

        self.status_var.set(
            text
        )


    # ========================================================
    # SZUKANIE
    # ========================================================

    def search_asset(self):

        code = (
            self.code_var
            .get()
            .strip()
            .upper()
        )

        if not code:

            self.set_status(
                "Wprowadź kod ST."
            )

            self.code_entry.focus_set()

            return

        if (
            self.database is None
            or not self.database.is_connected()
        ):

            self.set_status(
                "Brak połączenia z bazą ADMORA."
            )

            return

        self.set_status(
            "Pobieranie danych z bazy..."
        )

        self.preview_canvas.config(
            text="Pobieranie danych z bazy...",
            image=""
        )

        self.clear_asset_info()

        threading.Thread(
            target=self.load_asset_thread,
            args=(code,),
            daemon=True
        ).start()


    def load_asset_thread(
        self,
        code
    ):

        try:

            asset = (
                self.database.get_by_code(
                    code
                )
            )

            self.root.after(
                0,
                lambda asset=asset:
                    self.asset_loaded(
                        asset
                    )
            )

        except AssetNotFoundError as error:

            error_text = str(
                error
            )

            self.root.after(
                0,
                lambda error_text=error_text:
                    self.asset_not_found(
                        error_text
                    )
            )

        except DatabaseServiceError as error:

            error_text = str(
                error
            )

            self.root.after(
                0,
                lambda error_text=error_text:
                    self.database_read_error(
                        error_text
                    )
            )

        except Exception as error:

            error_text = str(
                error
            )

            self.root.after(
                0,
                lambda error_text=error_text:
                    self.database_read_error(
                        error_text
                    )
            )


    def asset_not_found(
        self,
        error
    ):

        self.set_status(
            "Nie znaleziono środka trwałego."
        )

        self.preview_canvas.config(
            text="Nie znaleziono środka trwałego.",
            image=""
        )

        messagebox.showwarning(
            "Brak rekordu",
            str(error)
        )


    def database_read_error(
        self,
        error
    ):

        self.set_status(
            "Błąd podczas pobierania danych."
        )

        self.preview_canvas.config(
            text="Błąd podczas pobierania danych.",
            image=""
        )

        messagebox.showerror(
            "ADMORA",
            str(error)
        )


    # ========================================================
    # ASSET LOADED
    # ========================================================

    def asset_loaded(
        self,
        asset
    ):

        self.asset = asset

        self.current_data = (
            prepare_template_data(
                asset
            )
        )

        asset_name = clean(
            getattr(asset, "name", "")
        )

        custom_template = get_custom_template(asset_name)

        if custom_template:
            classification = "własny obiekt: " + custom_template.stem
        else:
            classification = classify_asset(asset)

        self.classification_var.set(
            "Klasyfikacja: "
            + classification.upper()
        )

        # ----------------------------------------------------
        # INFORMACJE
        # ----------------------------------------------------

        self.info_vars[
            "ST"
        ].set(
            self.current_data[
                "st_num_inv"
            ]
        )

        self.info_vars[
            "Nazwa"
        ].set(
            self.current_data[
                "nazwa"
            ]
        )

        self.info_vars[
            "Producent"
        ].set(
            self.current_data[
                "brand"
            ]
        )

        self.info_vars[
            "Model"
        ].set(
            self.current_data[
                "model"
            ]
        )

        self.info_vars[
            "Nr fabryczny"
        ].set(
            self.current_data[
                "num_fab"
            ]
        )

        self.info_vars[
            "Miejsce"
        ].set(
            self.current_data[
                "miejsce"
            ]
        )

        self.info_vars[
            "Rok produkcji"
        ].set(
            self.current_data[
                "time"
            ]
        )

        self.info_vars[
            "Eksploatacja"
        ].set(
            self.current_data[
                "curr_time-time"
            ]
        )

        # ----------------------------------------------------
        # KOMPONENTY
        # ----------------------------------------------------

        self.components_text.config(
            state="normal"
        )

        self.components_text.delete(
            "1.0",
            END
        )

        components = getattr(
            asset,
            "components",
            []
        )

        if components:

            for component in components:

                name = clean(
                    getattr(
                        component,
                        "name",
                        ""
                    )
                )

                code = clean(
                    getattr(
                        component,
                        "code",
                        ""
                    )
                )

                component_type = clean(
                    getattr(
                        component,
                        "component_type",
                        ""
                    )
                )

                manufacturer = clean(
                    getattr(
                        component,
                        "manufacturer",
                        ""
                    )
                )

                model = clean(
                    getattr(
                        component,
                        "model",
                        ""
                    )
                )

                line = name

                if code:

                    line += (
                        "  ["
                        + code
                        + "]"
                    )

                if component_type:

                    line += (
                        " — "
                        + component_type
                    )

                self.components_text.insert(
                    END,
                    line
                    + "\n"
                )

                if manufacturer:

                    self.components_text.insert(
                        END,
                        "    Producent: "
                        + manufacturer
                        + "\n"
                    )

                if model:

                    self.components_text.insert(
                        END,
                        "    Model: "
                        + model
                        + "\n"
                    )

                self.components_text.insert(
                    END,
                    "\n"
                )

        else:

            self.components_text.insert(
                "1.0",
                "Brak aktywnych komponentów."
            )

        self.components_text.config(
            state="disabled"
        )

        self.set_status(
            "Dane pobrane z bazy ADMORA."
        )

        # ----------------------------------------------------
        # SZABLON
        # ----------------------------------------------------

        if custom_template:
            template = custom_template
        else:
            template = choose_template(
                classification
            )

        if template:

            self.template_var.set(
                template.name
            )

        else:

            self.template_var.set(
                "Brak szablonu"
            )

        # ----------------------------------------------------
        # GENEROWANIE
        # ----------------------------------------------------

        self.generate_preview()


    # ========================================================
    # CLEAR
    # ========================================================

    def clear_asset_info(self):

        for variable in (
            self.info_vars.values()
        ):

            variable.set("")

        self.classification_var.set(
            "—"
        )

        self.template_var.set(
            "—"
        )

        self.current_pdf = None

        self.current_odt = None

        self.components_text.config(
            state="normal"
        )

        self.components_text.delete(
            "1.0",
            END
        )

        self.components_text.insert(
            "1.0",
            "Brak danych."
        )

        self.components_text.config(
            state="disabled"
        )


    # ========================================================
    # GENEROWANIE PODGLĄDU
    # ========================================================

    def generate_preview(self):

        if self.asset is None:
            return

        asset_name = clean(
            getattr(self.asset, "name", "")
        )

        custom_template = get_custom_template(asset_name)

        if custom_template:
            template = custom_template
            self.classification_var.set(
                "Klasyfikacja: WŁASNY OBIEKT — "
                + custom_template.stem.upper()
            )
        else:
            classification = classify_asset(self.asset)
            template = choose_template(classification)
            self.classification_var.set(
                "Klasyfikacja: "
                + classification.upper()
            )

        if template is None:
            self.set_status("Brak szablonu.")
            self.preview_canvas.config(
                text=(
                    "Brak dostępnego szablonu.\n\n"
                    "Kliknij „DODAJ SZABLON”."
                ),
                image=""
            )
            return

        self.template_var.set(template.name)
        self.set_status("Generowanie dokumentu...")

        threading.Thread(
            target=self.generate_thread,
            args=(template,),
            daemon=True
        ).start()


    def generate_thread(
        self,
        template
    ):

        try:

            odt_path, data = (
                generate_document(
                    self.asset,
                    template,
                    1
                )
            )

            pdf_path = (
                convert_odt_to_pdf(
                    odt_path
                )
            )

            self.root.after(
                0,
                lambda odt_path=odt_path,
                       pdf_path=pdf_path,
                       data=data:
                    self.document_generated(
                        odt_path,
                        pdf_path,
                        data
                    )
            )

        except Exception as error:

            error_text = str(
                error
            )

            self.root.after(
                0,
                lambda error_text=error_text:
                    self.document_generation_error(
                        error_text
                    )
            )


    def document_generated(
        self,
        odt_path,
        pdf_path,
        data
    ):

        self.current_odt = (
            Path(
                odt_path
            )
        )

        self.current_pdf = (
            Path(
                pdf_path
            )
        )

        self.current_data = data

        self.set_status(
            "Dokument gotowy."
        )

        self.show_pdf_preview(
            pdf_path
        )


    def document_generation_error(
        self,
        error
    ):

        self.set_status(
            "Błąd generowania dokumentu."
        )

        self.preview_canvas.config(
            text=(
                "Nie udało się wygenerować "
                "dokumentu.\n\n"
                + str(error)
            ),
            image=""
        )

        messagebox.showerror(
            "Generator",
            str(error)
        )


    # ========================================================
    # PDF PREVIEW
    # ========================================================

    def show_pdf_preview(
        self,
        pdf_path
    ):

        if pymupdf is None:

            self.preview_canvas.config(
                text=(
                    "PDF został wygenerowany.\n\n"
                    + str(pdf_path)
                    + "\n\n"
                    "Do podglądu zainstaluj:\n"
                    "pip install pymupdf pillow"
                ),
                image=""
            )

            return

        if Image is None:

            self.preview_canvas.config(
                text=(
                    "PDF został wygenerowany.\n\n"
                    "Do podglądu wymagane są "
                    "biblioteki Pillow i PyMuPDF."
                ),
                image=""
            )

            return

        try:

            document = pymupdf.open(
                str(pdf_path)
            )

            if document.page_count == 0:

                document.close()

                self.preview_canvas.config(
                    text="PDF nie zawiera stron.",
                    image=""
                )

                return

            page = document.load_page(
                0
            )

            rect = page.rect

            self.root.update_idletasks()

            max_width = max(
                350,
                self.preview_canvas.winfo_width()
                - 60
            )

            max_height = max(
                450,
                self.preview_canvas.winfo_height()
                - 30
            )

            scale_x = (
                max_width
                / rect.width
            )

            scale_y = (
                max_height
                / rect.height
            )

            scale = min(
                scale_x,
                scale_y
            )

            scale = min(
                scale,
                1.7
            )

            matrix = pymupdf.Matrix(
                scale,
                scale
            )

            pix = page.get_pixmap(
                matrix=matrix,
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                (
                    pix.width,
                    pix.height
                ),
                pix.samples
            )

            photo = ImageTk.PhotoImage(
                image
            )

            self.preview_image = photo

            self.preview_canvas.config(
                image=photo,
                text=""
            )

            document.close()

        except Exception as error:

            self.preview_canvas.config(
                text=(
                    "Nie udało się wyświetlić "
                    "podglądu.\n\n"
                    + str(error)
                ),
                image=""
            )


    # ========================================================
    # DRUKOWANIE
    # ========================================================

    def print_document(self):

        if not self.current_pdf:

            messagebox.showwarning(
                "Drukowanie",
                "Najpierw zeskanuj lub wpisz kod ST."
            )

            return

        if not self.current_pdf.exists():

            messagebox.showerror(
                "Drukowanie",
                "Nie znaleziono wygenerowanego PDF."
            )

            return

        try:

            copies = int(
                self.copies_var.get()
            )

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

        self.copies_var.set(
            copies
        )

        self.set_status(
            "Wysyłanie dokumentu do drukarki..."
        )

        pdf_path = (
            self.current_pdf
        )

        threading.Thread(
            target=self.print_thread,
            args=(
                pdf_path,
                copies
            ),
            daemon=True
        ).start()

    def print_thread(
            self,
            pdf_path,
            copies
    ):

        try:

            result = self.print_service.print_pdf(
                pdf_path,
                copies
            )

            self.root.after(
                0,
                lambda result=result:
                self.print_success(
                    result
                )
            )

        except Exception as e:

            error_text = str(e)

            self.root.after(
                0,
                lambda error_text=error_text:
                self.print_error(
                    error_text
                )
            )

    def print_success(
            self,
            result
    ):

        printer = result.get(
            "printer",
            "drukarka domyślna"
        )

        copies = result.get(
            "copies",
            2
        )

        method = result.get(
            "method",
            "Windows"
        )

        self.set_status(
            "Dokument wysłany do drukarki: "
            + printer
        )

        messagebox.showinfo(
            "Drukowanie",
            (
                    "Dokument został wysłany do drukarki.\n\n"
                    "Drukarka:\n"
                    + printer
                    + "\n\n"
                      "Liczba kopii: "
                    + str(copies)
                    + "\n\n"
                      "Tryb: "
                    + method
            )
        )

    def print_error(
            self,
            error
    ):

        self.set_status(
            "Błąd drukowania."
        )

        messagebox.showerror(
            "Drukowanie",
            str(error)
        )

    # ========================================================
    # EDYCJA ORZECZENIA / SZABLONU
    # ========================================================

    def _open_in_libreoffice(self, odt_path, title="LibreOffice Writer"):
        """
        Otwiera ODT w prawdziwym LibreOffice Writer.

        To jest celowe: Tkinter nie potrafi być pełnoprawnym edytorem ODT
        z zachowaniem stylów, fontów, tabel, marginesów, odstępów itd.
        LibreOffice zachowuje 100% formatowania dokumentu.
        """
        odt_path = Path(odt_path)

        if not odt_path.exists():
            messagebox.showerror(
                title,
                "Nie znaleziono pliku ODT:\n\n" + str(odt_path)
            )
            return False

        libreoffice = find_libreoffice()
        if not libreoffice:
            messagebox.showerror(
                title,
                "Nie znaleziono LibreOffice.\n\n"
                "Zainstaluj LibreOffice Writer, aby edytować szablony "
                "z zachowaniem pełnego formatowania."
            )
            return False

        try:
            # Windows: otwieramy normalny dokument Writer.
            # Nie używamy trybu headless.
            subprocess.Popen(
                [
                    libreoffice,
                    "--writer",
                    str(odt_path)
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            self.set_status(
                "Dokument otwarty w LibreOffice Writer. "
                "Zapisz zmiany w LibreOffice."
            )
            return True

        except Exception as error:
            messagebox.showerror(
                title,
                str(error)
            )
            return False


    def refresh_current_pdf(self):
        """Ponownie tworzy PDF z aktualnego ODT po edycji w LibreOffice."""
        if not self.current_odt:
            messagebox.showwarning(
                "Odśwież podgląd",
                "Najpierw wygeneruj orzeczenie."
            )
            return

        odt_path = Path(self.current_odt)

        if not odt_path.exists():
            messagebox.showerror(
                "Odśwież podgląd",
                "Nie znaleziono pliku ODT."
            )
            return

        self.set_status("Odświeżanie podglądu PDF...")

        def worker():
            try:
                pdf_path = convert_odt_to_pdf(odt_path)
                self.root.after(
                    0,
                    lambda: self._pdf_refresh_success(pdf_path)
                )
            except Exception as error:
                error_text = str(error)
                self.root.after(
                    0,
                    lambda error_text=error_text:
                    self._pdf_refresh_error(error_text)
                )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()


    def _pdf_refresh_success(self, pdf_path):
        self.current_pdf = Path(pdf_path)
        self.show_pdf_preview(pdf_path)
        self.set_status("Podgląd PDF został odświeżony.")


    def _pdf_refresh_error(self, error):
        self.set_status("Błąd odświeżania PDF.")
        messagebox.showerror(
            "Odśwież podgląd",
            str(error)
        )


    def edit_document(self):
        """Edytuje wygenerowane orzeczenie w naszym edytorze ODT."""
        if not self.current_odt:
            messagebox.showwarning(
                "Edycja orzeczenia",
                "Najpierw wygeneruj orzeczenie."
            )
            return

        if not Path(self.current_odt).exists():
            messagebox.showerror(
                "Edycja orzeczenia",
                "Nie znaleziono wygenerowanego pliku ODT."
            )
            return

        self.editor = RichODTEditor(
            self.root,
            self.current_odt,
            title="EDYCJA ORZECZENIA",
            on_saved=self.document_edited,
        )


    def document_edited(self, odt_path):
        self.current_odt = Path(odt_path)
        self.refresh_current_pdf()


    def edit_template(self):
        """Otwiera pełnoekranowy menedżer wszystkich szablonów."""
        self.open_template_manager()


    def template_edited(self, odt_path):
        self.template_var.set(Path(odt_path).name)
        self.set_status("Szablon został zapisany.")


    def _all_template_entries(self):
        """Zwraca wszystkie szablony widoczne w menedżerze."""
        ensure_directories()
        ensure_object_templates_directory()

        entries = []

        if DEFAULT_TEMPLATE.exists():
            entries.append({
                "name": "Szablon domyślny",
                "path": DEFAULT_TEMPLATE,
                "kind": "DOMYŚLNY",
                "deletable": False,
            })

        for path in sorted(TEMPLATES_DIR.glob("*.odt"), key=lambda p: p.name.lower()):
            if path.resolve() == DEFAULT_TEMPLATE.resolve():
                continue
            entries.append({
                "name": path.stem,
                "path": path,
                "kind": "KLASYFIKACJA",
                "deletable": True,
            })

        for path in sorted(OBJECT_TEMPLATES_DIR.glob("*.odt"), key=lambda p: p.name.lower()):
            entries.append({
                "name": path.stem,
                "path": path,
                "kind": "OBIEKT DO KASACJI",
                "deletable": True,
            })

        return entries


    def _read_template_preview(self, path):
        """Szybki i bezpieczny podgląd tekstu ODT bez odfpy.teletype.

        ODT jest kontenerem ZIP, a właściwy tekst znajduje się w content.xml.
        Dzięki temu podgląd nie zależy od klas-fabryk odfpy i nie powoduje
        błędów typu: isinstance() arg 2 must be a type.
        """
        import zipfile
        import xml.etree.ElementTree as ET

        try:
            path = Path(path)
            with zipfile.ZipFile(path, "r") as archive:
                xml_data = archive.read("content.xml")

            root = ET.fromstring(xml_data)

            def local_name(tag):
                return str(tag).split("}")[-1].lower()

            paragraphs = []

            def extract(element):
                result = []
                if element.text:
                    result.append(element.text)

                for child in list(element):
                    name = local_name(child.tag)

                    if name == "line-break":
                        result.append("\n")
                    elif name == "tab":
                        result.append("\t")
                    elif name == "s":
                        try:
                            count = int(child.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}c", "1"))
                        except Exception:
                            count = 1
                        result.append(" " * max(1, count))
                    else:
                        result.append(extract(child))

                    if child.tail:
                        result.append(child.tail)

                return "".join(result)

            for element in root.iter():
                if local_name(element.tag) in {"p", "h"}:
                    text = extract(element).strip()
                    if text:
                        paragraphs.append(text)

            result = "\n\n".join(paragraphs)

            if len(result) > 7000:
                result = result[:7000] + "\n\n…"

            return result or "(Szablon nie zawiera tekstu.)"

        except Exception as error:
            return (
                "Nie udało się odczytać podglądu.\n\n"
                + str(error)
            )


    def open_template_manager(self):
        """Pełnoekranowy wybór, podgląd, edycja i usuwanie szablonów."""
        manager = Toplevel(self.root)
        manager.title("ADMORA — Szablony")
        manager.configure(bg=COLORS["background"])
        try:
            manager.attributes("-fullscreen", True)
        except Exception:
            manager.state("zoomed")

        manager.protocol("WM_DELETE_WINDOW", manager.destroy)

        outer = ttk.Frame(manager, padding=30)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))

        ttk.Label(
            header,
            text="SZABLONY ORZECZEŃ",
            font=(FONT_MAIN, 26, "bold")
        ).pack(side="left")

        ttk.Label(
            header,
            text="Wybierz szablon, zobacz podgląd, edytuj albo usuń.",
            foreground=COLORS["text_secondary"]
        ).pack(side="left", padx=20, pady=(8, 0))

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=5)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        columns = ("type", "name")
        tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        tree.heading("type", text="TYP")
        tree.heading("name", text="SZABLON")
        tree.column("type", width=180, anchor="w")
        tree.column("name", width=420, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        right = ttk.Frame(content, padding=22)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)

        selected_name = StringVar(value="Wybierz szablon")
        selected_type = StringVar(value="")
        selected_path = StringVar(value="")

        ttk.Label(
            right,
            textvariable=selected_name,
            font=(FONT_MAIN, 20, "bold")
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            right,
            textvariable=selected_type,
            foreground=COLORS["blue"],
            font=(FONT_MAIN, 10, "bold")
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Label(
            right,
            textvariable=selected_path,
            foreground=COLORS["text_secondary"],
            font=(FONT_MAIN, 9)
        ).grid(row=2, column=0, sticky="w", pady=(4, 15))

        preview = ScrolledText(
            right,
            wrap="word",
            font=(FONT_MAIN, 11),
            bg=COLORS["white"],
            fg=COLORS["text"],
            relief="solid",
            borderwidth=1,
            padx=22,
            pady=20,
            state="disabled",
        )
        preview.grid(row=3, column=0, sticky="nsew")

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(15, 0))

        edit_btn = ttk.Button(footer, text="EDYTUJ SZABLON", style="Blue.TButton", state="disabled")
        delete_btn = ttk.Button(footer, text="USUŃ", style="Secondary.TButton", state="disabled")
        refresh_btn = ttk.Button(footer, text="ODŚWIEŻ", style="Secondary.TButton")
        add_btn = ttk.Button(footer, text="DODAJ OBIEKT", style="Secondary.TButton")
        close_btn = ttk.Button(footer, text="ZAMKNIJ", style="Secondary.TButton", command=manager.destroy)

        close_btn.pack(side="right")
        add_btn.pack(side="right", padx=(0, 8))
        refresh_btn.pack(side="right", padx=(0, 8))
        delete_btn.pack(side="left")
        edit_btn.pack(side="left", padx=(8, 0))

        entries = []

        def refresh():
            nonlocal entries
            entries = self._all_template_entries()
            for item in tree.get_children():
                tree.delete(item)
            for index, entry in enumerate(entries):
                tree.insert("", "end", iid=str(index), values=(entry["kind"], entry["name"]))
            selected_name.set("Wybierz szablon")
            selected_type.set("")
            selected_path.set("")
            preview.config(state="normal")
            preview.delete("1.0", END)
            preview.config(state="disabled")
            edit_btn.config(state="disabled")
            delete_btn.config(state="disabled")

        def current_entry():
            selection = tree.selection()
            if not selection:
                return None
            index = int(selection[0])
            if index < 0 or index >= len(entries):
                return None
            return entries[index]

        def select(event=None):
            entry = current_entry()
            if not entry:
                return
            selected_name.set(entry["name"])
            selected_type.set(entry["kind"])
            selected_path.set(str(entry["path"]))
            preview.config(state="normal")
            preview.delete("1.0", END)
            preview.insert("1.0", self._read_template_preview(entry["path"]))
            preview.config(state="disabled")
            edit_btn.config(state="normal")
            delete_btn.config(state="normal" if entry["deletable"] else "disabled")

        def edit_selected():
            entry = current_entry()
            if not entry:
                return
            self.editor = RichODTEditor(
                self.root,
                entry["path"],
                title="EDYCJA SZABLONU — " + entry["name"],
                on_saved=lambda path: self.template_edited(path),
            )

        def delete_selected():
            entry = current_entry()
            if not entry or not entry["deletable"]:
                return

            if not messagebox.askyesno(
                "Usuń szablon",
                "Czy na pewno usunąć szablon:\n\n" + entry["name"] + "?",
                parent=manager,
            ):
                return

            try:
                _call_delete_object(entry["name"], entry["path"])
            except Exception as error:
                # Jeżeli API nie rozpoznało obiektu, plik nadal można
                # usunąć ręcznie. Nie blokujemy użytkownika.
                if entry["kind"] == "OBIEKT DO KASACJI":
                    messagebox.showwarning(
                        "Usuwanie obiektu",
                        "Nie udało się zaktualizować rejestru obiektów.\n\n" + str(error),
                        parent=manager,
                    )
                    return

            try:
                Path(entry["path"]).unlink(missing_ok=True)
                self.set_status("Usunięto szablon: " + entry["name"])
                refresh()
            except Exception as error:
                messagebox.showerror("Usuwanie szablonu", str(error), parent=manager)

        def add_object_from_manager():
            manager.destroy()
            self.add_disposal_object()

        tree.bind("<<TreeviewSelect>>", select)
        edit_btn.config(command=edit_selected)
        delete_btn.config(command=delete_selected)
        refresh_btn.config(command=refresh)
        add_btn.config(command=add_object_from_manager)

        refresh()


    def add_disposal_object(self):
        """Tworzy kopię domyślnego ODT i od razu otwiera ją w edytorze ADMORA."""
        ensure_object_templates_directory()

        if not DEFAULT_TEMPLATE.exists():
            messagebox.showerror(
                "Nowy obiekt",
                "Nie znaleziono domyślnego szablonu:\n\n" + str(DEFAULT_TEMPLATE),
            )
            return

        dialog = Toplevel(self.root)
        dialog.title("ADMORA — Nowy obiekt do kasacji")
        dialog.configure(bg=COLORS["background"])
        try:
            dialog.attributes("-fullscreen", True)
        except Exception:
            dialog.state("zoomed")
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        dialog.transient(self.root)
        dialog.grab_set()

        outer = ttk.Frame(dialog, padding=70)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="NOWY OBIEKT DO KASACJI",
            font=(FONT_MAIN, 28, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Wystarczy nazwa obiektu. Nazwa będzie jednocześnie słowem kluczowym. "
                "Przykład: Drukarka → rozpozna „Drukarka HP LaserJet”."
            ),
            foreground=COLORS["text_secondary"],
            wraplength=1200,
        ).pack(anchor="w", pady=(8, 30))

        card = ttk.Frame(outer, padding=35)
        card.pack(fill="x", anchor="n")

        ttk.Label(card, text="Nazwa obiektu", font=(FONT_MAIN, 13, "bold")).pack(anchor="w")
        name_var = StringVar()
        entry = ttk.Entry(card, textvariable=name_var, font=(FONT_MAIN, 18))
        entry.pack(fill="x", pady=(10, 18), ipady=8)

        ttk.Label(card, text="Szablon startowy", font=(FONT_MAIN, 10, "bold"), foreground=COLORS["text_secondary"]).pack(anchor="w")
        ttk.Label(card, text=DEFAULT_TEMPLATE.name, font=(FONT_MAIN, 12, "bold")).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            card,
            text="Po utworzeniu otworzy się kopia tego szablonu w Pythonowym edytorze. Formatowanie podstawowych fragmentów tekstu zostanie zachowane, a plik pozostanie ODT.",
            foreground=COLORS["text_secondary"],
            wraplength=1100,
        ).pack(anchor="w", pady=(6, 0))

        ttk.Label(
            outer,
            text="PODGLĄD SZABLONU DOMYŚLNEGO",
            font=(FONT_MAIN, 11, "bold"),
            foreground=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(24, 8))

        default_preview = ScrolledText(
            outer,
            height=12,
            wrap="word",
            font=(FONT_MAIN, 10),
            bg=COLORS["white"],
            fg=COLORS["text"],
            relief="solid",
            borderwidth=1,
            padx=16,
            pady=12,
        )
        default_preview.pack(fill="both", expand=True)
        default_preview.insert("1.0", self._read_template_preview(DEFAULT_TEMPLATE))
        default_preview.config(state="disabled")

        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(25, 0))

        def cancel():
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        def create():
            object_name = clean(name_var.get())
            if not object_name:
                messagebox.showwarning("Nowy obiekt", "Podaj nazwę obiektu.", parent=dialog)
                entry.focus_set()
                return

            destination = OBJECT_TEMPLATES_DIR / (safe_filename(object_name) + ".odt")
            if destination.exists():
                if not messagebox.askyesno(
                    "Obiekt już istnieje",
                    "Szablon dla „" + object_name + "” już istnieje.\n\nUtworzyć nową wersję szablonu?",
                    parent=dialog,
                ):
                    return
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                destination = OBJECT_TEMPLATES_DIR / (safe_filename(object_name) + "_" + stamp + ".odt")

            try:
                ensure_object_templates_directory()
                shutil.copy2(DEFAULT_TEMPLATE, destination)
                _call_add_object(object_name, destination, [object_name])
                cancel()
                self.editor = RichODTEditor(
                    self.root,
                    destination,
                    title="NOWY SZABLON — " + object_name,
                    on_saved=lambda path, name=object_name: self.object_template_saved(name, path),
                )
                self.set_status("Edytujesz szablon obiektu: " + object_name)
            except Exception as error:
                messagebox.showerror("Nowy obiekt", str(error), parent=dialog)

        ttk.Button(footer, text="ANULUJ", style="Secondary.TButton", command=cancel).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="UTWÓRZ I EDYTUJ SZABLON", style="Blue.TButton", command=create).pack(side="right")

        entry.focus_set()
        dialog.bind("<Return>", lambda e: create())
        dialog.bind("<Escape>", lambda e: cancel())


    def object_template_saved(self, object_name, odt_path):
        self.set_status("Szablon obiektu „" + object_name + "” został zapisany.")
        self.template_var.set(Path(odt_path).name)
        if self.asset is not None:
            self.generate_preview()


    # ========================================================
    # DODAWANIE SZABLONU
    # ========================================================

    def add_template(self):

        file_path = filedialog.askopenfilename(

            title="Wybierz szablon ODT",

            filetypes=[

                (
                    "Dokument LibreOffice",
                    "*.odt"
                ),

                (
                    "Wszystkie pliki",
                    "*.*"
                ),

            ]

        )

        if not file_path:

            return

        source = Path(
            file_path
        )

        dialog = Toplevel(
            self.root
        )

        dialog.title(
            "Dodaj szablon"
        )

        dialog.geometry(
            "520x430"
        )

        dialog.resizable(
            False,
            False
        )

        dialog.transient(
            self.root
        )

        dialog.grab_set()

        # ----------------------------------------------------
        # X w oknie dialogowym działa normalnie
        # ----------------------------------------------------

        dialog.protocol(
            "WM_DELETE_WINDOW",
            dialog.destroy
        )

        frame = ttk.Frame(
            dialog,
            padding=30
        )

        frame.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            frame,
            text="Dodaj szablon",
            font=(
                FONT_MAIN,
                18,
                "bold"
            )
        ).pack(
            anchor="w",
            pady=(
                0,
                8
            )
        )

        ttk.Label(
            frame,
            text=(
                "Przypisz dokument do klasyfikacji urządzenia."
            ),
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(
                0,
                20
            )
        )

        category_var = StringVar(
            value="domyślny"
        )

        categories = [

            "komputer",

            "drukarka",

            "łóżko",

            "monitor",

            "telefon",

            "tablet",

            "skaner",

            "serwer",

            "kserokopiarka",

            "urządzenie medyczne",

            "domyślny",

        ]

        combo = ttk.Combobox(
            frame,
            textvariable=
                category_var,
            values=categories,
            state="readonly"
        )

        combo.pack(
            fill="x"
        )

        combo.focus_set()

        file_info = ttk.Frame(
            frame,
            padding=15
        )

        file_info.pack(
            fill="x",
            pady=20
        )

        ttk.Label(
            file_info,
            text="Wybrany plik",
            font=(
                FONT_MAIN,
                9,
                "bold"
            )
        ).pack(
            anchor="w"
        )

        ttk.Label(
            file_info,
            text=source.name,
            font=(
                FONT_MAIN,
                10
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(
                4,
                0
            )
        )

        ttk.Label(
            frame,
            text=(
                "Po zapisaniu szablon zostanie automatycznie "
                "użyty dla wybranej klasyfikacji."
            ),
            font=(
                FONT_MAIN,
                9
            ),
            foreground=
                COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(
                0,
                15
            )
        )

        def save_template():

            category = normalize_template_category(
                category_var.get()
            )

            if not category:

                messagebox.showwarning(
                    "Szablon",
                    "Wybierz kategorię.",
                    parent=dialog
                )

                return

            # ------------------------------------------------
            # SZABLON DLA KLASY
            # ------------------------------------------------

            if category == "domyślny":

                destination = (
                    TEMPLATES_DIR
                    / source.name
                )

            else:

                destination = (
                    category_template_path(
                        category
                    )
                )

                if destination is None:

                    destination = (
                        TEMPLATES_DIR
                        / (
                            safe_filename(
                                category
                            )
                            + ".odt"
                        )
                    )

            try:

                ensure_directories()

                shutil.copy2(
                    source,
                    destination
                )

                # ------------------------------------------------
                # NOWY SZABLON JEST OSTATNIO UŻYWANY
                # ------------------------------------------------

                save_last_template(
                    destination
                )

                dialog.destroy()

                self.template_var.set(
                    destination.name
                )

                messagebox.showinfo(
                    "Szablon",
                    (
                        "Szablon został dodany.\n\n"
                        "Klasyfikacja: "
                        + category
                        + "\n\n"
                        "Plik:\n"
                        + str(destination)
                    )
                )

                # ------------------------------------------------
                # JEŚLI AKTUALNIE JEST URZĄDZENIE,
                # OD RAZU ODŚWIEŻ PODGLĄD
                # ------------------------------------------------

                if self.asset:

                    self.generate_preview()

            except Exception as error:

                messagebox.showerror(
                    "Szablon",
                    str(error),
                    parent=dialog
                )

        ttk.Button(
            frame,
            text="ZAPISZ SZABLON",
            style="Blue.TButton",
            command=save_template
        ).pack(
            fill="x"
        )

        ttk.Button(
            frame,
            text="ANULUJ",
            style="Secondary.TButton",
            command=dialog.destroy
        ).pack(
            fill="x",
            pady=(
                8,
                0
            )
        )


    # ========================================================
    # ZAMKNIĘCIE
    # ========================================================

    def close(self):

        if self.closing:

            return

        self.closing = True

        try:

            if self.database:

                self.database.disconnect()

        except Exception:
            pass

        self.root.destroy()


# ============================================================
# START
# ============================================================

def main():

    root = Tk()

    root.title(
        "ADMORA — Generator orzeczeń technicznych"
    )

    root.configure(
        bg=COLORS["background"]
    )

    # ========================================================
    # FULLSCREEN
    # ========================================================

    root.attributes(
        "-fullscreen",
        True
    )

    root.minsize(
        1100,
        700
    )

    # ========================================================
    # STYL GLOBALNY
    # ========================================================

    style = ttk.Style()

    try:

        style.theme_use(
            "clam"
        )

    except Exception:
        pass

    style.configure(
        "TFrame",
        background=
            COLORS["background"]
    )

    style.configure(
        "TLabel",
        background=
            COLORS["background"],
        foreground=
            COLORS["text"]
    )

    style.configure(
        "TButton",
        font=(
            FONT_MAIN,
            10
        )
    )

    # ========================================================
    # F11
    # ========================================================

    def toggle_fullscreen(
        event=None
    ):

        current = root.attributes(
            "-fullscreen"
        )

        root.attributes(
            "-fullscreen",
            not current
        )


    root.bind(
        "<F11>",
        toggle_fullscreen
    )

    # ========================================================
    # ESC
    # ========================================================

    def escape_fullscreen(
        event=None
    ):

        root.attributes(
            "-fullscreen",
            False
        )


    root.bind(
        "<Escape>",
        escape_fullscreen
    )

    # ========================================================
    # CTRL+Q
    # ========================================================

    root.bind(
        "<Control-q>",
        lambda event:
            root.destroy()
    )

    # ========================================================
    # APLIKACJA
    # ========================================================

    Application(
        root
    )

    root.mainloop()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    main()
