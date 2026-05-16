import tkinter as tk
from tkinter import ttk
import csv
import os
import time
import random
import threading
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import pooling


# ════════════════════════════════════════════════════════════════════
#  WINDOWS KIOSK KEY BLOCKER  (blocks Win key + exit combos only)
#  All other keys — including all typing — pass through normally.
# ════════════════════════════════════════════════════════════════════

import platform
import ctypes
import ctypes.wintypes
import threading as _threading

_HOOK_HANDLE   = None
_HOOK_CB_REF   = None
_LOCKDOWN_ON   = False

WH_KEYBOARD_LL = 13
WM_KEYDOWN     = 0x0100
WM_SYSKEYDOWN  = 0x0104

VK_LWIN   = 0x5B
VK_RWIN   = 0x5C
VK_TAB    = 0x09
VK_F4     = 0x73
VK_ESCAPE = 0x1B
VK_DELETE = 0x2E
VK_MENU   = 0x12   # Alt

BLOCKED_KEYS   = {VK_LWIN, VK_RWIN}
BLOCKED_COMBOS = [
    (VK_F4,     True,  False),  # Alt+F4
    (VK_TAB,    True,  False),  # Alt+Tab
    (VK_ESCAPE, True,  False),  # Alt+Esc
    (VK_ESCAPE, False, True),   # Ctrl+Esc
    (VK_DELETE, False, True),   # Ctrl+Del (guard)
]


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      ctypes.wintypes.DWORD),
        ("scanCode",    ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


def _keyboard_hook_proc(nCode, wParam, lParam):
    if _LOCKDOWN_ON and nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kb  = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
        vk  = kb.vkCode
        alt = bool(ctypes.windll.user32.GetAsyncKeyState(VK_MENU) & 0x8000)
        ctrl = bool(ctypes.windll.user32.GetAsyncKeyState(0x11)   & 0x8000)
        if vk in BLOCKED_KEYS:
            return 1
        for (bvk, need_alt, need_ctrl) in BLOCKED_COMBOS:
            if vk == bvk:
                if need_alt  and not alt:   continue
                if need_ctrl and not ctrl:  continue
                if not need_alt  and alt:   continue
                if not need_ctrl and ctrl:  continue
                return 1
    return ctypes.windll.user32.CallNextHookEx(_HOOK_HANDLE, nCode, wParam, lParam)


def _install_kb_hook():
    global _HOOK_HANDLE, _HOOK_CB_REF, _LOCKDOWN_ON
    if platform.system() != "Windows":
        return
    try:
        HOOKPROC     = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int,
                                          ctypes.wintypes.WPARAM,
                                          ctypes.wintypes.LPARAM)
        _HOOK_CB_REF = HOOKPROC(_keyboard_hook_proc)
        _HOOK_HANDLE = ctypes.windll.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, _HOOK_CB_REF, None, 0)
        _LOCKDOWN_ON = True

        def _loop():
            msg = ctypes.wintypes.MSG()
            while True:
                ret = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        _threading.Thread(target=_loop, daemon=True).start()
    except Exception as e:
        print(f"[Admin KbHook] {e}")


def _uninstall_kb_hook():
    global _HOOK_HANDLE, _LOCKDOWN_ON
    _LOCKDOWN_ON = False
    if _HOOK_HANDLE:
        try:
            ctypes.windll.user32.UnhookWindowsHookEx(_HOOK_HANDLE)
        except Exception:
            pass
        _HOOK_HANDLE = None

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
#  BUSINESS RULES
# ════════════════════════════════════════════════════════════════════

HOURLY_RATE    = 1.0
MINUTE_RATE    = HOURLY_RATE / 60
ADMIN_EXIT_PIN = "1234"

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
CYAN2      = "#00a0bb"
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
ORANGE     = "#f97316"
ORANGE_DIM = "#2a1200"
FD = "Segoe UI"
FB = "Segoe UI"
FM = "Consolas"

# ════════════════════════════════════════════════════════════════════
#  DATABASE LAYER
# ════════════════════════════════════════════════════════════════════

_pool = None
_pool_lock = threading.Lock()

def get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pooling.MySQLConnectionPool(
                    pool_name="timenet_admin",
                    pool_size=8,
                    pool_reset_session=False,
                    **DB_CONFIG,
                )
    return _pool


def db_exec(query, params=(), fetch=False):
    conn = cur = None
    try:
        conn = get_pool().get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute(query, params)
        if fetch:
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        conn.commit()
        cur.close()
        conn.close()
        return None
    except Exception as e:
        print(f"[DB ERROR] {e}")
        try:
            if cur:  cur.close()
        except: pass
        try:
            if conn: conn.close()
        except: pass
        return [] if fetch else None


def db_exec_safe(query, params=(), fetch=False):
    conn = cur = None
    try:
        conn = get_pool().get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute(query, params)
        if fetch:
            rows = cur.fetchall()
            cur.close(); conn.close()
            return rows, None
        conn.commit()
        cur.close(); conn.close()
        return None, None
    except Exception as e:
        err = str(e)
        print(f"[DB SAFE ERROR] {err}")
        try:
            if cur:  cur.close()
        except: pass
        try:
            if conn: conn.close()
        except: pass
        return ([] if fetch else None), err

# ════════════════════════════════════════════════════════════════════
#  DATETIME / TIME HELPERS
# ════════════════════════════════════════════════════════════════════

_DT_FMTS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f")

def now_dt():
    return datetime.now()

def now_dt_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_date_str():
    return datetime.now().strftime("%Y-%m-%d")

def parse_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in _DT_FMTS:
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    return None

def parse_time_str(val):
    if val is None:
        return 0
    if isinstance(val, timedelta):
        return max(0, int(val.total_seconds()))
    if isinstance(val, str):
        parts = val.split(":")
        try:
            h, m, s = int(parts[0]), int(parts[1]), int(float(parts[2]))
            return max(0, h * 3600 + m * 60 + s)
        except Exception:
            return 0
    return 0

def fmt_dt_display(val):
    dt = parse_dt(val)
    if dt is None:
        return "—"
    return dt.strftime("%B %d, %Y  %I:%M:%S %p")

def fmt_dt_short(val):
    dt = parse_dt(val)
    if dt is None:
        return "—"
    return dt.strftime("%b %d, %Y  %I:%M %p")

def fmt_seconds_hms(total_sec):
    total_sec = max(0, int(total_sec))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def remaining_seconds(start_time_val, duration_min):
    dt = parse_dt(start_time_val)
    if dt is None:
        return 0
    end_dt = dt + timedelta(minutes=int(duration_min))
    return int((end_dt - datetime.now()).total_seconds())

def norm_session(r):
    paused_sec = parse_time_str(r.get("paused_remain"))
    start_val  = r.get("start_time")
    end_val    = r.get("end_time")
    paused_val = r.get("paused_at")
    dur        = int(r.get("duration") or 0)
    return {
        "id":               r.get("id", ""),
        "username":         r.get("username", ""),
        "computer_id":      r.get("computer_id") or "",
        "duration":         dur,
        "cost":             float(r.get("cost") or 0),
        "status":           r.get("status", ""),
        "start_time":       start_val,
        "end_time":         end_val,
        "paused_at":        paused_val,
        "paused_remain_sec": paused_sec,
        "voucher_code":     r.get("voucher_code"),
        "start_disp":       fmt_dt_display(start_val),
        "end_disp":         fmt_dt_display(end_val),
        "paused_at_disp":   fmt_dt_display(paused_val),
        "paused_remain_disp": fmt_seconds_hms(paused_sec),
    }

def norm_payment(r):
    ts_val = r.get("timestamp")
    return {
        "id":         r.get("id", ""),
        "session_id": r.get("session_id", ""),
        "username":   r.get("username", ""),
        "amount":     float(r.get("amount") or 0),
        "method":     r.get("method", ""),
        "status":     r.get("status", ""),
        "receipt_no": r.get("receipt_no", ""),
        "timestamp":  ts_val,
        "ts_disp":    fmt_dt_short(ts_val),
    }

# ════════════════════════════════════════════════════════════════════
#  UTILITIES
# ════════════════════════════════════════════════════════════════════

def fmt_currency(amount):
    return f"₱{float(amount):,.2f}"

def gen_receipt():
    ts = datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
    return f"RN-{ts}"

def gen_payment_id(username):
    ts = datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
    return f"pay-{username}-{ts}"

def gen_session_id(username):
    ts = datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
    return f"ses-{username}-{ts}"

def gen_user_id(username):
    """FIX #2: unique user ID — NOT just the username string."""
    ts = datetime.now().strftime("%m%d%Y%H%M%S")
    return f"usr-{username}-{ts}"

def gen_voucher():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code  = "".join(random.choices(chars, k=8))
    return f"TNV-{code}"

def today_label():
    return datetime.now().strftime("%A, %B %d, %Y")

# ════════════════════════════════════════════════════════════════════
#  GRADIENT HELPERS
# ════════════════════════════════════════════════════════════════════

def _lerp_color(c1, c2, t):
    r1,g1,b1 = int(c1[1:3],16),int(c1[3:5],16),int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16),int(c2[3:5],16),int(c2[5:7],16)
    r = max(0,min(255,int(r1+(r2-r1)*t)))
    g = max(0,min(255,int(g1+(g2-g1)*t)))
    b = max(0,min(255,int(b1+(b2-b1)*t)))
    return f"#{r:02x}{g:02x}{b:02x}"

