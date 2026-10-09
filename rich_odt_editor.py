# ============================================================
# rich_odt_editor.py
# ADMORA — lekki edytor tekstowy ODT
#
# Ważne:
#   Ten edytor NIE przebudowuje dokumentu przez odfpy.
#   Czyta bezpośrednio content.xml z kontenera ODT i przy zapisie
#   podmienia tylko zmienione akapity. Pozostałe elementy ODT
#   pozostają nietknięte.
#
# Dzięki temu:
#   - zapis jest szybki,
#   - nie znika reszta dokumentu,
#   - zachowywane są style akapitów,
#   - zachowywane są podstawowe style tekstu,
#   - nie występuje błąd isinstance(..., odfpy.P),
#   - nie ma podwójnego przewijania.
# ============================================================

from __future__ import annotations

import copy
import difflib
import os
import re
import stat
import subprocess
import time
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import Toplevel, StringVar, END, messagebox
from tkinter import ttk, Text, font as tkfont


# ============================================================
# XML / ODT namespaces
# ============================================================

NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
NS_FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
NS_SVG = "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
NS_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS_META = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_XFORM = "http://openoffice.org/2000/formula"
NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_PRESENTATION = "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"
NS_ANIM = "urn:oasis:names:tc:opendocument:xmlns:animation:1.0"
NS_SCRIPT = "urn:oasis:names:tc:opendocument:xmlns:script:1.0"
NS_CHART = "urn:oasis:names:tc:opendocument:xmlns:chart:1.0"
NS_FORM = "urn:oasis:names:tc:opendocument:xmlns:form:1.0"
NS_DOM = "http://www.w3.org/2001/xml-events"
NS_XSD = "http://www.w3.org/2001/XMLSchema"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

NAMESPACES = {
    "office": NS_OFFICE,
    "text": NS_TEXT,
    "style": NS_STYLE,
    "fo": NS_FO,
    "svg": NS_SVG,
    "draw": NS_DRAW,
    "xlink": NS_XLINK,
    "meta": NS_META,
    "dc": NS_DC,
    "table": NS_TABLE,
    "presentation": NS_PRESENTATION,
    "anim": NS_ANIM,
    "script": NS_SCRIPT,
    "chart": NS_CHART,
    "form": NS_FORM,
    "dom": NS_DOM,
    "xsd": NS_XSD,
    "xsi": NS_XSI,
}

for prefix, uri in NAMESPACES.items():
    try:
        ET.register_namespace(prefix, uri)
    except Exception:
        pass


# ============================================================
# UI
# ============================================================

COLORS = {
    "background": "#EEF1F5",
    "surface": "#F8FAFC",
    "page": "#FFFFFF",
    "border": "#D4DAE3",
    "text": "#202A35",
    "secondary": "#667385",
    "blue": "#316BEA",
    "blue_dark": "#2457C7",
    "blue_light": "#E7EEFF",
    "green": "#218653",
    "red": "#C93636",
    "white": "#FFFFFF",
}
FONT_MAIN = "Segoe UI"


# ============================================================
# helpers
# ============================================================


def qname(namespace, name):
    return "{" + namespace + "}" + name


def local_name(tag):
    if not isinstance(tag, str):
        return ""
    return tag.split("}")[-1].lower()


def attr_local(element, name, default=""):
    """Znajduje atrybut niezależnie od użytego namespace."""
    for key, value in element.attrib.items():
        if local_name(key) == name.lower():
            return value
    return default


def set_attr_local(element, namespace, name, value):
    element.set(qname(namespace, name), value)


def parse_pt(value, default=11):
    if not value:
        return default
    match = re.search(r"(-?[0-9]+(?:\.[0-9]+)?)", str(value))
    if not match:
        return default
    try:
        return max(6, min(72, int(round(float(match.group(1))))))
    except Exception:
        return default


def parse_dimension(value):
    if not value:
        return 0
    match = re.match(r"\s*(-?[0-9.]+)\s*(cm|mm|in|pt|px)?\s*$", str(value).lower())
    if not match:
        return 0
    try:
        number = float(match.group(1))
    except Exception:
        return 0
    unit = match.group(2) or "px"
    if unit == "cm":
        return int(round(number * 37.7953))
    if unit == "mm":
        return int(round(number * 3.77953))
    if unit == "in":
        return int(round(number * 96))
    if unit == "pt":
        return int(round(number * 96 / 72))
    return int(round(number))


def text_node_value(element):
    return element.text or ""


# ============================================================
# EDITOR
# ============================================================


