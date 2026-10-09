# ============================================================
# template_editor.py
#
# ADMORA
# Edytor szablonów orzeczeń
#
# Edycja odbywa się bez uruchamiania LibreOffice.
# ============================================================

from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from odf.opendocument import load
from odf.text import P


class TemplateEditor:
    """
    Prosty edytor tekstowy szablonu ODT.

    Otwiera szablon w osobnym oknie Tkinter.
    Użytkownik może zmienić tekst oraz placeholdery.

    Przykładowe placeholdery:

        {miejsce}
        {nazwa}
        {paszport}
        {comp}
        {num_fab}
        {st_num_inv}
        {if_iscomp}
        {brand}
        {time}
        {curr_time-time}

    Po zapisaniu plik ODT zostaje nadpisany.
    """

    BG = "#EEF1F5"
    SURFACE = "#F8FAFC"
    BORDER = "#D3D9E1"
    TEXT = "#202A35"
    SECONDARY = "#687585"
    BLUE = "#316BEA"
    BLUE_DARK = "#2457C7"
    WHITE = "#FFFFFF"
    GREEN = "#218653"

    def __init__(
        self,
        parent,
        template_path,
        on_saved=None
    ):
        self.parent = parent
        self.template_path = Path(template_path)
        self.on_saved = on_saved

        self.window = tk.Toplevel(parent)

        self.window.title(
            f"Edytor szablonu — {self.template_path.name}"
        )

        self.window.geometry("1150x780")
        self.window.minsize(850, 600)

        self.window.configure(
            bg=self.BG
        )

        self.window.transient(parent)

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self._build_style()
        self._build_gui()
        self._load_template()

    # ========================================================
    # STYLE
    # ========================================================

    def _build_style(self):

        style = ttk.Style()

        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Editor.TFrame",
            background=self.BG
        )

        style.configure(
            "Card.TFrame",
            background=self.SURFACE,
            relief="flat"
        )

        style.configure(
            "Title.TLabel",
            background=self.BG,
            foreground=self.TEXT,
            font=("Segoe UI", 18, "bold")
        )

        style.configure(
            "Info.TLabel",
            background=self.BG,
            foreground=self.SECONDARY,
            font=("Segoe UI", 9)
        )

        style.configure(
            "Save.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(18, 10)
        )

        style.configure(
            "Cancel.TButton",
            font=("Segoe UI", 10),
            padding=(18, 10)
        )

    # ========================================================
    # GUI
    # ========================================================

    def _build_gui(self):

        main = ttk.Frame(
            self.window,
            style="Editor.TFrame",
            padding=22
        )

        main.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        ttk.Label(
            main,
            text="EDYTOR SZABLONU",
            style="Title.TLabel"
        ).pack(
            anchor="w"
        )

        ttk.Label(
            main,
            text=str(self.template_path),
            style="Info.TLabel"
        ).pack(
            anchor="w",
            pady=(4, 18)
        )

        # ----------------------------------------------------
        # PODPOWIEDŹ
        # ----------------------------------------------------

        info = tk.Frame(
            main,
            bg="#E7EEFF",
            padx=15,
            pady=12
        )

        info.pack(
            fill="x",
            pady=(0, 12)
        )

        tk.Label(
            info,
            text="Placeholdery:",
            bg="#E7EEFF",
            fg=self.BLUE_DARK,
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w"
        )

        tk.Label(
            info,
            text=(
                "{miejsce}   {nazwa}   {paszport}   {comp}   "
                "{num_fab}   {st_num_inv}   {if_iscomp}   "
                "{brand}   {time}   {curr_time-time}"
            ),
            bg="#E7EEFF",
            fg=self.TEXT,
            font=("Consolas", 9)
        ).pack(
            anchor="w",
            pady=(5, 0)
        )

        # ----------------------------------------------------
        # EDYTOR
        # ----------------------------------------------------

        editor_frame = tk.Frame(
            main,
            bg=self.SURFACE,
            highlightbackground=self.BORDER,
            highlightthickness=1
        )

        editor_frame.pack(
            fill="both",
            expand=True
        )

        self.text = ScrolledText(
            editor_frame,
            wrap="word",
            undo=True,
            font=("Consolas", 11),
            bg=self.WHITE,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground="#CFE0FF",
            selectforeground=self.TEXT,
            relief="flat",
            borderwidth=0,
            padx=18,
            pady=18
        )

        self.text.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        bottom = ttk.Frame(
            main,
            style="Editor.TFrame"
        )

        bottom.pack(
            fill="x",
            pady=(14, 0)
        )

        self.status_var = tk.StringVar(
            value="Gotowy."
        )

        ttk.Label(
            bottom,
            textvariable=self.status_var,
            style="Info.TLabel"
        ).pack(
            side="left"
        )

        buttons = ttk.Frame(
            bottom,
            style="Editor.TFrame"
        )

        buttons.pack(
            side="right"
        )

        ttk.Button(
            buttons,
            text="ANULUJ",
            style="Cancel.TButton",
            command=self.close
        ).pack(
            side="left",
            padx=(0, 8)
        )

        save_button = ttk.Button(
            buttons,
            text="ZAPISZ SZABLON",
            style="Save.TButton",
            command=self.save
        )

        save_button.pack(
            side="left"
        )

        self.text.bind(
            "<Control-s>",
            self._ctrl_s
        )

    # ========================================================
    # ODCZYT ODT
    # ========================================================

    def _load_template(self):

        if not self.template_path.exists():

            messagebox.showerror(
                "Edytor szablonu",
                "Nie znaleziono pliku szablonu.",
                parent=self.window
            )

            self.close()
            return

        try:

            document = load(
                str(self.template_path)
            )

            text = self._extract_text(
                document.text
            )

            self.text.delete(
                "1.0",
                tk.END
            )

            self.text.insert(
                "1.0",
                text
            )

            self.status_var.set(
                "Szablon został wczytany."
            )

        except Exception as error:

            messagebox.showerror(
                "Błąd",
                f"Nie udało się otworzyć szablonu:\n\n{error}",
                parent=self.window
            )

    # ========================================================
    # WYCIĄGANIE TEKSTU
    # ========================================================

    def _extract_text(self, element):

        result = []

        def walk(node):

            if not hasattr(
                node,
                "childNodes"
            ):
                return

            for child in node.childNodes:

                # P - paragraph
                if getattr(
                    child,
                    "qname",
                    None
                ) == P.qname:

                    paragraph_text = []

                    self._collect_text(
                        child,
                        paragraph_text
                    )

                    result.append(
                        "".join(
                            paragraph_text
                        )
                    )

                else:

                    walk(child)

        walk(element)

        return "\n".join(
            result
        )

    def _collect_text(
        self,
        node,
        output
    ):

        if not hasattr(
            node,
            "childNodes"
        ):
            return

        for child in node.childNodes:

            if hasattr(
                child,
                "data"
            ):

                output.append(
                    str(child.data)
                )

            else:

                self._collect_text(
                    child,
                    output
                )

    # ========================================================
    # ZAPIS
    # ========================================================

    def save(self):

        content = self.text.get(
            "1.0",
            tk.END
        )

        content = content.rstrip()

        if not content:

            messagebox.showwarning(
                "Szablon",
                "Szablon nie może być pusty.",
                parent=self.window
            )

            return

        try:

            document = load(
                str(self.template_path)
            )

            paragraphs = []

            self._find_paragraphs(
                document.text,
                paragraphs
            )

            lines = content.splitlines()

            # ------------------------------------------------
            # Jeżeli liczba akapitów się zgadza,
            # zachowujemy strukturę ODT.
            # ------------------------------------------------

            if len(paragraphs) == len(lines):

                for paragraph, line in zip(
                    paragraphs,
                    lines
                ):

                    self._replace_paragraph(
                        paragraph,
                        line
                    )

            else:

                # ------------------------------------------------
                # Jeżeli użytkownik dodał/usunął akapity,
                # przebudowujemy body.
                # ------------------------------------------------

                body = document.text

                for child in list(
                    body.childNodes
                ):

                    body.removeChild(
                        child
                    )

                for line in lines:

                    paragraph = P()

                    paragraph.addText(
                        line
                    )

                    body.addElement(
                        paragraph
                    )

            document.save(
                str(self.template_path)
            )

            self.status_var.set(
                "Szablon zapisany."
            )

            messagebox.showinfo(
                "Szablon",
                "Szablon został zapisany.",
                parent=self.window
            )

            if self.on_saved:

                try:
                    self.on_saved(
                        self.template_path
                    )
                except Exception:
                    pass

        except Exception as error:

            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się zapisać szablonu:\n\n{error}",
                parent=self.window
            )

    # ========================================================
    # PARAGRAPHY
    # ========================================================

    def _find_paragraphs(
        self,
        element,
        result
    ):

        if not hasattr(
            element,
            "childNodes"
        ):
            return

        for child in element.childNodes:

            if getattr(
                child,
                "qname",
                None
            ) == P.qname:

                result.append(
                    child
                )

            else:

                self._find_paragraphs(
                    child,
                    result
                )

    def _replace_paragraph(
        self,
        paragraph,
        text
    ):

        for child in list(
            paragraph.childNodes
        ):

            paragraph.removeChild(
                child
            )

        paragraph.addText(
            text
        )

    # ========================================================
    # CTRL + S
    # ========================================================

    def _ctrl_s(self, event=None):

        self.save()

        return "break"

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        try:
            self.window.grab_release()
        except Exception:
            pass

        self.window.destroy()