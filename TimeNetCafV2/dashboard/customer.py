"""
dashboard/customer.py — Customer dashboard and payment dialog.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from database.database import storage, now_ms, format_currency
from auth.login import AuthState
from services.session import (
    create_session,
    end_session,
    get_active_session_for_user,
    get_first_available_computer,
)
from services.billing import calc_cost
from ui.theme import (
    BG, BG2, BG3, BORDER, TEXT, TEXT2,
    CYAN, GREEN, RED, YELLOW, PURPLE,
    HOURLY_RATE, PRICING_TIERS, GRACE_SECONDS,
)
from ui.widget import styled_frame, label, heading, entry, btn, separator


# ═══════════════════════════════════════════════════════════════
#  PAYMENT DIALOG
# ═══════════════════════════════════════════════════════════════

class PaymentDialog(tk.Toplevel):
    def __init__(self, parent, computer_name: str, duration: int,
                 cost: float, on_complete):
        super().__init__(parent)
        self.on_complete    = on_complete
        self.computer_name  = computer_name
        self.duration       = duration
        self.cost           = cost
        self.method         = tk.StringVar(value="cash")

        self.configure(bg=BG2)
        self.overrideredirect(True)
        self.grab_set()
        self._build()
        self.update_idletasks()
        w, h = 440, 520
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self):
        heading(self, "💳 Pay First", bg=BG2).pack(pady=(20, 4))
        label(self, "Complete payment to start your session",
              fg=TEXT2, bg=BG2).pack()
        separator(self, bg=BORDER).pack(fill="x", padx=20, pady=10)

        summ = styled_frame(self, bg=BG)
        summ.pack(padx=20, fill="x")
        for lbl_text, val in [
            ("Computer", self.computer_name),
            ("Duration", f"{self.duration} minutes"),
            ("Total",    format_currency(self.cost)),
        ]:
            r = styled_frame(summ, bg=BG)
            r.pack(fill="x", padx=10, pady=3)
            label(r, lbl_text, fg=TEXT2, bg=BG).pack(side="left")
            label(r, val,
                  fg=(GREEN if lbl_text == "Total" else TEXT),
                  bg=BG,
                  font=("Segoe UI", 10,
                        "bold" if lbl_text == "Total" else "normal")
                  ).pack(side="right")

        separator(self, bg=BORDER).pack(fill="x", padx=20, pady=10)

        label(self, "Select Payment Method:", fg=TEXT2, bg=BG2).pack()
        mf = styled_frame(self, bg=BG2)
        mf.pack(pady=6)
        for txt, val in [("💵 Cash", "cash"),
                         ("📱 GCash", "gcash"),
                         ("💳 Maya",  "maya")]:
            tk.Radiobutton(
                mf, text=txt, variable=self.method, value=val,
                bg=BG2, fg=TEXT, selectcolor=BG3,
                font=("Segoe UI", 10), activebackground=BG2,
                activeforeground=TEXT, cursor="hand2",
                command=self._on_method_change,
            ).pack(side="left", padx=12)

        self.note_lbl = label(self, "", fg=TEXT2, bg=BG2, wraplength=380)
        self.note_lbl.pack(pady=6, padx=20)
        self._on_method_change()

        separator(self, bg=BORDER).pack(fill="x", padx=20, pady=8)

        bf = styled_frame(self, bg=BG2)
        bf.pack(padx=20, pady=(0, 20), fill="x")
        btn(bf, "Cancel", command=self.destroy,
            bg=BG3, fg=TEXT).pack(
            side="left", expand=True, fill="x", padx=(0, 6), ipady=6)
        btn(bf, f"Confirm — {format_currency(self.cost)}",
            command=self._confirm,
            bg=CYAN, fg=BG).pack(
            side="left", expand=True, fill="x", ipady=6)

    def _on_method_change(self):
        notes = {
            "cash":  "💵 Pay at the counter. You'll receive a voucher code that the admin will use to activate your PC.",
            "gcash": "📱 GCash: Send payment to 09671871430 then confirm.",
            "maya":  "💳 Maya: Send payment to 09671871430 then confirm.",
        }
        self.note_lbl.config(text=notes.get(self.method.get(), ""))

    def _confirm(self):
        method = self.method.get()
        self.destroy()
        self.on_complete(method)


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER DASHBOARD
# ═══════════════════════════════════════════════════════════════

class CustomerDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app               = app
        self.selected_tier     = None
        self.active_session    = None
        self.assigned_computer = None
        self._tick_running     = False
        self._build()
        self._load_data()
        self._poll()

    # ── Layout shell ──────────────────────────────────────────

    def _build(self):
        self.hdr = styled_frame(self, bg=BG2)
        self.hdr.pack(fill="x")
        self.hdr_sep = separator(self)
        inner = styled_frame(self.hdr, bg=BG2)
        inner.pack(fill="x", padx=30, pady=14)
        self.title_lbl = heading(
            inner, f"👤  {AuthState.user['username']}", size=15, bg=BG2)
        self.title_lbl.pack(side="left")
        self.logout_btn = btn(
            inner, "Sign Out", command=self._logout,
            bg=BG3, fg=TEXT, pad=(14, 6), font=("Segoe UI", 10, "bold"))
        self.logout_btn.pack(side="right")

        self.hdr_sep.pack(fill="x")

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self._show_booking()

    # ── Booking screen ────────────────────────────────────────

    def _show_booking(self):
        for w in self.content.winfo_children():
            w.destroy()

        if not self.assigned_computer:
            c = tk.Frame(self.content, bg=BG)
            c.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(c, text="🖥", font=("", 56), bg=BG, fg=TEXT2).pack(pady=(0, 10))
            heading(c, "No Computers Available", bg=BG, size=18).pack()
            label(c, "All computers are currently in use. Please try again later.",
                  fg=TEXT2, bg=BG, font=("Segoe UI", 11)).pack(pady=8)
            return

        canvas = tk.Canvas(self.content, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(self.content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        inner  = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        col = tk.Frame(inner, bg=BG)
        col.pack(expand=True, anchor="center")

        info = styled_frame(col, bg=BG2)
        info.pack(pady=24, fill="x", ipadx=40)
        heading(info, f"🖥  You are using {self.assigned_computer['name']}",
                size=17, bg=BG2).pack(pady=(18, 6))
        label(info, f"⚡ {format_currency(HOURLY_RATE)} / hour",
              fg=CYAN, bg=BG2, font=("Segoe UI", 12, "bold")).pack(pady=(0, 18))

        picker = styled_frame(col, bg=BG2)
        picker.pack(fill="x")
        heading(picker, "⏱  How long do you want to use the PC?",
                size=12, bg=BG2).pack(anchor="center", padx=20, pady=(16, 8))
        separator(picker).pack(fill="x", padx=20)

        grid = styled_frame(picker, bg=BG2)
        grid.pack(padx=20, pady=16)

        self.tier_btns: dict = {}
        for idx, tier in enumerate(PRICING_TIERS):
            cost  = calc_cost(tier["minutes"])
            col_n = idx % 4
            row_n = idx // 4
            f = tk.Frame(grid, bg=BG3, relief="flat", bd=1,
                         cursor="hand2", width=160, height=72)
            f.grid(row=row_n, column=col_n, padx=6, pady=6, sticky="nsew")
            f.pack_propagate(False)
            grid.columnconfigure(col_n, weight=1)
            lbl1 = tk.Label(f, text=tier["label"], bg=BG3, fg=TEXT2,
                            font=("Segoe UI", 10))
            lbl1.pack(pady=(10, 2))
            lbl2 = tk.Label(f, text=format_currency(cost), bg=BG3, fg=GREEN,
                            font=("Segoe UI", 14, "bold"))
            lbl2.pack(pady=(0, 10))
            mins = tier["minutes"]
            for w in (f, lbl1, lbl2):
                w.bind("<Button-1>", lambda e, m=mins: self._select_tier(m))
            self.tier_btns[mins] = (f, lbl1, lbl2)

        self.pay_btn = btn(col, "Select a time to continue",
                           command=self._proceed_payment,
                           bg=BG3, fg=TEXT2, font=("Segoe UI", 12, "bold"))
        self.pay_btn.pack(pady=18, fill="x", ipady=12)
        self.pay_btn.config(state="disabled")

    def _select_tier(self, minutes: int):
        if self.selected_tier and self.selected_tier in self.tier_btns:
            f, l1, l2 = self.tier_btns[self.selected_tier]
            f.config(bg=BG3)
            l1.config(bg=BG3, fg=TEXT2)
            l2.config(bg=BG3, fg=GREEN)
        self.selected_tier = minutes
        f, l1, l2 = self.tier_btns[minutes]
        f.config(bg="#0e4a5a")
        l1.config(bg="#0e4a5a", fg=CYAN)
        l2.config(bg="#0e4a5a", fg=TEXT)
        cost = calc_cost(minutes)
        self.pay_btn.config(
            text=f"Pay {format_currency(cost)} & Start",
            bg=CYAN, fg=BG, state="normal")

    def _proceed_payment(self):
        if not self.selected_tier or not self.assigned_computer:
            return
        cost = calc_cost(self.selected_tier)
        PaymentDialog(
            self,
            self.assigned_computer["name"],
            self.selected_tier,
            cost,
            self._on_payment_complete,
        )

    def _on_payment_complete(self, method: str):
        if not AuthState.user or not self.assigned_computer or not self.selected_tier:
            return

        result = create_session(
            user_id     = AuthState.user["id"],
            computer_id = self.assigned_computer["id"],
            minutes     = self.selected_tier,
            method      = method,
        )

        if method == "cash":
            messagebox.showinfo(
                "Go to Counter",
                f"Please pay {format_currency(result['session']['cost'])} at the counter.\n\n"
                f"Your Voucher Code: {result['voucher_code']}\n\n"
                "Show this code to the admin. They will activate your PC.",
            )
            self.app.logout()
        else:
            self.active_session = result["session"]
            self._show_active_session()

    # ── Active session screen ─────────────────────────────────

    def _show_active_session(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.hdr.pack_forget()
        self.hdr_sep.pack_forget()

        computers = storage.get_computers()
        computer  = next(
            (c for c in computers
             if c["id"] == self.active_session["computerId"]),
            None,
        )
        if self.app._locked:
            self.app.unlock_for_session()
        if computer:
            self._session_widget(computer)

    def _session_widget(self, computer):
        outer = tk.Frame(self.content, bg=BG2)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text=f"🖥  {computer['name']}", fg=TEXT2, bg=BG2,
                 font=("Segoe UI", 9, "bold")).pack(pady=(6, 0))

        self.time_lbl = tk.Label(outer, text="00:00:00", fg=TEXT, bg=BG2,
                                 font=("Segoe UI", 24, "bold"))
        self.time_lbl.pack(pady=(0, 2))

        self.prog = ttk.Progressbar(
            outer, maximum=100, value=100,
            style="Session.Horizontal.TProgressbar")
        self.prog.pack(fill="x", padx=8, pady=(0, 3))

        row_pct = tk.Frame(outer, bg=BG2)
        row_pct.pack(fill="x", padx=8)
        self.pct_lbl = tk.Label(row_pct, text="100%", fg=CYAN, bg=BG2,
                                font=("Segoe UI", 8, "bold"))
        self.pct_lbl.pack(side="left")

        total_min = self.active_session.get("duration", 60)
        start_ms  = self.active_session.get("startTime", now_ms())
        end_dt    = datetime.fromtimestamp(
            (start_ms + total_min * 60 * 1000) / 1000)

        if total_min >= 60 and total_min % 60 == 0:
            dur_str = f"{total_min // 60}h"
        elif total_min >= 60:
            dur_str = f"{total_min // 60}h {total_min % 60}m"
        else:
            dur_str = f"{total_min}m"

        tk.Label(row_pct, text=f"⏱ {dur_str} session", fg=TEXT2, bg=BG2,
                 font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))
        tk.Label(row_pct, text=f"Ends {end_dt.strftime('%I:%M %p')}",
                 fg=YELLOW, bg=BG2,
                 font=("Segoe UI", 8, "bold")).pack(side="right")

        if not self._tick_running:
            self._tick_running = True
            self._tick()

    # ── Session countdown tick ────────────────────────────────

    def _tick(self):
        if not self.active_session:
            self._tick_running = False
            return
        try:
            self.time_lbl.winfo_exists()
        except Exception:
            self._tick_running = False
            return

        total_min = self.active_session.get("duration", 60)
        end_time  = self.active_session["startTime"] + total_min * 60 * 1000
        diff      = end_time - now_ms()

        if diff <= 0:
            try:
                self.time_lbl.config(text="00:00:00", fg=RED)
                self.prog["value"] = 0
                self.pct_lbl.config(text="Time's Up!", fg=RED)
            except Exception:
                pass
            self._tick_running = False
            self.after(1500, self._end_session_and_grace)
            return

        try:
            hrs  = int(diff // 3_600_000)
            mins = int((diff % 3_600_000) // 60_000)
            secs = int((diff % 60_000) // 1000)
            self.time_lbl.config(text=f"{hrs:02d}:{mins:02d}:{secs:02d}")

            total_ms = total_min * 60 * 1000
            pct      = max(0, diff / total_ms * 100)
            self.prog["value"] = pct
            bar_color = RED if pct < 10 else (YELLOW if pct < 20 else CYAN)
            try:
                self.winfo_toplevel().tk.call(
                    "ttk::style", "configure",
                    "Session.Horizontal.TProgressbar",
                    "-background", bar_color)
            except Exception:
                pass
            self.time_lbl.config(fg=(YELLOW if pct < 20 else TEXT))
            self.pct_lbl.config(
                text=f"{pct:.0f}%",
                fg=(YELLOW if pct < 20 else CYAN))
        except Exception:
            self._tick_running = False
            return

        self.after(1000, self._tick)

    def _end_session_and_grace(self):
        if not self.active_session:
            return
        end_session(self.active_session["id"])
        self.active_session    = None
        self.selected_tier     = None
        self.assigned_computer = None

        if GRACE_SECONDS > 0:
            self.app.unlock_for_grace(self._on_grace_expired)
        else:
            self._on_grace_expired()

    def _on_grace_expired(self):
        self.app.relock()
        self._restore_and_reload()

    def _restore_and_reload(self):
        try:
            self.hdr.pack(fill="x", before=self.content)
            self.hdr_sep.pack(fill="x", before=self.content)
        except Exception:
            pass
        self._load_data()

    # ── Data loading / polling ────────────────────────────────

    def _load_data(self):
        uid    = AuthState.user["id"] if AuthState.user else None
        active = get_active_session_for_user(uid) if uid else None

        if active:
            self.active_session = active
            self._show_active_session()
            return

        try:
            self.hdr.pack(fill="x", before=self.content)
        except Exception:
            self.hdr.pack(fill="x")
        try:
            self.hdr_sep.pack(fill="x", before=self.content)
        except Exception:
            self.hdr_sep.pack(fill="x")

        self.logout_btn.pack(side="right")
        self.title_lbl.config(text=f"👤  {AuthState.user['username']}")
        self.assigned_computer = get_first_available_computer()
        self._show_booking()

    def _poll(self):
        if not self.active_session:
            self._load_data()
        self.after(10_000, self._poll)

    def _logout(self):
        self.app.logout()