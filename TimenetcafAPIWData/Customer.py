"""
TimeNet Cafe — CUSTOMER PC
Requires: pip install mysql-connector-python requests pystray pillow

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SINGLE PC SETUP (current):
    DB host is "localhost" — runs on the same machine as XAMPP.

  TWO PC SETUP (when you split admin and customer PCs):
    On every customer PC, change DB_CONFIG["host"] from
    "localhost" to the LAN IP of the PC running XAMPP,
    e.g. "192.168.1.10".  Leave everything else the same.

  RECAPTCHA SETUP:
    1. Go to https://www.google.com/recaptcha/admin and register
       your site with reCAPTCHA v2 ("I'm not a robot" checkbox).
    2. Add "localhost" and "127.0.0.1" to the allowed domains list.
    3. Replace RECAPTCHA_SITE_KEY below with your Site Key.
    4. Replace RECAPTCHA_SECRET_KEY below with your Secret Key.
    5. The reCAPTCHA page is served via a local HTTP server on
       127.0.0.1 (not file://) so Google's JS loads correctly.
    6. The browser opens in --kiosk (fullscreen) mode, identical
       to the PayMongo payment screen.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import tkinter as tk
from tkinter import ttk
import time
import random
import platform
import subprocess
import shutil
import threading
import tempfile
import base64
import os
from datetime import datetime
import requests
import mysql.connector
from mysql.connector import pooling

# ════════════════════════════════════════════════════════════════════
#  DATABASE CONFIG
# ════════════════════════════════════════════════════════════════════

DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "",
    "database": "timenet",
}

# ════════════════════════════════════════════════════════════════════
#  PAYMONGO CONFIG
# ════════════════════════════════════════════════════════════════════

PAYMONGO_SECRET_KEY = "sk_test_knuivMbT2mfYaub4f6oDNh5y"
PAYMONGO_PUBLIC_KEY = "pk_test_78P7sdJ2p33LmgwFLnrsTHQB"
PAYMONGO_BASE_URL   = "https://api.paymongo.com/v1"

# ════════════════════════════════════════════════════════════════════
#  RECAPTCHA CONFIG
# ════════════════════════════════════════════════════════════════════

RECAPTCHA_SITE_KEY   = "6Lex6eMsAAAAAIuGqF1G0drBafsHY3NLSEQD3473"
RECAPTCHA_SECRET_KEY = "6Lex6eMsAAAAAPQMh-xVBeXISEe-5AJpNUB91Xtl"
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

# ════════════════════════════════════════════════════════════════════
#  BUSINESS RULES
# ════════════════════════════════════════════════════════════════════

HOURLY_RATE      = 15.0
MINUTE_RATE      = HOURLY_RATE / 60
ADMIN_EXIT_PIN   = "1234"
PAYMONGO_MIN_PHP = 1.00

PRICING_TIERS = [
    {"label": "15 min",  "minutes": 1},
    {"label": "30 min",  "minutes": 30},
    {"label": "1 hour",  "minutes": 60},
    {"label": "1.5 hrs", "minutes": 90},
    {"label": "2 hours", "minutes": 120},
    {"label": "3 hours", "minutes": 180},
    {"label": "5 hours", "minutes": 300},
    {"label": "8 hours", "minutes": 480},
]

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
PURPLE2    = "#7e22ce"
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
            pool_name="timenet_customer", pool_size=5, **DB_CONFIG)
    return _pool


def db_exec(query, params=(), fetch=False):
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
    return f"₱{amount:,.2f}"


def gen_receipt():
    ts  = str(int(time.time() * 1000))[-6:]
    rnd = str(random.randint(0, 999)).zfill(3)
    return f"TN-{ts}-{rnd}"


def gen_voucher():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code  = "".join(random.choices(chars, k=8))
    return f"TNV-{code}"


def calc_cost(minutes):
    raw = minutes * MINUTE_RATE
    return max(round(raw * 100) / 100, PAYMONGO_MIN_PHP)


def paymongo_headers():
    token = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def find_browser():
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
    elif system == "Darwin":
        p = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(p):
            return p
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser"):
            f = shutil.which(name)
            if f:
                return f
    return None

# ════════════════════════════════════════════════════════════════════
#  TRAY ICON
# ════════════════════════════════════════════════════════════════════

_tray_icon = None


def _make_tray_image():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    size  = 64
    img   = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size - 1, size - 1], fill=(12, 19, 32, 255))
    draw.ellipse([2, 2, size - 3, size - 3],
                 outline=(168, 85, 247, 200), width=2)
    mx, my, mw, mh = 10, 14, 44, 26
    draw.rounded_rectangle([mx, my, mx + mw, my + mh],
                            radius=4, fill=(23, 34, 55, 255),
                            outline=(168, 85, 247, 255), width=1)
    draw.rounded_rectangle([mx + 3, my + 3, mx + mw - 3, my + mh - 3],
                            radius=2, fill=(0, 45, 56, 255))
    for yi in range(my + 6, my + mh - 3, 4):
        draw.line([(mx + 5, yi), (mx + mw - 5, yi)],
                  fill=(0, 200, 232, 120), width=1)
    draw.rectangle([29, 40, 35, 46], fill=(23, 34, 55, 255))
    draw.rectangle([22, 46, 42, 49], fill=(23, 34, 55, 255))
    try:
        font = ImageFont.truetype("segoeui.ttf", 9)
    except Exception:
        font = ImageFont.load_default()
    draw.text((32, 51), "TN", fill=(168, 85, 247, 220),
              font=font, anchor="mm")
    return img


def start_tray(on_restore):
    global _tray_icon
    try:
        import pystray
    except ImportError:
        print("[Tray] pystray not installed — taskbar icon disabled.")
        return
    img = _make_tray_image()
    if img is None:
        print("[Tray] Pillow not installed — taskbar icon disabled.")
        return

    def _restore(icon, item):
        on_restore()

    menu = pystray.Menu(
        pystray.MenuItem("Show Timer", _restore, default=True),
        pystray.MenuItem("TimeNet Cafe", None, enabled=False),
    )
    icon = pystray.Icon("timenet", img, "TimeNet Cafe — Session Timer", menu=menu)
    _tray_icon = icon
    threading.Thread(target=icon.run, daemon=True).start()


def stop_tray():
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception:
            pass
        _tray_icon = None

# ════════════════════════════════════════════════════════════════════
#  GRADIENT DRAWING
# ════════════════════════════════════════════════════════════════════


def _lerp_color(c1, c2, t):
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = max(0, min(255, int(r1 + (r2 - r1) * t)))
    g = max(0, min(255, int(g1 + (g2 - g1) * t)))
    b = max(0, min(255, int(b1 + (b2 - b1) * t)))
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_gradient_h(canvas, width, height, c1, c2, steps=80):
    canvas.delete("all")
    if width < 2:
        return
    sw = max(1, width // steps)
    for i in range(steps):
        col = _lerp_color(c1, c2, i / steps)
        sx  = i * sw
        canvas.create_rectangle(sx, 0, sx + sw + 1, height,
                                 fill=col, outline="")
    canvas.create_rectangle(steps * sw, 0, width, height,
                             fill=_lerp_color(c1, c2, 1.0), outline="")


def draw_gradient_v(canvas, width, height, c1, c2, steps=60):
    canvas.delete("all")
    if height < 2:
        return
    sh = max(1, height // steps)
    for i in range(steps):
        col = _lerp_color(c1, c2, i / steps)
        sy  = i * sh
        canvas.create_rectangle(0, sy, width, sy + sh + 1,
                                 fill=col, outline="")
    canvas.create_rectangle(0, steps * sh, width, height,
                             fill=_lerp_color(c1, c2, 1.0), outline="")

# ════════════════════════════════════════════════════════════════════
#  UI PRIMITIVES
# ════════════════════════════════════════════════════════════════════


def hsep(parent, color=BORDER2, h=1):
    return tk.Frame(parent, bg=color, height=h)


def accent_bar(parent, color=PURPLE, h=3):
    return tk.Frame(parent, bg=color, height=h)


def make_gradient_canvas_h(parent, height=4, c1=PURPLE, c2=CYAN):
    c     = tk.Canvas(parent, bg=BG2, height=height, highlightthickness=0)
    _last = [0]

    def _paint(w):
        if w > 1 and w != _last[0]:
            _last[0] = w
            draw_gradient_h(c, w, height, c1, c2)

    def _on_configure(e):
        _paint(e.width)

    def _poll():
        w = c.winfo_width()
        if w > 1:
            _paint(w)
        else:
            try:
                c.after(20, _poll)
            except Exception:
                pass

    c.bind("<Configure>", _on_configure)
    c.after(20, _poll)
    return c


def dot_grid(canvas, event, color=TEXT4, spacing=36):
    canvas.delete("dots")
    for x in range(0, event.width, spacing):
        for y in range(0, event.height, spacing):
            canvas.create_oval(x - 1, y - 1, x + 1, y + 1,
                               fill=color, outline="", tags="dots")


def make_bg_canvas(parent):
    c = tk.Canvas(parent, bg=BG, highlightthickness=0)
    c.place(relwidth=1, relheight=1)
    c.bind("<Configure>", lambda e: dot_grid(c, e))
    return c


def pill_button(parent, text, command, bg=PURPLE, fg=TEXT, width=None, pady=14):
    kw = {}
    if width:
        kw["width"] = width
    return tk.Button(parent, text=text, command=command,
                     bg=bg, fg=fg, font=(FD, 12, "bold"),
                     relief="flat", cursor="hand2",
                     activebackground=PURPLE2 if bg == PURPLE else bg,
                     activeforeground=fg,
                     padx=20, pady=pady, **kw)


def ghost_button(parent, text, command, color=TEXT2, pady=12):
    return tk.Button(parent, text=text, command=command,
                     bg=BG4, fg=color, font=(FB, 11, "bold"),
                     relief="flat", cursor="hand2",
                     activebackground=BG5, activeforeground=TEXT,
                     padx=16, pady=pady)

# ════════════════════════════════════════════════════════════════════
#  GRADIENT BORDER
# ════════════════════════════════════════════════════════════════════


def add_gradient_border(dialog, thickness=3, c1=PURPLE, c2=CYAN):
    def _make_h(parent, flip=False):
        ca   = tk.Canvas(parent, height=thickness,
                         highlightthickness=0, bg=BG2)
        _a, _b = (c2, c1) if flip else (c1, c2)

        def _draw(w=None):
            ww = w if (w and w > 1) else ca.winfo_width()
            if ww > 1:
                draw_gradient_h(ca, ww, thickness, _a, _b)

        ca.bind("<Configure>", lambda e: _draw(e.width))
        ca.after(1, _draw)
        return ca

    def _make_v(parent, flip=False):
        ca   = tk.Canvas(parent, width=thickness,
                         highlightthickness=0, bg=BG2)
        _a, _b = (c2, c1) if flip else (c1, c2)

        def _draw(h=None):
            hh = h if (h and h > 1) else ca.winfo_height()
            if hh > 1:
                draw_gradient_v(ca, thickness, hh, _a, _b)

        ca.bind("<Configure>", lambda e: _draw(e.height))
        ca.after(1, _draw)
        return ca

    top = _make_h(dialog, flip=False)
    top.place(x=0, y=0, relwidth=1)
    bot = _make_h(dialog, flip=True)
    bot.place(x=0, rely=1.0, anchor="sw", relwidth=1)
    lft = _make_v(dialog, flip=False)
    lft.place(x=0, y=0, relheight=1)
    rgt = _make_v(dialog, flip=True)
    rgt.place(relx=1.0, y=0, anchor="ne", relheight=1)

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
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.update_idletasks()
        add_gradient_border(self, thickness=3, c1=color, c2=PURPLE)

    def _build(self, color, dim, icon, title, message, detail):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3, y=3, relwidth=1, relheight=1, width=-6, height=-6)
        badge = tk.Frame(inner, bg=dim, highlightthickness=1,
                         highlightbackground=color, width=64, height=64)
        badge.pack(pady=(28, 0))
        badge.pack_propagate(False)
        tk.Label(badge, text=icon, bg=dim, fg=color,
                 font=(FD, 26, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        if title:
            tk.Label(inner, text=title, bg=BG2, fg=TEXT,
                     font=(FD, 15, "bold")).pack(pady=(14, 2))
        if message:
            tk.Label(inner, text=message, bg=BG2, fg=TEXT2,
                     font=(FB, 10), wraplength=400,
                     justify="center").pack(padx=36, pady=(0, 4))
        if detail:
            hsep(inner, BORDER2).pack(fill="x", padx=28, pady=(14, 0))
            df = tk.Frame(inner, bg=BG3, highlightthickness=1,
                          highlightbackground=BORDER2)
            df.pack(padx=28, pady=(10, 0), fill="x")
            tk.Entry(df, textvariable=tk.StringVar(value=detail),
                     state="readonly", bg=BG3, fg=color,
                     readonlybackground=BG3, font=(FM, 10), relief="flat",
                     justify="center").pack(padx=14, pady=10, fill="x")
        hsep(inner, BORDER2).pack(fill="x", padx=28, pady=(20, 0))
        btn = tk.Button(inner, text="  Close  ", command=self._close,
                        bg=color, fg=BG, font=(FD, 11, "bold"),
                        relief="flat", cursor="hand2",
                        activebackground=PURPLE2 if color == PURPLE else color,
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
#  ADMIN PIN DIALOG
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
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.update_idletasks()
        self.bind("<Return>", lambda _: self._check())
        self.bind("<Escape>", lambda _: self.destroy())
        add_gradient_border(self, thickness=3, c1=RED, c2=PURPLE)

    def _build(self):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3, y=3, relwidth=1, relheight=1, width=-6, height=-6)
        tk.Label(inner, text="🔐", bg=BG2, fg=RED, font=(FD, 32)).pack(pady=(28, 0))
        tk.Label(inner, text="Admin Access Required", bg=BG2, fg=TEXT,
                 font=(FD, 15, "bold")).pack(pady=(6, 2))
        tk.Label(inner, text="Enter PIN to exit kiosk mode",
                 bg=BG2, fg=TEXT2, font=(FB, 10)).pack(pady=(0, 18))
        hsep(inner).pack(fill="x", padx=28, pady=(0, 18))
        self.pin_var = tk.StringVar()
        pf = tk.Frame(inner, bg=BG4, highlightthickness=2,
                      highlightbackground=BORDER3)
        pf.pack(padx=36, fill="x")
        e = tk.Entry(pf, textvariable=self.pin_var, show="●",
                     bg=BG4, fg=TEXT, insertbackground=RED,
                     font=(FD, 24, "bold"), justify="center", relief="flat")
        e.pack(padx=12, pady=10, fill="x")
        e.focus_set()
        self.err = tk.Label(inner, text="", bg=BG2, fg=RED, font=(FB, 9))
        self.err.pack(pady=(10, 4))
        row = tk.Frame(inner, bg=BG2)
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
#  CASH VOUCHER WAITING DIALOG
# ════════════════════════════════════════════════════════════════════


class CashVoucherDialog(tk.Toplevel):
    def __init__(self, app, session_id, voucher_code, computer_name,
                 duration, cost, on_activated, on_cancel):
        super().__init__(app)
        self.app           = app
        self.session_id    = session_id
        self.voucher_code  = voucher_code
        self.computer_name = computer_name
        self.duration      = duration
        self.cost          = cost
        self.on_activated  = on_activated
        self.on_cancel     = on_cancel
        self._done         = False
        self._dots         = 0
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self._build()
        self.update_idletasks()
        w  = 520
        h  = max(self.winfo_reqheight() + 40, 620)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.update_idletasks()
        add_gradient_border(self, thickness=3, c1=PURPLE, c2=CYAN)
        self._animate()
        self._poll()

    def _build(self):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3, y=3, relwidth=1, relheight=1, width=-6, height=-6)
        tk.Label(inner, text="💵", bg=BG2, fg=GREEN, font=(FD, 44)).pack(pady=(28, 0))
        tk.Label(inner, text="Cash Payment", bg=BG2, fg=TEXT,
                 font=(FD, 17, "bold")).pack(pady=(6, 2))
        tk.Label(inner, text="Show voucher code at the counter",
                 bg=BG2, fg=TEXT2, font=(FB, 10)).pack(pady=(0, 16))
        hsep(inner).pack(fill="x", padx=24)
        s = tk.Frame(inner, bg=BG3, highlightthickness=1,
                     highlightbackground=BORDER2)
        s.pack(padx=28, pady=16, fill="x")
        tk.Label(s, text="SESSION SUMMARY", fg=TEXT3, bg=BG3,
                 font=(FB, 8, "bold")).pack(anchor="w", padx=16, pady=(12, 6))
        for lbl, val, col in [
            ("Computer",   self.computer_name,      TEXT2),
            ("Duration",   f"{self.duration} min",  TEXT),
            ("Amount Due", fmt_currency(self.cost), GREEN),
        ]:
            r = tk.Frame(s, bg=BG3)
            r.pack(fill="x", padx=16, pady=3)
            tk.Label(r, text=lbl, fg=TEXT3, bg=BG3,
                     font=(FB, 10)).pack(side="left")
            sz = 14 if lbl == "Amount Due" else 11
            wt = "bold" if lbl == "Amount Due" else "normal"
            tk.Label(r, text=val, fg=col, bg=BG3,
                     font=(FD, sz, wt)).pack(side="right")
        tk.Frame(s, bg=BG3, height=6).pack()
        hsep(inner).pack(fill="x", padx=24)
        vc = tk.Frame(inner, bg=BG3, highlightthickness=2,
                      highlightbackground=PURPLE)
        vc.pack(padx=28, pady=18, fill="x")
        tk.Label(vc, text="VOUCHER CODE", fg=TEXT3, bg=BG3,
                 font=(FB, 8, "bold")).pack(pady=(14, 6))
        tk.Label(vc, text=self.voucher_code, fg=PURPLE, bg=BG3,
                 font=(FM, 26, "bold")).pack(pady=(0, 6))

        def _copy():
            self.app.clipboard_clear()
            self.app.clipboard_append(self.voucher_code)
            cb.config(text="✓  Copied!", bg=PURPLE_DIM, fg=PURPLE)
            self.after(2200,
                       lambda: cb.config(text="📋  Copy Code", bg=BG5, fg=CYAN))

        cb = tk.Button(vc, text="📋  Copy Code", command=_copy,
                       bg=BG5, fg=CYAN, font=(FB, 9, "bold"),
                       relief="flat", cursor="hand2", padx=14, pady=6)
        cb.pack(pady=(0, 14))
        hsep(inner).pack(fill="x", padx=24)
        sf = tk.Frame(inner, bg=BG2)
        sf.pack(pady=(14, 0))
        self.status_lbl = tk.Label(sf,
                                   text="⏳  Waiting for staff to activate…",
                                   bg=BG2, fg=YELLOW, font=(FB, 11, "bold"))
        self.status_lbl.pack()
        self.dot_lbl = tk.Label(sf, text="●○○", bg=BG2, fg=TEXT3,
                                font=(FB, 10))
        self.dot_lbl.pack(pady=(4, 0))
        tk.Label(inner,
                 text="Pay the cashier and give them your voucher code.\n"
                      "Your PC will start automatically once confirmed.",
                 bg=BG2, fg=TEXT2, font=(FB, 9),
                 justify="center").pack(pady=(8, 0))
        hsep(inner).pack(fill="x", padx=24, pady=16)
        bf = tk.Frame(inner, bg=BG2)
        bf.pack(padx=28, pady=(0, 28), fill="x")
        ghost_button(bf, "✕  Cancel", self._cancel, RED, 14).pack(
            side="left", expand=True, fill="x", padx=(0, 10))
        tk.Label(bf, text="Activates\nautomatically", bg=BG2, fg=TEXT3,
                 font=(FB, 8), justify="center").pack(side="left", expand=True)

    def _animate(self):
        if self._done:
            return
        self._dots = (self._dots + 1) % 4
        d = "●" * self._dots + "○" * (3 - self._dots)
        try:
            self.dot_lbl.config(text=f"Checking  {d}")
        except Exception:
            return
        self.after(600, self._animate)

    def _poll(self):
        if self._done:
            return
        rows = db_exec(
            "SELECT status FROM sessions WHERE id=%s",
            (self.session_id,), fetch=True)
        if rows and rows[0]["status"] == "active":
            self._on_activated()
            return
        self.after(1000, self._poll)

    def _on_activated(self):
        if self._done:
            return
        self._done = True
        try:
            self.status_lbl.config(
                text="✅  Activated! Starting session…", fg=GREEN)
            self.dot_lbl.config(text="")
        except Exception:
            pass
        self.after(1400, lambda: self._finish(True))

    def _cancel(self):
        if self._done:
            return
        self._done = True
        db_exec(
            "UPDATE sessions SET status='cancelled', cancelled_at=%s WHERE id=%s",
            (now_ms(), self.session_id))
        self._finish(False)

    def _finish(self, activated):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        if activated and self.on_activated:
            self.on_activated()
        elif not activated and self.on_cancel:
            self.on_cancel()

# ════════════════════════════════════════════════════════════════════
#  PAYMENT WAITING SCREEN  (GCash / Maya)
#
#  FIX: The main app window is hidden (withdraw) so the browser gets
#  full screen. A slim top-bar Toplevel floats above the browser with
#  the payment status, amount, and a Cancel button — identical to how
#  RecaptchaWaitingScreen works. When no browser is found, a fullscreen
#  overlay is shown instead (with the payment URL to copy/scan).
# ════════════════════════════════════════════════════════════════════


class PaymentWaitingScreen:
    BAR_H = 72

    def __init__(self, app, link_id, checkout_url, method, amount,
                 on_paid, on_cancel=None):
        self.app          = app
        self.link_id      = link_id
        self.checkout_url = checkout_url
        self.method       = method.upper()
        self.amount       = amount
        self.on_paid      = on_paid
        self.on_cancel    = on_cancel
        self._done        = False
        self._dots        = 0
        self._browser     = None
        self._top_bar     = None
        self._overlay     = None
        self._tmp_dir     = None
        self._browser_path = find_browser()

        self._start_watcher()

        if self._browser_path:
            # Hide main app, launch browser fullscreen, float the top bar
            self.app.withdraw()
            self._launch_browser()
            self._build_top_bar()
        else:
            # No browser — show a fullscreen overlay with the payment URL
            self._build_overlay()

    # ── browser ───────────────────────────────────────────────────────

    def _launch_browser(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="timenet_pay_")
        cmd = [
            self._browser_path, "--kiosk", self.checkout_url,
            f"--user-data-dir={self._tmp_dir}",
            "--disable-extensions", "--no-first-run", "--disable-default-apps",
        ]
        try:
            self._browser = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Browser] {e}")
            self._browser = None
            # Restore app and show fallback overlay
            self.app.after(0, self._fallback_no_browser)

    def _fallback_no_browser(self):
        self.app.deiconify()
        self._destroy_top_bar()
        self._build_overlay()

    def _kill_browser(self):
        if self._browser:
            try:
                self._browser.terminate()
                self._browser.wait(timeout=3)
            except Exception:
                try:
                    self._browser.kill()
                except Exception:
                    pass
            self._browser = None
        if self._tmp_dir:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None

    # ── top bar (shown above the kiosk browser) ───────────────────────

    def _build_top_bar(self):
        sw     = self.app.winfo_screenwidth()
        colors = {"GCASH": ("#00B4D8", "📱"), "MAYA": (PURPLE, "💜")}
        color, icon = colors.get(self.method, (CYAN, "💳"))

        bar = tk.Toplevel(self.app)
        bar.configure(bg=BG2)
        bar.overrideredirect(True)
        bar.attributes("-topmost", True)
        bar.geometry(f"{sw}x{self.BAR_H}+0+0")
        bar.protocol("WM_DELETE_WINDOW", lambda: None)
        self._top_bar = bar

        gc = make_gradient_canvas_h(bar, height=3, c1=PURPLE, c2=CYAN)
        gc.pack(fill="x")

        inner = tk.Frame(bar, bg=BG2)
        inner.pack(fill="both", expand=True, padx=20)

        # Left — icon + method name + amount
        left = tk.Frame(inner, bg=BG2)
        left.pack(side="left", fill="y")
        tk.Label(left, text=icon, bg=BG2, fg=color,
                 font=(FD, 18)).pack(side="left", padx=(0, 10), pady=14)
        ic = tk.Frame(left, bg=BG2)
        ic.pack(side="left")
        tk.Label(ic, text=f"{self.method} Payment", bg=BG2, fg=color,
                 font=(FD, 13, "bold")).pack(anchor="w")
        tk.Label(ic, text=fmt_currency(self.amount), bg=BG2, fg=TEXT,
                 font=(FD, 11)).pack(anchor="w")

        # Centre — status + dots
        self._status_lbl = tk.Label(inner, text="⏳  Waiting for payment…",
                                    bg=BG2, fg=YELLOW, font=(FB, 11, "bold"))
        self._status_lbl.pack(side="left", padx=40)
        self._dot_lbl = tk.Label(inner, text="●○○", bg=BG2, fg=TEXT3,
                                 font=(FB, 10))
        self._dot_lbl.pack(side="left")

        # Right — cancel button
        tk.Button(inner, text="✕  Cancel Payment", command=self._cancel,
                  bg=RED_DIM, fg=RED, font=(FB, 11, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8,
                  activebackground=RED, activeforeground=TEXT,
                  highlightthickness=1,
                  highlightbackground=RED).pack(side="right", pady=12)

        bot = make_gradient_canvas_h(bar, height=2, c1=CYAN, c2=PURPLE)
        bot.pack(fill="x", side="bottom")

        self._animate()

    # ── no-browser fallback overlay ───────────────────────────────────

    def _build_overlay(self):
        sw, sh = self.app.winfo_screenwidth(), self.app.winfo_screenheight()
        colors = {"GCASH": ("#00B4D8", "📱"), "MAYA": (PURPLE, "💜")}
        color, icon = colors.get(self.method, (CYAN, "💳"))

        ov = tk.Toplevel(self.app)
        ov.configure(bg=BG)
        ov.overrideredirect(True)
        ov.geometry(f"{sw}x{sh}+0+0")
        ov.attributes("-topmost", True)
        ov.protocol("WM_DELETE_WINDOW", lambda: None)
        self._overlay = ov

        # Header bar
        bar = tk.Frame(ov, bg=BG2, height=70)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=color, width=4).pack(side="left", fill="y")
        lf = tk.Frame(bar, bg=BG2)
        lf.pack(side="left", padx=20, fill="y")
        tk.Label(lf, text=f"{icon}  {self.method} Payment",
                 bg=BG2, fg=color, font=(FD, 14, "bold")).pack(
                     side="left", pady=20)
        tk.Label(lf, text=f"   {fmt_currency(self.amount)}",
                 bg=BG2, fg=GREEN, font=(FD, 13, "bold")).pack(side="left")
        rf = tk.Frame(bar, bg=BG2)
        rf.pack(side="right", padx=20)
        self._status_lbl = tk.Label(rf, text="⏳  Waiting…",
                                    bg=BG2, fg=YELLOW, font=(FB, 11, "bold"))
        self._status_lbl.pack(side="left", padx=(0, 16))
        tk.Button(rf, text="✕  Cancel", command=self._cancel,
                  bg=RED_DIM, fg=RED, font=(FB, 11, "bold"),
                  relief="flat", cursor="hand2", padx=16, pady=8,
                  highlightthickness=1, highlightbackground=RED,
                  activebackground=RED, activeforeground=TEXT).pack(side="left")

        gc = make_gradient_canvas_h(ov, height=2, c1=PURPLE, c2=CYAN)
        gc.pack(fill="x")

        body   = tk.Frame(ov, bg=BG)
        body.pack(fill="both", expand=True)
        centre = tk.Frame(body, bg=BG)
        centre.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(centre, text=icon, bg=BG, fg=color,
                 font=(FD, 72)).pack(pady=(0, 12))
        tk.Label(centre,
                 text=f"Pay {fmt_currency(self.amount)} via {self.method}",
                 bg=BG, fg=TEXT, font=(FD, 20, "bold")).pack(pady=(0, 6))
        tk.Label(centre,
                 text="No browser found — scan or open the link below.",
                 bg=BG, fg=YELLOW, font=(FB, 11)).pack(pady=(0, 18))

        uf = tk.Frame(centre, bg=BG3, padx=20, pady=14,
                      highlightthickness=1, highlightbackground=BORDER2)
        uf.pack(fill="x", padx=40)
        tk.Label(uf, text="PAYMENT LINK", bg=BG3, fg=TEXT3,
                 font=(FB, 8, "bold")).pack(anchor="w")
        tk.Entry(uf, textvariable=tk.StringVar(value=self.checkout_url),
                 state="readonly", bg=BG3, fg=CYAN,
                 font=(FM, 9), relief="flat", readonlybackground=BG3,
                 width=70).pack(fill="x", pady=(4, 0))

        self._dot_lbl = tk.Label(centre,
                                 text="Checking payment status  ●○○",
                                 bg=BG, fg=TEXT3, font=(FB, 10))
        self._dot_lbl.pack(pady=(10, 0))
        self._animate()

    # ── animation ─────────────────────────────────────────────────────

    def _animate(self):
        if self._done:
            return
        self._dots = (self._dots + 1) % 4
        d = "●" * self._dots + "○" * (3 - self._dots)
        try:
            self._dot_lbl.config(text=f"Checking payment  {d}")
        except Exception:
            return
        self.app.after(600, self._animate)

    # ── watcher thread ────────────────────────────────────────────────

    def _start_watcher(self):
        def _w():
            while not self._done:
                time.sleep(0.05)
                # Payment confirmed by poller
                if self.link_id not in paymongo.pending:
                    if not self._done:
                        self.app.after(0, self._on_confirmed)
                    return
                # Browser closed by user without paying (treat as cancel)
                proc = self._browser
                if proc and proc.poll() is not None:
                    if not self._done and self.link_id in paymongo.pending:
                        self.app.after(0, self._cancel)
                    return
        threading.Thread(target=_w, daemon=True).start()

    # ── outcome handlers ──────────────────────────────────────────────

    def _on_confirmed(self):
        if self._done:
            return
        self._done = True
        threading.Thread(target=self._kill_browser, daemon=True).start()
        try:
            self._status_lbl.config(text="✅  Payment Confirmed!", fg=GREEN)
            self._dot_lbl.config(text="Starting your session…", fg=GREEN)
        except Exception:
            pass
        self.app.after(2000, self._finish_paid)

    def _finish_paid(self):
        self._destroy_all()
        # Restore main app before handing off
        self.app.deiconify()
        if self.on_paid:
            self.on_paid()

    def _cancel(self):
        if self._done:
            return
        self._done = True
        paymongo.pending.pop(self.link_id, None)
        threading.Thread(target=self._kill_browser, daemon=True).start()
        self._destroy_all()
        # Restore main app before handing off
        self.app.deiconify()
        if self.on_cancel:
            self.on_cancel()

    def _destroy_top_bar(self):
        if self._top_bar:
            try:
                self._top_bar.destroy()
            except Exception:
                pass
            self._top_bar = None

    def _destroy_all(self):
        self._destroy_top_bar()
        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None

# ════════════════════════════════════════════════════════════════════
#  PAYMONGO API
# ════════════════════════════════════════════════════════════════════


class PayMongoAPI:
    def __init__(self):
        self.pending: dict = {}
        self._running      = False
        self.on_success    = None

    def create_link(self, amount, desc, info):
        cents   = int(round(amount * 100))
        payload = {"data": {"attributes": {
            "amount":      cents,
            "currency":    "PHP",
            "description": desc,
            "remarks":     f"TimeNet | {info.get('method', 'online').upper()}",
        }}}
        try:
            r = requests.post(f"{PAYMONGO_BASE_URL}/links",
                              headers=paymongo_headers(), json=payload,
                              timeout=20)
            d = r.json()
            if r.status_code not in (200, 201):
                errs = d.get("errors", [])
                msg  = (errs[0].get("detail", "Error")
                        if errs else f"HTTP {r.status_code}")
                return {"success": False, "error": msg}
            ld  = d["data"]
            lid = ld["id"]
            url = ld["attributes"]["checkout_url"]
            self.pending[lid] = {**info, "amount": amount, "link_id": lid,
                                 "checkout_url": url, "status": "pending"}
            return {"success": True, "link_id": lid, "checkout_url": url}
        except requests.ConnectionError:
            return {"success": False, "error": "No internet connection."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def poll_link(self, lid):
        try:
            r = requests.get(f"{PAYMONGO_BASE_URL}/links/{lid}",
                             headers=paymongo_headers(), timeout=10)
            if r.status_code != 200:
                return "error"
            status = r.json()["data"]["attributes"].get("status")
            return "paid" if status == "paid" else "pending"
        except Exception:
            return "error"

    def activate(self, info):
        sid = info["session_id"]
        cid = info["computer_id"]
        db_exec(
            "UPDATE sessions SET status='active', start_time=%s WHERE id=%s",
            (now_ms(), sid))
        db_exec(
            "UPDATE computers SET status='occupied', "
            "current_session_id=%s WHERE id=%s",
            (sid, cid))
        existing = db_exec(
            "SELECT id FROM sessions WHERE id=%s", (sid,), fetch=True)
        if not existing:
            db_exec("""
                INSERT IGNORE INTO sessions
                  (id, user_id, computer_id, duration, cost,
                   status, start_time, created_at)
                VALUES (%s,%s,%s,%s,%s,'active',%s,%s)
            """, (sid, info.get("user_id", ""), cid,
                  info.get("duration", 0), info.get("amount", 0),
                  now_ms(), now_ms()))
        db_exec("""
            INSERT IGNORE INTO payments
              (id, session_id, user_id, amount, method,
               timestamp, receipt_no, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'completed')
        """, (f"pay-{now_ms()}", sid, info.get("user_id", ""),
              info.get("amount", 0), info.get("method", "online"),
              now_ms(), gen_receipt()))
        if self.on_success:
            self.on_success(info)

    def start_polling(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            time.sleep(3)
            for lid in list(self.pending):
                info = self.pending.get(lid)
                if not info or info["status"] != "pending":
                    continue
                if self.poll_link(lid) == "paid":
                    info["status"] = "paid"
                    self.activate(info)
                    self.pending.pop(lid, None)


paymongo = PayMongoAPI()
paymongo.start_polling()

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

    @classmethod
    def is_admin(cls):
        return cls.user and cls.user.get("role") == "admin"

# ════════════════════════════════════════════════════════════════════
#  MAIN APP WINDOW  (kiosk)
# ════════════════════════════════════════════════════════════════════


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TimeNet Cafe — Customer")
        self.configure(bg=BG)
        self._locked              = True
        self._hook_running        = False
        self._taskbar_enforce_on  = False
        self._registered_hk_ids   = []
        self._tray_active         = False
        self._apply_lock()
        self._setup_ttk()
        self.container     = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.current_frame = None
        self.show_login()
        self.bind_all("<Control-Shift-A>", lambda _: self._admin_exit())
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        paymongo.on_success = self._on_payment_success

    def _on_payment_success(self, info):
        self.after(300, self._handle_pay_success, info)

    def _handle_pay_success(self, info):
        if isinstance(self.current_frame, CustomerDashboard):
            self.current_frame._force_load_session()

    @staticmethod
    def _set_taskbar(visible):
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            for cls_name in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
                hw = user32.FindWindowW(cls_name, None)
                if hw:
                    user32.ShowWindow(hw, 5 if visible else 0)
        except Exception:
            pass

    def _apply_lock(self):
        self._locked = True
        self._set_taskbar(False)
        self._start_hotkeys()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.overrideredirect(False)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.update_idletasks()
        self.overrideredirect(True)
        self.update_idletasks()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))

    def unlock_for_session(self):
        self._locked             = False
        self._taskbar_enforce_on = False
        self.overrideredirect(False)
        self.update_idletasks()
        self.resizable(True, True)
        w, h = 300, 170
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{sw - w - 12}+{sh - h - 48}")
        self.update_idletasks()
        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self._set_taskbar(True)
        if not self._tray_active:
            self._tray_active = True
            start_tray(self._restore_from_tray)

    def _restore_from_tray(self):
        self.after(0, self._do_restore)

    def _do_restore(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", True))
        except Exception:
            pass

    def relock(self):
        self._taskbar_enforce_on = False
        self.attributes("-topmost", False)
        self.overrideredirect(False)
        self.resizable(True, True)
        self.update_idletasks()
        if self._tray_active:
            self._tray_active = False
            stop_tray()
        self._apply_lock()

    def _start_hotkeys(self):
        if platform.system() != "Windows" or self._hook_running:
            return
        self._hook_running       = True
        self._hook_stop          = threading.Event()
        self._hook_tid           = None
        self._hook_thread        = threading.Thread(
            target=self._hook_loop, daemon=True)
        self._hook_thread.start()
        self.after(200, self._register_hotkeys)
        self._taskbar_enforce_on = True
        self._taskbar_enforce()

    def _stop_hotkeys(self):
        if platform.system() != "Windows":
            return
        self._hook_running       = False
        self._taskbar_enforce_on = False
        self._unregister_hotkeys()
        if hasattr(self, "_hook_stop"):
            self._hook_stop.set()

    def _register_hotkeys(self):
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            user32  = ctypes.windll.user32
            hwnd    = self.winfo_id()
            MOD_WIN = 0x0008
            vks = [
                0x09, 0x44, 0x45, 0x49, 0x4C, 0x52, 0x53, 0x58,
                0x41, 0x4B, 0x50, 0x1B, 0x70, 0x20, 0x21, 0x22,
                0x25, 0x26, 0x27, 0x28,
            ]
            for i, vk in enumerate(vks):
                hid = 0xBE01 + i
                if user32.RegisterHotKey(hwnd, hid, MOD_WIN, vk):
                    self._registered_hk_ids.append(hid)
        except Exception:
            pass

    def _unregister_hotkeys(self):
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd   = self.winfo_id()
            for hid in self._registered_hk_ids:
                user32.UnregisterHotKey(hwnd, hid)
            self._registered_hk_ids.clear()
        except Exception:
            pass

    def _taskbar_enforce(self):
        if not self._taskbar_enforce_on:
            return
        self._set_taskbar(False)
        self.after(500, self._taskbar_enforce)

    def _hook_loop(self):
        import ctypes, ctypes.wintypes
        WH_KEYBOARD_LL = 13
        WM_KEYDOWN     = 0x0100
        WM_SYSKEYDOWN  = 0x0104
        HC_ACTION      = 0
        PM_REMOVE      = 0x0001
        VK_LWIN        = 0x5B
        VK_RWIN        = 0x5C
        MOD_ALT        = 0x20
        VK_F4          = 0x73
        VK_ESC         = 0x1B
        VK_TAB         = 0x09
        VK_SPACE       = 0x20
        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode",      ctypes.wintypes.DWORD),
                ("scanCode",    ctypes.wintypes.DWORD),
                ("flags",       ctypes.wintypes.DWORD),
                ("time",        ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int,
            ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)
        win_dn   = [False]
        hook_ref = [None]

        def _handler(nCode, wParam, lParam):
            if nCode != HC_ACTION:
                return user32.CallNextHookEx(
                    hook_ref[0], nCode, wParam, lParam)
            kb    = ctypes.cast(
                lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk    = kb.vkCode
            alt   = bool(kb.flags & MOD_ALT)
            is_dn = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            if vk in (VK_LWIN, VK_RWIN):
                win_dn[0] = is_dn
                return 1
            if win_dn[0]:
                return 1
            if alt and vk in (VK_TAB, VK_ESC, VK_F4, VK_SPACE):
                return 1
            return user32.CallNextHookEx(hook_ref[0], nCode, wParam, lParam)

        cb   = HOOKPROC(_handler)
        hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, cb, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self._hook_running = False
            return
        hook_ref[0]    = hook
        self._hook_tid = kernel32.GetCurrentThreadId()
        msg = ctypes.wintypes.MSG()
        while not self._hook_stop.is_set():
            while user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.005)
        user32.UnhookWindowsHookEx(hook)
        self._hook_running = False

    def _admin_exit(self):
        def _do():
            self._stop_hotkeys()
            self._set_taskbar(True)
            stop_tray()
            self.destroy()
        AdminPinDialog(self, on_success=_do)

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
              foreground=[("selected", PURPLE)])
        s.configure("TScrollbar",
                    background=BG4, troughcolor=BG2,
                    bordercolor=BG, arrowcolor=TEXT3, relief="flat")
        s.configure("Session.Horizontal.TProgressbar",
                    troughcolor=BG3, background=PURPLE,
                    thickness=8, bordercolor=BG3)

    def switch_frame(self, cls, *a, **kw):
        if self.current_frame:
            self.current_frame.destroy()
        f = cls(self.container, self, *a, **kw)
        f.pack(fill="both", expand=True)
        self.current_frame = f

    def show_login(self):
        self.switch_frame(LoginPage)

    def show_register(self):
        self.switch_frame(RegisterPage)

    def show_customer_dashboard(self):
        self.switch_frame(CustomerDashboard)

    def logout(self):
        Auth.logout()
        if not self._locked:
            self.relock()
        else:
            self._set_taskbar(False)
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

        gc = make_gradient_canvas_h(card, height=4, c1=PURPLE, c2=CYAN)
        gc.pack(fill="x")

        tk.Label(card, text="🖥", bg=BG2, fg=PURPLE,
                 font=(FD, 36)).pack(pady=(30, 0))
        tk.Label(card, text="TimeNet Cafe", bg=BG2, fg=TEXT,
                 font=(FD, 22, "bold")).pack(pady=(6, 2))
        tk.Label(card, text="Sign in to your account", bg=BG2, fg=TEXT2,
                 font=(FB, 11)).pack(pady=(0, 20))
        hsep(card).pack(fill="x", padx=36, pady=(0, 20))

        form = tk.Frame(card, bg=BG2)
        form.pack(padx=48, fill="x")
        self.err = tk.Label(form, text="", fg=RED, bg=BG2,
                            wraplength=340, font=(FB, 10), justify="left")
        self.err.pack(fill="x", pady=(0, 8))
        self.usr = tk.StringVar()
        self.pwd = tk.StringVar()

        tk.Label(form, text="USERNAME", fg=TEXT3, bg=BG2,
                 font=(FB, 8, "bold")).pack(anchor="w", pady=(0, 3))
        uf = tk.Frame(form, bg=BG4, highlightthickness=1,
                      highlightbackground=BORDER2)
        uf.pack(fill="x", pady=(0, 16))
        eu = tk.Entry(uf, textvariable=self.usr, bg=BG4, fg=TEXT,
                      insertbackground=PURPLE, font=(FB, 12), relief="flat")
        eu.pack(padx=14, pady=10, fill="x")
        eu.bind("<FocusIn>",  lambda _: uf.config(highlightbackground=PURPLE))
        eu.bind("<FocusOut>", lambda _: uf.config(highlightbackground=BORDER2))

        tk.Label(form, text="PASSWORD", fg=TEXT3, bg=BG2,
                 font=(FB, 8, "bold")).pack(anchor="w", pady=(0, 3))
        pf = tk.Frame(form, bg=BG4, highlightthickness=1,
                      highlightbackground=BORDER2)
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
                  activebackground=PURPLE2, activeforeground=TEXT,
                  padx=20, pady=14).pack(fill="x", pady=(0, 6))

        hsep(card).pack(fill="x", padx=36, pady=20)
        footer = tk.Frame(card, bg=BG2)
        footer.pack(pady=(0, 28))
        tk.Label(footer, text="New here? ", fg=TEXT2, bg=BG2,
                 font=(FB, 10)).pack(side="left")
        rl = tk.Label(footer, text="Create an account", fg=CYAN, bg=BG2,
                      cursor="hand2", font=(FB, 10, "bold"))
        rl.pack(side="left")
        rl.bind("<Button-1>", lambda _: self.app.show_register())

    def _login(self):
        u = self.usr.get().strip()
        p = self.pwd.get().strip()
        if not u or not p:
            self.err.config(text="⚠  Please fill in all fields.")
            return
        rows = db_exec(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (u, p), fetch=True)
        if rows:
            user = dict(rows[0])
            if user.get("role") == "admin":
                self.err.config(
                    text="✗  Use the Admin portal for admin accounts.")
                return
            Auth.login(user)
            self.app.show_customer_dashboard()
        else:
            self.err.config(text="✗  Invalid username or password.")

# ════════════════════════════════════════════════════════════════════
#  RECAPTCHA HTML PAGE
# ════════════════════════════════════════════════════════════════════

_RECAPTCHA_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Human Verification — TimeNet Cafe</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{
    background:#070b12;
    display:flex;align-items:center;justify-content:center;
    min-height:100vh;
    font-family:'Segoe UI',sans-serif;
    color:#e2ecff;
  }}
  body::before{{
    content:'';
    position:fixed;inset:0;
    background-image:radial-gradient(#253a55 1px,transparent 1px);
    background-size:36px 36px;
    pointer-events:none;
    z-index:0;
  }}
  .card{{
    position:relative;z-index:1;
    background:#0c1320;
    border:1px solid #243a5e;
    border-radius:14px;
    padding:0;
    width:420px;
    overflow:hidden;
    box-shadow:0 0 60px rgba(168,85,247,.18),0 0 120px rgba(0,200,232,.08);
  }}
  .grad-bar{{height:4px;background:linear-gradient(90deg,#a855f7,#00c8e8);}}
  .body{{padding:36px 40px 32px}}
  .icon{{font-size:42px;text-align:center;margin-bottom:10px}}
  h2{{font-size:18px;font-weight:700;text-align:center;color:#e2ecff;margin-bottom:4px;}}
  .sub{{font-size:11px;color:#7a9cc4;text-align:center;margin-bottom:24px;}}
  .divider{{height:1px;background:#243a5e;margin:0 -40px 22px}}
  .rc-wrap{{
    display:flex;justify-content:center;
    background:#111b2e;
    border:1px solid #2e4a72;
    border-radius:8px;
    padding:18px 16px;
    margin-bottom:18px;
  }}
  .status{{
    display:flex;align-items:center;gap:10px;
    font-size:12px;color:#fbbf24;
    min-height:22px;margin-bottom:18px;
    justify-content:center;
  }}
  .status.ok {{color:#00e56e}}
  .status.err{{color:#ff3b5c}}
  .dot-row{{text-align:center;font-size:11px;color:#3d5a80;letter-spacing:4px;margin-bottom:4px;}}
  .help{{font-size:10px;color:#3d5a80;text-align:center;line-height:1.6;margin-bottom:18px;}}
  .grad-bar-bot{{height:2px;background:linear-gradient(90deg,#00c8e8,#a855f7);}}
</style>
<script src="https://www.google.com/recaptcha/api.js" async defer></script>
</head>
<body>
<div class="card">
  <div class="grad-bar"></div>
  <div class="body">
    <div class="icon">🤖</div>
    <h2>Human Verification</h2>
    <p class="sub">Complete the reCAPTCHA to create your account</p>
    <div class="divider"></div>
    <div class="rc-wrap">
      <div class="g-recaptcha"
           data-sitekey="{site_key}"
           data-callback="onSolved"
           data-expired-callback="onExpired"
           data-theme="dark"></div>
    </div>
    <div class="status" id="status">⏳&nbsp; Waiting for verification…</div>
    <div class="dot-row" id="dots">●○○</div>
    <p class="help">Tick the checkbox above.<br>This window closes automatically once verified.</p>
  </div>
  <div class="grad-bar-bot"></div>
</div>
<script>
  var _d=0,_dot=['●○○','●●○','●●●','○●●'],_running=true;
  function animDots(){{if(!_running)return;_d=(_d+1)%4;document.getElementById('dots').textContent=_dot[_d];setTimeout(animDots,600);}}
  animDots();
  function onSolved(token){{
    _running=false;
    var st=document.getElementById('status');
    st.textContent='✅  Verified! Closing window…';
    st.className='status ok';
    document.getElementById('dots').textContent='';
    fetch('http://127.0.0.1:{port}/token',{{method:'POST',headers:{{'Content-Type':'text/plain'}},body:token}}).catch(function(){{}});
  }}
  function onExpired(){{
    _running=true;animDots();
    var st=document.getElementById('status');
    st.textContent='⚠  Expired — please tick again.';
    st.className='status err';
  }}
</script>
</body>
</html>
"""


