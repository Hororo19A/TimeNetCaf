"""
dashboard/lockscreen.py — Kiosk lock/unlock helpers and overlay dialogs.

Contains:
  • AdminPinDialog  — fullscreen-safe PIN prompt for forced exit
  • GraceOverlay    — countdown overlay shown after a session ends
"""

import tkinter as tk
from ui.theme import BG, BG2, BG3, BORDER, TEXT, TEXT2, CYAN, RED, YELLOW
from ui.widget import btn
from ui.theme import ADMIN_EXIT_PIN, GRACE_SECONDS


# ═══════════════════════════════════════════════════════════════
#  ADMIN PIN DIALOG
# ═══════════════════════════════════════════════════════════════

class AdminPinDialog(tk.Toplevel):
    """
    PIN entry dialog that stays above a fullscreen kiosk window.
    Calls on_success() when the correct PIN is entered.
    """

    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success

        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()

        w, h = 320, 220
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._build()
        self.bind("<Return>", lambda _: self._check())

    def _build(self):
        tk.Label(self, text="🔐  Admin Exit", bg=BG2, fg=RED,
                 font=("Segoe UI", 14, "bold")).pack(pady=(24, 6))
        tk.Label(self, text="Enter admin PIN to exit kiosk mode:",
                 bg=BG2, fg=TEXT2, font=("Segoe UI", 10)).pack(pady=(0, 12))

        self.pin_var = tk.StringVar()
        e = tk.Entry(
            self,
            textvariable=self.pin_var,
            show="●",
            width=16,
            bg=BG, fg=TEXT,
            insertbackground=TEXT,
            font=("Segoe UI", 16, "bold"),
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=CYAN,
        )
        e.pack(ipady=8, pady=(0, 6))
        e.focus_set()

        self.err = tk.Label(self, text="", bg=BG2, fg=RED,
                            font=("Segoe UI", 9))
        self.err.pack(pady=(0, 10))

        row = tk.Frame(self, bg=BG2)
        row.pack(padx=20, fill="x")
        btn(row, "Cancel", command=self.destroy,
            bg=BG3, fg=TEXT, pad=(10, 5)).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        btn(row, "Confirm", command=self._check,
            bg=RED, fg=TEXT, pad=(10, 5)).pack(
            side="left", expand=True, fill="x")

    def _check(self):
        if self.pin_var.get() == ADMIN_EXIT_PIN:
            self.destroy()
            self.on_success()
        else:
            self.err.config(text="Incorrect PIN. Try again.")
            self.pin_var.set("")


# ═══════════════════════════════════════════════════════════════
#  GRACE PERIOD OVERLAY
# ═══════════════════════════════════════════════════════════════

class GraceOverlay(tk.Toplevel):
    """
    Floating countdown shown after a session expires.
    After GRACE_SECONDS seconds (or when "Lock Now" is clicked)
    it calls on_expired().
    """

    def __init__(self, app, seconds: int, on_expired):
        super().__init__(app)
        self.remaining  = seconds
        self.on_expired = on_expired

        self.title("TimeNet — Session Ended")
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.overrideredirect(False)
        self.geometry("340x180+20+160")
        self.protocol("WM_DELETE_WINDOW", lambda: None)   # block close button

        self._build()
        self._tick()

    def _build(self):
        tk.Label(self, text="⏰  Time's Up!", bg=BG2, fg=RED,
                 font=("Segoe UI", 14, "bold")).pack(pady=(16, 4))
        self.msg = tk.Label(self, text="", bg=BG2, fg=YELLOW,
                            font=("Segoe UI", 11))
        self.msg.pack(pady=(0, 6))
        tk.Label(self,
                 text="Please purchase a new session\nor log out at the screen.",
                 bg=BG2, fg=TEXT2, font=("Segoe UI", 9)).pack(pady=(0, 8))
        btn(self, "🔒  Lock Now", command=self._lock_now,
            bg=RED, fg=TEXT,
            font=("Segoe UI", 10, "bold")).pack(pady=(0, 14), padx=20, fill="x")

    def _tick(self):
        if self.remaining <= 0:
            self._lock_now()
            return
        mins, secs = divmod(self.remaining, 60)
        self.msg.config(text=f"Locking in {mins:02d}:{secs:02d}…")
        self.remaining -= 1
        self.after(1000, self._tick)

    def _lock_now(self):
        self.on_expired()