def draw_gradient_h(canvas, width, height, c1, c2, steps=80):
    canvas.delete("all")
    if width < 2: return
    sw = max(1, width // steps)
    for i in range(steps):
        col = _lerp_color(c1, c2, i/steps)
        sx  = i * sw
        canvas.create_rectangle(sx,0,sx+sw+1,height,fill=col,outline="")
    canvas.create_rectangle(steps*sw,0,width,height,
                             fill=_lerp_color(c1,c2,1.0),outline="")

def draw_gradient_v(canvas, width, height, c1, c2, steps=60):
    canvas.delete("all")
    if height < 2: return
    sh = max(1, height // steps)
    for i in range(steps):
        col = _lerp_color(c1, c2, i/steps)
        sy  = i * sh
        canvas.create_rectangle(0,sy,width,sy+sh+1,fill=col,outline="")
    canvas.create_rectangle(0,steps*sh,width,height,
                             fill=_lerp_color(c1,c2,1.0),outline="")

def make_gradient_canvas_h(parent, height=4, c1=PURPLE, c2=CYAN):
    c = tk.Canvas(parent, bg=BG2, height=height, highlightthickness=0)
    _last = [0]
    def _paint(w):
        if w > 1 and w != _last[0]:
            _last[0] = w
            draw_gradient_h(c, w, height, c1, c2)
    def _on_configure(e): _paint(e.width)
    def _poll():
        w = c.winfo_width()
        if w > 1: _paint(w)
        else:
            try: c.after(20, _poll)
            except: pass
    c.bind("<Configure>", _on_configure)
    c.after(20, _poll)
    return c

def add_gradient_border(dialog, thickness=3, c1=PURPLE, c2=CYAN):
    def _make_h(parent, flip=False):
        ca = tk.Canvas(parent, height=thickness, highlightthickness=0, bg=BG2)
        _a, _b = (c2,c1) if flip else (c1,c2)
        def _draw(w=None):
            ww = w if (w and w>1) else ca.winfo_width()
            if ww > 1: draw_gradient_h(ca, ww, thickness, _a, _b)
        ca.bind("<Configure>", lambda e: _draw(e.width))
        ca.after(1, _draw)
        return ca
    def _make_v(parent, flip=False):
        ca = tk.Canvas(parent, width=thickness, highlightthickness=0, bg=BG2)
        _a, _b = (c2,c1) if flip else (c1,c2)
        def _draw(h=None):
            hh = h if (h and h>1) else ca.winfo_height()
            if hh > 1: draw_gradient_v(ca, thickness, hh, _a, _b)
        ca.bind("<Configure>", lambda e: _draw(e.height))
        ca.after(1, _draw)
        return ca
    top = _make_h(dialog, flip=False); top.place(x=0,y=0,relwidth=1)
    bot = _make_h(dialog, flip=True);  bot.place(x=0,rely=1.0,anchor="sw",relwidth=1)
    lft = _make_v(dialog, flip=False); lft.place(x=0,y=0,relheight=1)
    rgt = _make_v(dialog, flip=True);  rgt.place(relx=1.0,y=0,anchor="ne",relheight=1)

# ════════════════════════════════════════════════════════════════════
#  UI PRIMITIVES
# ════════════════════════════════════════════════════════════════════

def hsep(parent, color=BORDER2, h=1):
    return tk.Frame(parent, bg=color, height=h)

def accent_bar(parent, color=AMBER, h=3):
    return tk.Frame(parent, bg=color, height=h)

def dot_grid(canvas, event, color=TEXT4, spacing=36):
    canvas.delete("dots")
    for x in range(0, event.width, spacing):
        for y in range(0, event.height, spacing):
            canvas.create_oval(x-1,y-1,x+1,y+1,fill=color,outline="",tags="dots")

def make_bg_canvas(parent):
    c = tk.Canvas(parent, bg=BG, highlightthickness=0)
    c.place(relwidth=1, relheight=1)
    c.bind("<Configure>", lambda e: dot_grid(c, e))
    return c

def ghost_button(parent, text, command, color=TEXT2, pady=12):
    return tk.Button(parent, text=text, command=command,
                     bg=BG4, fg=color, font=(FB,11,"bold"),
                     relief="flat", cursor="hand2",
                     activebackground=BG5, activeforeground=TEXT,
                     padx=16, pady=pady)

def stat_card(parent, icon, title, value, color):
    f = tk.Frame(parent, bg=BG3, highlightthickness=1,
                 highlightbackground=BORDER2)
    gc = make_gradient_canvas_h(f, height=3, c1=color, c2=BG3)
    gc.pack(fill="x")
    tk.Label(f, text=icon, bg=BG3, fg=color, font=(FD,20)).pack(
        anchor="w", padx=18, pady=(14,0))
    tk.Label(f, text=title.upper(), bg=BG3, fg=TEXT3,
             font=(FB,8,"bold")).pack(anchor="w", padx=18, pady=(4,0))
    val_lbl = tk.Label(f, text=value, bg=BG3, fg=color, font=(FD,22,"bold"))
    val_lbl.pack(anchor="w", padx=18, pady=(2,16))
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
                 message="", detail="", on_close=None, auto_dismiss_ms=None):
        super().__init__(parent)
        color, dim, icon = self._STYLES.get(kind, self._STYLES["info"])
        self._on_close = on_close
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self.bind("<Return>", lambda _: self._close())
        self.bind("<Escape>", lambda _: self._close())
        self._build(color, dim, icon, title, message, detail)
        self.update_idletasks()
        w  = 480
        h  = max(self.winfo_reqheight()+40, 300)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.update_idletasks()
        add_gradient_border(self, thickness=3, c1=color, c2=PURPLE)
        if auto_dismiss_ms:
            self.after(auto_dismiss_ms, self._close)

    def _build(self, color, dim, icon, title, message, detail):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3,y=3,relwidth=1,relheight=1,width=-6,height=-6)
        badge = tk.Frame(inner, bg=dim, highlightthickness=1,
                         highlightbackground=color, width=64, height=64)
        badge.pack(pady=(28,0))
        badge.pack_propagate(False)
        tk.Label(badge, text=icon, bg=dim, fg=color,
                 font=(FD,26,"bold")).place(relx=0.5,rely=0.5,anchor="center")
        if title:
            tk.Label(inner, text=title, bg=BG2, fg=TEXT,
                     font=(FD,15,"bold")).pack(pady=(14,2))
        if message:
            tk.Label(inner, text=message, bg=BG2, fg=TEXT2, font=(FB,10),
                     wraplength=400, justify="center").pack(padx=36, pady=(0,4))
        if detail:
            hsep(inner, BORDER2).pack(fill="x", padx=28, pady=(14,0))
            df = tk.Frame(inner, bg=BG3, highlightthickness=1,
                          highlightbackground=BORDER2)
            df.pack(padx=28, pady=(10,0), fill="x")
            tk.Entry(df, textvariable=tk.StringVar(value=detail), state="readonly",
                     bg=BG3, fg=color, readonlybackground=BG3,
                     font=(FM,10), relief="flat",
                     justify="center").pack(padx=14, pady=10, fill="x")
        hsep(inner, BORDER2).pack(fill="x", padx=28, pady=(20,0))
        btn = tk.Button(inner, text="  Close  ", command=self._close,
                        bg=color, fg=BG, font=(FD,11,"bold"),
                        relief="flat", cursor="hand2",
                        activebackground=AMBER2 if color==AMBER else color,
                        activeforeground=BG, padx=28, pady=12)
        btn.pack(pady=(14,28))
        btn.focus_set()

    def _close(self):
        try:
            self.grab_release()
            self.destroy()
        except: pass
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
        h  = max(self.winfo_reqheight()+40, 280)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.update_idletasks()
        add_gradient_border(self, thickness=3, c1=confirm_color, c2=PURPLE)

    def _build(self, title, message, confirm_label, cancel_label, confirm_color):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3,y=3,relwidth=1,relheight=1,width=-6,height=-6)
        tk.Label(inner, text="⚠", bg=BG2, fg=confirm_color,
                 font=(FD,30)).pack(pady=(24,0))
        tk.Label(inner, text=title, bg=BG2, fg=TEXT,
                 font=(FD,14,"bold")).pack(pady=(8,2))
        if message:
            tk.Label(inner, text=message, bg=BG2, fg=TEXT2, font=(FB,10),
                     wraplength=380, justify="center").pack(padx=36, pady=(0,6))
        hsep(inner, BORDER2).pack(fill="x", padx=24, pady=(18,0))
        row = tk.Frame(inner, bg=BG2)
        row.pack(padx=28, pady=(14,28), fill="x")
        ghost_button(row, cancel_label, self.destroy, TEXT2, 14).pack(
            side="left", expand=True, fill="x", padx=(0,8))
        tk.Button(row, text=confirm_label, command=self._confirm,
                  bg=confirm_color,
                  fg=BG if confirm_color in (AMBER,GREEN) else TEXT,
                  font=(FD,11,"bold"), relief="flat", cursor="hand2",
                  activebackground=RED2 if confirm_color==RED else AMBER2,
                  activeforeground=BG if confirm_color==AMBER else TEXT,
                  padx=12, pady=14).pack(side="left", expand=True, fill="x")

    def _confirm(self):
        try:
            self.grab_release()
            self.destroy()
        except: pass
        if self._on_confirm:
            self._on_confirm()

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
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.update_idletasks()
        self.bind("<Return>", lambda _: self._check())
        self.bind("<Escape>", lambda _: self.destroy())
        add_gradient_border(self, thickness=3, c1=RED, c2=PURPLE)

    def _build(self):
        inner = tk.Frame(self, bg=BG2)
        inner.place(x=3,y=3,relwidth=1,relheight=1,width=-6,height=-6)
        tk.Label(inner, text="🔐", bg=BG2, fg=RED, font=(FD,32)).pack(pady=(28,0))
        tk.Label(inner, text="Admin Exit", bg=BG2, fg=TEXT,
                 font=(FD,15,"bold")).pack(pady=(6,2))
        tk.Label(inner, text="Enter PIN to close TimeNet Admin",
                 bg=BG2, fg=TEXT2, font=(FB,10)).pack(pady=(0,18))
        hsep(inner).pack(fill="x", padx=28, pady=(0,18))
        self.pin_var = tk.StringVar()
        pf = tk.Frame(inner, bg=BG4, highlightthickness=2,
                      highlightbackground=BORDER3)
        pf.pack(padx=36, fill="x")
        e = tk.Entry(pf, textvariable=self.pin_var, show="●",
                     bg=BG4, fg=TEXT, insertbackground=RED,
                     font=(FD,24,"bold"), justify="center", relief="flat")
        e.pack(padx=12, pady=10, fill="x")
        e.focus_set()
        self.err = tk.Label(inner, text="", bg=BG2, fg=RED, font=(FB,9))
        self.err.pack(pady=(10,4))
        row = tk.Frame(inner, bg=BG2)
        row.pack(padx=28, pady=(14,28), fill="x")
        ghost_button(row, "Cancel", self.destroy, TEXT2, 14).pack(
            side="left", expand=True, fill="x", padx=(0,8))
        tk.Button(row, text="Confirm Exit", command=self._check,
                  bg=RED, fg=TEXT, font=(FD,11,"bold"),
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
# ════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TimeNet Cafe — Admin")
        self.configure(bg=BG)
        self._setup_ttk()
        self._apply_fullscreen()
        self.container     = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.current_frame = None
        self.show_login()
        # Install keyboard hook – blocks Win key / exit combos for kiosk safety
        _install_kb_hook()

        self.bind_all("<Control-Shift-A>", lambda _: self._admin_exit())
        self.protocol("WM_DELETE_WINDOW", lambda: None)

    def _apply_fullscreen(self):
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
        self.after(500, lambda: self.attributes("-topmost", False))

    def _admin_exit(self):
        def _do_exit():
            _uninstall_kb_hook()
            self.destroy()
        AdminPinDialog(self, on_success=_do_exit)

    def _setup_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=BG2, foreground=TEXT,
                    fieldbackground=BG2, bordercolor=BORDER,
                    rowheight=32, font=(FB,10))
        s.configure("Treeview.Heading",
                    background=BG3, foreground=TEXT2,
                    relief="flat", font=(FB,10,"bold"), borderwidth=0)
        s.map("Treeview",
              background=[("selected","#0d2a42")],
              foreground=[("selected",AMBER)])
        s.configure("TScrollbar",
                    background=BG4, troughcolor=BG2,
                    bordercolor=BG, arrowcolor=TEXT3, relief="flat")
        s.configure("Session.Horizontal.TProgressbar",
                    troughcolor=BG3, background=PURPLE,
                    thickness=6, bordercolor=BG3)
        s.configure("Paused.Horizontal.TProgressbar",
                    troughcolor=BG3, background=AMBER,
                    thickness=6, bordercolor=BG3)

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
    _ERR_CLEAR_MS = 2500

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app      = app
        self._err_job = None
        self._build()

    def _show_msg(self, text, color=RED, auto_clear=True):
        if self._err_job is not None:
            try: self.after_cancel(self._err_job)
            except: pass
            self._err_job = None
        self.err.config(text=text, fg=color)
        if auto_clear and text:
            self._err_job = self.after(
                self._ERR_CLEAR_MS, lambda: self.err.config(text=""))

    def _build(self):
        make_bg_canvas(self)
        outer = tk.Frame(self, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")
        card_border = tk.Frame(outer, bg=BORDER2)
        card_border.pack()
        card = tk.Frame(card_border, bg=BG2)
        card.pack(padx=1, pady=1)
        make_gradient_canvas_h(card, height=4, c1=PURPLE, c2=AMBER).pack(fill="x")
        tk.Label(card, text="🛡", bg=BG2, fg=PURPLE, font=(FD,36)).pack(pady=(30,0))
        tk.Label(card, text="TimeNet Admin", bg=BG2, fg=TEXT,
                 font=(FD,22,"bold")).pack(pady=(6,2))
        tk.Label(card, text="Staff & management portal", bg=BG2, fg=TEXT2,
                 font=(FB,11)).pack(pady=(0,20))
        hsep(card).pack(fill="x", padx=36, pady=(0,20))
        form = tk.Frame(card, bg=BG2)
        form.pack(padx=48, fill="x")
        self.err = tk.Label(form, text="", fg=RED, bg=BG2,
                            wraplength=340, font=(FB,10), justify="left")
        self.err.pack(fill="x", pady=(0,8))
        self.usr = tk.StringVar()
        self.pwd = tk.StringVar()
        tk.Label(form, text="USERNAME", fg=TEXT3, bg=BG2,
                 font=(FB,8,"bold")).pack(anchor="w", pady=(0,3))
        uf = tk.Frame(form, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        uf.pack(fill="x", pady=(0,16))
        eu = tk.Entry(uf, textvariable=self.usr, bg=BG4, fg=TEXT,
                      insertbackground=PURPLE, font=(FB,12), relief="flat")
        eu.pack(padx=14, pady=10, fill="x")
        eu.bind("<FocusIn>",  lambda _: uf.config(highlightbackground=PURPLE))
        eu.bind("<FocusOut>", lambda _: uf.config(highlightbackground=BORDER2))
        eu.focus_set()
        tk.Label(form, text="PASSWORD", fg=TEXT3, bg=BG2,
                 font=(FB,8,"bold")).pack(anchor="w", pady=(0,3))
        pf = tk.Frame(form, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        pf.pack(fill="x", pady=(0,16))
        ep = tk.Entry(pf, textvariable=self.pwd, show="●",
                      bg=BG4, fg=TEXT, insertbackground=PURPLE,
                      font=(FB,12), relief="flat")
        ep.pack(padx=14, pady=10, fill="x")
        ep.bind("<FocusIn>",  lambda _: pf.config(highlightbackground=PURPLE))
        ep.bind("<FocusOut>", lambda _: pf.config(highlightbackground=BORDER2))
        ep.bind("<Return>", lambda _: self._login())
        self.sign_btn = tk.Button(
            form, text="Sign In →", command=self._login,
            bg=PURPLE, fg=TEXT, font=(FD,12,"bold"),
            relief="flat", cursor="hand2",
            activebackground=PURPLE2, activeforeground=TEXT,
            padx=20, pady=14)
        self.sign_btn.pack(fill="x", pady=(0,6))
        hsep(card).pack(fill="x", padx=36, pady=20)
        tk.Label(card, text="Admin accounts only  •  Ctrl+Shift+A to exit",
                 fg=TEXT3, bg=BG2, font=(FB,9)).pack(pady=(0,24))

    def _login(self):
        u = self.usr.get().strip()
        p = self.pwd.get().strip()
        if not u or not p:
            self._show_msg("⚠  Please fill in all fields.")
            return
        self.sign_btn.config(state="disabled", bg=BG4, fg=TEXT3,
                             text="⏳  Logging in…", activebackground=BG4)
        self._show_msg("⏳  Logging in…", color=CYAN, auto_clear=False)
        self.update_idletasks()

        def _do():
            rows = db_exec(
                "SELECT * FROM users WHERE username=%s AND password=%s AND role='admin'",
                (u, p), fetch=True)
            self.after(0, lambda: self._finish(rows))

        threading.Thread(target=_do, daemon=True).start()

    def _finish(self, rows):
        self.sign_btn.config(state="normal", bg=PURPLE, fg=TEXT,
                             text="Sign In →", activebackground=PURPLE2)
        if rows:
            Auth.login(dict(rows[0]))
            self._show_msg("✅  Welcome! Loading dashboard…", color=GREEN, auto_clear=False)
            self.after(800, self.app.show_dashboard)
        else:
            self._show_msg("✗  Invalid credentials or not an admin account.")

# ════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ════════════════════════════════════════════════════════════════════

class AdminDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app          = app
        self._current_tab = "overview"
        self._data_cache  = {}
        self._last_hash   = {}
        self._live_rows   = {}
        self._paused_rows = {}
        self._fetch_lock  = threading.Lock()
        self._destroyed   = False
        self._mw_binding_canvas = None
        self._mw_binding_id     = None
        self._build()
        self._start_bg_fetch()
        self._poll()
        self._tick_live()

    # ── SHELL ─────────────────────────────────────────────────────

    def _build(self):
        hdr = tk.Frame(self, bg=BG2)
        hdr.pack(fill="x")
        make_gradient_canvas_h(hdr, height=3, c1=PURPLE, c2=AMBER).pack(fill="x")
        hi = tk.Frame(hdr, bg=BG2)
        hi.pack(fill="x", padx=28, pady=14)
        left = tk.Frame(hi, bg=BG2)
        left.pack(side="left")
        tk.Label(left, text="🛡", bg=BG2, fg=PURPLE,
                 font=(FD,18)).pack(side="left", padx=(0,10))
        nc = tk.Frame(left, bg=BG2)
        nc.pack(side="left")
        tk.Label(nc, text="Admin Portal", bg=BG2, fg=TEXT,
                 font=(FD,14,"bold")).pack(anchor="w")
        tk.Label(nc, text="TimeNet Cafe Management",
                 bg=BG2, fg=TEXT2, font=(FB,10)).pack(anchor="w")
        ghost_button(hi, "Sign Out", self.app.logout, TEXT2, 8).pack(side="right")
        hsep(self, BORDER2).pack(fill="x")
        tab_bar = tk.Frame(self, bg=BG2)
        tab_bar.pack(fill="x")
        self.tab_btns = {}
        self.tab_inds = {}
        tabs = [
            ("overview", "📊  Overview"),
            ("vouchers", "🎫  Vouchers"),
            ("reports",  "📈  Reports"),
            ("users",    "👥  Users"),
        ]
        for tid, lbl in tabs:
            col = tk.Frame(tab_bar, bg=BG2)
            col.pack(side="left")
            b = tk.Button(col, text=lbl,
                          command=lambda t=tid: self._switch_tab(t),
                          bg=BG2,
                          fg=TEXT if tid=="overview" else TEXT2,
                          font=(FB,11,"bold"), relief="flat", cursor="hand2",
                          activebackground=BG2, activeforeground=TEXT,
                          padx=24, pady=14)
            b.pack()
            ind = tk.Frame(col, bg=AMBER if tid=="overview" else BG2, height=2)
            ind.pack(fill="x")
            self.tab_btns[tid] = b
            self.tab_inds[tid] = ind
        hsep(self, BORDER2).pack(fill="x")
        self.tab_content = tk.Frame(self, bg=BG)
        self.tab_content.pack(fill="both", expand=True)
        self._build_overview()

    def _switch_tab(self, tab):
        if tab == self._current_tab: return
        self._current_tab = tab
        self._last_hash   = {}
        self._unbind_mousewheel()
        for tid, b in self.tab_btns.items():
            active = tid == tab
            b.config(fg=TEXT if active else TEXT2)
            self.tab_inds[tid].config(bg=AMBER if active else BG2)
        for w in self.tab_content.winfo_children():
            w.destroy()
        {
            "overview": self._build_overview,
            "vouchers": self._build_vouchers,
            "reports":  self._build_reports,
            "users":    self._build_users,
        }[tab]()
        self._force_refresh()

    def destroy(self):
        self._destroyed = True
        self._unbind_mousewheel()
        super().destroy()

    # FIX #6: per-canvas mousewheel management
    def _bind_mousewheel(self, canvas):
        self._unbind_mousewheel()
        bid = canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._mw_binding_canvas = canvas
        self._mw_binding_id     = bid

    def _unbind_mousewheel(self):
        if self._mw_binding_canvas is not None:
            try:
                self._mw_binding_canvas.unbind_all("<MouseWheel>")
            except: pass
            self._mw_binding_canvas = None
            self._mw_binding_id     = None

    # ── BACKGROUND FETCH ──────────────────────────────────────────

    def _start_bg_fetch(self):
        def _loop():
            while not self._destroyed:
                try:
                    sessions  = db_exec("SELECT * FROM sessions",  fetch=True) or []
                    computers = db_exec("SELECT * FROM computers",  fetch=True) or []
                    payments  = db_exec("SELECT * FROM payments",   fetch=True) or []
                    users     = db_exec(
                        "SELECT id, username, role, registered_on_pc, created_at "
                        "FROM users WHERE role='customer' ORDER BY username",
                        fetch=True) or []
                    normed_sessions = [norm_session(r) for r in sessions]
                    normed_payments = [norm_payment(r) for r in payments]
                    with self._fetch_lock:
                        self._data_cache = {
                            "sessions":  normed_sessions,
                            "computers": computers,
                            "payments":  normed_payments,
                            "users":     users,
                        }
                except Exception as e:
                    print(f"[BG fetch] {e}")
                time.sleep(2)
        threading.Thread(target=_loop, daemon=True).start()

    def _get_data(self):
        with self._fetch_lock:
            return dict(self._data_cache)

    def _force_refresh(self):
        self._last_hash = {}
        self.after(80, self._poll_once)

    # ── POLL ──────────────────────────────────────────────────────

    def _poll(self):
        if self._destroyed: return
        self._poll_once()
        self.after(2000, self._poll)

    def _poll_once(self):
        if self._destroyed: return
        data = self._get_data()
        if not data: return
        tab = self._current_tab
        if tab == "overview":
            self._smart_refresh_live(data)
            self._smart_refresh_fleet(data)
        elif tab == "vouchers":
            self._smart_refresh_vouchers(data)
            self._smart_refresh_pending_vouchers(data)
        elif tab == "reports":
            self._smart_refresh_stats(data)
            self._smart_refresh_table(data)
        elif tab == "users":
            self._smart_refresh_users(data)

    # ── LIVE TICK (1-second countdown) ────────────────────────────
    # FIX #5: paused sessions actually decrement their counter

    def _tick_live(self):
        if self._destroyed: return
        now = datetime.now()

        # Active sessions: compute from end_dt
        for cid, info in list(self._live_rows.items()):
            end_dt    = info.get("end_dt")
            total_sec = info.get("total_sec", 1)
            if end_dt is None: continue
            diff_sec = int((end_dt - now).total_seconds())
            rem_min  = max(0, diff_sec // 60)
            rem_str  = fmt_seconds_hms(max(0, diff_sec))
            color    = RED if rem_min <= 5 else YELLOW if rem_min <= 10 else CYAN
            pct      = max(0.0, min(100.0, diff_sec / total_sec * 100)) if total_sec else 0
            try:
                info["time_lbl"].config(text=rem_str, fg=color)
                info["prog"]["value"] = pct
                info["pct_lbl"].config(
                    text=f"{pct:.0f}%",
                    fg=RED if pct < 10 else YELLOW if pct < 20 else PURPLE)
            except: pass

        # Paused sessions: decrement counter by 1 each tick
        for sid, info in list(self._paused_rows.items()):
            if info.get("remain_sec", 0) > 0:
                info["remain_sec"] = max(0, info["remain_sec"] - 1)
            remain_sec = info["remain_sec"]
            try:
                info["time_lbl"].config(text=fmt_seconds_hms(remain_sec), fg=AMBER)
                total_sec = info.get("total_sec", 1)
                pct = max(0.0, min(100.0, remain_sec / total_sec * 100)) if total_sec else 0
                info["prog"]["value"] = pct
                info["pct_lbl"].config(text=f"{pct:.0f}%", fg=AMBER)
            except: pass

        self.after(1000, self._tick_live)

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
        wid     = canvas.create_window((0,0), window=wrapper, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        wrapper.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._bind_mousewheel(canvas)
        self._ov = tk.Frame(wrapper, bg=BG)
        self._ov.pack(anchor="center", expand=True, fill="x")
        self._build_live_paused_section()
        self._build_fleet_section()

    def _build_live_paused_section(self):
        card = tk.Frame(self._ov, bg=BG2, highlightthickness=1,
                        highlightbackground=BORDER2)
        card.pack(padx=32, pady=(16,0), fill="x")
        hdr = tk.Frame(card, bg=BG2)
        hdr.pack(fill="x", padx=24, pady=(18,0))
        tk.Label(hdr, text="📡  Sessions", fg=TEXT, bg=BG2,
                 font=(FD,13,"bold")).pack(side="left")
        hsep(card, BORDER).pack(fill="x", padx=20, pady=12)
        body = tk.Frame(card, bg=BG2)
        body.pack(fill="x", padx=20, pady=(0,18))
        body.columnconfigure(0, weight=1, uniform="half")
        body.columnconfigure(1, weight=0)
        body.columnconfigure(2, weight=1, uniform="half")
        live_col = tk.Frame(body, bg=BG2)
        live_col.grid(row=0, column=0, sticky="nsew")
        live_hdr = tk.Frame(live_col, bg=BG2)
        live_hdr.pack(fill="x", pady=(0,6))
        tk.Frame(live_hdr, bg=GREEN, width=3, height=16).pack(side="left", padx=(0,6))
        tk.Label(live_hdr, text="LIVE SESSIONS", fg=GREEN, bg=BG2,
                 font=(FB,9,"bold")).pack(side="left")
        self.live_frame = tk.Frame(live_col, bg=BG2)
        self.live_frame.pack(fill="x")
        tk.Frame(body, bg=BORDER2, width=1).grid(row=0, column=1, sticky="ns", padx=16)
        paused_col = tk.Frame(body, bg=BG2)
        paused_col.grid(row=0, column=2, sticky="nsew")
        paused_hdr = tk.Frame(paused_col, bg=BG2)
        paused_hdr.pack(fill="x", pady=(0,6))
        tk.Frame(paused_hdr, bg=AMBER, width=3, height=16).pack(side="left", padx=(0,6))
        tk.Label(paused_hdr, text="PAUSED SESSIONS", fg=AMBER, bg=BG2,
                 font=(FB,9,"bold")).pack(side="left")
        self.paused_frame = tk.Frame(paused_col, bg=BG2)
        self.paused_frame.pack(fill="x")
        tk.Label(self.live_frame, text="No active sessions.",
                 fg=TEXT3, bg=BG2, font=(FB,10)).pack(anchor="w", pady=4)
        tk.Label(self.paused_frame, text="No paused sessions.",
                 fg=TEXT3, bg=BG2, font=(FB,10)).pack(anchor="w", pady=4)

    def _build_fleet_section(self):
        card = tk.Frame(self._ov, bg=BG2, highlightthickness=1,
                        highlightbackground=BORDER2)
        card.pack(padx=32, pady=(16,32), fill="x")
        top = tk.Frame(card, bg=BG2)
        top.pack(fill="x", padx=24, pady=(18,0))
        tk.Label(top, text="🖥  Computer Fleet", fg=TEXT, bg=BG2,
                 font=(FD,13,"bold")).pack(side="left")
        ar = tk.Frame(top, bg=BG2)
        ar.pack(side="right")
        self.new_pc_var = tk.StringVar()
        nf = tk.Frame(ar, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        nf.pack(side="left", padx=(0,10))
        ne = tk.Entry(nf, textvariable=self.new_pc_var, width=18,
                      bg=BG4, fg=TEXT, insertbackground=AMBER,
                      font=(FB,10), relief="flat")
        ne.pack(padx=10, pady=6)
        ne.bind("<Return>", lambda _: self._add_pc())
        tk.Button(ar, text="+ Add PC", command=self._add_pc,
                  bg=AMBER, fg=BG, font=(FB,10,"bold"), relief="flat",
                  cursor="hand2", activebackground=AMBER2, activeforeground=BG,
                  padx=14, pady=6).pack(side="left")
        hsep(card, BORDER).pack(fill="x", padx=20, pady=12)
        self.pc_grid = tk.Frame(card, bg=BG2)
        self.pc_grid.pack(fill="x", padx=20, pady=(0,20))

    # ── Smart refresh: live sessions ──────────────────────────────

    def _smart_refresh_live(self, data):
        sessions  = data.get("sessions", [])
        computers = data.get("computers", [])
        active = [s for s in sessions if s["status"] == "active"]
        paused = [s for s in sessions if s["status"] == "paused"]

        h_live = str([(s["computer_id"], s.get("duration"), str(s.get("start_time")))
                      for s in sorted(active, key=lambda x: x["computer_id"])])
        h_paused = str([(s["id"], s.get("paused_remain_sec"))
                        for s in sorted(paused, key=lambda x: x["id"])])

        if h_live != self._last_hash.get("live"):
            self._last_hash["live"] = h_live
            for w in self.live_frame.winfo_children(): w.destroy()
            self._live_rows = {}
            if not active:
                tk.Label(self.live_frame, text="No active sessions.",
                         fg=TEXT3, bg=BG2, font=(FB,10)).pack(anchor="w", pady=4)
            else:
                for s in sorted(active, key=lambda x: str(x.get("start_time") or "")):
                    pc        = next((c for c in computers
                                      if c["id"] == s["computer_id"]), None)
                    dur_min   = int(s.get("duration") or 0)
                    total_sec = dur_min * 60
                    start_dt  = parse_dt(s.get("start_time"))
                    if start_dt:
                        end_dt   = start_dt + timedelta(minutes=dur_min)
                        diff_sec = int((end_dt - datetime.now()).total_seconds())
                    else:
                        end_dt   = None
                        diff_sec = 0
                    pct     = max(0.0, min(100.0, diff_sec / total_sec * 100)) if total_sec else 0
                    rem_min = max(0, diff_sec // 60)
                    color   = RED if rem_min <= 5 else YELLOW if rem_min <= 10 else CYAN

                    row = tk.Frame(self.live_frame, bg=BG3, highlightthickness=1,
                                   highlightbackground=BORDER2)
                    row.pack(fill="x", pady=3)
                    tk.Frame(row, bg=GREEN, width=3).pack(side="left", fill="y")
                    left_col = tk.Frame(row, bg=BG3)
                    left_col.pack(side="left", padx=(10,0), pady=8)
                    tk.Label(left_col, text=pc["name"] if pc else "?",
                             fg=TEXT, bg=BG3, font=(FB,10,"bold")).pack(anchor="w")
                    tk.Label(left_col,
                             text=f"{s.get('username','?')}  ·  {dur_min} min",
                             fg=TEXT2, bg=BG3, font=(FB,8)).pack(anchor="w")
                    tk.Label(left_col, text=f"Started: {s.get('start_disp','—')}",
                             fg=TEXT3, bg=BG3, font=(FB,7)).pack(anchor="w")
                    mid_col = tk.Frame(row, bg=BG3)
                    mid_col.pack(side="left", padx=12, pady=8)
                    prog = ttk.Progressbar(mid_col, maximum=100, value=pct,
                                           style="Session.Horizontal.TProgressbar",
                                           length=160)
                    prog.pack(anchor="w", pady=(2,2))
                    pct_lbl = tk.Label(mid_col, text=f"{pct:.0f}%",
                                       fg=PURPLE, bg=BG3, font=(FB,7,"bold"))
                    pct_lbl.pack(anchor="w")
                    right_col = tk.Frame(row, bg=BG3)
                    right_col.pack(side="right", padx=10, pady=6)
                    tk.Label(right_col, text="TIME LEFT", fg=TEXT3, bg=BG3,
                             font=(FB,7,"bold")).pack(anchor="e")
                    time_lbl = tk.Label(right_col,
                                        text=fmt_seconds_hms(max(0, diff_sec)),
                                        fg=color, bg=BG3, font=(FM,14,"bold"))
                    time_lbl.pack(anchor="e")
                    self._live_rows[s["computer_id"]] = {
                        "end_dt":    end_dt,
                        "total_sec": total_sec,
                        "time_lbl":  time_lbl,
                        "prog":      prog,
                        "pct_lbl":   pct_lbl,
                    }

        if h_paused != self._last_hash.get("paused"):
            self._last_hash["paused"] = h_paused
            for w in self.paused_frame.winfo_children(): w.destroy()
            self._paused_rows = {}
            if not paused:
                tk.Label(self.paused_frame, text="No paused sessions.",
                         fg=TEXT3, bg=BG2, font=(FB,10)).pack(anchor="w", pady=4)
            else:
                for s in sorted(paused, key=lambda x: str(x.get("paused_at") or "")):
                    pc         = next((c for c in computers
                                       if c["id"] == s["computer_id"]), None)
                    remain_sec = int(s.get("paused_remain_sec") or 0)
                    total_sec  = int(s.get("duration") or 0) * 60
                    pct        = max(0.0, min(100.0, remain_sec / total_sec * 100)) if total_sec else 0

                    row = tk.Frame(self.paused_frame, bg=BG3, highlightthickness=1,
                                   highlightbackground=BORDER2)
                    row.pack(fill="x", pady=3)
                    tk.Frame(row, bg=AMBER, width=3).pack(side="left", fill="y")
                    left_col = tk.Frame(row, bg=BG3)
                    left_col.pack(side="left", padx=(10,0), pady=8)
                    tk.Label(left_col, text=pc["name"] if pc else "?",
                             fg=TEXT, bg=BG3, font=(FB,10,"bold")).pack(anchor="w")
                    tk.Label(left_col,
                             text=f"{s.get('username','?')}  ·  {s.get('duration','?')} min",
                             fg=TEXT2, bg=BG3, font=(FB,8)).pack(anchor="w")
                    tk.Label(left_col, text=f"Paused: {s.get('paused_at_disp','—')}",
                             fg=TEXT3, bg=BG3, font=(FB,7)).pack(anchor="w")
                    mid_col = tk.Frame(row, bg=BG3)
                    mid_col.pack(side="left", padx=12, pady=8)
                    prog = ttk.Progressbar(mid_col, maximum=100, value=pct,
                                           style="Paused.Horizontal.TProgressbar",
                                           length=160)
                    prog.pack(anchor="w", pady=(2,2))
                    pct_lbl = tk.Label(mid_col, text=f"{pct:.0f}%",
                                       fg=AMBER, bg=BG3, font=(FB,7,"bold"))
                    pct_lbl.pack(anchor="w")
                    right_col = tk.Frame(row, bg=BG3)
                    right_col.pack(side="right", padx=10, pady=6)
                    tk.Label(right_col, text="PAUSED", fg=AMBER, bg=BG3,
                             font=(FB,7,"bold")).pack(anchor="e")
                    time_lbl = tk.Label(right_col,
                                        text=fmt_seconds_hms(remain_sec),
                                        fg=AMBER, bg=BG3, font=(FM,14,"bold"))
                    time_lbl.pack(anchor="e")
                    # FIX #5: store mutable remain_sec in info dict for tick decrement
                    self._paused_rows[s["id"]] = {
                        "remain_sec": remain_sec,
                        "total_sec":  total_sec,
                        "time_lbl":   time_lbl,
                        "prog":       prog,
                        "pct_lbl":    pct_lbl,
                    }

    def _smart_refresh_fleet(self, data):
        computers = data.get("computers", [])
        h = str([(c["id"], c.get("status")) for c in sorted(computers, key=lambda x: x["id"])])
        if h == self._last_hash.get("fleet"): return
        self._last_hash["fleet"] = h
        for w in self.pc_grid.winfo_children(): w.destroy()
        for idx, c in enumerate(computers):
            rn, cn = divmod(idx, 4)
            status  = c.get("status","")
            color   = {"available": GREEN, "occupied": RED,
                       "maintenance": YELLOW}.get(status, TEXT2)
            label   = {"available": "AVAILABLE", "occupied": "IN USE",
                       "maintenance": "MAINTENANCE"}.get(status, status.upper())
            occupied = status == "occupied"
            frame = tk.Frame(self.pc_grid, bg=BG3, highlightthickness=1,
                             highlightbackground=BORDER2)
            frame.grid(row=rn, column=cn, padx=6, pady=6, sticky="nsew")
            self.pc_grid.columnconfigure(cn, weight=1)
            accent_bar(frame, color, 2).pack(fill="x")
            info = tk.Frame(frame, bg=BG3)
            info.pack(fill="x", padx=12, pady=(10,4))
            tk.Label(info, text="🖥", bg=BG3, fg=color,
                     font=(FD,18)).pack(side="left", padx=(0,8))
            nc = tk.Frame(info, bg=BG3)
            nc.pack(side="left")
            tk.Label(nc, text=c["name"], fg=TEXT, bg=BG3,
                     font=(FB,11,"bold")).pack(anchor="w")
            tk.Label(nc, text=label, fg=color, bg=BG3,
                     font=(FB,8,"bold")).pack(anchor="w")
            if occupied and c.get("current_session_id"):
                sid_short = str(c["current_session_id"])[:22]
                tk.Label(nc, text=f"Session: {sid_short}…",
                         fg=TEXT3, bg=BG3, font=(FB,7)).pack(anchor="w")
            br = tk.Frame(frame, bg=BG3)
            br.pack(fill="x", padx=10, pady=(6,12))
            maint_lbl = "✓ Fixed"   if status == "maintenance" else "🔧 Maintain"
            maint_fg  = YELLOW      if status == "maintenance" else TEXT3
            mb = tk.Button(br, text=maint_lbl,
                           command=lambda cid=c["id"]: self._toggle_maint(cid),
                           bg=BG4, fg=maint_fg, font=(FB,8,"bold"), relief="flat",
                           cursor="hand2" if not occupied else "arrow",
                           padx=8, pady=5)
            if occupied: mb.config(state="disabled", fg=TEXT3)
            mb.pack(side="left", expand=True, fill="x", padx=(0,4))
            db_btn = tk.Button(br, text="🗑",
                               command=lambda cid=c["id"], cn=c["name"]:
                                   self._del_pc(cid, cn),
                               bg=BG4, fg=RED, font=(FB,8), relief="flat",
                               cursor="hand2" if not occupied else "arrow",
                               padx=8, pady=5)
            if occupied: db_btn.config(state="disabled", fg=TEXT3)
            db_btn.pack(side="left")

    # ════════════════════════════════════════════════════════════
    #  VOUCHERS TAB
    # ════════════════════════════════════════════════════════════

    def _build_vouchers(self):
        outer = tk.Frame(self.tab_content, bg=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = tk.Frame(outer, bg=BG2, highlightthickness=1, highlightbackground=BORDER2)
        top.pack(fill="x", pady=(0,16))
        accent_bar(top, GREEN).pack(fill="x")

        title_row = tk.Frame(top, bg=BG2)
        title_row.pack(fill="x", padx=20, pady=(14,2))
        tk.Label(title_row, text="🎫  Activate Cash Voucher", fg=TEXT, bg=BG2,
                 font=(FD,13,"bold")).pack(side="left")
        tk.Label(top, text="Enter a voucher code manually, or click a pending card below to paste it.",
                 fg=TEXT2, bg=BG2, font=(FB,10)).pack(anchor="w", padx=20)
        hsep(top, BORDER).pack(fill="x", padx=16, pady=(10,0))

        input_section = tk.Frame(top, bg=BG2)
        input_section.pack(fill="x", padx=20, pady=(12,0))
        tk.Label(input_section, text="VOUCHER CODE", fg=TEXT3, bg=BG2,
                 font=(FB,8,"bold")).pack(anchor="w", pady=(0,4))

        code_row = tk.Frame(input_section, bg=BG2)
        code_row.pack(fill="x", pady=(0,4))

        self.vt_var = tk.StringVar()
        self.vt_var.trace("w", lambda *_: self.vt_var.set(
            self.vt_var.get().upper()[:16]))

        vf = tk.Frame(code_row, bg=BG4, highlightthickness=2,
                      highlightbackground=BORDER3)
        vf.pack(side="left", padx=(0,12))
        self.vt_entry = tk.Entry(
            vf, textvariable=self.vt_var, width=24,
            bg=BG4, fg=GREEN, insertbackground=GREEN,
            font=(FM,16,"bold"), relief="flat", justify="center")
        self.vt_entry.pack(padx=16, pady=12)
        self.vt_entry.bind("<FocusIn>",  lambda _: vf.config(highlightbackground=GREEN))
        self.vt_entry.bind("<FocusOut>", lambda _: vf.config(highlightbackground=BORDER3))
        self.vt_entry.bind("<Return>",   lambda _: self._activate_voucher())
        self.vt_entry.focus_set()

        tk.Button(code_row, text="✓  Activate", command=self._activate_voucher,
                  bg=GREEN, fg=BG, font=(FB,12,"bold"), relief="flat",
                  cursor="hand2", activebackground=GREEN2, activeforeground=BG,
                  padx=24, pady=12).pack(side="left")

        self.vt_msg = tk.Label(input_section, text="", fg=GREEN, bg=BG2, font=(FB,10))
        self.vt_msg.pack(anchor="w", pady=(4,0))

        hsep(top, BORDER).pack(fill="x", padx=16, pady=(10,0))
        pending_section = tk.Frame(top, bg=BG2)
        pending_section.pack(fill="x", padx=20, pady=(12,16))

        pending_hdr = tk.Frame(pending_section, bg=BG2)
        pending_hdr.pack(fill="x", pady=(0,8))
        tk.Frame(pending_hdr, bg=AMBER, width=3, height=14).pack(side="left", padx=(0,8))
        tk.Label(pending_hdr, text="PENDING VOUCHERS", fg=AMBER, bg=BG2,
                 font=(FB,9,"bold")).pack(side="left")
        tk.Label(pending_hdr, text="— click a card to paste into the input box",
                 fg=TEXT3, bg=BG2, font=(FB,8)).pack(side="left", padx=(8,0))

        pending_canvas_frame = tk.Frame(pending_section, bg=BG2)
        pending_canvas_frame.pack(fill="x")
        self.pending_tiles_frame = tk.Frame(pending_canvas_frame, bg=BG2)
        self.pending_tiles_frame.pack(fill="x")

        log_hdr = tk.Frame(outer, bg=BG)
        log_hdr.pack(fill="x", pady=(0,8))
        tk.Label(log_hdr, text="Voucher Log", fg=TEXT, bg=BG,
                 font=(FD,13,"bold")).pack(side="left")

        # FIX #8: show all voucher sessions (full history, no dedup)
        cols = ("Voucher Code","User","PC","Duration","Amount","Status","Started")
        tf = tk.Frame(outer, bg=BG, highlightthickness=1, highlightbackground=BORDER2)
        tf.pack(fill="both", expand=True)
        self.vt_tree = ttk.Treeview(tf, columns=cols, show="headings", height=14)
        widths = {"Voucher Code":160,"User":120,"PC":90,
                  "Duration":90,"Amount":120,"Status":130,"Started":210}
        for c in cols:
            self.vt_tree.heading(c, text=c, anchor="center")
            self.vt_tree.column(c, width=widths.get(c,120), anchor="center", stretch=True)
        self.vt_tree.tag_configure("pending",   background="#1a2a10", foreground=YELLOW)
        self.vt_tree.tag_configure("active",    background="#0d2a1a", foreground=GREEN)
        self.vt_tree.tag_configure("cancelled", background="#300010", foreground=RED)
        self.vt_tree.tag_configure("used",      background=BG3,       foreground=TEXT2)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.vt_tree.yview)
        self.vt_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.vt_tree.pack(fill="both", expand=True)

    def _paste_voucher_code(self, code):
        self.vt_var.set(code)
        self.vt_entry.focus_set()
        self.vt_entry.icursor("end")
        self.vt_msg.config(
            text=f"📋  Code pasted: {code}  — press Activate or Enter", fg=AMBER)

    def _smart_refresh_pending_vouchers(self, data):
        sessions  = data.get("sessions", [])
        computers = data.get("computers", [])
        pending   = [s for s in sessions if s["status"] == "pending_voucher"]
        h         = str([s["id"] for s in sorted(pending, key=lambda x: x["id"])])
        if h == self._last_hash.get("pend_tiles"): return
        self._last_hash["pend_tiles"] = h
        try:
            for w in self.pending_tiles_frame.winfo_children(): w.destroy()
        except: return

        if not pending:
            tk.Label(self.pending_tiles_frame,
                     text="No vouchers waiting for activation.",
                     fg=TEXT4, bg=BG2, font=(FB,10)).pack(anchor="w", pady=4)
            return

        cards_row = tk.Frame(self.pending_tiles_frame, bg=BG2)
        cards_row.pack(fill="x")
        for s in sorted(pending, key=lambda x: str(x.get("start_time") or "")):
            code    = s.get("voucher_code", "?")
            pc      = next((c for c in computers if c["id"] == s["computer_id"]), None)
            pc_name = pc["name"] if pc else "?"
            dur     = s.get("duration", "?")
            user    = s.get("username", "?")
            cost    = fmt_currency(s.get("cost", 0))

            card = tk.Frame(cards_row, bg=BG3, highlightthickness=2,
                            highlightbackground=AMBER)
            card.pack(side="left", padx=(0,12), pady=4)
            accent_bar(card, AMBER, 3).pack(fill="x")
            body = tk.Frame(card, bg=BG3)
            body.pack(padx=14, pady=(10,4))
            code_lbl = tk.Label(body, text=code, fg=AMBER, bg=BG3,
                                font=(FM,13,"bold"), cursor="hand2")
            code_lbl.pack(anchor="center")
            tk.Label(body, text=f"🖥  {pc_name}  ·  {dur} min",
                     fg=TEXT2, bg=BG3, font=(FB,8)).pack(anchor="center", pady=(2,0))
            tk.Label(body, text=f"👤  {user}  ·  {cost}",
                     fg=TEXT3, bg=BG3, font=(FB,8)).pack(anchor="center")
            paste_btn = tk.Button(card, text="📋  Click to Paste",
                                  command=lambda c=code: self._paste_voucher_code(c),
                                  bg=AMBER_DIM, fg=AMBER, font=(FB,9,"bold"),
                                  relief="flat", cursor="hand2",
                                  activebackground=AMBER, activeforeground=BG,
                                  padx=14, pady=7, highlightthickness=0)
            paste_btn.pack(fill="x", padx=8, pady=(6,10))
            for widget in (card, body, code_lbl):
                widget.bind("<Button-1>", lambda e, c=code: self._paste_voucher_code(c))
                widget.bind("<Enter>",    lambda e, f=card: f.config(highlightbackground=AMBER2))
                widget.bind("<Leave>",    lambda e, f=card: f.config(highlightbackground=AMBER))

    def _activate_voucher(self):
        """
        FIX #3: writes end_time = start_time + duration into DB.
        FIX #10: shows error dialog on DB failure.
        """
        code = self.vt_var.get().strip().upper()
        if not code:
            self.vt_msg.config(text="⚠  Please enter a voucher code.", fg=YELLOW)
            return
        rows = db_exec(
            "SELECT * FROM sessions WHERE status='pending_voucher' AND voucher_code=%s",
            (code,), fetch=True)
        if not rows:
            self.vt_msg.config(text="✗  Invalid code or already activated.", fg=RED)
            return
        pending  = norm_session(rows[0])
        now_str  = now_dt_str()
        now_obj  = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
        dur_min  = int(pending.get("duration") or 0)
        end_obj  = now_obj + timedelta(minutes=dur_min)
        end_str  = end_obj.strftime("%Y-%m-%d %H:%M:%S")
        username = pending.get("username", "")

        _, err = db_exec_safe(
            "UPDATE sessions SET status='active', start_time=%s, end_time=%s WHERE id=%s",
            (now_str, end_str, pending["id"]))
        if err:
            ThemedDialog(self, kind="error", title="Activation Failed",
                         message="Could not update session.", detail=err)
            return

        db_exec("UPDATE computers SET status='occupied', current_session_id=%s WHERE id=%s",
                (pending["id"], pending["computer_id"]))

        pay_exists = db_exec(
            "SELECT id FROM payments WHERE session_id=%s AND status='completed'",
            (pending["id"],), fetch=True)
        if not pay_exists:
            db_exec("""
                INSERT IGNORE INTO payments
                  (id, session_id, username, amount, method, timestamp, receipt_no, status)
                VALUES (%s, %s, %s, %s, 'cash', %s, %s, 'completed')
            """, (gen_payment_id(username), pending["id"], username,
                  pending.get("cost", 0), now_str, gen_receipt()))

        pc_rows = db_exec("SELECT name FROM computers WHERE id=%s",
                          (pending["computer_id"],), fetch=True)
        pc_name = pc_rows[0]["name"] if pc_rows else "PC"
        self.vt_var.set("")
        self.vt_msg.config(
            text=f"✓  Activated!  {pc_name} is now live  ·  {dur_min} min  "
                 f"·  Ends at {end_obj.strftime('%I:%M %p')}",
            fg=GREEN)
        self._last_hash = {}

    def _smart_refresh_vouchers(self, data):
        """FIX #8: show full voucher history — no deduplication."""
        sessions  = data.get("sessions", [])
        computers = data.get("computers", [])
        # All sessions that have a voucher_code (full history)
        cash = [s for s in sessions if s.get("voucher_code")]
        cash.sort(key=lambda x: str(x.get("start_time") or ""), reverse=True)
        h = str([(s["id"], s["status"]) for s in cash])
        if h == self._last_hash.get("vouchers"): return
        self._last_hash["vouchers"] = h
        try:
            self.vt_tree.delete(*self.vt_tree.get_children())
        except: return
        for s in cash:
            pc = next((c for c in computers if c["id"] == s["computer_id"]), None)
            st = s["status"]
            if st == "pending_voucher":  sl, tag = "⏳ Waiting",  "pending"
            elif st == "active":         sl, tag = "✅ Active",   "active"
            elif st == "completed":      sl, tag = "✓ Used",      "used"
            elif st == "cancelled":      sl, tag = "✕ Cancelled", "cancelled"
            else:                        sl, tag = st.title(),     "used"
            self.vt_tree.insert("", "end", tags=(tag,), values=(
                s.get("voucher_code", "—"),
                s.get("username", "—"),
                pc["name"] if pc else "?",
                f"{s.get('duration','?')} min",
                fmt_currency(s.get("cost", 0)),
                sl,
                s.get("start_disp", "—"),
            ))

    # ════════════════════════════════════════════════════════════
    #  REPORTS TAB
    # ════════════════════════════════════════════════════════════

    def _build_reports(self):
        f = tk.Frame(self.tab_content, bg=BG)
        f.pack(fill="both", expand=True, padx=40, pady=24)
        date_row = tk.Frame(f, bg=BG)
        date_row.pack(fill="x", pady=(0,16))
        dl = tk.Frame(date_row, bg=BG)
        dl.pack(side="left")
        tk.Label(dl, text="📅", bg=BG, fg=AMBER, font=(FD,16)).pack(side="left", padx=(0,8))
        lc = tk.Frame(dl, bg=BG)
        lc.pack(side="left")
        tk.Label(lc, text="STATISTICS FOR", fg=TEXT3, bg=BG,
                 font=(FB,8,"bold")).pack(anchor="w")
        self.date_lbl = tk.Label(lc, text=today_label(), fg=TEXT, bg=BG,
                                 font=(FD,15,"bold"))
        self.date_lbl.pack(anchor="w")
        self.clock_lbl = tk.Label(date_row,
                                  text=datetime.now().strftime("%I:%M:%S %p"),
                                  fg=AMBER, bg=BG, font=(FM,13,"bold"))
        self.clock_lbl.pack(side="right")
        self._tick_clock()
        hsep(f, BORDER2).pack(fill="x", pady=(0,16))
        stat_outer = tk.Frame(f, bg=BG)
        stat_outer.pack(fill="x", pady=(0,20))
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
        th.pack(fill="x", pady=(0,10))
        tk.Label(th, text="Session History", fg=TEXT, bg=BG,
                 font=(FD,13,"bold")).pack(side="left")
        tk.Button(th, text="⬇  Export CSV", command=self._export_csv,
                  bg=BG3, fg=TEXT2, font=(FB,10,"bold"), relief="flat",
                  cursor="hand2", activebackground=BG4, activeforeground=TEXT,
                  padx=14, pady=7).pack(side="right")
        cols = ("Date","User","PC","Duration","Cost","Method","Status","Receipt")
        tf = tk.Frame(f, bg=BG, highlightthickness=1, highlightbackground=BORDER2)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=14)
        cw = {"Date":180,"User":110,"PC":80,
              "Duration":90,"Cost":110,"Method":90,"Status":110,"Receipt":170}
        for col in cols:
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=cw.get(col,110), anchor="center",
                             minwidth=60, stretch=True)
        self.tree.tag_configure("odd",       background=BG3,       foreground=TEXT)
        self.tree.tag_configure("even",      background=BG2,       foreground=TEXT)
        self.tree.tag_configure("cancelled", background="#300010", foreground=RED)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

    def _tick_clock(self):
        if self._destroyed: return
        try:
            self.clock_lbl.config(text=datetime.now().strftime("%I:%M:%S %p"))
            self.date_lbl.config(text=today_label())
            self.after(1000, self._tick_clock)
        except: pass

    def _smart_refresh_stats(self, data):
        """
        FIX #4: income = payments completed today + sessions with no
        payment row but with a cost (voucher cash sessions).
        """
        sessions  = data.get("sessions", [])
        payments  = data.get("payments", [])
        today_str = today_date_str()

        completed_today = []
        for s in sessions:
            if s["status"] != "completed": continue
            end_dt = parse_dt(s.get("end_time"))
            if end_dt and end_dt.strftime("%Y-%m-%d") == today_str:
                completed_today.append(s)

        # Payments completed today
        today_pay = []
        for p in payments:
            if p.get("status") != "completed": continue
            ts_dt = parse_dt(p.get("timestamp"))
            if ts_dt and ts_dt.strftime("%Y-%m-%d") == today_str:
                today_pay.append(p)

        # Sessions with payments
        paid_session_ids = {p.get("session_id") for p in today_pay}

        # Income from payments
        income = sum(p.get("amount", 0) for p in today_pay)

        # Add income from completed sessions that have NO payment record
        # (e.g. voucher cash sessions recorded before payment table row exists)
        for s in completed_today:
            if s["id"] not in paid_session_ids:
                income += float(s.get("cost", 0))

        total_min = sum(s.get("duration", 0) for s in completed_today)
        try:
            self.stat_cards["sessions"].config(text=str(len(completed_today)))
            self.stat_cards["hours"].config(text=f"{total_min/60:.1f} hrs")
            self.stat_cards["income"].config(text=fmt_currency(income))
        except: pass

    def _smart_refresh_table(self, data):
        sessions  = data.get("sessions", [])
        payments  = data.get("payments", [])
        computers = data.get("computers", [])
        rows = sorted(
            [s for s in sessions if s["status"] in ("completed","cancelled")],
            key=lambda x: str(x.get("end_time") or ""), reverse=True)
        h = str([(s["id"], s["status"]) for s in rows])
        if h == self._last_hash.get("report_table"): return
        self._last_hash["report_table"] = h
        try:
            self.tree.delete(*self.tree.get_children())
        except: return
        for i, s in enumerate(rows):
            pay = next((p for p in payments
                        if p.get("session_id") == s["id"] and
                        p.get("status") == "completed"), None)
            pc  = next((c for c in computers if c["id"] == s["computer_id"]), None)
            is_c = s["status"] == "cancelled"
            tag  = "cancelled" if is_c else ("odd" if i%2 else "even")
            self.tree.insert("", "end", tags=(tag,), values=(
                s.get("end_disp", "—"),
                s.get("username", "—"),
                pc["name"] if pc else "?",
                f"{s.get('duration','?')} min",
                fmt_currency(s.get("cost", 0)),
                (pay["method"].upper() if pay else
                 ("CASH" if s.get("voucher_code") else "—")),
                "Cancelled" if is_c else "Completed",
                pay.get("receipt_no", "—") if pay else "—",
            ))

    # ════════════════════════════════════════════════════════════
    #  USERS TAB
    # ════════════════════════════════════════════════════════════

    def _build_users(self):
        outer = tk.Frame(self.tab_content, bg=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)
        create_card = tk.Frame(outer, bg=BG2, highlightthickness=1,
                               highlightbackground=BORDER2)
        create_card.pack(fill="x", pady=(0,20))
        make_gradient_canvas_h(create_card, height=3, c1=CYAN, c2=PURPLE).pack(fill="x")
        tk.Label(create_card, text="➕  Create Customer Account", fg=TEXT, bg=BG2,
                 font=(FD,13,"bold")).pack(anchor="w", padx=20, pady=(14,2))
        tk.Label(create_card,
                 text="Register a new customer account from the admin portal",
                 fg=TEXT2, bg=BG2, font=(FB,10)).pack(anchor="w", padx=20)
        hsep(create_card, BORDER).pack(fill="x", padx=16, pady=10)
        form_row = tk.Frame(create_card, bg=BG2)
        form_row.pack(padx=20, pady=(0,16), fill="x")

        def _field(parent, label, var, show=None, width=18):
            wrap = tk.Frame(parent, bg=BG2)
            wrap.pack(side="left", padx=(0,12))
            tk.Label(wrap, text=label, fg=TEXT3, bg=BG2,
                     font=(FB,7,"bold")).pack(anchor="w")
            ff = tk.Frame(wrap, bg=BG4, highlightthickness=1,
                          highlightbackground=BORDER2)
            ff.pack(fill="x", pady=(2,0))
            kw = {"show": show} if show else {}
            e = tk.Entry(ff, textvariable=var, width=width,
                         bg=BG4, fg=TEXT, insertbackground=CYAN,
                         font=(FB,11), relief="flat", **kw)
            e.pack(padx=10, pady=8)
            e.bind("<FocusIn>",  lambda _: ff.config(highlightbackground=CYAN))
            e.bind("<FocusOut>", lambda _: ff.config(highlightbackground=BORDER2))
            return e

        self._nu_user = tk.StringVar()
        self._nu_pass = tk.StringVar()
        self._nu_conf = tk.StringVar()
        _field(form_row, "USERNAME", self._nu_user)
        _field(form_row, "PASSWORD", self._nu_pass, show="●")
        e_conf = _field(form_row, "CONFIRM PASSWORD", self._nu_conf, show="●")
        e_conf.bind("<Return>", lambda _: self._create_user())
        btn_wrap = tk.Frame(form_row, bg=BG2)
        btn_wrap.pack(side="left")
        tk.Label(btn_wrap, text=" ", fg=BG2, bg=BG2, font=(FB,7)).pack(anchor="w")
        tk.Button(btn_wrap, text="Create Account", command=self._create_user,
                  bg=CYAN, fg=BG, font=(FB,11,"bold"),
                  relief="flat", cursor="hand2",
                  activebackground=CYAN2, activeforeground=BG,
                  padx=16, pady=8).pack(pady=(2,0))
        self._nu_msg     = tk.Label(create_card, text="", fg=GREEN, bg=BG2, font=(FB,10))
        self._nu_msg.pack(anchor="w", padx=20, pady=(0,10))
        self._nu_msg_job = None

        th = tk.Frame(outer, bg=BG)
        th.pack(fill="x", pady=(0,6))
        tk.Label(th, text="Customer Accounts", fg=TEXT, bg=BG,
                 font=(FD,13,"bold")).pack(side="left")
        self._user_search_var = tk.StringVar()
        self._user_search_var.trace("w", lambda *_: self._filter_users())
        sf = tk.Frame(th, bg=BG4, highlightthickness=1, highlightbackground=BORDER2)
        sf.pack(side="right")
        tk.Label(sf, text="🔍", fg=TEXT3, bg=BG4, font=(FD,10)).pack(side="left", padx=(8,0))
        tk.Entry(sf, textvariable=self._user_search_var, width=22,
                 bg=BG4, fg=TEXT, insertbackground=CYAN,
                 font=(FB,10), relief="flat").pack(padx=8, pady=6, side="left")

        col_hdr = tk.Frame(outer, bg=BG3)
        col_hdr.pack(fill="x")
        hsep(col_hdr, BORDER2).pack(fill="x")
        hdr_inner = tk.Frame(col_hdr, bg=BG3)
        hdr_inner.pack(fill="x", padx=2)
        hdr_inner.columnconfigure(0, weight=2, minsize=180)
        hdr_inner.columnconfigure(1, weight=2, minsize=150)
        hdr_inner.columnconfigure(2, weight=2, minsize=180)
        hdr_inner.columnconfigure(3, weight=0, minsize=280)

        def _hdr_btn(col_idx, text, sort_key):
            btn = tk.Button(hdr_inner, text=text,
                            command=lambda k=sort_key: self._sort_users(k),
                            bg=BG3, fg=TEXT2, font=(FB,9,"bold"),
                            relief="flat", cursor="hand2",
                            activebackground=BG4, activeforeground=TEXT,
                            anchor="center", padx=10, pady=8)
            btn.grid(row=0, column=col_idx, sticky="ew")

        _hdr_btn(0, "USERNAME ↕",      "Username")
        _hdr_btn(1, "REGISTERED PC ↕", "Registered PC")
        _hdr_btn(2, "CREATED AT ↕",    "Created At")
        tk.Label(hdr_inner, text="ACTIONS", bg=BG3, fg=TEXT2,
                 font=(FB,9,"bold"), anchor="center", padx=10).grid(
            row=0, column=3, sticky="ew")
        hsep(col_hdr, BORDER2).pack(fill="x")

        list_outer = tk.Frame(outer, bg=BG, highlightthickness=1,
                              highlightbackground=BORDER2)
        list_outer.pack(fill="both", expand=True)
        self._user_canvas = tk.Canvas(list_outer, bg=BG, highlightthickness=0)
        user_vsb = ttk.Scrollbar(list_outer, orient="vertical",
                                  command=self._user_canvas.yview)
        self._user_canvas.configure(yscrollcommand=user_vsb.set)
        user_vsb.pack(side="right", fill="y")
        self._user_canvas.pack(fill="both", expand=True)
        self._user_list_frame = tk.Frame(self._user_canvas, bg=BG)
        self._user_list_wid   = self._user_canvas.create_window(
            (0,0), window=self._user_list_frame, anchor="nw")
        self._user_canvas.bind(
            "<Configure>",
            lambda e: self._user_canvas.itemconfig(self._user_list_wid, width=e.width))
        self._user_list_frame.bind(
            "<Configure>",
            lambda e: self._user_canvas.configure(
                scrollregion=self._user_canvas.bbox("all")))
        # FIX #6: use per-canvas bind instead of bind_all
        self._bind_mousewheel(self._user_canvas)

        self._all_users_cache   = []
        self._user_sort_col     = "Username"
        self._user_sort_reverse = False

    def _set_nu_msg(self, text, color=GREEN):
        if self._nu_msg_job:
            try: self.after_cancel(self._nu_msg_job)
            except: pass
        self._nu_msg.config(text=text, fg=color)
        self._nu_msg_job = self.after(2500, lambda: self._nu_msg.config(text=""))

    def _sort_users(self, col):
        if self._user_sort_col == col:
            self._user_sort_reverse = not self._user_sort_reverse
        else:
            self._user_sort_col     = col
            self._user_sort_reverse = False
        self._filter_users()

    def _create_user(self):
        """FIX #2: id uses gen_user_id() — unique timestamp string, not username."""
        u = self._nu_user.get().strip()
        p = self._nu_pass.get().strip()
        c = self._nu_conf.get().strip()
        if not u or not p or not c:
            self._set_nu_msg("⚠  Fill in all fields.", YELLOW); return
        if len(u) < 3:
            self._set_nu_msg("✗  Username must be at least 3 characters.", RED); return
        if len(p) < 6:
            self._set_nu_msg("✗  Password must be at least 6 characters.", RED); return
        if p != c:
            self._set_nu_msg("✗  Passwords do not match.", RED); return
        existing = db_exec("SELECT id FROM users WHERE username=%s", (u,), fetch=True)
        if existing:
            self._set_nu_msg(f"✗  Username '{u}' is already taken.", RED); return
        dt_str   = now_dt_str()
        new_id   = gen_user_id(u)   # FIX #2
        _, err = db_exec_safe("""
            INSERT INTO users (id, username, password, role, registered_on_pc, created_at)
            VALUES (%s, %s, %s, 'customer', 'admin-portal', %s)
        """, (new_id, u, p, dt_str))
        if err:
            self._set_nu_msg(f"✗  DB error: {err[:60]}", RED); return
        self._nu_user.set("")
        self._nu_pass.set("")
        self._nu_conf.set("")
        self._set_nu_msg(f"✓  Customer account '{u}' created successfully!", GREEN)
        self._last_hash.pop("users", None)

    def _smart_refresh_users(self, data):
        users = data.get("users", [])
        h     = str([(u.get("id"), u.get("username")) for u in users])
        if h == self._last_hash.get("users"): return
        self._last_hash["users"] = h
        self._all_users_cache    = users
        self._filter_users()

    def _filter_users(self):
        q = (self._user_search_var.get().strip().lower()
             if hasattr(self, "_user_search_var") else "")
        filtered = self._all_users_cache
        if q:
            filtered = [u for u in filtered
                        if q in str(u.get("username","")).lower()
                        or q in str(u.get("registered_on_pc","")).lower()]
        self._render_user_list(filtered)

    def _render_user_list(self, users):
        try:
            for w in self._user_list_frame.winfo_children(): w.destroy()
        except: return

        col_map = {
            "Username":      lambda u: str(u.get("username","")).lower(),
            "Registered PC": lambda u: str(u.get("registered_on_pc","")).lower(),
            "Created At":    lambda u: str(u.get("created_at") or ""),
        }
        sort_fn = col_map.get(getattr(self,"_user_sort_col","Username"),
                               col_map["Username"])
        try:
            users = sorted(users, key=sort_fn,
                           reverse=getattr(self,"_user_sort_reverse",False))
        except: pass

        if not users:
            tk.Label(self._user_list_frame, text="No customers found.",
                     fg=TEXT3, bg=BG, font=(FB,10)).pack(anchor="w", padx=16, pady=12)
            return

        self._user_list_frame.columnconfigure(0, weight=2, minsize=180)
        self._user_list_frame.columnconfigure(1, weight=2, minsize=150)
        self._user_list_frame.columnconfigure(2, weight=2, minsize=180)
        self._user_list_frame.columnconfigure(3, weight=0, minsize=280)

        for i, u in enumerate(users):
            dt_disp = fmt_dt_short(u.get("created_at"))
            bg      = BG3 if i%2 else BG2
            uname   = u.get("username","—")
            tk.Label(self._user_list_frame, text=uname,
                     fg=TEXT, bg=bg, font=(FB,10,"bold"),
                     anchor="center", padx=10, pady=10).grid(
                row=i*2, column=0, sticky="ew")
            tk.Label(self._user_list_frame,
                     text=u.get("registered_on_pc") or "—",
                     fg=TEXT2, bg=bg, font=(FB,10),
                     anchor="center", padx=10, pady=10).grid(
                row=i*2, column=1, sticky="ew")
            tk.Label(self._user_list_frame, text=dt_disp,
                     fg=TEXT2, bg=bg, font=(FB,10),
                     anchor="center", padx=10, pady=10).grid(
                row=i*2, column=2, sticky="ew")
            actions_cell = tk.Frame(self._user_list_frame, bg=bg)
            actions_cell.grid(row=i*2, column=3, sticky="nsew", padx=8)
            self._build_action_row(actions_cell, uname, bg)
            hsep(self._user_list_frame, BORDER, 1).grid(
                row=i*2+1, column=0, columnspan=4, sticky="ew")

    def _build_action_row(self, cell, uname, bg):
        for w in cell.winfo_children(): w.destroy()
        inner = tk.Frame(cell, bg=bg)
        inner.pack(anchor="center", expand=True)
        tk.Button(inner, text="🔑  Reset PW",
                  command=lambda: ResetPasswordDialog(self, uname),
                  bg=CYAN_DIM, fg=CYAN, font=(FB,9,"bold"),
                  relief="flat", cursor="hand2",
                  activebackground=CYAN, activeforeground=BG,
                  highlightthickness=1, highlightbackground=CYAN,
                  padx=10, pady=6).pack(side="left", padx=(0,8))
        tk.Button(inner, text="🗑  Delete",
                  command=lambda un=uname: ConfirmDialog(
                      self,
                      title="Delete Account",
                      message=f'Permanently delete "{un}"?',
                      on_confirm=lambda: self._do_delete_user(un)),
                  bg=RED_DIM, fg=RED, font=(FB,9,"bold"),
                  relief="flat", cursor="hand2",
                  activebackground=RED, activeforeground=TEXT,
                  highlightthickness=1, highlightbackground=RED,
                  padx=10, pady=6).pack(side="left")

    def _do_delete_user(self, username):
        _, err = db_exec_safe("DELETE FROM users WHERE username=%s", (username,))
        if err:
            ThemedDialog(self, kind="error", title="Delete Failed", detail=err)
            return
        self._last_hash.pop("users", None)

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
        pc_id = f"pc-{datetime.now().strftime('%m-%d-%Y-%H-%M-%S')}"
        _, err = db_exec_safe(
            "INSERT INTO computers (id, name, status, created_at) VALUES (%s,%s,'available',%s)",
            (pc_id, name, now_dt_str()))
        if err:
            ThemedDialog(self, kind="error", title="Add PC Failed", detail=err)
            return
        self.new_pc_var.set("")
        self._last_hash.pop("fleet", None)

    def _del_pc(self, cid, name):
        ConfirmDialog(self, title="Delete PC",
                      message=f'Delete "{name}"? This cannot be undone.',
                      on_confirm=lambda: self._do_del_pc(cid))

    def _do_del_pc(self, cid):
        _, err = db_exec_safe("DELETE FROM computers WHERE id=%s", (cid,))
        if err:
            ThemedDialog(self, kind="error", title="Delete Failed", detail=err)
            return
        self._last_hash.pop("fleet", None)

    def _toggle_maint(self, cid):
        rows = db_exec("SELECT status FROM computers WHERE id=%s", (cid,), fetch=True)
        if not rows: return
        new_status = ("available" if rows[0]["status"] == "maintenance"
                      else "maintenance")
        db_exec("UPDATE computers SET status=%s WHERE id=%s", (new_status, cid))
        self._last_hash.pop("fleet", None)

    # ════════════════════════════════════════════════════════════
    #  CSV EXPORT
    # ════════════════════════════════════════════════════════════

    def _export_csv(self):
        data      = self._get_data()
        sessions  = data.get("sessions", [])
        payments  = data.get("payments", [])
        computers = data.get("computers", [])
        relevant  = [s for s in sessions if s["status"] in ("completed","cancelled")]
        filename  = f"timenet_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Date","Session ID","User","PC","Duration (min)",
                            "Cost (PHP)","Payment Method","Status","Receipt No"])
                for s in sorted(relevant, key=lambda x: str(x.get("end_time") or ""), reverse=True):
                    pay = next((p for p in payments
                                if p.get("session_id") == s["id"] and
                                p.get("status") == "completed"), None)
                    pc  = next((c for c in computers if c["id"] == s["computer_id"]), None)
                    w.writerow([
                        s.get("end_disp",""),
                        s["id"],
                        s.get("username",""),
                        pc["name"] if pc else "?",
                        s.get("duration",""),
                        f"{float(s.get('cost',0)):.2f}",
                        pay["method"] if pay else ("cash" if s.get("voucher_code") else ""),
                        s["status"],
                        pay.get("receipt_no","") if pay else "",
                    ])
            ThemedDialog(self, kind="success", title="Export Successful",
                         message=f"{len(relevant)} session(s) exported.",
                         detail=os.path.abspath(filename),
                         auto_dismiss_ms=3000)
        except Exception as e:
            ThemedDialog(self, kind="error", title="Export Failed",
                         message="Could not write the CSV file.", detail=str(e))

# ════════════════════════════════════════════════════════════════════
#  RESET PASSWORD DIALOG
# ════════════════════════════════════════════════════════════════════

class ResetPasswordDialog(tk.Toplevel):
    def __init__(self, parent, username, on_done=None):
        super().__init__(parent)
        self.username = username
        self.on_done  = on_done
        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()
        self.bind("<Escape>", lambda _: self._close())
        self._build()
        self.update_idletasks()
        w  = 460
        h  = max(self.winfo_reqheight()+60, 360)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.update_idletasks()
        add_gradient_border(self, thickness=3, c1=CYAN, c2=PURPLE)

    def _build(self):
        outer = tk.Frame(self, bg=BG2)
        outer.pack(fill="both", expand=True, padx=3, pady=3)
        make_gradient_canvas_h(outer, height=3, c1=CYAN, c2=PURPLE).pack(fill="x")
        tk.Label(outer, text="🔑  Reset Password", bg=BG2, fg=TEXT,
                 font=(FD,14,"bold")).pack(pady=(20,2))
        tk.Label(outer, text=self.username, bg=BG2, fg=CYAN,
                 font=(FM,12,"bold")).pack(pady=(0,10))
        hsep(outer, BORDER2).pack(fill="x", padx=24, pady=(0,16))
        self._new_pw  = tk.StringVar()
        self._conf_pw = tk.StringVar()

        def _make_field(parent, label, var):
            lf = tk.Frame(parent, bg=BG2)
            lf.pack(padx=28, fill="x", pady=(0,10))
            tk.Label(lf, text=label, fg=TEXT3, bg=BG2,
                     font=(FB,7,"bold")).pack(anchor="w")
            ef = tk.Frame(lf, bg=BG4, highlightthickness=1,
                          highlightbackground=BORDER2)
            ef.pack(fill="x", pady=(3,0))
            e = tk.Entry(ef, textvariable=var, show="●",
                         bg=BG4, fg=TEXT, insertbackground=CYAN,
                         font=(FB,12), relief="flat")
            e.pack(padx=12, pady=9, fill="x")
            e.bind("<FocusIn>",  lambda _: ef.config(highlightbackground=CYAN))
            e.bind("<FocusOut>", lambda _: ef.config(highlightbackground=BORDER2))
            return e

        _make_field(outer, "NEW PASSWORD", self._new_pw).focus_set()
        _make_field(outer, "CONFIRM PASSWORD", self._conf_pw).bind(
            "<Return>", lambda _: self._save())

        self._msg = tk.Label(outer, text="", fg=GREEN, bg=BG2,
                             font=(FB,9), anchor="w")
        self._msg.pack(padx=28, fill="x", pady=(4,0))
        hsep(outer, BORDER2).pack(fill="x", padx=24, pady=(14,0))
        btn_row = tk.Frame(outer, bg=BG2)
        btn_row.pack(padx=28, pady=(14,24), fill="x")
        tk.Button(btn_row, text="Cancel", command=self._close,
                  bg=BG4, fg=TEXT2, font=(FB,11,"bold"),
                  relief="flat", cursor="hand2",
                  activebackground=BG5, activeforeground=TEXT,
                  padx=16, pady=12).pack(side="left", expand=True, fill="x", padx=(0,8))
        tk.Button(btn_row, text="Save Password", command=self._save,
                  bg=CYAN, fg=BG, font=(FB,11,"bold"),
                  relief="flat", cursor="hand2",
                  activebackground=CYAN2, activeforeground=BG,
                  padx=16, pady=12).pack(side="left", expand=True, fill="x")

    def _save(self):
        pw   = self._new_pw.get().strip()
        conf = self._conf_pw.get().strip()
        if not pw:
            self._msg.config(text="✗  Please enter a new password.", fg=RED); return
        if len(pw) < 6:
            self._msg.config(text="✗  Minimum 6 characters required.", fg=RED); return
        if pw != conf:
            self._msg.config(text="✗  Passwords do not match.", fg=RED); return
        _, err = db_exec_safe(
            "UPDATE users SET password=%s WHERE username=%s", (pw, self.username))
        if err:
            self._msg.config(text=f"✗  DB error: {err[:50]}", fg=RED); return
        self._msg.config(text="✓  Password updated successfully.", fg=GREEN)
        self.after(900, self._close)

    def _close(self):
        try:
            self.grab_release()
            self.destroy()
        except: pass
        if self.on_done:
            self.on_done()

# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()