class RichODTEditor:

    def __init__(self, parent, odt_path, title="Edytor szablonu", on_saved=None):
        self.parent = parent
        self.odt_path = Path(odt_path)
        self.title = title
        self.on_saved = on_saved

        self.root_xml = None
        self.paragraphs = []
        self.original_paragraph_text = []
        self.original_char_styles = []
        self.original_style_names = []
        self.paragraph_alignments = []
        self.paragraph_alignment_changed = []

        self.text_style_cache = {}
        self.paragraph_style_cache = {}
        self.tag_to_props = {}
        self.paragraph_tags = []

        self.loading = False
        self.saving = False
        self.saved = False

        self.zoom = 1.0

        self.window = Toplevel(parent)
        self.window.title(self.title)
        self.window.configure(bg=COLORS["background"])

        try:
            self.window.attributes("-fullscreen", True)
        except Exception:
            self.window.state("zoomed")

        # Bez systemowego X — zamykamy tylko przyciskami ADMORA.
        try:
            self.window.overrideredirect(True)
        except Exception:
            pass
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)

        self.font_var = StringVar(value=FONT_MAIN)
        self.size_var = StringVar(value="11")
        self.zoom_var = StringVar(value="100%")
        self.status_var = StringVar(value="Ładowanie…")

        self._build_style()
        self._build_ui()
        self._load_document()

    # --------------------------------------------------------
    # style
    # --------------------------------------------------------

    def _build_style(self):
        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Editor.TFrame", background=COLORS["background"])
        style.configure(
            "Editor.TButton",
            font=(FONT_MAIN, 9, "bold"),
            padding=(9, 6),
        )
        style.configure(
            "EditorBlue.TButton",
            font=(FONT_MAIN, 10, "bold"),
            padding=(16, 9),
            foreground=COLORS["white"],
            background=COLORS["blue"],
        )
        style.map(
            "EditorBlue.TButton",
            background=[("active", COLORS["blue_dark"])],
        )
        style.configure(
            "Editor.TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
        )
        style.configure(
            "Editor.TCombobox",
            padding=4,
        )

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _build_ui(self):
        main = ttk.Frame(self.window, style="Editor.TFrame", padding=(18, 12))
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main, style="Editor.TFrame")
        header.pack(fill="x", pady=(0, 5))

        ttk.Label(
            header,
            text="EDYTOR SZABLONU",
            style="Editor.TLabel",
            font=(FONT_MAIN, 20, "bold"),
        ).pack(side="left")

        ttk.Label(
            header,
            text=self.odt_path.name,
            style="Editor.TLabel",
            foreground=COLORS["blue"],
            font=(FONT_MAIN, 10, "bold"),
        ).pack(side="right")

        ttk.Label(
            main,
            text=str(self.odt_path),
            style="Editor.TLabel",
            foreground=COLORS["secondary"],
            font=(FONT_MAIN, 8),
        ).pack(anchor="w", pady=(0, 8))

        # Pierwszy pasek narzędzi.
        toolbar = ttk.Frame(main, style="Editor.TFrame")
        toolbar.pack(fill="x", pady=(0, 5))

        ttk.Button(toolbar, text="↶", width=3, style="Editor.TButton", command=self.undo).pack(side="left", padx=2)
        ttk.Button(toolbar, text="↷", width=3, style="Editor.TButton", command=self.redo).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=7)

        ttk.Button(toolbar, text="B", width=3, style="Editor.TButton", command=lambda: self.toggle_tag("bold")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="I", width=3, style="Editor.TButton", command=lambda: self.toggle_tag("italic")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="U", width=3, style="Editor.TButton", command=lambda: self.toggle_tag("underline")).pack(side="left", padx=2)

        ttk.Label(toolbar, text="Czcionka", style="Editor.TLabel").pack(side="left", padx=(10, 4))
        fonts = sorted(set(tkfont.families(self.window)))
        self.font_combo = ttk.Combobox(
            toolbar,
            textvariable=self.font_var,
            values=fonts,
            width=17,
        )
        self.font_combo.pack(side="left", padx=(0, 5))
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_font())
        self.font_combo.bind("<Return>", lambda e: self.apply_font())

        ttk.Label(toolbar, text="Rozmiar", style="Editor.TLabel").pack(side="left", padx=(3, 4))
        self.size_combo = ttk.Combobox(
            toolbar,
            textvariable=self.size_var,
            values=[str(i) for i in range(8, 41)],
            width=5,
        )
        self.size_combo.pack(side="left", padx=(0, 6))
        self.size_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_size())
        self.size_combo.bind("<Return>", lambda e: self.apply_size())

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=7)

        for label, value in (
            ("LEWO", "left"),
            ("ŚRODEK", "center"),
            ("PRAWO", "right"),
            ("JUSTUJ", "justify"),
        ):
            ttk.Button(
                toolbar,
                text=label,
                style="Editor.TButton",
                command=lambda v=value: self.align(v),
            ).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=7)

        ttk.Label(toolbar, text="Widok", style="Editor.TLabel").pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="−", width=3, style="Editor.TButton", command=lambda: self.set_zoom(-0.1)).pack(side="left", padx=1)
        ttk.Label(toolbar, textvariable=self.zoom_var, width=6, anchor="center", style="Editor.TLabel").pack(side="left")
        ttk.Button(toolbar, text="+", width=3, style="Editor.TButton", command=lambda: self.set_zoom(0.1)).pack(side="left", padx=1)

        # Drugi pasek — placeholdery.
        placeholder = ttk.Frame(main, style="Editor.TFrame")
        placeholder.pack(fill="x", pady=(0, 8))

        ttk.Label(
            placeholder,
            text="PLACEHOLDERY",
            style="Editor.TLabel",
            font=(FONT_MAIN, 8, "bold"),
        ).pack(side="left", padx=(0, 6))

        placeholders = (
            "{miejsce}", "{nazwa}", "{paszport}", "{comp}",
            "{num_fab}", "{st_num_inv}", "{if_iscomp}",
            "{brand}", "{model}", "{time}", "{curr_time-time}",
        )
        for value in placeholders:
            ttk.Button(
                placeholder,
                text=value,
                style="Editor.TButton",
                command=lambda v=value: self.insert_text(v),
            ).pack(side="left", padx=1)

        # Jedna przestrzeń przewijania.
        # Nie ma już Canvas + ScrolledText, więc nie ma dwóch scrollbarów.
        workspace = ttk.Frame(main, style="Editor.TFrame")
        workspace.pack(fill="both", expand=True)

        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)

        self.page = ttk.Frame(
            workspace,
            style="Editor.TFrame",
            width=794,
            height=1123,
        )
        self.page.grid(row=0, column=0, sticky="n", pady=10)
        self.page.grid_propagate(False)

        # Kartka A4.
        self.text_frame = ttk.Frame(
            self.page,
            style="Editor.TFrame",
            padding=1,
        )
        self.text_frame.pack(fill="both", expand=True)

        self.text = Text(
            self.text_frame,
            wrap="word",
            undo=True,
            maxundo=-1,
            font=(FONT_MAIN, 11),
            bg=COLORS["page"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground="#CFE0FF",
            selectforeground=COLORS["text"],
            relief="solid",
            borderwidth=1,
            padx=72,
            pady=68,
            spacing1=0,
            spacing2=0,
            spacing3=0,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        self.text_scroll = ttk.Scrollbar(
            self.text_frame,
            orient="vertical",
            command=self.text.yview,
        )
        self.text_scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=self.text_scroll.set)

        self.text_frame.columnconfigure(0, weight=1)
        self.text_frame.rowconfigure(0, weight=1)

        self.text.bind("<Control-s>", self._ctrl_s)
        self.text.bind("<<Modified>>", self._mark_dirty)
        self.text.bind("<Control-b>", lambda e: self._hotkey("bold"))
        self.text.bind("<Control-i>", lambda e: self._hotkey("italic"))
        self.text.bind("<Control-u>", lambda e: self._hotkey("underline"))
        self.text.bind("<KeyRelease>", self._on_changed)

        # Stopka.
        footer = ttk.Frame(main, style="Editor.TFrame")
        footer.pack(fill="x", pady=(8, 0))

        ttk.Label(
            footer,
            textvariable=self.status_var,
            style="Editor.TLabel",
            foreground=COLORS["secondary"],
        ).pack(side="left")

        self.cancel_button = ttk.Button(
            footer,
            text="ANULUJ",
            style="Editor.TButton",
            command=self.close,
        )
        self.cancel_button.pack(side="right", padx=(8, 0))

        self.save_button = ttk.Button(
            footer,
            text="ZAPISZ",
            style="EditorBlue.TButton",
            command=self.save,
        )
        self.save_button.pack(side="right")

    # --------------------------------------------------------
    # LOAD ODT
    # --------------------------------------------------------

    def _load_document(self):
        self.loading = True
        try:
            if not self.odt_path.exists():
                raise FileNotFoundError(str(self.odt_path))

            with zipfile.ZipFile(self.odt_path, "r") as archive:
                xml_data = archive.read("content.xml")

            self.root_xml = ET.fromstring(xml_data)
            self._build_style_cache()

            self.paragraphs = list(self._iter_paragraphs(self.root_xml))
            self.original_paragraph_text = []
            self.original_char_styles = []
            self.original_style_names = []
            self.paragraph_alignments = []
            self.paragraph_alignment_changed = []
            self.paragraph_tags = []

            self.text.delete("1.0", END)

            for index, paragraph in enumerate(self.paragraphs):
                text_value, char_styles = self._extract_paragraph(paragraph)
                style_name = attr_local(paragraph, "style-name", "")

                self.original_paragraph_text.append(text_value)
                self.original_char_styles.append(char_styles)
                self.original_style_names.append(style_name)
                self.paragraph_alignments.append(self._paragraph_alignment(style_name))
                self.paragraph_alignment_changed.append(False)

                start = self.text.index("end-1c")
                self._insert_styled_text(text_value, char_styles)
                end = self.text.index("end-1c")

                tag = f"para_{index}"
                self.paragraph_tags.append(tag)
                self._configure_paragraph_tag(tag, index)
                self.text.tag_add(tag, start, end)

                if index < len(self.paragraphs) - 1:
                    self.text.insert("end", "\n")

            self.text.edit_reset()
            self.text.edit_modified(False)
            self.saved = True
            self.status_var.set(
                f"Gotowy • {len(self.paragraphs)} akapitów • zapis ODT bez przebudowy dokumentu"
            )
            self.window.after(100, self._center_page)

        except Exception as error:
            self.status_var.set("Błąd otwierania ODT.")
            messagebox.showerror(
                "Edytor ODT",
                "Nie udało się otworzyć dokumentu:\n\n" + str(error),
                parent=self.window,
            )
        finally:
            self.loading = False

    def _iter_paragraphs(self, root):
        for element in root.iter():
            name = local_name(element.tag)
            if name in {"p", "h"}:
                yield element

    # --------------------------------------------------------
    # STYLE CACHE
    # --------------------------------------------------------

    def _build_style_cache(self):
        self.text_style_cache = {}
        self.paragraph_style_cache = {}

        for element in self.root_xml.iter():
            if local_name(element.tag) != "style":
                continue

            name = attr_local(element, "name", "")
            if not name:
                continue

            parent = attr_local(element, "parent-style-name", "")
            text_props = {}
            paragraph_props = {}

            for child in list(element):
                child_name = local_name(child.tag)
                if child_name == "text-properties":
                    text_props = self._read_text_properties(child)
                elif child_name == "paragraph-properties":
                    paragraph_props = self._read_paragraph_properties(child)

            self.text_style_cache[name] = {
                "parent": parent,
                **text_props,
            }
            self.paragraph_style_cache[name] = {
                "parent": parent,
                **paragraph_props,
            }

    def _read_text_properties(self, element):
        font = (
            attr_local(element, "font-family", "")
            or attr_local(element, "font-name", "")
            or attr_local(element, "font-family-asian", "")
            or attr_local(element, "font-name-asian", "")
        )
        size = (
            attr_local(element, "font-size", "")
            or attr_local(element, "font-size-asian", "")
        )
        weight = attr_local(element, "font-weight", "").lower()
        italic = attr_local(element, "font-style", "").lower()
        underline = attr_local(element, "text-underline-style", "").lower()
        color = attr_local(element, "color", "")

        return {
            "font": font,
            "size": parse_pt(size, 11),
            "bold": weight in {"bold", "700", "800", "900"},
            "italic": italic in {"italic", "oblique"},
            "underline": underline not in {"", "none"},
            "color": color,
        }

    def _read_paragraph_properties(self, element):
        align = (
            attr_local(element, "text-align", "")
            or attr_local(element, "text-align-last", "")
            or "left"
        ).lower()
        if align not in {"left", "center", "right", "justify"}:
            align = "left"

        return {
            "align": align,
            "margin_left": parse_dimension(attr_local(element, "margin-left", "")),
            "margin_right": parse_dimension(attr_local(element, "margin-right", "")),
            "indent": parse_dimension(attr_local(element, "text-indent", "")),
            "top": parse_dimension(attr_local(element, "margin-top", "")),
            "bottom": parse_dimension(attr_local(element, "margin-bottom", "")),
        }

    def _resolved_text_style(self, style_name):
        result = {
            "font": FONT_MAIN,
            "size": 11,
            "bold": False,
            "italic": False,
            "underline": False,
            "color": "",
        }
        visited = set()
        current = style_name

        chain = []
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            current = self.text_style_cache.get(current, {}).get("parent", "")

        for name in reversed(chain):
            values = self.text_style_cache.get(name, {})
            for key in result:
                value = values.get(key)
                if value not in (None, ""):
                    result[key] = value
        return result

    def _resolved_paragraph_style(self, style_name):
        result = {
            "align": "left",
            "margin_left": 0,
            "margin_right": 0,
            "indent": 0,
            "top": 0,
            "bottom": 0,
        }
        visited = set()
        current = style_name
        chain = []

        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            current = self.paragraph_style_cache.get(current, {}).get("parent", "")

        for name in reversed(chain):
            values = self.paragraph_style_cache.get(name, {})
            for key in result:
                value = values.get(key)
                if value not in (None, ""):
                    result[key] = value
        return result

    def _paragraph_alignment(self, style_name):
        return self._resolved_paragraph_style(style_name).get("align", "left")

    # --------------------------------------------------------
    # ODT paragraph -> text + styles
    # --------------------------------------------------------

    def _extract_paragraph(self, paragraph):
        chars = []
        styles = []

        def add_text(value, props):
            if not value:
                return
            for char in value:
                chars.append(char)
                styles.append(dict(props))

        def walk(element, inherited):
            props = dict(inherited)
            name = local_name(element.tag)

            if name == "span":
                style_name = attr_local(element, "style-name", "")
                if style_name:
                    props = self._resolved_text_style(style_name)

            if element.text:
                add_text(element.text, props)

            for child in list(element):
                child_name = local_name(child.tag)

                if child_name == "line-break":
                    add_text("\n", props)
                elif child_name == "tab":
                    add_text("\t", props)
                elif child_name == "s":
                    count = attr_local(child, "c", "1")
                    try:
                        count = max(1, int(count))
                    except Exception:
                        count = 1
                    add_text(" " * count, props)
                elif child_name in {"page-number", "page-count", "date", "time", "sequence"}:
                    # Pola/field zostawiamy jako pusty tekst w edytorze.
                    # Nie niszczymy ich, jeżeli akapit nie zostanie zmieniony.
                    pass
                else:
                    walk(child, props)

                if child.tail:
                    add_text(child.tail, props)

        walk(paragraph, self._resolved_text_style(""))
        return "".join(chars), styles

    def _insert_styled_text(self, text_value, styles):
        if not text_value:
            return

        if len(styles) != len(text_value):
            styles = [self._resolved_text_style("")] * len(text_value)

        start = 0
        while start < len(text_value):
            current = styles[start]
            end = start + 1
            while end < len(text_value) and styles[end] == current:
                end += 1

            chunk = text_value[start:end]
            if chunk:
                self.text.insert("end", chunk, self._tag_for(current))
            start = end

    # --------------------------------------------------------
    # Tk formatting
    # --------------------------------------------------------

    def _tag_for(self, props):
        props = props or {}
        key = (
            props.get("font") or FONT_MAIN,
            int(props.get("size") or 11),
            bool(props.get("bold")),
            bool(props.get("italic")),
            bool(props.get("underline")),
            props.get("color") or "",
        )
        tag = "txt_" + str(abs(hash(key)))

        if tag not in self.tag_to_props:
            font_name, size, bold, italic, underline, color = key
            font_weight = "bold" if bold else "normal"
            slant = "italic" if italic else "roman"
            kwargs = {
                "font": (font_name, size, font_weight, slant),
                "underline": 1 if underline else 0,
            }
            if color and color.startswith("#"):
                kwargs["foreground"] = color

            self.text.tag_configure(tag, **kwargs)
            self.tag_to_props[tag] = dict(props)

        return tag

    def _configure_paragraph_tag(self, tag, index):
        style_name = self.original_style_names[index] if index < len(self.original_style_names) else ""
        props = self._resolved_paragraph_style(style_name)

        # Tk Text nie ma justowania. Wizualnie pokazujemy tekst od lewej,
        # natomiast wartość justify zostaje zapisana do ODT.
        visual = props.get("align", "left")
        if visual not in {"left", "center", "right"}:
            visual = "left"

        options = {"justify": visual}

        if props.get("margin_left"):
            options["lmargin1"] = props["margin_left"]
            options["lmargin2"] = props["margin_left"]
        if props.get("margin_right"):
            options["rmargin"] = props["margin_right"]
        if props.get("indent"):
            options["lmargin1"] = max(0, props["margin_left"] + props["indent"])
        if props.get("top"):
            options["spacing1"] = props["top"]
        if props.get("bottom"):
            options["spacing3"] = props["bottom"]

        self.text.tag_configure(tag, **options)

    # --------------------------------------------------------
    # Editing
    # --------------------------------------------------------

    def _selected_range(self):
        try:
            return self.text.index("sel.first"), self.text.index("sel.last")
        except Exception:
            return None, None

    def _current_properties(self):
        start, _ = self._selected_range()
        index = start or self.text.index("insert")
        tags = self.text.tag_names(index)

        for tag in reversed(tags):
            if tag in self.tag_to_props:
                return dict(self.tag_to_props[tag])

        return {
            "font": FONT_MAIN,
            "size": 11,
            "bold": False,
            "italic": False,
            "underline": False,
            "color": "",
        }

    def _apply_properties(self, props):
        start, end = self._selected_range()
        if not start or not end:
            return

        tag = self._tag_for(props)
        for existing in list(self.tag_to_props):
            try:
                self.text.tag_remove(existing, start, end)
            except Exception:
                pass
        self.text.tag_add(tag, start, end)
        self.text.focus_set()
        self.saved = False

    def toggle_tag(self, which):
        start, end = self._selected_range()
        if not start or not end:
            return
        props = self._current_properties()
        props[which] = not bool(props.get(which))
        self._apply_properties(props)

    def _hotkey(self, which):
        self.toggle_tag(which)
        return "break"

    def apply_font(self):
        props = self._current_properties()
        props["font"] = self.font_var.get().strip() or FONT_MAIN
        self._apply_properties(props)

    def apply_size(self):
        try:
            size = int(float(self.size_var.get()))
        except Exception:
            size = 11
        props = self._current_properties()
        props["size"] = max(6, min(72, size))
        self._apply_properties(props)

    def _current_paragraph_index(self):
        try:
            line = int(self.text.index("insert").split(".")[0]) - 1
            return max(0, min(line, len(self.paragraphs) - 1))
        except Exception:
            return 0

    def align(self, value):
        index = self._current_paragraph_index()
        if index >= len(self.paragraphs):
            return

        tag = self.paragraph_tags[index]
        visual = value if value in {"left", "center", "right"} else "left"
        self.text.tag_configure(tag, justify=visual)

        self.paragraph_alignments[index] = value
        self.paragraph_alignment_changed[index] = True
        self.saved = False

        if value == "justify":
            self.status_var.set("Justowanie zostanie zapisane w ODT.")
        else:
            self.status_var.set("Wyrównanie: " + value.upper())

    def insert_text(self, value):
        self.text.insert("insert", value)
        self.text.focus_set()
        self.saved = False
        self.cancel_button.configure(text="ANULUJ", command=self.close)

    def set_zoom(self, delta):
        self.zoom = max(0.85, min(1.15, self.zoom + delta))
        percent = int(round(self.zoom * 100))
        self.zoom_var.set(str(percent) + "%")

        width = int(round(794 * self.zoom))
        height = int(round(1123 * self.zoom))
        self.page.configure(width=width, height=height)

        # Nie zmieniamy rozmiaru tekstu — zoom jest tylko rozmiarem kartki.

    def undo(self):
        try:
            self.text.edit_undo()
            self.saved = False
        except Exception:
            pass

    def redo(self):
        try:
            self.text.edit_redo()
            self.saved = False
        except Exception:
            pass

    def _on_changed(self, event=None):
        if not self.loading:
            self.saved = False
            self.status_var.set("Niezapisane zmiany")

    def _center_page(self):
        try:
            workspace = self.page.master
            available = workspace.winfo_width()
            width = self.page.winfo_reqwidth()
            if available > width:
                self.page.grid_configure(padx=(available - width) // 2)
            else:
                self.page.grid_configure(padx=0)
        except Exception:
            pass

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    def save(self):
        if self.saving:
            return False
        if self.root_xml is None:
            return False

        self.saving = True
        self.save_button.configure(state="disabled", text="ZAPISYWANIE…")
        self.status_var.set("Zapisywanie ODT…")
        self.window.update_idletasks()

        try:
            current_lines = self.text.get("1.0", "end-1c").split("\n")
            old_lines = list(self.original_paragraph_text)
            old_paragraphs = list(self.paragraphs)
            old_alignments = list(self.paragraph_alignments)
            old_changed = list(self.paragraph_alignment_changed)
            old_styles = list(self.original_char_styles)
            old_style_names = list(self.original_style_names)

            # Dopasowujemy stare i nowe akapity. Dzięki temu można dowolnie
            # dodawać, usuwać i przestawiać treść bez blokowania zapisu.
            matcher = difflib.SequenceMatcher(None, old_lines, current_lines, autojunk=False)
            new_paragraphs = []
            new_alignments = []
            new_alignment_changed = []
            new_char_styles = []
            new_style_names = []

            def nearest_template(index):
                # Szukamy istniejącego akapitu najbliżej miejsca wstawienia.
                if old_paragraphs:
                    if index < len(old_paragraphs):
                        return old_paragraphs[index], index
                    return old_paragraphs[-1], len(old_paragraphs) - 1
                return None, -1

            def insert_before_or_after(clone, new_index, anchor_old_index):
                if anchor_old_index >= 0:
                    # Wstaw przed pierwszym zachowanym akapitem po tej pozycji.
                    for p in new_paragraphs[new_index:]:
                        parent = self._find_parent(self.root_xml, p)
                        if parent is not None:
                            try:
                                pos = list(parent).index(p)
                                parent.insert(pos, clone)
                                return
                            except ValueError:
                                pass
                # Fallback: po ostatnim już utworzonym akapicie.
                if new_paragraphs:
                    last = new_paragraphs[-1]
                    parent = self._find_parent(self.root_xml, last)
                    if parent is not None:
                        try:
                            pos = list(parent).index(last)
                            parent.insert(pos + 1, clone)
                            return
                        except ValueError:
                            pass
                body_parent = self._find_parent(self.root_xml, old_paragraphs[0]) if old_paragraphs else None
                if body_parent is not None:
                    body_parent.append(clone)

            changed = 0
            inserted = 0
            deleted = 0

            # Najpierw przetwarzamy sekwencję od lewej do prawej. Istniejące
            # akapity są ponownie wykorzystywane, a nowe dostają kopię stylu
            # sąsiedniego akapitu.
            old_cursor = 0
            new_cursor = 0
            opcodes = matcher.get_opcodes()

            # Usunięte/zmienione w XML obsługujemy przez operacje na blokach.
            for tag, i1, i2, j1, j2 in opcodes:
                if tag == "equal":
                    for oi, nj in zip(range(i1, i2), range(j1, j2)):
                        paragraph = old_paragraphs[oi]
                        text_value = current_lines[nj]
                        if text_value != old_lines[oi]:
                            self._rewrite_paragraph_preserving_styles(
                                paragraph, old_lines[oi], old_styles[oi], text_value
                            )
                            changed += 1
                        if oi < len(old_changed) and old_changed[oi]:
                            self.paragraph_alignments = old_alignments
                            self.original_style_names = old_style_names
                            self._save_alignment(paragraph, oi)
                        new_paragraphs.append(paragraph)
                        new_alignments.append(old_alignments[oi] if oi < len(old_alignments) else "left")
                        new_alignment_changed.append(False)
                        new_char_styles.append(self._extract_paragraph(paragraph)[1])
                        new_style_names.append(attr_local(paragraph, "style-name", ""))
                    continue

                if tag in ("replace", "delete"):
                    # Stare akapity, które nie mają odpowiednika, usuwamy.
                    for oi in range(i1, i2):
                        paragraph = old_paragraphs[oi]
                        self._remove_paragraph_from_xml(paragraph)
                        deleted += 1

                if tag in ("replace", "insert"):
                    # Dla każdego nowego akapitu klonujemy wzorzec z najbliższego
                    # starego akapitu. Kopia zachowuje styl akapitu i formatowanie.
                    for nj in range(j1, j2):
                        template, template_index = nearest_template(nj)
                        if template is None:
                            continue
                        clone = self._clone_paragraph(template)
                        new_text = current_lines[nj]
                        template_text = old_lines[template_index] if template_index >= 0 else ""
                        template_styles = old_styles[template_index] if template_index >= 0 else []
                        self._rewrite_paragraph_preserving_styles(
                            clone, template_text, template_styles, new_text
                        )
                        insert_before_or_after(clone, len(new_paragraphs), i2)
                        new_paragraphs.append(clone)
                        new_alignments.append(old_alignments[template_index] if template_index >= 0 else "left")
                        new_alignment_changed.append(False)
                        new_char_styles.append(self._extract_paragraph(clone)[1])
                        new_style_names.append(attr_local(clone, "style-name", ""))
                        inserted += 1

            # Zastosuj wyrównanie również do akapitów, których tekst został
            # zastąpiony albo nowo utworzony. Wcześniej w takich przypadkach
            # _save_alignment() nie był wywoływany, więc zmiana wyrównania mogła
            # zniknąć po zapisie.
            for new_index, paragraph in enumerate(new_paragraphs):
                if new_index < len(new_alignment_changed) and new_alignment_changed[new_index]:
                    old_alignment_list = self.paragraph_alignments
                    old_style_list = self.original_style_names
                    self.paragraph_alignments = new_alignments
                    self.original_style_names = new_style_names
                    try:
                        self._save_alignment(paragraph, new_index)
                    finally:
                        self.paragraph_alignments = old_alignment_list
                        self.original_style_names = old_style_list

            # SequenceMatcher dla replace może pozostawić kolejność XML niezgodną
            # z kolejnością edytora. Przebudowujemy kolejność akapitów w ich wspólnym
            # rodzicu, zachowując elementy niebędące akapitami.
            self._reorder_paragraphs_in_xml(new_paragraphs)

            self.paragraphs = new_paragraphs
            self.paragraph_alignments = new_alignments
            self.paragraph_alignment_changed = new_alignment_changed
            self.original_paragraph_text = list(current_lines)
            self.original_char_styles = new_char_styles
            self.original_style_names = new_style_names

            self._write_odt()

            self.saved = True
            self.text.edit_modified(False)
            self.cancel_button.configure(text="OK", command=self.close)
            self.status_var.set(
                "✓ Zapisano ODT"
                + (f" • zmienione: {changed}" if changed else "")
                + (f" • dodane: {inserted}" if inserted else "")
                + (f" • usunięte: {deleted}" if deleted else "")
            )

            if self.on_saved:
                callback = self.on_saved
                def run_callback():
                    try:
                        callback(self.odt_path)
                    except Exception as callback_error:
                        messagebox.showwarning(
                            "Zapisano ODT",
                            "Dokument zapisano, ale odświeżenie podglądu nie powiodło się:\n\n" + str(callback_error),
                            parent=self.window,
                        )
                self.window.after(50, run_callback)
            return True

        except Exception as error:
            self.saved = False
            self.status_var.set("Błąd zapisu ODT")
            messagebox.showerror("Edytor ODT", "Nie udało się zapisać dokumentu:\n\n" + str(error), parent=self.window)
            return False
        finally:
            self.saving = False
            self.save_button.configure(state="normal", text="ZAPISZ")

    def _find_parent(self, root, target):
        """Zwraca element XML, który bezpośrednio zawiera target."""
        if root is None or target is None:
            return None
        for parent in root.iter():
            for child in list(parent):
                if child is target:
                    return parent
        return None

    def _clone_paragraph(self, paragraph):
        """Tworzy kopię akapitu wraz z jego stylem, ale bez starej treści."""
        clone = copy.deepcopy(paragraph)
        self._clear_paragraph_content(clone)
        return clone

    def _clear_paragraph_content(self, paragraph):
        """Usuwa zawartość tekstową akapitu, pozostawiając atrybuty/style akapitu."""
        paragraph.text = None
        for child in list(paragraph):
            paragraph.remove(child)

    def _remove_paragraph_from_xml(self, paragraph):
        """Bezpiecznie usuwa akapit z content.xml."""
        if paragraph is None or self.root_xml is None:
            return False
        parent = self._find_parent(self.root_xml, paragraph)
        if parent is None:
            return False
        try:
            parent.remove(paragraph)
            return True
        except ValueError:
            return False

    def _reorder_paragraphs_in_xml(self, paragraphs):
        if not paragraphs:
            return
        parent = self._find_parent(self.root_xml, paragraphs[0])
        if parent is None:
            return
        current = [child for child in list(parent) if child in paragraphs]
        if not current:
            return
        positions = [list(parent).index(p) for p in current]
        insert_at = min(positions)
        for p in current:
            parent.remove(p)
        for offset, p in enumerate(paragraphs):
            parent.insert(insert_at + offset, p)

    def _rewrite_paragraph_preserving_styles(self, paragraph, old_text, old_styles, new_text):
        """Przepisuje tylko zawartość tekstową akapitu.

        Style znaków są przenoszone na podstawie SequenceMatcher. Dzięki temu
        np. pogrubiony nagłówek pozostaje pogrubiony po poprawieniu jego treści.
        """
        if not old_styles:
            old_styles = [self._resolved_text_style("")] * len(old_text)

        char_styles = self._map_styles(old_text, old_styles, new_text)

        # Jeżeli akapit zawiera skomplikowane elementy nietekstowe, nie próbujemy
        # ich niszczyć. Dla zwykłego szablonu tekstowego odbudowujemy tylko
        # warstwę inline.
        removable = []
        for child in list(paragraph):
            name = local_name(child.tag)
            if name in {
                "span", "s", "tab", "line-break", "a", "ruby",
                "soft-page-break",
            }:
                removable.append(child)
            elif child.text:
                removable.append(child)

        # Dla zwykłych paragrafów jest bezpiecznie usunąć zawartość i wstawić
        # nowe spany. Nie zmieniamy atrybutów samego <text:p>.
        for child in list(paragraph):
            paragraph.remove(child)
        paragraph.text = None

        self._append_styled_content(paragraph, new_text, char_styles)

    def _map_styles(self, old_text, old_styles, new_text):
        if not new_text:
            return []
        if not old_text:
            base = self._resolved_text_style("")
            return [dict(base) for _ in new_text]

        matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
        result = [None] * len(new_text)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for offset in range(j2 - j1):
                    result[j1 + offset] = dict(old_styles[i1 + offset])
            else:
                if i1 < len(old_styles):
                    style = dict(old_styles[i1])
                elif i1 > 0 and i1 - 1 < len(old_styles):
                    style = dict(old_styles[i1 - 1])
                else:
                    style = self._resolved_text_style("")
                for pos in range(j1, j2):
                    result[pos] = dict(style)

        fallback = self._resolved_text_style("")
        return [x if x is not None else dict(fallback) for x in result]

    def _append_styled_content(self, paragraph, text_value, styles):
        if not text_value:
            return

        if len(styles) != len(text_value):
            styles = [self._resolved_text_style("")] * len(text_value)

        # Grupujemy znaki według stylu.
        groups = []
        start = 0
        while start < len(text_value):
            current = styles[start]
            end = start + 1
            while end < len(text_value) and styles[end] == current:
                end += 1
            groups.append((start, end, current))
            start = end

        for start, end, props in groups:
            chunk = text_value[start:end]
            self._append_text_chunk(paragraph, chunk, props)

    def _append_text_chunk(self, paragraph, chunk, props):
        if not chunk:
            return

        # text:line-break i text:tab muszą być osobnymi elementami.
        buffer = []

        def append_preserving_spaces(container, value):
            """Wstawia tekst tak, aby ODT nie zgubił spacji wiodących/końcowych."""
            if not value:
                return

            # Zwykła spacja w XML ODT może zostać zredukowana przez LibreOffice.
            # Dlatego serie spacji zapisujemy jako text:s. Dzięki temu np.
            # "   Nr inwentaryzacyjny" pozostaje dokładnie tak samo ustawione.
            parts = re.split(r"( +)", value)
            first_text_slot = True
            for part in parts:
                if not part:
                    continue
                if part.startswith(" "):
                    spaces = ET.Element(qname(NS_TEXT, "s"))
                    if len(part) > 1:
                        set_attr_local(spaces, NS_TEXT, "c", str(len(part)))
                    container.append(spaces)
                else:
                    if getattr(container, "text", None) is None and first_text_slot and len(container) == 0:
                        container.text = part
                    else:
                        last = container[-1] if len(container) else None
                        if last is not None:
                            last.tail = (last.tail or "") + part
                        else:
                            container.text = (container.text or "") + part
                first_text_slot = False

        def flush():
            if not buffer:
                return
            value = "".join(buffer)
            buffer.clear()
            style_name = self._style_for_props(props)
            if style_name:
                span = ET.Element(qname(NS_TEXT, "span"))
                set_attr_local(span, NS_TEXT, "style-name", style_name)
                append_preserving_spaces(span, value)
                paragraph.append(span)
            else:
                append_preserving_spaces(paragraph, value)

        for char in chunk:
            if char == "\n":
                flush()
                paragraph.append(ET.Element(qname(NS_TEXT, "line-break")))
            elif char == "\t":
                flush()
                paragraph.append(ET.Element(qname(NS_TEXT, "tab")))
            else:
                buffer.append(char)

        flush()

    def _style_for_props(self, props):
        # Gdy styl jest pusty, używamy zwykłego tekstu.
        if not props:
            return ""

        font = props.get("font") or ""
        size = int(props.get("size") or 11)
        bold = bool(props.get("bold"))
        italic = bool(props.get("italic"))
        underline = bool(props.get("underline"))
        color = props.get("color") or ""

        if not any((font, size != 11, bold, italic, underline, color)):
            return ""

        key = (font, size, bold, italic, underline, color)
        existing = getattr(self, "generated_styles", {}).get(key)
        if existing:
            return existing

        if not hasattr(self, "generated_styles"):
            self.generated_styles = {}

        style_name = "ADMORA_Text_" + str(abs(hash(key)))

        automatic = self._automatic_styles_element()
        style = ET.Element(qname(NS_STYLE, "style"))
        set_attr_local(style, NS_STYLE, "name", style_name)
        set_attr_local(style, NS_STYLE, "family", "text")

        props_element = ET.SubElement(style, qname(NS_STYLE, "text-properties"))
        if font:
            set_attr_local(props_element, NS_STYLE, "font-name", font)
            set_attr_local(props_element, NS_FO, "font-family", font)
        if size:
            set_attr_local(props_element, NS_FO, "font-size", f"{size}pt")
        if bold:
            set_attr_local(props_element, NS_FO, "font-weight", "bold")
        if italic:
            set_attr_local(props_element, NS_FO, "font-style", "italic")
        if underline:
            set_attr_local(props_element, NS_STYLE, "text-underline-style", "solid")
        if color:
            set_attr_local(props_element, NS_FO, "color", color)

        automatic.append(style)
        self.generated_styles[key] = style_name
        return style_name

    def _automatic_styles_element(self):
        for element in self.root_xml.iter():
            if element.tag == qname(NS_OFFICE, "automatic-styles"):
                return element

        office = next(
            (x for x in self.root_xml.iter() if x.tag == qname(NS_OFFICE, "document-content")),
            self.root_xml,
        )
        automatic = ET.Element(qname(NS_OFFICE, "automatic-styles"))
        office.insert(0, automatic)
        return automatic

    # --------------------------------------------------------
    # paragraph alignment
    # --------------------------------------------------------

    def _save_alignment(self, paragraph, index):
        value = self.paragraph_alignments[index]
        original_style = self.original_style_names[index]

        key = (original_style, value)
        if not hasattr(self, "generated_paragraph_styles"):
            self.generated_paragraph_styles = {}

        style_name = self.generated_paragraph_styles.get(key)
        if not style_name:
            style_name = "ADMORA_Para_" + str(abs(hash(key)))
            self.generated_paragraph_styles[key] = style_name

            style = ET.Element(qname(NS_STYLE, "style"))
            set_attr_local(style, NS_STYLE, "name", style_name)
            set_attr_local(style, NS_STYLE, "family", "paragraph")
            if original_style:
                set_attr_local(style, NS_STYLE, "parent-style-name", original_style)

            props = ET.SubElement(style, qname(NS_STYLE, "paragraph-properties"))
            set_attr_local(props, NS_FO, "text-align", value)
            self._automatic_styles_element().append(style)

        set_attr_local(paragraph, NS_TEXT, "style-name", style_name)
        self.original_style_names[index] = style_name

    # --------------------------------------------------------
    # write ZIP ODT
    # --------------------------------------------------------

    def _write_odt(self):
        """Zapis ODT bez blokady własnego pliku źródłowego.

        WAŻNE: na Windows nie wolno wykonywać os.replace() wewnątrz
        `with ZipFile(self.odt_path)`, bo otwarty ZipFile trzyma uchwyt do ODT
        i Windows zwraca PermissionError. Najpierw całkowicie zamykamy źródło,
        dopiero potem podmieniamy plik.
        """
        # 1. Najpierw zamykamy ODT źródłowe i pobieramy wszystkie dane do pamięci.
        #    Dzięki temu self.odt_path nie jest już przez nas zablokowany.
        with zipfile.ZipFile(self.odt_path, "r") as source:
            entries = source.infolist()
            files_data = {
                info.filename: source.read(info.filename)
                for info in entries
                if info.filename != "content.xml"
            }

        content = ET.tostring(
            self.root_xml,
            encoding="utf-8",
            xml_declaration=True,
            short_empty_elements=True,
        )

        fd, temp_name = tempfile.mkstemp(
            prefix=self.odt_path.stem + "_",
            suffix=".odt",
            dir=str(self.odt_path.parent),
        )
        os.close(fd)

        try:
            # 2. Budujemy kompletny nowy ODT obok starego pliku.
            with zipfile.ZipFile(temp_name, "w") as target:
                for info in entries:
                    data = content if info.filename == "content.xml" else files_data[info.filename]
                    if info.filename == "mimetype":
                        target.writestr(info, data, compress_type=zipfile.ZIP_STORED)
                    else:
                        target.writestr(info, data)

            # 3. Usuń atrybut tylko-do-odczytu, jeśli istnieje.
            try:
                os.chmod(
                    self.odt_path,
                    stat.S_IRUSR | stat.S_IWUSR |
                    stat.S_IRGRP | stat.S_IWGRP |
                    stat.S_IROTH | stat.S_IWOTH,
                )
            except Exception:
                pass

            if os.name == "nt":
                try:
                    subprocess.run(
                        ["attrib", "-R", str(self.odt_path)],
                        capture_output=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        timeout=3,
                    )
                except Exception:
                    pass

            # 4. Teraz stary ODT jest już zamknięty również przez ADMORA.
            #    Próbujemy kilka razy, bo Explorer/antywirus/LibreOffice może
            #    przez krótką chwilę trzymać uchwyt.
            last_error = None
            for attempt in range(8):
                try:
                    os.replace(temp_name, self.odt_path)
                    last_error = None
                    break
                except PermissionError as error:
                    last_error = error
                    if os.name == "nt":
                        try:
                            subprocess.run(
                                ["attrib", "-R", str(self.odt_path)],
                                capture_output=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                timeout=3,
                            )
                        except Exception:
                            pass
                    time.sleep(0.20 + attempt * 0.20)

            if last_error is not None:
                raise PermissionError(
                    "Nie udało się zapisać pliku ODT, ponieważ Windows nadal "
                    "trzyma go otwartego przez inny proces.\n\n"
                    "ADMORA sam zwolnił swój uchwyt przed zapisem. Jeśli nadal "
                    "występuje ten błąd, zamknij LibreOffice/Word lub podgląd, "
                    "który otworzył TEN SAM plik ODT.\n\n"
                    f"Plik: {self.odt_path}\n\nSzczegóły: {last_error}"
                )
        finally:
            try:
                if os.path.exists(temp_name):
                    os.remove(temp_name)
            except Exception:
                pass

    # --------------------------------------------------------
    # close
    # --------------------------------------------------------

    def _ctrl_s(self, event=None):
        self.save()
        return "break"

    def _mark_dirty(self, event=None):
        if self.loading or self.saving:
            return
        try:
            if not self.text.edit_modified():
                return
            self.text.edit_modified(False)
        except Exception:
            pass
        self.saved = False
        if hasattr(self, "cancel_button"):
            self.cancel_button.configure(text="ANULUJ", command=self.close)

    def close(self):
        if self.saving:
            return

        if self.saved:
            self.window.destroy()
            return

        answer = messagebox.askyesnocancel(
            "Edytor ODT",
            "Masz niezapisane zmiany. Czy zapisać je przed zamknięciem?",
            parent=self.window,
        )

        if answer is None:
            return

        if answer:
            if not self.save():
                return

        self.window.destroy()
