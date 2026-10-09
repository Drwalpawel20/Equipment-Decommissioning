# ============================================================
# odt_editor.py
#
# Edytor dokumentu ODT dla generatora ADMORA.
#
# Edycja odbywa się bezpośrednio w GUI aplikacji.
# Zmiany są automatycznie zapisywane do ODT.
#
# ============================================================

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import (
    Toplevel,
    StringVar,
    END,
    messagebox,
)
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from odf.opendocument import load
from odf import text as odf_text


# ============================================================
# KOLORY
# ============================================================

COLORS = {
    "background": "#EEF1F5",
    "surface": "#F8FAFC",
    "surface_alt": "#E7EBF0",
    "border": "#D3D9E1",
    "text": "#202A35",
    "text_secondary": "#687585",
    "blue": "#316BEA",
    "blue_dark": "#2457C7",
    "green": "#218653",
    "red": "#C93636",
    "white": "#FFFFFF",
}


FONT_MAIN = "Segoe UI"


# ============================================================
# EDYTOR ODT
# ============================================================

class ODTEditor:

    def __init__(
        self,
        parent,
        odt_path,
        on_change=None,
        title="Edycja orzeczenia"
    ):

        self.parent = parent

        self.odt_path = Path(
            odt_path
        )

        self.on_change = on_change

        self.title = title

        self.document = None

        self.text_nodes = []

        self.loading = False

        self.save_after_id = None

        self.closed = False

        # ----------------------------------------------------
        # OKNO
        # ----------------------------------------------------

        self.window = Toplevel(
            parent
        )

        self.window.title(
            self.title
        )

        self.window.geometry(
            "1100x760"
        )

        self.window.minsize(
            850,
            600
        )

        self.window.transient(
            parent
        )

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        # ----------------------------------------------------
        # STYLE
        # ----------------------------------------------------

        self.setup_style()

        # ----------------------------------------------------
        # ZMIENNE
        # ----------------------------------------------------

        self.status_var = StringVar(
            value="Ładowanie dokumentu..."
        )

        self.file_var = StringVar(
            value=str(
                self.odt_path
            )
        )

        # ----------------------------------------------------
        # INTERFEJS
        # ----------------------------------------------------

        self.build_ui()

        # ----------------------------------------------------
        # WCZYTANIE
        # ----------------------------------------------------

        self.load_document()


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
            "Editor.TFrame",
            background=COLORS["background"]
        )

        style.configure(
            "Editor.TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"]
        )

        style.configure(
            "EditorBlue.TButton",
            font=(
                FONT_MAIN,
                10,
                "bold"
            ),
            padding=(
                16,
                9
            ),
            foreground=COLORS["white"],
            background=COLORS["blue"],
            borderwidth=0
        )

        style.map(
            "EditorBlue.TButton",
            background=[
                (
                    "active",
                    COLORS["blue_dark"]
                )
            ]
        )

        style.configure(
            "EditorSecondary.TButton",
            font=(
                FONT_MAIN,
                10
            ),
            padding=(
                14,
                9
            )
        )


    # ========================================================
    # GUI
    # ========================================================

    def build_ui(self):

        main = ttk.Frame(
            self.window,
            style="Editor.TFrame",
            padding=20
        )

        main.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # NAGŁÓWEK
        # ----------------------------------------------------

        header = ttk.Frame(
            main,
            style="Editor.TFrame"
        )

        header.pack(
            fill="x",
            pady=(
                0,
                12
            )
        )

        ttk.Label(
            header,
            text="EDYCJA ORZECZENIA",
            style="Editor.TLabel",
            font=(
                FONT_MAIN,
                18,
                "bold"
            )
        ).pack(
            side="left"
        )

        ttk.Label(
            header,
            text="ODT",
            style="Editor.TLabel",
            foreground=COLORS["blue"],
            font=(
                FONT_MAIN,
                10,
                "bold"
            )
        ).pack(
            side="right"
        )

        # ----------------------------------------------------
        # PLIK
        # ----------------------------------------------------

        file_frame = ttk.Frame(
            main,
            style="Editor.TFrame"
        )

        file_frame.pack(
            fill="x",
            pady=(
                0,
                12
            )
        )

        ttk.Label(
            file_frame,
            text="Plik:",
            style="Editor.TLabel",
            font=(
                FONT_MAIN,
                9,
                "bold"
            )
        ).pack(
            side="left"
        )

        ttk.Label(
            file_frame,
            textvariable=self.file_var,
            style="Editor.TLabel",
            foreground=COLORS["text_secondary"],
            font=(
                FONT_MAIN,
                9
            )
        ).pack(
            side="left",
            padx=8
        )

        # ----------------------------------------------------
        # EDYTOR
        # ----------------------------------------------------

        editor_frame = ttk.Frame(
            main,
            style="Editor.TFrame"
        )

        editor_frame.pack(
            fill="both",
            expand=True
        )

        editor_frame.rowconfigure(
            0,
            weight=1
        )

        editor_frame.columnconfigure(
            0,
            weight=1
        )

        self.text = ScrolledText(
            editor_frame,

            font=(
                FONT_MAIN,
                11
            ),

            bg=COLORS["white"],

            fg=COLORS["text"],

            insertbackground=COLORS["text"],

            relief="solid",

            borderwidth=1,

            padx=25,

            pady=20,

            wrap="word"
        )

        self.text.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.text.bind(
            "<KeyRelease>",
            self.text_changed
        )

        # ----------------------------------------------------
        # STOPKA
        # ----------------------------------------------------

        footer = ttk.Frame(
            main,
            style="Editor.TFrame"
        )

        footer.pack(
            fill="x",
            pady=(
                12,
                0
            )
        )

        ttk.Label(
            footer,
            textvariable=self.status_var,
            style="Editor.TLabel",
            foreground=COLORS["text_secondary"],
            font=(
                FONT_MAIN,
                9
            )
        ).pack(
            side="left"
        )

        buttons = ttk.Frame(
            footer,
            style="Editor.TFrame"
        )

        buttons.pack(
            side="right"
        )

        ttk.Button(
            buttons,
            text="ZAPISZ",
            style="EditorSecondary.TButton",
            command=self.save_now
        ).pack(
            side="left",
            padx=(
                0,
                8
            )
        )

        ttk.Button(
            buttons,
            text="ZAMKNIJ",
            style="EditorBlue.TButton",
            command=self.close
        ).pack(
            side="left"
        )


    # ========================================================
    # WCZYTYWANIE ODT
    # ========================================================

    def load_document(self):

        if not self.odt_path.exists():

            self.status_var.set(
                "Nie znaleziono pliku ODT."
            )

            return

        try:

            self.document = load(
                str(
                    self.odt_path
                )
            )

            content = (
                self.extract_text(
                    self.document
                )
            )

            self.loading = True

            self.text.delete(
                "1.0",
                END
            )

            self.text.insert(
                "1.0",
                content
            )

            self.text.edit_modified(
                False
            )

            self.loading = False

            self.status_var.set(
                "Dokument gotowy — zmiany zapisują się automatycznie."
            )

        except Exception as error:

            self.status_var.set(
                "Błąd ładowania dokumentu."
            )

            messagebox.showerror(
                "Edytor ODT",
                str(error),
                parent=self.window
            )


    # ========================================================
    # ODCZYT TEKSTU
    # ========================================================

    def extract_text(
        self,
        document
    ):

        self.text_nodes = []

        result = []

        body = document.text

        self.collect_text_nodes(
            body,
            result
        )

        return "\n".join(
            result
        )


    def collect_text_nodes(
        self,
        element,
        result
    ):

        if not hasattr(
            element,
            "childNodes"
        ):

            return

        paragraph_text = []

        for child in element.childNodes:

            if (
                getattr(
                    child,
                    "nodeType",
                    None
                )
                == child.TEXT_NODE
            ):

                paragraph_text.append(
                    child.data
                )

                self.text_nodes.append(
                    child
                )

            else:

                self.collect_text_nodes(
                    child,
                    paragraph_text
                )

        if paragraph_text:

            text_value = "".join(
                paragraph_text
            )

            if text_value.strip():

                result.append(
                    text_value
                )


    # ========================================================
    # ZMIANA TEKSTU
    # ========================================================

    def text_changed(
        self,
        event=None
    ):

        if self.loading:
            return

        self.status_var.set(
            "Zapisywanie zmian..."
        )

        if self.save_after_id:

            try:

                self.window.after_cancel(
                    self.save_after_id
                )

            except Exception:
                pass

        # ----------------------------------------------------
        # DEBOUNCE
        #
        # Nie zapisujemy ODT po każdym pojedynczym znaku.
        # Czekamy 500 ms od ostatniej zmiany.
        # ----------------------------------------------------

        self.save_after_id = (
            self.window.after(
                500,
                self.save_now
            )
        )


    # ========================================================
    # ZAPIS
    # ========================================================

    def save_now(self):

        self.save_after_id = None

        if self.document is None:
            return

        try:

            new_text = (
                self.text
                .get(
                    "1.0",
                    "end-1c"
                )
            )

            self.replace_document_text(
                new_text
            )

            self.document.save(
                str(
                    self.odt_path
                )
            )

            self.status_var.set(
                "Zapisano ODT."
            )

            # ------------------------------------------------
            # CALLBACK DO GUI
            # ------------------------------------------------

            if self.on_change:

                try:

                    self.on_change(
                        self.odt_path
                    )

                except Exception:
                    pass

        except Exception as error:

            self.status_var.set(
                "Błąd zapisu ODT."
            )

            messagebox.showerror(
                "Edytor ODT",
                str(error),
                parent=self.window
            )


    # ========================================================
    # ZASTĘPOWANIE TEKSTU
    # ========================================================

    def replace_document_text(
        self,
        new_text
    ):

        paragraphs = (
            new_text.split(
                "\n"
            )
        )

        # ----------------------------------------------------
        # Ponowne pobranie wszystkich paragrafów.
        # ----------------------------------------------------

        paragraph_nodes = []

        def collect_paragraphs(
            element
        ):

            if not hasattr(
                element,
                "childNodes"
            ):

                return

            for child in element.childNodes:

                if isinstance(
                    child,
                    odf_text.P
                ):

                    paragraph_nodes.append(
                        child
                    )

                else:

                    collect_paragraphs(
                        child
                    )

        collect_paragraphs(
            self.document.text
        )

        # ----------------------------------------------------
        # Jeżeli liczba linii się zgadza,
        # aktualizujemy istniejące paragrafy.
        # ----------------------------------------------------

        if len(paragraph_nodes) == len(
            paragraphs
        ):

            for node, value in zip(
                paragraph_nodes,
                paragraphs
            ):

                self.set_paragraph_text(
                    node,
                    value
                )

            return

        # ----------------------------------------------------
        # Jeżeli użytkownik zmienił liczbę
        # paragrafów, przebudowujemy treść.
        #
        # Formatowanie struktury ODT pozostaje,
        # ale nowe paragrafy otrzymują podstawowy
        # styl dokumentu.
        # ----------------------------------------------------

        body = self.document.text

        for child in list(
            body.childNodes
        ):

            body.removeChild(
                child
            )

        for value in paragraphs:

            paragraph = odf_text.P()

            paragraph.addText(
                value
            )

            body.addElement(
                paragraph
            )


    # ========================================================
    # TEKST PARAGRAFU
    # ========================================================

    def set_paragraph_text(
        self,
        paragraph,
        value
    ):

        for child in list(
            paragraph.childNodes
        ):

            paragraph.removeChild(
                child
            )

        paragraph.addText(
            value
        )


    # ========================================================
    # ZAMKNIĘCIE
    # ========================================================

    def close(self):

        if self.closed:
            return

        self.closed = True

        if self.save_after_id:

            try:

                self.window.after_cancel(
                    self.save_after_id
                )

            except Exception:
                pass

            self.save_after_id = None

        # ----------------------------------------------------
        # OSTATNI ZAPIS
        # ----------------------------------------------------

        try:

            if self.document:

                self.save_now()

        except Exception:
            pass

        self.window.destroy()