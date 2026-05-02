import customtkinter as ctk
from ui.theme import T


def lbl(parent, text="", size=T.FS, color=None, bold=False, **kw):
    weight = "bold" if bold else "normal"
    return ctk.CTkLabel(parent, text=text, text_color=color or T.TXT,
                        font=(T.FF, size, weight), **kw)


def btn(parent, text, cmd=None, variant="primary", **kw):
    palettes = {
        "primary":   (T.CYAN, T.BG,  T.CDARK, T.BG),
        "secondary": (T.CARD, T.TXT, T.BDR,   T.TXT),
        "danger":    (T.RED,  T.TXT, "#dc2626", T.TXT),
        "success":   (T.GRN,  T.BG,  "#16a34a", T.BG),
    }
    bg, fg, hbg, hfg = palettes.get(variant, palettes["primary"])
    return ctk.CTkButton(parent, text=text, command=cmd,
                         fg_color=bg, text_color=fg, hover_color=hbg,
                         font=(T.FF, T.FS, "bold"), corner_radius=6, **kw)


class Entry(ctk.CTkEntry):
    def __init__(self, parent, placeholder="", show=None, **kw):
        super().__init__(parent,
                         placeholder_text=placeholder,
                         fg_color=T.INP,
                         text_color=T.TXT,
                         placeholder_text_color=T.MUT,
                         border_color=T.BDR,
                         border_width=1,
                         show=show or "",
                         font=(T.FF, T.FS),
                         corner_radius=6, **kw)

    def val(self):
        return self.get()

    def delete(self, first, last=None):
        try:
            super().delete(first, last)
        except Exception:
            pass


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=T.CARD,
                        border_color=T.BDR, border_width=1,
                        corner_radius=8, **kw)