"""
ui/widget.py — Reusable styled widget factories and ttk style setup.
"""

import tkinter as tk
from tkinter import ttk
from ui.theme import (
    BG, BG2, BG3, BORDER, TEXT, TEXT2, CYAN, GREEN, RED, YELLOW, PURPLE, BLUE
)


# ─────────────────────────────────────────────
#  WIDGET FACTORIES
# ─────────────────────────────────────────────

def styled_frame(parent, bg=BG2, **kw):
    return tk.Frame(parent, bg=bg, **kw)


def label(parent, text, fg=TEXT, bg=BG2, font=("Segoe UI", 10), **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg, font=font, **kw)


def heading(parent, text, size=14, fg=TEXT, bg=BG2, bold=True):
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text, fg=fg, bg=bg,
                    font=("Segoe UI", size, weight))


def entry(parent, textvariable=None, show=None, width=28,
          bg=BG, fg=TEXT, insertbackground=TEXT,
          font=("Segoe UI", 10), **kw):
    return tk.Entry(
        parent,
        textvariable=textvariable,
        show=show,
        width=width,
        bg=bg,
        fg=fg,
        insertbackground=insertbackground,
        font=font,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=CYAN,
        **kw,
    )


def btn(parent, text, command=None, fg=BG, bg=CYAN,
        font=("Segoe UI", 10, "bold"), width=None, pad=(12, 6), **kw):
    b = tk.Button(
        parent,
        text=text,
        command=command,
        fg=fg,
        bg=bg,
        font=font,
        relief="flat",
        cursor="hand2",
        activebackground=bg,
        activeforeground=fg,
        padx=pad[0],
        pady=pad[1],
        **kw,
    )
    if width:
        b.config(width=width)
    return b


def separator(parent, bg=BORDER):
    return tk.Frame(parent, bg=bg, height=1)


# ─────────────────────────────────────────────
#  TTK STYLE SETUP
# ─────────────────────────────────────────────

def apply_ttk_style(root):
    """Call once on the root Tk window to configure all ttk styles."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        "Treeview",
        background=BG2,
        foreground=TEXT,
        fieldbackground=BG2,
        bordercolor=BORDER,
        rowheight=28,
    )
    style.configure(
        "Treeview.Heading",
        background=BG3,
        foreground=TEXT2,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", "#1e40af")])

    style.configure(
        "TScrollbar",
        background=BG3,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=TEXT2,
    )
    style.configure(
        "Session.Horizontal.TProgressbar",
        troughcolor=BG3,
        background=CYAN,
        thickness=10,
        bordercolor=BG3,
    )