def verify_recaptcha(token):
    if RECAPTCHA_SECRET_KEY == "YOUR_SECRET_KEY_HERE":
        return True
    try:
        r = requests.post(
            RECAPTCHA_VERIFY_URL,
            data={"secret": RECAPTCHA_SECRET_KEY, "response": token},
            timeout=10,
        )
        return r.json().get("success", False)
    except Exception:
        return False

# ════════════════════════════════════════════════════════════════════
#  RECAPTCHA WAITING SCREEN
# ════════════════════════════════════════════════════════════════════


class RecaptchaWaitingScreen:
    BAR_H = 72

    def __init__(self, app, on_success, on_cancel=None):
        self.app        = app
        self.on_success = on_success
        self.on_cancel  = on_cancel
        self._done      = False
        self._dots      = 0
        self._browser   = None
        self._top_bar   = None
        self._overlay   = None
        self._tmp_dir   = None
        self._port      = None
        self._server    = None
        self._token     = None
        self._browser_path = find_browser()
        self._start_server()
        self._page_url = f"http://127.0.0.1:{self._port}/"
        if self._browser_path:
            self._launch_browser()
            self._build_top_bar()
        else:
            self._build_overlay()
        self._animate()

    def _start_server(self):
        import http.server
        import socketserver
        screen = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/recaptcha"):
                    html = _RECAPTCHA_HTML.format(
                        site_key=RECAPTCHA_SITE_KEY,
                        port=screen._port,
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path == "/token":
                    length = int(self.headers.get("Content-Length", 0))
                    token  = self.rfile.read(length).decode().strip()
                    self.send_response(200)
                    self.end_headers()
                    if token and not screen._done:
                        screen._token = token
                        screen.app.after(0, screen._on_token_received)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
        self._port   = srv.server_address[1]
        self._server = srv
        threading.Thread(target=srv.serve_forever, daemon=True).start()

    def _launch_browser(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="timenet_rc_")
        cmd = [
            self._browser_path, "--kiosk", self._page_url,
            f"--user-data-dir={self._tmp_dir}",
            "--disable-extensions", "--no-first-run", "--disable-default-apps",
        ]
        try:
            self._browser = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            threading.Thread(target=self._watch_browser, daemon=True).start()
        except Exception as e:
            print(f"[ReCAPTCHA Browser] {e}")
            self._browser = None
            self.app.after(0, self._build_overlay)

    def _watch_browser(self):
        if not self._browser:
            return
        self._browser.wait()
        if not self._done:
            self.app.after(0, self._cancel)

    def _kill_browser(self):
        if self._browser:
            try:
                self._browser.terminate()
                self._browser.wait(timeout=3)
            except Exception:
                try:
                    self._browser.kill()
                except Exception:
                    pass
            self._browser = None

    def _cleanup(self):
        threading.Thread(target=self._kill_browser, daemon=True).start()
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
        if self._tmp_dir:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None

    def _build_top_bar(self):
        sw  = self.app.winfo_screenwidth()
        bar = tk.Toplevel(self.app)
        bar.configure(bg=BG2)
        bar.overrideredirect(True)
        bar.attributes("-topmost", True)
        bar.geometry(f"{sw}x{self.BAR_H}+0+0")
        bar.protocol("WM_DELETE_WINDOW", lambda: None)
        self._top_bar = bar
        gc = make_gradient_canvas_h(bar, height=3, c1=PURPLE, c2=CYAN)
        gc.pack(fill="x")
        inner = tk.Frame(bar, bg=BG2)
        inner.pack(fill="both", expand=True, padx=20)
        left = tk.Frame(inner, bg=BG2)
        left.pack(side="left", fill="y")
        tk.Label(left, text="🤖", bg=BG2, fg=CYAN,
                 font=(FD, 18)).pack(side="left", padx=(0, 10), pady=14)
        ic = tk.Frame(left, bg=BG2)
        ic.pack(side="left")
        tk.Label(ic, text="Human Verification", bg=BG2, fg=CYAN,
                 font=(FD, 13, "bold")).pack(anchor="w")
        tk.Label(ic, text="Complete the reCAPTCHA in the browser window",
                 bg=BG2, fg=TEXT2, font=(FD, 10)).pack(anchor="w")
        self._status_lbl = tk.Label(
            inner, text="⏳  Waiting for reCAPTCHA…",
            bg=BG2, fg=YELLOW, font=(FB, 11, "bold"))
        self._status_lbl.pack(side="left", padx=40)
        self._dot_lbl = tk.Label(inner, text="●○○", bg=BG2, fg=TEXT3,
                                 font=(FB, 10))
        self._dot_lbl.pack(side="left")
        tk.Button(
            inner, text="✕  Cancel Verification", command=self._cancel,
            bg=RED_DIM, fg=RED, font=(FB, 11, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=8,
            activebackground=RED, activeforeground=TEXT,
            highlightthickness=1, highlightbackground=RED,
        ).pack(side="right", pady=12)
        bot = make_gradient_canvas_h(bar, height=2, c1=CYAN, c2=PURPLE)
        bot.pack(fill="x", side="bottom")

    def _build_overlay(self):
        sw, sh = self.app.winfo_screenwidth(), self.app.winfo_screenheight()
        ov = tk.Toplevel(self.app)
        ov.configure(bg=BG)
        ov.overrideredirect(True)
        ov.geometry(f"{sw}x{sh}+0+0")
        ov.attributes("-topmost", True)
        ov.protocol("WM_DELETE_WINDOW", lambda: None)
        self._overlay = ov
        bar = tk.Frame(ov, bg=BG2, height=70)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=CYAN, width=4).pack(side="left", fill="y")
        lf = tk.Frame(bar, bg=BG2)
        lf.pack(side="left", padx=20, fill="y")
        tk.Label(lf, text="🤖  Human Verification",
                 bg=BG2, fg=CYAN, font=(FD, 14, "bold")).pack(side="left", pady=20)
        rf = tk.Frame(bar, bg=BG2)
        rf.pack(side="right", padx=20)
        self._status_lbl = tk.Label(
            rf, text="⏳  Waiting…", bg=BG2, fg=YELLOW, font=(FB, 11, "bold"))
        self._status_lbl.pack(side="left", padx=(0, 16))
        tk.Button(
            rf, text="✕  Cancel", command=self._cancel,
            bg=RED_DIM, fg=RED, font=(FB, 11, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=8,
            highlightthickness=1, highlightbackground=RED,
            activebackground=RED, activeforeground=TEXT,
        ).pack(side="left")
        gc = make_gradient_canvas_h(ov, height=2, c1=PURPLE, c2=CYAN)
        gc.pack(fill="x")
        body   = tk.Frame(ov, bg=BG)
        body.pack(fill="both", expand=True)
        centre = tk.Frame(body, bg=BG)
        centre.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(centre, text="🤖", bg=BG, fg=CYAN,
                 font=(FD, 72)).pack(pady=(0, 12))
        tk.Label(centre, text="Human Verification Required",
                 bg=BG, fg=TEXT, font=(FD, 20, "bold")).pack(pady=(0, 6))
        tk.Label(centre, text="No browser found — open the link below in any browser.",
                 bg=BG, fg=YELLOW, font=(FB, 11)).pack(pady=(0, 18))
        uf = tk.Frame(centre, bg=BG3, padx=20, pady=14,
                      highlightthickness=1, highlightbackground=BORDER2)
        uf.pack(fill="x", padx=40)
        tk.Label(uf, text="VERIFICATION LINK", bg=BG3, fg=TEXT3,
                 font=(FB, 8, "bold")).pack(anchor="w")
        tk.Entry(uf, textvariable=tk.StringVar(value=self._page_url),
                 state="readonly", bg=BG3, fg=CYAN, font=(FM, 9),
                 relief="flat", readonlybackground=BG3,
                 width=70).pack(fill="x", pady=(4, 0))
        self._dot_lbl = tk.Label(
            centre, text="Waiting for verification  ●○○",
            bg=BG, fg=TEXT3, font=(FB, 10))
        self._dot_lbl.pack(pady=(14, 0))

    def _animate(self):
        if self._done:
            return
        self._dots = (self._dots + 1) % 4
        d = "●" * self._dots + "○" * (3 - self._dots)
        try:
            self._dot_lbl.config(text=f"Waiting for verification  {d}")
        except Exception:
            return
        self.app.after(600, self._animate)

    def _on_token_received(self):
        if self._done:
            return
        try:
            self._status_lbl.config(text="🔒  Verifying with Google…", fg=CYAN)
            self._dot_lbl.config(text="Please wait…")
        except Exception:
            pass
        token = self._token

        def _do_verify():
            ok = verify_recaptcha(token)
            self.app.after(0, lambda: self._after_verify(ok, token))

        threading.Thread(target=_do_verify, daemon=True).start()

    def _after_verify(self, ok, token):
        if self._done:
            return
        if ok:
            self._done = True
            try:
                self._status_lbl.config(text="✅  Verified! Continuing…", fg=GREEN)
                self._dot_lbl.config(text="")
            except Exception:
                pass
            self.app.after(1200, lambda: self._finish_success(token))
        else:
            try:
                self._status_lbl.config(
                    text="✗  Verification failed — please try again.", fg=RED)
                self._dot_lbl.config(text="●○○")
            except Exception:
                pass
            self._token = None
            self._done  = False

    def _finish_success(self, token):
        self._destroy_all()
        self._cleanup()
        if self.on_success:
            self.on_success(token)

    def _cancel(self):
        if self._done:
            return
        self._done = True
        self._destroy_all()
        self._cleanup()
        if self.on_cancel:
            self.on_cancel()

    def _destroy_all(self):
        for w in (self._top_bar, self._overlay):
            if w:
                try:
                    w.destroy()
                except Exception:
                    pass

# ════════════════════════════════════════════════════════════════════
#  REGISTER PAGE
# ════════════════════════════════════════════════════════════════════


class RegisterPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app            = app
        self._captcha_token = None
        self._build()

    def _build(self):
        make_bg_canvas(self)
        outer = tk.Frame(self, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card_border = tk.Frame(outer, bg=BORDER2)
        card_border.pack()
        card = tk.Frame(card_border, bg=BG2)
        card.pack(padx=1, pady=1)

        make_gradient_canvas_h(card, height=4, c1=PURPLE, c2=CYAN).pack(fill="x")

        tk.Label(card, text="✨", bg=BG2, fg=CYAN,
                 font=(FD, 36)).pack(pady=(30, 0))
        tk.Label(card, text="Create Account", bg=BG2, fg=TEXT,
                 font=(FD, 22, "bold")).pack(pady=(6, 2))
        tk.Label(card, text="Join TimeNet Cafe", bg=BG2, fg=TEXT2,
                 font=(FB, 11)).pack(pady=(0, 20))
        hsep(card).pack(fill="x", padx=36, pady=(0, 20))

        form = tk.Frame(card, bg=BG2)
        form.pack(padx=48, fill="x")

        self.err = tk.Label(form, text="", fg=RED, bg=BG2,
                            wraplength=380, font=(FB, 10), justify="left")
        self.err.pack(fill="x", pady=(0, 8))

        self.fields = {k: tk.StringVar()
                       for k in ("username", "password", "confirm")}

        def _entry_field(parent_frm, label, key, show=None):
            tk.Label(parent_frm, text=label, fg=TEXT3, bg=BG2,
                     font=(FB, 8, "bold")).pack(anchor="w", pady=(0, 3))
            ff = tk.Frame(parent_frm, bg=BG4, highlightthickness=1,
                          highlightbackground=BORDER2)
            ff.pack(fill="x", pady=(0, 14))
            kw = {"show": show} if show else {}
            e = tk.Entry(ff, textvariable=self.fields[key],
                         bg=BG4, fg=TEXT, insertbackground=PURPLE,
                         font=(FB, 12), relief="flat", **kw)
            e.pack(padx=14, pady=10, fill="x")
            e.bind("<FocusIn>",
                   lambda _: ff.config(highlightbackground=PURPLE))
            e.bind("<FocusOut>",
                   lambda _: ff.config(highlightbackground=BORDER2))
            return e

        _entry_field(form, "USERNAME", "username")

        pw_row = tk.Frame(form, bg=BG2)
        pw_row.pack(fill="x")
        pw_row.columnconfigure(0, weight=1)
        pw_row.columnconfigure(1, weight=1)
        lf = tk.Frame(pw_row, bg=BG2)
        lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        rf_frm = tk.Frame(pw_row, bg=BG2)
        rf_frm.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        _entry_field(lf,     "PASSWORD",         "password", show="●")
        _entry_field(rf_frm, "CONFIRM PASSWORD", "confirm",  show="●")

        hsep(form, BORDER).pack(fill="x", pady=(0, 14))

        rc_card = tk.Frame(form, bg=BG3, highlightthickness=1,
                           highlightbackground=BORDER3)
        rc_card.pack(fill="x", pady=(0, 14))

        rc_left = tk.Frame(rc_card, bg=BG3)
        rc_left.pack(side="left", padx=(14, 8), pady=12)
        self._rc_icon = tk.Label(rc_left, text="🔒", bg=BG3, fg=TEXT3,
                                 font=(FD, 20))
        self._rc_icon.pack()

        rc_mid = tk.Frame(rc_card, bg=BG3)
        rc_mid.pack(side="left", fill="both", expand=True, pady=12)
        self._rc_title = tk.Label(rc_mid, text="Human Verification",
                                  bg=BG3, fg=TEXT2,
                                  font=(FB, 10, "bold"), anchor="w")
        self._rc_title.pack(fill="x")
        self._rc_sub = tk.Label(rc_mid,
                                text="Click Verify to open the reCAPTCHA popup.",
                                bg=BG3, fg=TEXT3, font=(FB, 9),
                                anchor="w", wraplength=200)
        self._rc_sub.pack(fill="x")

        self._rc_btn = tk.Button(
            rc_card, text="🛡  Verify",
            command=self._launch_recaptcha,
            bg=CYAN_DIM, fg=CYAN, font=(FD, 9, "bold"),
            relief="flat", cursor="hand2",
            activebackground=CYAN, activeforeground=BG,
            highlightthickness=1, highlightbackground=CYAN,
            padx=14, pady=8,
        )
        self._rc_btn.pack(side="right", padx=12, pady=12)
        self._rc_btn.bind(
            "<Enter>", lambda _: self._rc_btn.config(bg=CYAN, fg=BG)
            if not self._captcha_token else None)
        self._rc_btn.bind(
            "<Leave>", lambda _: self._rc_btn.config(bg=CYAN_DIM, fg=CYAN)
            if not self._captcha_token else
            self._rc_btn.config(bg=GREEN_DIM, fg=GREEN))

        tk.Button(form, text="Create Account →", command=self._register,
                  bg=PURPLE, fg=TEXT, font=(FD, 12, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground=PURPLE2, activeforeground=TEXT,
                  padx=20, pady=14).pack(fill="x", pady=(0, 6))

        hsep(card).pack(fill="x", padx=36, pady=20)
        footer = tk.Frame(card, bg=BG2)
        footer.pack(pady=(0, 28))
        tk.Label(footer, text="Already have an account? ", fg=TEXT2, bg=BG2,
                 font=(FB, 10)).pack(side="left")
        bl = tk.Label(footer, text="Sign in here", fg=CYAN, bg=BG2,
                      cursor="hand2", font=(FB, 10, "bold"))
        bl.pack(side="left")
        bl.bind("<Button-1>", lambda _: self.app.show_login())

    def _launch_recaptcha(self):
        self._rc_btn.config(state="disabled", bg=BG4, fg=TEXT3,
                            text="⏳  Opening…")
        self.err.config(text="")

        def _on_solved(token):
            self._captcha_token = token
            self._rc_icon.config(text="✅", fg=GREEN)
            self._rc_title.config(text="Verified!", fg=GREEN)
            self._rc_sub.config(
                text="reCAPTCHA passed. You can now register.", fg=GREEN2)
            self._rc_btn.config(
                state="normal", bg=GREEN_DIM, fg=GREEN,
                text="✓  Re-verify",
                activebackground=GREEN, activeforeground=BG)
            self._rc_btn.unbind("<Enter>")
            self._rc_btn.unbind("<Leave>")
            self._rc_btn.bind("<Enter>",
                              lambda _: self._rc_btn.config(bg=GREEN, fg=BG))
            self._rc_btn.bind("<Leave>",
                              lambda _: self._rc_btn.config(bg=GREEN_DIM,
                                                            fg=GREEN))

        def _on_cancel():
            self._rc_btn.config(state="normal", bg=CYAN_DIM, fg=CYAN,
                                text="🛡  Verify")

        RecaptchaWaitingScreen(self.app, on_success=_on_solved,
                               on_cancel=_on_cancel)

    def _register(self):
        d = {k: v.get().strip() for k, v in self.fields.items()}
        if not d["username"] or not d["password"] or not d["confirm"]:
            self.err.config(text="⚠  Please fill in all fields.")
            return
        if d["password"] != d["confirm"]:
            self.err.config(text="✗  Passwords do not match.")
            return
        if len(d["password"]) < 6:
            self.err.config(text="✗  Password must be at least 6 characters.")
            return
        if not self._captcha_token:
            self.err.config(
                text="⚠  Please complete the reCAPTCHA verification first.")
            return

        self.err.config(text="⏳  Creating account…", fg=YELLOW)
        self.update()

        def _finish():
            exists = db_exec(
                "SELECT id FROM users WHERE username=%s",
                (d["username"],), fetch=True)
            if exists:
                self.after(0, lambda: self.err.config(
                    text="✗  Username already taken.", fg=RED))
                return
            new = {
                "id":       f"user-{now_ms()}",
                "username": d["username"],
                "password": d["password"],
                "role":     "customer",
            }
            db_exec("""
                INSERT INTO users (id, username, password, role, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (new["id"], new["username"], new["password"],
                  new["role"], now_ms()))
            Auth.login(new)
            self.after(0, self.app.show_customer_dashboard)

        threading.Thread(target=_finish, daemon=True).start()

# ════════════════════════════════════════════════════════════════════
#  PAYMENT DIALOG
# ════════════════════════════════════════════════════════════════════


class PaymentDialog(tk.Toplevel):
    METHODS = [
        ("cash",  "💵", "Cash",  GREEN),
        ("gcash", "📱", "GCash", "#00B4D8"),
        ("maya",  "💜", "Maya",  PURPLE),
    ]

    def __init__(self, parent_dash, computer_name, duration, cost, on_complete):
        super().__init__(parent_dash)
        self.dash          = parent_dash
        self.app           = parent_dash.app
        self.on_complete   = on_complete
        self.computer_name = computer_name
        self.duration      = duration
        self.cost          = cost
        self.method        = tk.StringVar(value="cash")
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self._build()
        self.update_idletasks()
        w  = 520
        h  = max(self.winfo_reqheight() + 60, 700)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.update_idletasks()
        add_gradient_border(self, thickness=3, c1=PURPLE, c2=CYAN)

    def _build(self):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3, y=3, relwidth=1, relheight=1, width=-6, height=-6)

        tk.Label(inner, text="💳  Complete Payment", bg=BG2, fg=TEXT,
                 font=(FD, 16, "bold")).pack(pady=(22, 2))
        tk.Label(inner, text="Choose how you'd like to pay",
                 bg=BG2, fg=TEXT2, font=(FB, 10)).pack(pady=(0, 18))
        hsep(inner).pack(fill="x", padx=24)

        sc = tk.Frame(inner, bg=BG3, highlightthickness=1,
                      highlightbackground=BORDER2)
        sc.pack(padx=28, pady=18, fill="x")
        tk.Label(sc, text="SESSION SUMMARY", fg=TEXT3, bg=BG3,
                 font=(FB, 8, "bold")).pack(anchor="w", padx=16, pady=(12, 6))
        for lbl, val, col in [
            ("Computer",  self.computer_name,         TEXT2),
            ("Duration",  f"{self.duration} minutes", TEXT),
            ("Total Due", fmt_currency(self.cost),    PURPLE),
        ]:
            r = tk.Frame(sc, bg=BG3)
            r.pack(fill="x", padx=16, pady=3)
            tk.Label(r, text=lbl, fg=TEXT3, bg=BG3,
                     font=(FB, 10)).pack(side="left")
            sz = 14 if lbl == "Total Due" else 11
            wt = "bold" if lbl == "Total Due" else "normal"
            tk.Label(r, text=val, fg=col, bg=BG3,
                     font=(FD, sz, wt)).pack(side="right")
        tk.Frame(sc, bg=BG3, height=8).pack()

        hsep(inner).pack(fill="x", padx=24)
        tk.Label(inner, text="PAYMENT METHOD", fg=TEXT3, bg=BG2,
                 font=(FB, 8, "bold")).pack(pady=(18, 10))

        self._m_widgets = {}
        mf = tk.Frame(inner, bg=BG2)
        mf.pack(padx=28, fill="x")
        for ci, (val, icon, lbl_txt, color) in enumerate(self.METHODS):
            mf.columnconfigure(ci, weight=1)
            is_sel     = self.method.get() == val
            outer_card = tk.Frame(mf, bg=color if is_sel else BORDER,
                                  cursor="hand2")
            outer_card.grid(row=0, column=ci, padx=5, pady=4, sticky="nsew")
            inner_card = tk.Frame(outer_card, bg=BG4 if is_sel else BG3)
            inner_card.pack(fill="both", expand=True, padx=2, pady=2)
            il = tk.Label(inner_card, text=icon, bg=inner_card["bg"],
                          fg=color, font=(FD, 22))
            il.pack(pady=(14, 2))
            nl = tk.Label(inner_card, text=lbl_txt, bg=inner_card["bg"],
                          fg=TEXT, font=(FB, 11, "bold"))
            nl.pack(pady=(0, 14))
            self._m_widgets[val] = {
                "outer": outer_card, "inner": inner_card,
                "il": il, "nl": nl, "color": color,
            }
            for w in (outer_card, inner_card, il, nl):
                w.bind("<Button-1>", lambda e, v=val: self._pick(v))

        self.note_lbl = tk.Label(inner, text="", fg=TEXT2, bg=BG2,
                                 wraplength=460, font=(FB, 10),
                                 justify="center")
        self.note_lbl.pack(pady=(14, 0), padx=28)
        self._update_note()

        hsep(inner).pack(fill="x", padx=24, pady=18)
        bf = tk.Frame(inner, bg=BG2)
        bf.pack(padx=28, pady=(0, 32), fill="x")
        bf.columnconfigure(0, weight=1)
        bf.columnconfigure(1, weight=1)
        tk.Button(
            bf, text="Cancel", command=self.destroy,
            bg=BG4, fg=TEXT2, font=(FD, 13, "bold"),
            relief="flat", cursor="hand2",
            activebackground=BG5, activeforeground=TEXT,
            padx=20, pady=16,
        ).grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.confirm_btn = tk.Button(
            bf, text=f"Pay {fmt_currency(self.cost)}  →",
            command=self._confirm,
            bg=PURPLE, fg=TEXT, font=(FD, 13, "bold"),
            relief="flat", cursor="hand2",
            activebackground=PURPLE2, activeforeground=TEXT,
            padx=20, pady=16,
        )
        self.confirm_btn.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    def _pick(self, val):
        self.method.set(val)
        for v, ww in self._m_widgets.items():
            s = v == val
            ww["outer"].config(bg=ww["color"] if s else BORDER)
            ww["inner"].config(bg=BG4 if s else BG3)
            ww["il"].config(bg=BG4 if s else BG3)
            ww["nl"].config(bg=BG4 if s else BG3)
        self._update_note()

    def _update_note(self):
        notes = {
            "cash":  "💵 A voucher code will be generated. Show it at the counter.",
            "gcash": "📱 GCash checkout opens in a secure browser popup.",
            "maya":  "💜 Maya checkout opens in a secure browser popup.",
        }
        self.note_lbl.config(text=notes.get(self.method.get(), ""))

    def _confirm(self):
        m = self.method.get()
        if m == "cash":
            self._handle_cash()
        else:
            self._handle_paymongo(m)

    def _handle_cash(self):
        voucher    = gen_voucher()
        session_id = f"sess-{now_ms()}"
        computer   = self.dash.assigned_computer
        db_exec("""
            INSERT INTO sessions
              (id, user_id, computer_id, duration, cost,
               status, voucher_code, created_at)
            VALUES (%s,%s,%s,%s,%s,'pending_voucher',%s,%s)
        """, (session_id, Auth.user["id"], computer["id"],
              self.duration, self.cost, voucher, now_ms()))
        self.destroy()

        def _activated():
            if isinstance(self.app.current_frame, CustomerDashboard):
                self.app.current_frame._force_load_session()
            if self.on_complete:
                self.on_complete()

        def _cancelled():
            if isinstance(self.app.current_frame, CustomerDashboard):
                d = self.app.current_frame
                d.selected_tier  = None
                d.active_session = None
                d._load_data()

        CashVoucherDialog(self.app, session_id, voucher,
                          computer["name"], self.duration, self.cost,
                          _activated, _cancelled)

    def _handle_paymongo(self, method):
        if not Auth.user:
            ThemedDialog(self, kind="error", title="Not Logged In",
                         message="Please login first.")
            return
        self.confirm_btn.config(state="disabled",
                                bg=BG5, activebackground=BG5, fg=TEXT3)
        self._spinner = tk.Label(
            self.confirm_btn, text="⏳  Creating link…",
            bg=BG5, fg=TEXT2, font=(FD, 11, "bold"))
        self._spinner.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._spinner.lift()
        self.update()
        session_id    = f"sess-{now_ms()}"
        computer_id   = self.dash.assigned_computer["id"]
        computer_name = self.dash.assigned_computer["name"]
        info = {
            "session_id":  session_id,
            "computer_id": computer_id,
            "user_id":     Auth.user["id"],
            "duration":    self.duration,
            "method":      method,
        }
        desc = (f"TimeNet Cafe — {computer_name} — "
                f"{self.duration} min ({method.upper()})")

        def _create():
            result = paymongo.create_link(self.cost, desc, info)
            self.after(0, lambda: self._on_link_result(result, method))

        threading.Thread(target=_create, daemon=True).start()

    def _on_link_result(self, result, method):
        if not result["success"]:
            try:
                if hasattr(self, "_spinner"):
                    self._spinner.destroy()
                self.confirm_btn.config(
                    state="normal",
                    bg=PURPLE, activebackground=PURPLE2, fg=TEXT)
            except Exception:
                pass
            ThemedDialog(self, kind="error", title="Payment Error",
                         message="Could not create payment link.",
                         detail=result.get("error", "Unknown error"))
            return
        url = result["checkout_url"]
        lid = result["link_id"]
        self.destroy()

        def _paid():
            if isinstance(self.app.current_frame, CustomerDashboard):
                self.app.current_frame._force_load_session()
            if self.on_complete:
                self.on_complete()

        def _cancelled():
            def _rl():
                self.app.relock()
                self.app.lift()
                self.app.focus_force()
                self.app.attributes("-topmost", True)
                self.app.after(
                    800, lambda: self.app.attributes("-topmost", False))
                if isinstance(self.app.current_frame, CustomerDashboard):
                    d = self.app.current_frame
                    d.selected_tier  = None
                    d.active_session = None
                    d._show_booking()
            self.app.after(420, _rl)

        PaymentWaitingScreen(self.app, lid, url, method,
                             self.cost, _paid, _cancelled)

# ════════════════════════════════════════════════════════════════════
#  CUSTOMER DASHBOARD
# ════════════════════════════════════════════════════════════════════


class CustomerDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app               = app
        self.selected_tier     = None
        self.active_session    = None
        self.assigned_computer = None
        self._ticking          = False
        self._last_session_id    = None
        self._last_booking_state = None
        self._view_mode          = None
        self._build()
        self._load_data()
        self._poll()

    def _build(self):
        self.hdr = tk.Frame(self, bg=BG2)
        self.hdr.pack(fill="x")
        gc = make_gradient_canvas_h(self.hdr, height=3, c1=PURPLE, c2=CYAN)
        gc.pack(fill="x")
        hi = tk.Frame(self.hdr, bg=BG2)
        hi.pack(fill="x", padx=28, pady=14)
        left = tk.Frame(hi, bg=BG2)
        left.pack(side="left")
        tk.Label(left, text="🖥", bg=BG2, fg=PURPLE,
                 font=(FD, 18)).pack(side="left", padx=(0, 10))
        tc = tk.Frame(left, bg=BG2)
        tc.pack(side="left")
        tk.Label(tc, text="TimeNet Cafe", bg=BG2, fg=TEXT,
                 font=(FD, 14, "bold")).pack(anchor="w")
        self.welcome_lbl = tk.Label(tc, text="", bg=BG2, fg=TEXT2,
                                    font=(FB, 10))
        self.welcome_lbl.pack(anchor="w")
        right = tk.Frame(hi, bg=BG2)
        right.pack(side="right")
        self.logout_btn = ghost_button(right, "Sign Out", self._logout,
                                       TEXT2, 8)
        self.logout_btn.pack(side="right")
        self.hdr_sep = hsep(self, BORDER2)
        self.hdr_sep.pack(fill="x")
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self._show_booking()

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _show_booking(self):
        self._clear_content()
        computers = db_exec("SELECT * FROM computers", fetch=True) or []
        available = [c for c in computers if c["status"] == "available"]
        if not available:
            self._view_mode = "no_computers"
            self._show_no_computers()
            return

        self._view_mode            = "booking"
        self.assigned_computer     = available[0]
        self._last_booking_state   = (len(available),
                                      self.assigned_computer["id"])

        canvas = tk.Canvas(self.content, bg=BG, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        wid   = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(wid, width=e.width))
        inner.bind("<Configure>",
                   lambda e: canvas.configure(
                       scrollregion=canvas.bbox("all")))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        col = tk.Frame(inner, bg=BG)
        col.pack(expand=True, anchor="center", pady=24, padx=40)

        pc_card = tk.Frame(col, bg=BG2, highlightthickness=1,
                           highlightbackground=BORDER2)
        pc_card.pack(pady=(0, 20), fill="x")
        accent_bar(pc_card, PURPLE).pack(fill="x")
        pi = tk.Frame(pc_card, bg=BG2)
        pi.pack(padx=28, pady=20, fill="x")
        tk.Label(pi, text="🖥", bg=BG2, fg=PURPLE,
                 font=(FD, 36)).pack(side="left", padx=(0, 20))
        info = tk.Frame(pi, bg=BG2)
        info.pack(side="left")
        tk.Label(info, text=self.assigned_computer["name"], bg=BG2,
                 fg=TEXT, font=(FD, 22, "bold")).pack(anchor="w")
        rf = tk.Frame(info, bg=BG2)
        rf.pack(anchor="w")
        tk.Label(rf, text=f"{fmt_currency(HOURLY_RATE)} / hour",
                 fg=PURPLE, bg=BG2,
                 font=(FD, 12, "bold")).pack(side="left")
        tk.Label(rf, text="  ●  Ready", fg=GREEN, bg=BG2,
                 font=(FB, 10)).pack(side="left")

        picker = tk.Frame(col, bg=BG2, highlightthickness=1,
                          highlightbackground=BORDER2)
        picker.pack(fill="x")
        accent_bar(picker, CYAN, 2).pack(fill="x")
        ph = tk.Frame(picker, bg=BG2)
        ph.pack(padx=28, pady=(16, 8), fill="x")
        tk.Label(ph, text="SELECT DURATION", fg=TEXT3, bg=BG2,
                 font=(FB, 8, "bold")).pack(side="left")
        hsep(picker, BORDER).pack(fill="x", padx=24)

        grid = tk.Frame(picker, bg=BG2)
        grid.pack(padx=24, pady=18)
        self.tier_btns = {}
        for idx, tier in enumerate(PRICING_TIERS):
            cost    = calc_cost(tier["minutes"])
            rn, cn  = divmod(idx, 4)
            f = tk.Frame(grid, bg=BG3, cursor="hand2",
                         width=160, height=80, highlightthickness=1,
                         highlightbackground=BORDER)
            f.grid(row=rn, column=cn, padx=5, pady=5, sticky="nsew")
            f.pack_propagate(False)
            grid.columnconfigure(cn, weight=1)
            l1 = tk.Label(f, text=tier["label"], bg=BG3, fg=TEXT2,
                          font=(FB, 9))
            l1.pack(pady=(16, 2))
            l2 = tk.Label(f, text=fmt_currency(cost), bg=BG3, fg=GREEN,
                          font=(FD, 13, "bold"))
            l2.pack(pady=(0, 16))
            mins = tier["minutes"]
            for w in (f, l1, l2):
                w.bind("<Button-1>", lambda e, m=mins: self._pick_tier(m))
            self.tier_btns[mins] = (f, l1, l2)

        self.pay_btn = tk.Button(
            col, text="Select a duration to continue",
            command=self._proceed,
            bg=BG4, fg=TEXT3, font=(FD, 13, "bold"),
            relief="flat", cursor="hand2",
            activebackground=PURPLE2, activeforeground=TEXT,
            padx=20, pady=18, state="disabled")
        self.pay_btn.pack(pady=20, fill="x")

    def _show_no_computers(self):
        c = tk.Frame(self.content, bg=BG)
        c.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(c, text="🖥", font=(FD, 56), bg=BG,
                 fg=TEXT3).pack(pady=(0, 10))
        tk.Label(c, text="No Computers Available", bg=BG, fg=TEXT,
                 font=(FD, 20, "bold")).pack()
        tk.Label(c,
                 text="All PCs are currently in use. Please check back shortly.",
                 fg=TEXT2, bg=BG, font=(FB, 11)).pack(pady=8)

    def _pick_tier(self, minutes):
        if self.selected_tier and self.selected_tier in self.tier_btns:
            f, l1, l2 = self.tier_btns[self.selected_tier]
            f.config(bg=BG3, highlightbackground=BORDER)
            l1.config(bg=BG3, fg=TEXT2)
            l2.config(bg=BG3, fg=GREEN)
        self.selected_tier = minutes
        f, l1, l2 = self.tier_btns[minutes]
        f.config(bg=PURPLE_DIM, highlightbackground=PURPLE)
        l1.config(bg=PURPLE_DIM, fg=PURPLE)
        l2.config(bg=PURPLE_DIM, fg=TEXT)
        cost = calc_cost(minutes)
        self.pay_btn.config(
            text=f"Pay {fmt_currency(cost)} & Start Session  →",
            bg=PURPLE, fg=TEXT, state="normal",
            activebackground=PURPLE2)

    def _proceed(self):
        if not self.selected_tier or not self.assigned_computer:
            return
        cost = calc_cost(self.selected_tier)
        PaymentDialog(self, self.assigned_computer["name"],
                      self.selected_tier, cost, self._on_paid)

    def _on_paid(self):
        self._load_data()

    def _show_active_session(self):
        self._clear_content()
        self.hdr.pack_forget()
        self.hdr_sep.pack_forget()
        if self.app._locked:
            self.app.unlock_for_session()
        computers = db_exec("SELECT * FROM computers", fetch=True) or []
        pc = next((c for c in computers
                   if c["id"] == self.active_session["computerId"]), None)
        if pc:
            self._session_widget(pc)

    def _session_widget(self, computer):
        outer = tk.Frame(self.content, bg=BG2)
        outer.pack(fill="both", expand=True)
        accent_bar(outer, PURPLE, 2).pack(fill="x")
        title_bar = tk.Frame(outer, bg=BG2)
        title_bar.pack(fill="x", padx=6, pady=(4, 0))
        left_side = tk.Frame(title_bar, bg=BG2)
        left_side.pack(side="left", fill="y")
        tk.Label(left_side, text="🖥", bg=BG2, fg=PURPLE,
                 font=(FD, 11)).pack(side="left", padx=(2, 4))
        tk.Label(left_side, text=computer["name"], bg=BG2, fg=TEXT3,
                 font=(FB, 8, "bold")).pack(side="left")

        def _minimise():
            try:
                self.app.withdraw()
            except Exception:
                pass

        min_btn = tk.Button(
            title_bar, text="  —  ", command=_minimise,
            bg=BG3, fg=TEXT2, font=(FD, 9, "bold"),
            relief="flat", cursor="hand2",
            padx=6, pady=2,
            activebackground=BG5, activeforeground=TEXT, bd=0,
        )
        min_btn.pack(side="right", padx=(0, 2), pady=2)
        min_btn.bind("<Enter>", lambda _: min_btn.config(bg=BG4, fg=YELLOW))
        min_btn.bind("<Leave>", lambda _: min_btn.config(bg=BG3, fg=TEXT2))

        hsep(outer, BORDER, 1).pack(fill="x", padx=0, pady=(3, 0))

        self.time_lbl = tk.Label(
            outer, text="00:00:00", fg=TEXT, bg=BG2,
            font=(FD, 24, "bold"))
        self.time_lbl.pack(pady=(4, 2))

        self.prog = ttk.Progressbar(
            outer, maximum=100, value=100,
            style="Session.Horizontal.TProgressbar")
        self.prog.pack(fill="x", padx=10, pady=(0, 3))

        row = tk.Frame(outer, bg=BG2)
        row.pack(fill="x", padx=10)
        self.pct_lbl = tk.Label(
            row, text="100%", fg=PURPLE, bg=BG2, font=(FB, 8, "bold"))
        self.pct_lbl.pack(side="left")

        total_min = self.active_session.get("duration", 60)
        start_ms  = self.active_session.get("startTime", now_ms())
        end_dt    = datetime.fromtimestamp(
            (start_ms + total_min * 60 * 1000) / 1000)
        tk.Label(row, text=f"Ends {end_dt.strftime('%I:%M %p')}",
                 fg=CYAN, bg=BG2, font=(FB, 8, "bold")).pack(side="right")

        self._ticking = True
        self._tick()

    def _tick(self):
        if not self._ticking or not self.active_session:
            self._ticking = False
            return
        try:
            if not self.time_lbl.winfo_exists():
                self._ticking = False
                return
        except Exception:
            self._ticking = False
            return

        total_min = self.active_session.get("duration", 60)
        end_time  = (self.active_session["startTime"]
                     + total_min * 60 * 1000)
        diff      = end_time - now_ms()

        if diff <= 0:
            try:
                self.time_lbl.config(text="00:00:00", fg=RED)
                self.prog["value"] = 0
                self.pct_lbl.config(text="Time's Up!", fg=RED)
            except Exception:
                pass
            self._ticking = False
            self.after(1500, self._end_session)
            return

        try:
            h   = int(diff // 3_600_000)
            m   = int((diff % 3_600_000) // 60_000)
            s   = int((diff % 60_000) // 1000)
            pct = max(0, diff / (total_min * 60 * 1000) * 100)
            clr = RED if pct < 10 else YELLOW if pct < 20 else TEXT
            self.time_lbl.config(text=f"{h:02d}:{m:02d}:{s:02d}", fg=clr)
            self.prog["value"] = pct
            self.pct_lbl.config(
                text=f"{pct:.0f}%",
                fg=RED if pct < 10 else YELLOW if pct < 20 else PURPLE)
        except Exception:
            self._ticking = False
            return

        self.after(1000, self._tick)

    def _end_session(self):
        if not self.active_session:
            return
        db_exec(
            "UPDATE sessions SET status='completed', end_time=%s WHERE id=%s",
            (now_ms(), self.active_session["id"]))
        db_exec(
            "UPDATE computers SET status='available', "
            "current_session_id=NULL WHERE id=%s",
            (self.active_session["computerId"],))
        self.active_session      = None
        self.selected_tier       = None
        self.assigned_computer   = None
        self._last_session_id    = None
        self._last_booking_state = None
        self._view_mode          = None
        self.app.relock()
        try:
            self.hdr.pack(fill="x", before=self.content)
            self.hdr_sep.pack(fill="x", before=self.content)
        except Exception:
            pass
        self._load_data()

    def _force_load_session(self):
        if not Auth.user:
            return
        rows = db_exec(
            "SELECT * FROM sessions WHERE user_id=%s AND status='active'",
            (Auth.user["id"],), fetch=True)
        if not rows:
            self.after(400, self._force_load_session)
            return
        self._ticking         = False
        self.active_session   = _norm_session(rows[0])
        self._last_session_id = self.active_session["id"]
        self._view_mode       = "active"
        self._show_active_session()

    def _load_data(self):
        if not Auth.user:
            return
        rows   = db_exec(
            "SELECT * FROM sessions WHERE user_id=%s AND status='active'",
            (Auth.user["id"],), fetch=True)
        active = _norm_session(rows[0]) if rows else None

        if active:
            if (self._view_mode == "active"
                    and self._last_session_id == active["id"]
                    and self._ticking):
                return
            self._ticking         = False
            self.active_session   = active
            self._last_session_id = active["id"]
            self._view_mode       = "active"
            self._show_active_session()
            return

        computers = db_exec("SELECT * FROM computers", fetch=True) or []
        available = [c for c in computers if c["status"] == "available"]
        new_state = (len(available),
                     available[0]["id"] if available else None)

        if self._view_mode == "active":
            try:
                self.hdr.pack(fill="x", before=self.content)
                self.hdr_sep.pack(fill="x", before=self.content)
            except Exception:
                self.hdr.pack(fill="x")
                self.hdr_sep.pack(fill="x")

        self.logout_btn.pack(side="right")
        self.welcome_lbl.config(
            text=(f"Welcome back, {Auth.user['username']}"
                  if Auth.user else ""))

        if (self._view_mode in ("booking", "no_computers")
                and self._last_booking_state == new_state):
            return

        self.active_session      = None
        self._last_session_id    = None
        self._last_booking_state = new_state

        if not available:
            self._view_mode = "no_computers"
            self._clear_content()
            self._show_no_computers()
        else:
            self.assigned_computer = available[0]
            self._view_mode        = "booking"
            self.selected_tier     = None
            self._show_booking()

    def _poll(self):
        self._load_data()
        self.after(2000, self._poll)

    def _logout(self):
        self.app.logout()

# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
