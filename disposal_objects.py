# ============================================================
# disposal_objects.py
#
# ADMORA
# Własne obiekty do kasacji / reguły klasyfikacji
# ============================================================

from pathlib import Path
import json
import re


PROJECT_DIR = Path(__file__).resolve().parent

CONFIG_DIR = (
    PROJECT_DIR / "konfiguracja"
)

OBJECTS_FILE = (
    CONFIG_DIR / "obiekty_kasacji.json"
)


def ensure_objects_file():

    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not OBJECTS_FILE.exists():

        save_objects([])


def load_objects():

    ensure_objects_file()

    try:

        with open(
            OBJECTS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            list
        ):
            return []

        return data

    except Exception:

        return []


def save_objects(objects):

    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OBJECTS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            objects,
            file,
            ensure_ascii=False,
            indent=4
        )


def clean_text(value):

    if value is None:
        return ""

    value = str(value).strip().lower()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


def add_object(
    name,
    keywords,
    template
):

    name = str(
        name
    ).strip()

    template = str(
        template
    ).strip()

    keywords = [
        str(keyword).strip()
        for keyword in keywords
        if str(keyword).strip()
    ]

    if not name:
        raise ValueError(
            "Nazwa obiektu nie może być pusta."
        )

    if not keywords:
        keywords = [
            name
        ]

    objects = load_objects()

    # --------------------------------------------------------
    # Nie dodawaj dwóch takich samych obiektów.
    # --------------------------------------------------------

    for item in objects:

        if clean_text(
            item.get("name")
        ) == clean_text(
            name
        ):

            raise ValueError(
                "Obiekt o takiej nazwie już istnieje."
            )

    objects.append(
        {
            "name": name,
            "keywords": keywords,
            "template": template
        }
    )

    save_objects(
        objects
    )


def delete_object(name):

    objects = load_objects()

    name = clean_text(
        name
    )

    new_objects = [
        item
        for item in objects
        if clean_text(
            item.get("name")
        ) != name
    ]

    save_objects(
        new_objects
    )


def find_matching_object(
    asset_name
):

    asset_name = clean_text(
        asset_name
    )

    if not asset_name:
        return None

    objects = load_objects()

    # --------------------------------------------------------
    # Najpierw sprawdzamy najdłuższe nazwy.
    #
    # Dzięki temu np.
    #
    # "drukarka kolorowa"
    #
    # będzie miała pierwszeństwo przed:
    #
    # "drukarka"
    # --------------------------------------------------------

    objects = sorted(
        objects,
        key=lambda item: max(
            [
                len(
                    clean_text(keyword)
                )
                for keyword in item.get(
                    "keywords",
                    []
                )
            ] or [0]
        ),
        reverse=True
    )

    for item in objects:

        keywords = item.get(
            "keywords",
            []
        )

        for keyword in keywords:

            keyword = clean_text(
                keyword
            )

            if not keyword:
                continue

            if keyword in asset_name:

                return item

    return None


def get_matching_template(
    asset_name
):

    item = find_matching_object(
        asset_name
    )

    if not item:
        return None

    template = item.get(
        "template",
        ""
    )

    if not template:
        return None

    path = Path(
        template
    )

    if not path.is_absolute():

        path = (
            PROJECT_DIR / path
        )

    if not path.exists():

        return None

    return path


def get_object_names():

    return [
        item.get(
            "name",
            ""
        )
        for item in load_objects()
    ]