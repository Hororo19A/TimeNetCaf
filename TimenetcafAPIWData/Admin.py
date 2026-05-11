"""
TimeNet Cafe — ADMIN PC
Requires: pip install mysql-connector-python

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SINGLE PC SETUP (current):
    DB host is "localhost" — admin and customer apps
    both run on the same machine alongside XAMPP.

  TWO PC SETUP (when you split admin and customer PCs):
    This file stays on the ADMIN PC.
    Change DB_CONFIG["host"] from "localhost" to the
    LAN IP of whichever PC is running XAMPP, e.g.
    "192.168.1.10".  If XAMPP is on THIS admin PC,
    keep "localhost" and only change customer.py.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import tkinter as tk
from tkinter import ttk
import csv
import os
import time
import random
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import pooling
import base64

# ════════════════════════════════════════════════════════════════════
#  DATABASE CONFIG
# ════════════════════════════════════════════════════════════════════

DB_CONFIG = {
    # ── SINGLE PC: keep as "localhost" ───────────────────────────
    # ── TWO PCs  : change to the XAMPP PC's LAN IP, e.g. "192.168.1.10"
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "",          # default XAMPP password is blank
    "database": "timenet",
}

# ════════════════════════════════════════════════════════════════════
#  BUSINESS RULES
# ════════════════════════════════════════════════════════════════════

HOURLY_RATE    = 0.1
MINUTE_RATE    = HOURLY_RATE / 60
ADMIN_EXIT_PIN = "1234"      # PIN to exit fullscreen / close the app

# ════════════════════════════════════════════════════════════════════
#  WINDOW ICON  (64×64 RGBA PNG, base64-encoded)
#  — Navy circle with amber "TN" lettering, matches the app palette.
# ════════════════════════════════════════════════════════════════════

ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABpElEQVR42u3a"
    "wUrDQBCG4XQPehE8efCgBy9eFDx48OCLePLgwYMHL168ePHixYsXL168ePHi"
    "xYsXL168ePHixYsXL168ePHixYsXL168ePHixYsXL168ePHixUvJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZ"
    "smTJkiVLlixZsmTJkiVLlixZsmTJkiVLlixZsmTJkiVLAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAP8BLR8kM8MAAAAASUVORK5CYII="
)

# ════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS
# ════════════════════════════════════════════════════════════════════

BG         = "#070b12"
BG2        = "#0c1320"
BG3        = "#111b2e"
BG4        = "#172237"
BG5        = "#1d2d44"
BORDER     = "#1e3050"
BORDER2    = "#243a5e"
BORDER3    = "#2e4a72"
TEXT       = "#e2ecff"
TEXT2      = "#7a9cc4"
TEXT3      = "#3d5a80"
TEXT4      = "#253a55"
AMBER      = "#f5a623"
AMBER2     = "#e08c00"
AMBER_DIM  = "#2d1e00"
CYAN       = "#00c8e8"
CYAN_DIM   = "#002d38"
GREEN      = "#00e56e"
GREEN2     = "#00b855"
GREEN_DIM  = "#002d1a"
RED        = "#ff3b5c"
RED2       = "#cc2040"
RED_DIM    = "#300010"
PURPLE     = "#a855f7"
PURPLE_DIM = "#200040"
BLUE       = "#3b82f6"
YELLOW     = "#fbbf24"
FD = "Segoe UI"
FB = "Segoe UI"
FM = "Consolas"

# ════════════════════════════════════════════════════════════════════
#  DATABASE LAYER
# ════════════════════════════════════════════════════════════════════

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="timenet_admin", pool_size=5, **DB_CONFIG)
    return _pool

def db_exec(query, params=(), fetch=False):
    """Run a query. Returns list of dicts if fetch=True, else None."""
    try:
        conn = get_pool().get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute(query, params)
        if fetch:
            rows = cur.fetchall()
            conn.close()
            return rows
        conn.commit()
        conn.close()
        return None
    except Exception as e:
        print(f"[DB] {e}")
        return [] if fetch else None


def _norm_session(r):
    """Map snake_case DB columns → camelCase dict used throughout the app."""
    return {
        "id":          r["id"],
        "userId":      r.get("user_id")      or r.get("userId",     ""),
        "computerId":  r.get("computer_id")  or r.get("computerId", ""),
        "duration":    r.get("duration",  0),
        "cost":        float(r.get("cost", 0)),
        "status":      r.get("status",    ""),
        "startTime":   r.get("start_time")   or r.get("startTime"),
        "endTime":     r.get("end_time")     or r.get("endTime"),
        "cancelledAt": r.get("cancelled_at") or r.get("cancelledAt"),
        "voucherCode": r.get("voucher_code") or r.get("voucherCode"),
    }

# ════════════════════════════════════════════════════════════════════
#  UTILITIES
# ════════════════════════════════════════════════════════════════════

def now_ms():
    return int(time.time() * 1000)

def fmt_currency(amount):
    return f"₱{float(amount):,.2f}"

def gen_receipt():
    ts  = str(int(time.time() * 1000))[-6:]
    rnd = str(random.randint(0, 999)).zfill(3)
    return f"TN-{ts}-{rnd}"

def today_label():
    return datetime.now().strftime("%A, %B %d, %Y")

def today_start_ms():
    d = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp() * 1000)

# ════════════════════════════════════════════════════════════════════
#  UI PRIMITIVES
# ════════════════════════════════════════════════════════════════════

def hsep(parent, color=BORDER2, h=1):
    return tk.Frame(parent, bg=color, height=h)

def accent_bar(parent, color=AMBER, h=3):
    return tk.Frame(parent, bg=color, height=h)

def gradient_bar(canvas, x1, y1, x2, y2, c1=AMBER, c2=CYAN, steps=60):
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    w = max(1, (x2 - x1) // steps)
    for i in range(steps):
        t   = i / steps
        r   = max(0, min(255, int(r1 + (r2 - r1) * t)))
        g   = max(0, min(255, int(g1 + (g2 - g1) * t)))
        b   = max(0, min(255, int(b1 + (b2 - b1) * t)))
        col = f"#{r:02x}{g:02x}{b:02x}"
        sx  = x1 + i * w
        canvas.create_rectangle(sx, y1, sx + w + 1, y2, fill=col, outline="")

def ghost_button(parent, text, command, color=TEXT2, pady=12):
    return tk.Button(parent, text=text, command=command,
                     bg=BG4, fg=color, font=(FB, 11, "bold"),
                     relief="flat", cursor="hand2",
                     activebackground=BG5, activeforeground=TEXT,
                     padx=16, pady=pady)

def dot_grid(canvas, event, color=TEXT4, spacing=36):
    canvas.delete("dots")
    for x in range(0, event.width, spacing):
        for y in range(0, event.height, spacing):
            canvas.create_oval(x-1, y-1, x+1, y+1,
                               fill=color, outline="", tags="dots")

def make_bg_canvas(parent):
    c = tk.Canvas(parent, bg=BG, highlightthickness=0)
    c.place(relwidth=1, relheight=1)
    c.bind("<Configure>", lambda e: dot_grid(c, e))
    return c

def stat_card(parent, icon, title, value, color):
    f = tk.Frame(parent, bg=BG3, highlightthickness=1,
                 highlightbackground=BORDER2)
    gc = tk.Canvas(f, bg=BG3, height=3, highlightthickness=0)
    gc.pack(fill="x")
    gc.bind("<Configure>",
            lambda e, canvas=gc, c=color:
                (canvas.delete("all"),
                 gradient_bar(canvas, 0, 0, e.width, 3, c, BG3)))
    tk.Label(f, text=icon, bg=BG3, fg=color, font=(FD, 20)).pack(
        anchor="w", padx=18, pady=(14, 0))
    tk.Label(f, text=title.upper(), bg=BG3, fg=TEXT3,
             font=(FB, 8, "bold")).pack(anchor="w", padx=18, pady=(4, 0))
    val_lbl = tk.Label(f, text=value, bg=BG3, fg=color, font=(FD, 22, "bold"))
    val_lbl.pack(anchor="w", padx=18, pady=(2, 16))
    return f, val_lbl

# ════════════════════════════════════════════════════════════════════
#  THEMED DIALOG
# ════════════════════════════════════════════════════════════════════

class ThemedDialog(tk.Toplevel):
    _STYLES = {
        "success": (GREEN,  GREEN_DIM,  "✓"),
        "error":   (RED,    RED_DIM,    "✗"),
        "warning": (YELLOW, AMBER_DIM,  "⚠"),
        "info":    (CYAN,   CYAN_DIM,   "ℹ"),
    }

    def __init__(self, parent, kind="info", title="",
                 message="", detail="", on_close=None):
        super().__init__(parent)
        color, dim, icon = self._STYLES.get(kind, self._STYLES["info"])
        self._on_close   = on_close
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self.bind("<Return>", lambda _: self._close())
        self.bind("<Escape>", lambda _: self._close())
        self._build(color, dim, icon, title, message, detail)
        self.update_idletasks()
        w  = 480
        h  = max(self.winfo_reqheight() + 40, 300)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build(self, color, dim, icon, title, message, detail):
        gc = tk.Canvas(self, bg=BG2, height=4, highlightthickness=0)
        gc.pack(fill="x")
        gc.bind("<Configure>",
                lambda e, c=color: gradient_bar(gc, 0, 0, e.width, 4, c, BG2))
        badge = tk.Frame(self, bg=dim, highlightthickness=1,
                         highlightbackground=color, width=64, height=64)
        badge.pack(pady=(28, 0))
        badge.pack_propagate(False)
        tk.Label(badge, text=icon, bg=dim, fg=color,
                 font=(FD, 26, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        if title:
            tk.Label(self, text=title, bg=BG2, fg=TEXT,
                     font=(FD, 15, "bold")).pack(pady=(14, 2))
        if message:
            tk.Label(self, text=message, bg=BG2, fg=TEXT2, font=(FB, 10),
                     wraplength=400, justify="center").pack(padx=36, pady=(0, 4))
        if detail:
            hsep(self, BORDER2).pack(fill="x", padx=28, pady=(14, 0))
            df = tk.Frame(self, bg=BG3, highlightthickness=1,
                          highlightbackground=BORDER2)
            df.pack(padx=28, pady=(10, 0), fill="x")
            tk.Entry(df, textvariable=tk.StringVar(value=detail), state="readonly",
                     bg=BG3, fg=color, readonlybackground=BG3,
                     font=(FM, 10), relief="flat",
                     justify="center").pack(padx=14, pady=10, fill="x")
        hsep(self, BORDER2).pack(fill="x", padx=28, pady=(20, 0))
        btn = tk.Button(self, text="  Close  ", command=self._close,
                        bg=color, fg=BG, font=(FD, 11, "bold"),
                        relief="flat", cursor="hand2",
                        activebackground=AMBER2 if color == AMBER else color,
                        activeforeground=BG, padx=28, pady=12)
        btn.pack(pady=(14, 28))
        btn.focus_set()

    def _close(self):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        if self._on_close:
            self._on_close()

# ════════════════════════════════════════════════════════════════════
#  CONFIRM DIALOG
# ════════════════════════════════════════════════════════════════════

class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title="Confirm", message="",
                 confirm_label="Confirm", cancel_label="Cancel",
                 confirm_color=RED, on_confirm=None):
        super().__init__(parent)
        self._on_confirm = on_confirm
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self.bind("<Escape>", lambda _: self.destroy())
        self._build(title, message, confirm_label, cancel_label, confirm_color)
        self.update_idletasks()
        w  = 440
        h  = max(self.winfo_reqheight() + 40, 280)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build(self, title, message, confirm_label, cancel_label, confirm_color):
        accent_bar(self, confirm_color).pack(fill="x")
        tk.Label(self, text="⚠", bg=BG2, fg=confirm_color,
                 font=(FD, 30)).pack(pady=(24, 0))
        tk.Label(self, text=title, bg=BG2, fg=TEXT,
                 font=(FD, 14, "bold")).pack(pady=(8, 2))
        if message:
            tk.Label(self, text=message, bg=BG2, fg=TEXT2, font=(FB, 10),
                     wraplength=380, justify="center").pack(padx=36, pady=(0, 6))
        hsep(self, BORDER2).pack(fill="x", padx=24, pady=(18, 0))
        row = tk.Frame(self, bg=BG2)
        row.pack(padx=28, pady=(14, 28), fill="x")
        ghost_button(row, cancel_label, self.destroy, TEXT2, 14).pack(
            side="left", expand=True, fill="x", padx=(0, 8))
        tk.Button(row, text=confirm_label, command=self._confirm,
                  bg=confirm_color,
                  fg=BG if confirm_color == AMBER else TEXT,
                  font=(FD, 11, "bold"), relief="flat", cursor="hand2",
                  activebackground=RED2 if confirm_color == RED else AMBER2,
                  activeforeground=BG if confirm_color == AMBER else TEXT,
                  padx=12, pady=14).pack(side="left", expand=True, fill="x")

    def _confirm(self):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        if self._on_confirm:
            self._on_confirm()

# ════════════════════════════════════════════════════════════════════
#  ADMIN PIN DIALOG  (Ctrl+Shift+A → exit fullscreen / close app)
# ════════════════════════════════════════════════════════════════════

class AdminPinDialog(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()
        self.update_idletasks()
        w, h = 420, 400
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.bind("<Return>", lambda _: self._check())
        self.bind("<Escape>", lambda _: self.destroy())

    def _build(self):
        accent_bar(self, color=RED).pack(fill="x")
        tk.Label(self, text="🔐", bg=BG2, fg=RED, font=(FD, 32)).pack(pady=(28, 0))
        tk.Label(self, text="Admin Exit", bg=BG2, fg=TEXT,
                 font=(FD, 15, "bold")).pack(pady=(6, 2))
        tk.Label(self, text="Enter PIN to close TimeNet Admin",
                 bg=BG2, fg=TEXT2, font=(FB, 10)).pack(pady=(0, 18))
        hsep(self).pack(fill="x", padx=28, pady=(0, 18))
        self.pin_var = tk.StringVar()
        pf = tk.Frame(self, bg=BG4, highlightthickness=2,
                      highlightbackground=BORDER3)
        pf.pack(padx=36, fill="x")
        e = tk.Entry(pf, textvariable=self.pin_var, show="●",
                     bg=BG4, fg=TEXT, insertbackground=RED,
                     font=(FD, 24, "bold"), justify="center", relief="flat")
        e.pack(padx=12, pady=10, fill="x")
        e.focus_set()
        self.err = tk.Label(self, text="", bg=BG2, fg=RED, font=(FB, 9))
        self.err.pack(pady=(10, 4))
        row = tk.Frame(self, bg=BG2)
        row.pack(padx=28, pady=(14, 28), fill="x")
        ghost_button(row, "Cancel", self.destroy, TEXT2, 14).pack(
            side="left", expand=True, fill="x", padx=(0, 8))
        tk.Button(row, text="Confirm Exit", command=self._check,
                  bg=RED, fg=TEXT, font=(FD, 11, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground=RED2, activeforeground=TEXT,
                  padx=12, pady=14).pack(side="left", expand=True, fill="x")

    def _check(self):
        if self.pin_var.get() == ADMIN_EXIT_PIN:
            self.destroy()
            self.on_success()
        else:
            self.err.config(text="✗  Incorrect PIN — please try again.")
            self.pin_var.set("")

# ════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════

class Auth:
    user = None

    @classmethod
    def login(cls, u):
        cls.user = {k: v for k, v in u.items() if k != "password"}

    @classmethod
    def logout(cls):
        cls.user = None

# ════════════════════════════════════════════════════════════════════
#  MAIN APP WINDOW
#  — Fullscreen kiosk (same approach as customer.py).
#  — Ctrl+Shift+A  →  PIN dialog  →  closes the app.
#  — Title-bar / close button are hidden via overrideredirect.
# ════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TimeNet Cafe — Admin")
        self.configure(bg=BG)
        self._setup_ttk()
        self._set_icon()
        self._apply_fullscreen()
        self.container     = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.current_frame = None
        self.show_login()
        # Ctrl+Shift+A  →  exit PIN dialog
        self.bind_all("<Control-Shift-A>", lambda _: self._admin_exit())
        # Block the OS close button (there won't be one, but just in case)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

    # ── icon ──────────────────────────────────────────────────────

    def _set_icon(self):
        """Embed a base64 PNG as the window / taskbar icon."""
        try:
            # Build the icon from the embedded base64 PNG
            icon_data = base64.b64decode(self._make_icon_png())
            import io
            img = tk.PhotoImage(data=base64.b64encode(icon_data).decode())
            self.wm_iconphoto(True, img)
            self._icon_ref = img   # keep a reference so GC doesn't collect it
        except Exception as e:
            print(f"[Icon] {e}")

    @staticmethod
    def _make_icon_png():
        """Generate a crisp 64×64 RGBA PNG with a navy circle and amber 'TN'."""
        import struct, zlib, math

        W, H = 64, 64
        TRANSPARENT = (0,   0,  0,   0)
        FILL        = (12, 19, 32, 255)   # navy BG2
        RING        = (245, 166, 35, 255)  # amber border
        AMB         = (245, 166, 35, 255)  # amber letters
        BG_OUTER    = (7,  11, 18, 255)    # outermost BG

        cx, cy, r_outer, r_inner = 32.0, 32.0, 31.0, 27.5

        pixels = [[list(TRANSPARENT)] * W for _ in range(H)]

        for y in range(H):
            for x in range(W):
                d = math.hypot(x - cx, y - cy)
                if d <= r_inner:
                    pixels[y][x] = list(FILL)
                elif d <= r_outer:
                    pixels[y][x] = list(RING)

        def fill_rect(x0, y0, x1, y1, color):
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if 0 <= x < W and 0 <= y < H:
                        if math.hypot(x - cx, y - cy) <= r_inner:
                            pixels[y][x] = list(color)

        # ── T  (left side, cols 8-29) ──
        fill_rect(8,  13, 29, 20, AMB)   # crossbar
        fill_rect(15, 20, 22, 51, AMB)   # stem

        # ── N  (right side, cols 32-55) ──
        fill_rect(32, 13, 39, 51, AMB)   # left post
        fill_rect(48, 13, 55, 51, AMB)   # right post
        # diagonal
        for i in range(38):
            x = 39 + int(i * 9 / 37)
            y = 13 + i
            if 0 <= x < W and 0 <= y < H:
                if math.hypot(x - cx, y - cy) <= r_inner:
                    for dx in range(3):
                        nx = x + dx
                        if nx < W and math.hypot(nx - cx, y - cy) <= r_inner:
                            pixels[y][nx] = list(AMB)

        def png_chunk(tag, data):
            c = tag + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        raw = b""
        for row in pixels:
            raw += b"\x00"
            for px in row:
                raw += bytes(px)

        png = b"\x89PNG\r\n\x1a\n"
        png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
        png += png_chunk(b"IDAT", zlib.compress(raw, 9))
        png += png_chunk(b"IEND", b"")
        return base64.b64encode(png).decode()

    # ── fullscreen ────────────────────────────────────────────────

    def _apply_fullscreen(self):
        """Cover the entire screen, no title bar, no taskbar gap."""
        self.overrideredirect(False)
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.update_idletasks()
        self.overrideredirect(True)
        self.update_idletasks()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        # Drop topmost shortly after so dialogs can appear above the window
        self.after(500, lambda: self.attributes("-topmost", False))

    # ── admin exit ────────────────────────────────────────────────

    def _admin_exit(self):
        """Ctrl+Shift+A → PIN → destroy the app."""
        def _do():
            self.destroy()
        AdminPinDialog(self, on_success=_do)

    # ── ttk styling ───────────────────────────────────────────────

    def _setup_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=BG2, foreground=TEXT,
                    fieldbackground=BG2, bordercolor=BORDER,
                    rowheight=32, font=(FB, 10))
        s.configure("Treeview.Heading",
                    background=BG3, foreground=TEXT2,
                    relief="flat", font=(FB, 10, "bold"), borderwidth=0)
        s.map("Treeview",
              background=[("selected", "#0d2a42")],
              foreground=[("selected", AMBER)])
        s.configure("TScrollbar",
                    background=BG4, troughcolor=BG2,
                    bordercolor=BG, arrowcolor=TEXT3, relief="flat")

    def switch_frame(self, cls, *a, **kw):
        if self.current_frame:
            self.current_frame.destroy()
        f = cls(self.container, self, *a, **kw)
        f.pack(fill="both", expand=True)
        self.current_frame = f

    def show_login(self):
        self.switch_frame(LoginPage)

    def show_dashboard(self):
        self.switch_frame(AdminDashboard)

    def logout(self):
        Auth.logout()
        self.show_login()

# ════════════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ════════════════════════════════════════════════════════════════════

class LoginPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        make_bg_canvas(self)
        outer = tk.Frame(self, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")
        card_border = tk.Frame(outer, bg=BORDER2)
        card_border.pack()
        card = tk.Frame(card_border, bg=BG2)
        card.pack(padx=1, pady=1)

        gc = tk.Canvas(card, bg=BG2, height=4, highlightthickness=0, width=440)
        gc.pack(fill="x")
        gc.bind("<Configure>", lambda e: gradient_bar(gc, 0, 0, e.width, 4, PURPLE, AMBER))

        tk.Label(card, text="🛡", bg=BG2, fg=PURPLE, font=(FD, 36)).pack(pady=(30, 0))
        tk.Label(card, text="TimeNet Admin", bg=BG2, fg=TEXT,
                 font=(FD, 22, "bold")).pack(pady=(6, 2))
        tk.Label(card, text="Staff & management portal", bg=BG2, fg=TEXT2,
                 font=(FB, 11)).pack(pady=(0, 20))
        hsep(card).pack(fill="x", padx=36, pady=(0, 20))

        form = tk.Frame(card, bg=BG2)
        form.pack(padx=48, fill="x")
        self.err = tk.Label(form, text="", fg=RED, bg=BG2,
                            wraplength=340, font=(FB, 10), justify="left")
        self.err.pack(fill="x", pady=(0, 8))
        self.usr = tk.StringVar()
        self.pwd = tk.StringVar()

        # Username field
        tk.Label(form, text="USERNAME", fg=TEXT3, bg=BG2,
                 font=(FB, 8, "bold")).pack(anchor="w", pady=(0, 3))
        uf = tk.Frame(form, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        uf.pack(fill="x", pady=(0, 16))
        eu = tk.Entry(uf, textvariable=self.usr, bg=BG4, fg=TEXT,
                      insertbackground=PURPLE, font=(FB, 12), relief="flat")
        eu.pack(padx=14, pady=10, fill="x")
        eu.bind("<FocusIn>",  lambda _: uf.config(highlightbackground=PURPLE))
        eu.bind("<FocusOut>", lambda _: uf.config(highlightbackground=BORDER2))

        # Password field
        tk.Label(form, text="PASSWORD", fg=TEXT3, bg=BG2,
                 font=(FB, 8, "bold")).pack(anchor="w", pady=(0, 3))
        pf = tk.Frame(form, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        pf.pack(fill="x", pady=(0, 16))
        ep = tk.Entry(pf, textvariable=self.pwd, show="●",
                      bg=BG4, fg=TEXT, insertbackground=PURPLE,
                      font=(FB, 12), relief="flat")
        ep.pack(padx=14, pady=10, fill="x")
        ep.bind("<FocusIn>",  lambda _: pf.config(highlightbackground=PURPLE))
        ep.bind("<FocusOut>", lambda _: pf.config(highlightbackground=BORDER2))
        ep.bind("<Return>", lambda _: self._login())

        tk.Button(form, text="Sign In →", command=self._login,
                  bg=PURPLE, fg=TEXT, font=(FD, 12, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground="#7e22ce", activeforeground=TEXT,
                  padx=20, pady=14).pack(fill="x", pady=(0, 6))
        hsep(card).pack(fill="x", padx=36, pady=20)

        # Exit hint
        tk.Label(card, text="Admin accounts only  •  Ctrl+Shift+A to exit",
                 fg=TEXT3, bg=BG2, font=(FB, 9)).pack(pady=(0, 24))

    def _login(self):
        u = self.usr.get().strip()
        p = self.pwd.get().strip()
        if not u or not p:
            self.err.config(text="⚠  Please fill in all fields.")
            return
        rows = db_exec(
            "SELECT * FROM users WHERE username=%s AND password=%s AND role='admin'",
            (u, p), fetch=True)
        if rows:
            Auth.login(dict(rows[0]))
            self.app.show_dashboard()
        else:
            self.err.config(text="✗  Invalid credentials or not an admin account.")

# ════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ════════════════════════════════════════════════════════════════════

class AdminDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app          = app
        self._current_tab = "overview"
        self._build()
        self._load_data()
        self._poll()

    def _build(self):
        # ── header ────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2)
        hdr.pack(fill="x")
        gc = tk.Canvas(hdr, bg=BG2, height=3, highlightthickness=0)
        gc.pack(fill="x")
        gc.bind("<Configure>", lambda e: gradient_bar(gc, 0, 0, e.width, 3, PURPLE, AMBER))
        hi = tk.Frame(hdr, bg=BG2)
        hi.pack(fill="x", padx=28, pady=14)
        left = tk.Frame(hi, bg=BG2)
        left.pack(side="left")
        tk.Label(left, text="🛡", bg=BG2, fg=PURPLE,
                 font=(FD, 18)).pack(side="left", padx=(0, 10))
        nc = tk.Frame(left, bg=BG2)
        nc.pack(side="left")
        tk.Label(nc, text="Admin Portal", bg=BG2, fg=TEXT,
                 font=(FD, 14, "bold")).pack(anchor="w")
        tk.Label(nc, text="TimeNet Cafe Management",
                 bg=BG2, fg=TEXT2, font=(FB, 10)).pack(anchor="w")
        ghost_button(hi, "Sign Out", self.app.logout, TEXT2, 8).pack(side="right")

        hsep(self, BORDER2).pack(fill="x")

        # ── tab bar ───────────────────────────────────────────────
        tab_bar = tk.Frame(self, bg=BG2)
        tab_bar.pack(fill="x")
        self.tab_btns = {}
        self.tab_inds = {}
        tabs = [
            ("overview", "📊  Overview"),
            ("vouchers", "🎫  Vouchers"),
            ("reports",  "📈  Reports"),
        ]
        for tid, lbl in tabs:
            col = tk.Frame(tab_bar, bg=BG2)
            col.pack(side="left")
            b = tk.Button(col, text=lbl,
                          command=lambda t=tid: self._switch_tab(t),
                          bg=BG2,
                          fg=TEXT if tid == "overview" else TEXT2,
                          font=(FB, 11, "bold"), relief="flat", cursor="hand2",
                          activebackground=BG2, activeforeground=TEXT,
                          padx=24, pady=14)
            b.pack()
            ind = tk.Frame(col, bg=AMBER if tid == "overview" else BG2, height=2)
            ind.pack(fill="x")
            self.tab_btns[tid] = b
            self.tab_inds[tid] = ind

        hsep(self, BORDER2).pack(fill="x")
        self.tab_content = tk.Frame(self, bg=BG)
        self.tab_content.pack(fill="both", expand=True)
        self._build_overview()

    def _switch_tab(self, tab):
        if tab == self._current_tab:
            return
        self._current_tab = tab
        for tid, b in self.tab_btns.items():
            active = tid == tab
            b.config(fg=TEXT if active else TEXT2)
            self.tab_inds[tid].config(bg=AMBER if active else BG2)
        for w in self.tab_content.winfo_children():
            w.destroy()
        builders = {
            "overview": self._build_overview,
            "vouchers": self._build_vouchers,
            "reports":  self._build_reports,
        }
        builders[tab]()
        self._load_data()

    # ════════════════════════════════════════════════════════════
    #  OVERVIEW TAB
    # ════════════════════════════════════════════════════════════

    def _build_overview(self):
        canvas = tk.Canvas(self.tab_content, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(self.tab_content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        wrapper = tk.Frame(canvas, bg=BG)
        wid     = canvas.create_window((0, 0), window=wrapper, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        wrapper.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._ov = tk.Frame(wrapper, bg=BG)
        self._ov.pack(anchor="center", expand=True, fill="x")
        self._build_live_section()
        self._build_fleet_section()

    def _section(self, title):
        card = tk.Frame(self._ov, bg=BG2, highlightthickness=1,
                        highlightbackground=BORDER2)
        card.pack(padx=32, pady=(16, 0), fill="x")
        hdr = tk.Frame(card, bg=BG2)
        hdr.pack(fill="x", padx=24, pady=(18, 0))
        tk.Label(hdr, text=title, fg=TEXT, bg=BG2,
                 font=(FD, 13, "bold")).pack(side="left")
        hsep(card, BORDER).pack(fill="x", padx=20, pady=12)
        return card

    def _build_live_section(self):
        card = self._section("📡  Live Sessions")
        self.live_frame = tk.Frame(card, bg=BG2)
        self.live_frame.pack(fill="x", padx=20, pady=(0, 18))

    def _build_fleet_section(self):
        card = tk.Frame(self._ov, bg=BG2, highlightthickness=1,
                        highlightbackground=BORDER2)
        card.pack(padx=32, pady=(16, 32), fill="x")
        top = tk.Frame(card, bg=BG2)
        top.pack(fill="x", padx=24, pady=(18, 0))
        tk.Label(top, text="🖥  Computer Fleet", fg=TEXT, bg=BG2,
                 font=(FD, 13, "bold")).pack(side="left")
        ar = tk.Frame(top, bg=BG2)
        ar.pack(side="right")
        self.new_pc_var = tk.StringVar()
        nf = tk.Frame(ar, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        nf.pack(side="left", padx=(0, 10))
        tk.Entry(nf, textvariable=self.new_pc_var, width=18,
                 bg=BG4, fg=TEXT, insertbackground=AMBER,
                 font=(FB, 10), relief="flat").pack(padx=10, pady=6)
        tk.Button(ar, text="+ Add PC", command=self._add_pc,
                  bg=AMBER, fg=BG, font=(FB, 10, "bold"), relief="flat",
                  cursor="hand2", activebackground=AMBER2, activeforeground=BG,
                  padx=14, pady=6).pack(side="left")
        hsep(card, BORDER).pack(fill="x", padx=20, pady=12)
        self.pc_grid = tk.Frame(card, bg=BG2)
        self.pc_grid.pack(fill="x", padx=20, pady=(0, 20))

    # ════════════════════════════════════════════════════════════
    #  VOUCHERS TAB
    # ════════════════════════════════════════════════════════════

    def _build_vouchers(self):
        outer = tk.Frame(self.tab_content, bg=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = tk.Frame(outer, bg=BG2, highlightthickness=1, highlightbackground=BORDER2)
        top.pack(fill="x", pady=(0, 20))
        accent_bar(top, GREEN).pack(fill="x")
        tk.Label(top, text="🎫  Activate Cash Voucher", fg=TEXT, bg=BG2,
                 font=(FD, 13, "bold")).pack(anchor="w", padx=20, pady=(14, 2))
        tk.Label(top, text="Enter the customer's voucher code to start their session",
                 fg=TEXT2, bg=BG2, font=(FB, 10)).pack(anchor="w", padx=20)
        hsep(top, BORDER).pack(fill="x", padx=16, pady=10)

        ar = tk.Frame(top, bg=BG2)
        ar.pack(padx=20, pady=(0, 14), fill="x")
        self.vt_var = tk.StringVar()
        self.vt_var.trace("w", lambda *_: self.vt_var.set(self.vt_var.get().upper()))
        vf = tk.Frame(ar, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        vf.pack(side="left", padx=(0, 12))
        self.vt_entry = tk.Entry(vf, textvariable=self.vt_var, width=32,
                                 bg=BG4, fg=TEXT, insertbackground=GREEN,
                                 font=(FM, 13), relief="flat")
        self.vt_entry.pack(padx=14, pady=10)
        self.vt_entry.bind("<Return>", lambda _: self._activate_voucher())
        self.vt_entry.focus_set()
        tk.Button(ar, text="✓  Activate", command=self._activate_voucher,
                  bg=GREEN, fg=BG, font=(FB, 11, "bold"), relief="flat",
                  cursor="hand2", activebackground=GREEN2, activeforeground=BG,
                  padx=20, pady=10).pack(side="left")

        self.vt_msg = tk.Label(top, text="", fg=GREEN, bg=BG2, font=(FB, 10))
        self.vt_msg.pack(anchor="w", padx=20, pady=(0, 14))

        tk.Label(outer, text="Voucher Log", fg=TEXT, bg=BG,
                 font=(FD, 13, "bold")).pack(anchor="w", pady=(0, 8))
        cols = ("Voucher Code", "PC", "Duration", "Amount", "Status", "Time")
        tf   = tk.Frame(outer, bg=BG, highlightthickness=1, highlightbackground=BORDER2)
        tf.pack(fill="both", expand=True)
        self.vt_tree = ttk.Treeview(tf, columns=cols, show="headings", height=18)
        widths = {"Voucher Code": 160, "PC": 80, "Duration": 90,
                  "Amount": 100, "Status": 110, "Time": 160}
        for c in cols:
            self.vt_tree.heading(c, text=c)
            self.vt_tree.column(c, width=widths.get(c, 120), anchor="w")
        self.vt_tree.tag_configure("pending",   background="#1a2a10", foreground=YELLOW)
        self.vt_tree.tag_configure("active",    background="#0d2a1a", foreground=GREEN)
        self.vt_tree.tag_configure("cancelled", background="#300010", foreground=RED)
        self.vt_tree.tag_configure("used",      background=BG3,       foreground=TEXT2)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.vt_tree.yview)
        self.vt_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.vt_tree.pack(fill="both", expand=True)

    def _activate_voucher(self):
        code = self.vt_var.get().strip().upper()
        if not code:
            self.vt_msg.config(text="⚠  Please enter a voucher code.", fg=YELLOW)
            return
        rows = db_exec(
            "SELECT * FROM sessions WHERE status='pending_voucher' AND voucher_code=%s",
            (code,), fetch=True)
        if not rows:
            self.vt_msg.config(text="✗  Invalid code or session already activated.", fg=RED)
            return
        pending = _norm_session(rows[0])

        db_exec(
            "UPDATE sessions SET status='active', start_time=%s WHERE id=%s",
            (now_ms(), pending["id"]))
        db_exec(
            "UPDATE computers SET status='occupied', current_session_id=%s WHERE id=%s",
            (pending["id"], pending["computerId"]))

        pay_exists = db_exec(
            "SELECT id FROM payments WHERE session_id=%s AND status='completed'",
            (pending["id"],), fetch=True)
        if not pay_exists:
            db_exec("""
                INSERT IGNORE INTO payments
                  (id, session_id, user_id, amount, method, timestamp, receipt_no, status)
                VALUES (%s,%s,%s,%s,'cash',%s,%s,'completed')
            """, (f"pay-{now_ms()}", pending["id"], pending.get("userId", ""),
                  pending.get("cost", 0), now_ms(), gen_receipt()))

        pc_rows = db_exec(
            "SELECT name FROM computers WHERE id=%s",
            (pending["computerId"],), fetch=True)
        pc_name = pc_rows[0]["name"] if pc_rows else "PC"
        self.vt_var.set("")
        self.vt_msg.config(
            text=f"✓  Activated!  {pc_name} is now live ({pending.get('duration','?')} min)",
            fg=GREEN)
        self._load_data()

    # ════════════════════════════════════════════════════════════
    #  REPORTS TAB
    # ════════════════════════════════════════════════════════════

    def _build_reports(self):
        f = tk.Frame(self.tab_content, bg=BG)
        f.pack(fill="both", expand=True, padx=40, pady=24)

        date_row = tk.Frame(f, bg=BG)
        date_row.pack(fill="x", pady=(0, 16))
        dl = tk.Frame(date_row, bg=BG)
        dl.pack(side="left")
        tk.Label(dl, text="📅", bg=BG, fg=AMBER, font=(FD, 16)).pack(
            side="left", padx=(0, 8))
        lc = tk.Frame(dl, bg=BG)
        lc.pack(side="left")
        tk.Label(lc, text="STATISTICS FOR", fg=TEXT3, bg=BG,
                 font=(FB, 8, "bold")).pack(anchor="w")
        self.date_lbl = tk.Label(lc, text=today_label(), fg=TEXT, bg=BG,
                                 font=(FD, 15, "bold"))
        self.date_lbl.pack(anchor="w")
        self.clock_lbl = tk.Label(date_row,
                                  text=datetime.now().strftime("%I:%M:%S %p"),
                                  fg=AMBER, bg=BG, font=(FM, 13, "bold"))
        self.clock_lbl.pack(side="right")
        self._tick_clock()
        hsep(f, BORDER2).pack(fill="x", pady=(0, 16))

        stat_outer = tk.Frame(f, bg=BG)
        stat_outer.pack(fill="x", pady=(0, 20))
        for i in range(3):
            stat_outer.columnconfigure(i, weight=1, minsize=180)
        self.stat_cards = {}
        defs = [
            ("sessions", "Today's Sessions", "0",       CYAN,   "🗓"),
            ("hours",    "Hours Used Today",  "0.0 hrs", PURPLE, "⏱"),
            ("income",   "Today's Income",    "₱0.00",   GREEN,  "💰"),
        ]
        for col_idx, (key, title, default, color, icon) in enumerate(defs):
            card, val_lbl = stat_card(stat_outer, icon, title, default, color)
            card.grid(row=0, column=col_idx, padx=6, sticky="nsew")
            self.stat_cards[key] = val_lbl

        th = tk.Frame(f, bg=BG)
        th.pack(fill="x", pady=(0, 10))
        tk.Label(th, text="Session History", fg=TEXT, bg=BG,
                 font=(FD, 13, "bold")).pack(side="left")
        tk.Button(th, text="⬇  Export CSV", command=self._export_csv,
                  bg=BG3, fg=TEXT2, font=(FB, 10, "bold"), relief="flat",
                  cursor="hand2", activebackground=BG4, activeforeground=TEXT,
                  padx=14, pady=7).pack(side="right")

        cols = ("Date", "PC", "Duration", "Cost", "Method", "Status", "Receipt")
        tf   = tk.Frame(f, bg=BG, highlightthickness=1, highlightbackground=BORDER2)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=16)
        cw = {"Date": 160, "PC": 70, "Duration": 90, "Cost": 100,
              "Method": 80, "Status": 100, "Receipt": 150}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=cw.get(col, 110), anchor="w")
        self.tree.tag_configure("odd",       background=BG3)
        self.tree.tag_configure("even",      background=BG2)
        self.tree.tag_configure("cancelled", background="#300010", foreground=RED)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

    def _tick_clock(self):
        try:
            self.clock_lbl.config(text=datetime.now().strftime("%I:%M:%S %p"))
            self.date_lbl.config(text=today_label())
            self.after(1000, self._tick_clock)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════
    #  DATA LOADING
    # ════════════════════════════════════════════════════════════

    def _load_data(self):
        computers = db_exec("SELECT * FROM computers", fetch=True) or []
        sessions  = [_norm_session(r)
                     for r in (db_exec("SELECT * FROM sessions", fetch=True) or [])]
        payments  = db_exec("SELECT * FROM payments", fetch=True) or []

        if self._current_tab == "overview":
            self._refresh_live(sessions, computers)
            self._refresh_fleet(computers)
        elif self._current_tab == "vouchers":
            self._refresh_vouchers(sessions, computers)
        elif self._current_tab == "reports":
            self._refresh_stats(sessions, payments)
            self._refresh_table(sessions, payments, computers)

    def _refresh_live(self, sessions, computers):
        for w in self.live_frame.winfo_children():
            w.destroy()
        active = [s for s in sessions if s["status"] == "active"]
        if not active:
            tk.Label(self.live_frame, text="No active sessions right now.",
                     fg=TEXT3, bg=BG2, font=(FB, 10)).pack(anchor="w", pady=4)
            return
        for s in active:
            pc        = next((c for c in computers if c["id"] == s["computerId"]), None)
            total_ms  = s.get("duration", 60) * 60 * 1000
            start     = s.get("startTime") or 0
            rem_min   = max(0, (start + total_ms - now_ms()) // 60_000)
            row = tk.Frame(self.live_frame, bg=BG3, highlightthickness=1,
                           highlightbackground=BORDER2)
            row.pack(fill="x", pady=4)
            tk.Frame(row, bg=GREEN, width=3).pack(side="left", fill="y")
            tk.Label(row, text=pc["name"] if pc else "?",
                     fg=TEXT, bg=BG3, font=(FB, 11, "bold")).pack(
                side="left", padx=(14, 6), pady=10)
            tk.Label(row, text=f"{s.get('duration','?')} min session",
                     fg=TEXT2, bg=BG3, font=(FB, 10)).pack(side="left")
            bbg = CYAN_DIM if rem_min > 10 else RED_DIM
            bfg = CYAN     if rem_min > 10 else RED
            tk.Label(row, text=f"  {rem_min}m left  ",
                     fg=bfg, bg=bbg, font=(FB, 10, "bold")).pack(
                side="right", padx=14, pady=8)

    def _refresh_fleet(self, computers):
        for w in self.pc_grid.winfo_children():
            w.destroy()
        for idx, c in enumerate(computers):
            rn, cn  = divmod(idx, 4)
            status   = c["status"]
            color    = {"available": GREEN, "occupied": RED,
                        "maintenance": YELLOW}.get(status, TEXT2)
            label    = {"available": "AVAILABLE", "occupied": "IN USE",
                        "maintenance": "MAINTENANCE"}.get(status, status.upper())
            occupied = status == "occupied"

            frame = tk.Frame(self.pc_grid, bg=BG3, highlightthickness=1,
                             highlightbackground=BORDER2)
            frame.grid(row=rn, column=cn, padx=6, pady=6, sticky="nsew")
            self.pc_grid.columnconfigure(cn, weight=1)
            accent_bar(frame, color, 2).pack(fill="x")
            info = tk.Frame(frame, bg=BG3)
            info.pack(fill="x", padx=12, pady=(10, 4))
            tk.Label(info, text="🖥", bg=BG3, fg=color,
                     font=(FD, 18)).pack(side="left", padx=(0, 8))
            nc = tk.Frame(info, bg=BG3)
            nc.pack(side="left")
            tk.Label(nc, text=c["name"], fg=TEXT, bg=BG3,
                     font=(FB, 11, "bold")).pack(anchor="w")
            tk.Label(nc, text=label, fg=color, bg=BG3,
                     font=(FB, 8, "bold")).pack(anchor="w")
            br = tk.Frame(frame, bg=BG3)
            br.pack(fill="x", padx=10, pady=(6, 12))
            maint_lbl = "✓ Fixed"   if status == "maintenance" else "🔧 Maintain"
            maint_fg  = YELLOW      if status == "maintenance" else TEXT3
            mb = tk.Button(br, text=maint_lbl,
                           command=lambda cid=c["id"]: self._toggle_maint(cid),
                           bg=BG4, fg=maint_fg, font=(FB, 8, "bold"), relief="flat",
                           cursor="hand2" if not occupied else "arrow",
                           padx=8, pady=5)
            if occupied:
                mb.config(state="disabled", fg=TEXT3)
            mb.pack(side="left", expand=True, fill="x", padx=(0, 4))
            db_btn = tk.Button(br, text="🗑",
                               command=lambda cid=c["id"], cn=c["name"]:
                                   self._del_pc(cid, cn),
                               bg=BG4, fg=RED, font=(FB, 8), relief="flat",
                               cursor="hand2" if not occupied else "arrow",
                               padx=8, pady=5)
            if occupied:
                db_btn.config(state="disabled", fg=TEXT3)
            db_btn.pack(side="left")

    def _refresh_vouchers(self, sessions, computers):
        try:
            self.vt_tree.delete(*self.vt_tree.get_children())
        except Exception:
            return
        cash = [s for s in sessions
                if s.get("voucherCode") or
                s.get("status") in ("pending_voucher", "cancelled")]
        cash.sort(
            key=lambda x: x.get("startTime") or x.get("cancelledAt") or 0,
            reverse=True)
        for s in cash:
            pc = next((c for c in computers if c["id"] == s["computerId"]), None)
            st = s["status"]
            if st == "pending_voucher": sl, tag = "⏳ Waiting",   "pending"
            elif st == "active":        sl, tag = "✅ Active",    "active"
            elif st == "completed":     sl, tag = "✓ Used",       "used"
            elif st == "cancelled":     sl, tag = "✕ Cancelled",  "cancelled"
            else:                       sl, tag = st.title(),      "used"
            ts     = s.get("startTime") or s.get("cancelledAt")
            ts_str = (datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
                      if ts else "—")
            self.vt_tree.insert("", "end", tags=(tag,), values=(
                s.get("voucherCode", "—"),
                pc["name"] if pc else "?",
                f"{s.get('duration', '?')} min",
                fmt_currency(s.get("cost", 0)),
                sl,
                ts_str,
            ))

    def _refresh_stats(self, sessions, payments):
        try:
            self.date_lbl.config(text=today_label())
        except Exception:
            pass
        today_ms  = today_start_ms()
        completed = [s for s in sessions
                     if s["status"] == "completed" and
                     (s.get("endTime") or 0) >= today_ms]
        today_pay = [p for p in payments
                     if (p.get("timestamp") or 0) >= today_ms and
                     p.get("status") == "completed"]
        income    = sum(float(p.get("amount", 0)) for p in today_pay)
        total_min = sum(s.get("duration", 0) for s in completed)
        try:
            self.stat_cards["sessions"].config(text=str(len(completed)))
            self.stat_cards["hours"].config(text=f"{total_min / 60:.1f} hrs")
            self.stat_cards["income"].config(text=fmt_currency(income))
        except Exception:
            pass

    def _refresh_table(self, sessions, payments, computers):
        try:
            self.tree.delete(*self.tree.get_children())
        except Exception:
            return
        rows = sorted(
            [s for s in sessions if s["status"] in ("completed", "cancelled")],
            key=lambda x: x.get("endTime") or x.get("cancelledAt") or 0,
            reverse=True)
        for i, s in enumerate(rows):
            pay  = next((p for p in payments
                         if p.get("session_id") == s["id"] and
                         p.get("status") == "completed"), None)
            pc   = next((c for c in computers if c["id"] == s["computerId"]), None)
            is_c = s["status"] == "cancelled"
            ts   = s.get("endTime") or s.get("cancelledAt")
            date = (datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d  %H:%M")
                    if ts else "—")
            tag  = "cancelled" if is_c else ("odd" if i % 2 else "even")
            self.tree.insert("", "end", tags=(tag,), values=(
                date,
                pc["name"] if pc else "?",
                f"{s.get('duration', '?')} min",
                fmt_currency(s.get("cost", 0)),
                (pay.get("method", "").upper() if pay else
                 ("CASH" if s.get("voucherCode") else "—")),
                "Cancelled" if is_c else "Completed",
                pay.get("receipt_no", "—") if pay else "—",
            ))

    # ════════════════════════════════════════════════════════════
    #  FLEET ACTIONS
    # ════════════════════════════════════════════════════════════

    def _add_pc(self):
        name = self.new_pc_var.get().strip()
        if not name:
            ThemedDialog(self, kind="warning", title="Add PC",
                         message="Please enter a PC name first.")
            return
        exists = db_exec(
            "SELECT id FROM computers WHERE LOWER(name)=LOWER(%s)", (name,), fetch=True)
        if exists:
            ThemedDialog(self, kind="error", title="Duplicate Name",
                         message=f'A PC named "{name}" already exists.')
            return
        db_exec(
            "INSERT INTO computers (id, name, status) VALUES (%s,%s,'available')",
            (f"pc-{now_ms()}", name))
        self.new_pc_var.set("")
        self._load_data()

    def _del_pc(self, cid, name):
        ConfirmDialog(self, title="Delete PC",
                      message=f'Are you sure you want to delete "{name}"?',
                      on_confirm=lambda: self._do_del_pc(cid))

    def _do_del_pc(self, cid):
        db_exec("DELETE FROM computers WHERE id=%s", (cid,))
        self._load_data()

    def _toggle_maint(self, cid):
        rows = db_exec(
            "SELECT status FROM computers WHERE id=%s", (cid,), fetch=True)
        if not rows:
            return
        new_status = ("available" if rows[0]["status"] == "maintenance"
                      else "maintenance")
        db_exec("UPDATE computers SET status=%s WHERE id=%s", (new_status, cid))
        self._load_data()

    # ════════════════════════════════════════════════════════════
    #  CSV EXPORT
    # ════════════════════════════════════════════════════════════

    def _export_csv(self):
        sessions  = [_norm_session(r)
                     for r in (db_exec("SELECT * FROM sessions", fetch=True) or [])]
        payments  = db_exec("SELECT * FROM payments", fetch=True) or []
        computers = db_exec("SELECT * FROM computers", fetch=True) or []
        relevant  = [s for s in sessions if s["status"] in ("completed", "cancelled")]
        filename  = f"timenet_report_{datetime.now().strftime('%Y-%m-%d')}.csv"
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Date", "Session ID", "PC", "Duration (min)",
                            "Cost (PHP)", "Payment Method", "Status", "Receipt No"])
                for s in relevant:
                    pay = next((p for p in payments
                                if p.get("session_id") == s["id"] and
                                p.get("status") == "completed"), None)
                    pc  = next((c for c in computers if c["id"] == s["computerId"]), None)
                    ts  = s.get("endTime") or s.get("cancelledAt")
                    w.writerow([
                        datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
                            if ts else "",
                        s["id"],
                        pc["name"] if pc else "?",
                        s.get("duration", ""),
                        s.get("cost", ""),
                        pay["method"] if pay else
                            ("cash" if s.get("voucherCode") else ""),
                        s["status"],
                        pay.get("receipt_no", "") if pay else "",
                    ])
            ThemedDialog(self, kind="success", title="Export Successful",
                         message=f"{len(relevant)} session(s) exported.",
                         detail=os.path.abspath(filename))
        except Exception as e:
            ThemedDialog(self, kind="error", title="Export Failed",
                         message="Could not write the CSV file.", detail=str(e))

    # ════════════════════════════════════════════════════════════
    #  POLL LOOP  (refreshes every 2 seconds)
    # ════════════════════════════════════════════════════════════

    def _poll(self):
        self._load_data()
        self.after(2000, self._poll)

# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()