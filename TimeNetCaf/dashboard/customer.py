import customtkinter as ctk
import time
from datetime import datetime
from ui.theme import T
from ui.widget import lbl, btn, Entry, card
from database.database import DB, fmt_php, fmt_elapsed, HOURLY_RATE, MINUTE_RATE


# ──────────────────────────────────────────────────────────────────────────────
#  Floating Timer Window  (shown while app is "unlocked" / minimized)
# ──────────────────────────────────────────────────────────────────────────────
class FloatingTimer(ctk.CTkToplevel):
    """Small always-on-top timer shown while the customer is free to use the PC."""

    def __init__(self, master, remaining_seconds: int, on_expired, on_buy_more, on_logout):
        super().__init__(master)
        self._remaining = remaining_seconds
        self._on_expired = on_expired
        self._on_buy_more = on_buy_more
        self._on_logout = on_logout
        self._job = None

        # ── window chrome ──────────────────────────────────────────────────
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#1a1a2e")
        self.resizable(False, False)

        w, h = 260, 170
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - 60}")

        # allow dragging
        self.bind("<ButtonPress-1>",   self._drag_start)
        self.bind("<B1-Motion>",       self._drag_move)

        self._build()
        self._tick()

    # ── drag helpers ──────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx = e.x
        self._dy = e.y

    def _drag_move(self, e):
        x = self.winfo_x() + e.x - self._dx
        y = self.winfo_y() + e.y - self._dy
        self.geometry(f"+{x}+{y}")

    # ── UI ────────────────────────────────────────────────────────────────
    def _build(self):
        outer = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12,
                             border_color="#3a3a5c", border_width=2)
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(outer, text="⏱  TIME REMAINING",
                     font=("Segoe UI", 10, "bold"),
                     text_color="#8888aa").pack(pady=(12, 0))

        self._tlbl = ctk.CTkLabel(outer, text="00:00:00",
                                  font=("Segoe UI", 30, "bold"),
                                  text_color="#00d4ff")
        self._tlbl.pack(pady=(4, 10))

        bf = ctk.CTkFrame(outer, fg_color="transparent")
        bf.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkButton(bf, text="＋ Buy More",
                      font=("Segoe UI", 11, "bold"),
                      fg_color="#00d4ff", hover_color="#0099bb",
                      text_color="#000000", corner_radius=6, height=30,
                      command=self._buy_more).pack(side="left", expand=True, padx=(0, 4))

        ctk.CTkButton(bf, text="Sign Out",
                      font=("Segoe UI", 11),
                      fg_color="#3a3a5c", hover_color="#555580",
                      text_color="#cccccc", corner_radius=6, height=30,
                      command=self._logout).pack(side="left", expand=True, padx=(4, 0))

    # ── countdown ─────────────────────────────────────────────────────────
    def _tick(self):
        if self._remaining <= 0:
            self._tlbl.configure(text="00:00:00", text_color="#ff4444")
            self.stop()
            self._on_expired()
            return

        h = self._remaining // 3600
        m = (self._remaining % 3600) // 60
        s = self._remaining % 60
        self._tlbl.configure(text=f"{h:02}:{m:02}:{s:02}")

        # turn red in last 60 seconds
        self._tlbl.configure(text_color="#ff4444" if self._remaining <= 60 else "#00d4ff")

        self._remaining -= 1
        self._job = self.after(1000, self._tick)

    def stop(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None

    def get_remaining(self):
        return self._remaining

    # ── button callbacks ──────────────────────────────────────────────────
    def _buy_more(self):
        self.stop()
        self._on_buy_more(self._remaining)

    def _logout(self):
        self.stop()
        self._on_logout()


# ──────────────────────────────────────────────────────────────────────────────
#  Payment Modal  — CTkToplevel dialog, always centered, no black screen
# ──────────────────────────────────────────────────────────────────────────────
class PaymentModal(ctk.CTkToplevel):

    METHODS = [
        ("📱  GCash",   "gcash"),
        ("💜  PayMaya", "paymaya"),
        ("💳  Card",    "card"),
        ("💵  Cash",    "cash"),
    ]

    def __init__(self, root, cost: float, label: str, on_confirm, on_cancel):
        super().__init__(root)
        self._cost       = cost
        self._label      = label
        self._on_confirm = on_confirm
        self._on_cancel  = on_cancel
        self._method     = ctk.StringVar(value="cash")
        self._tiles      = {}
        self._tile_lbls  = {}

        # ── remove ALL window decorations (title bar, buttons) ────────────
        self.overrideredirect(True)
        self.configure(fg_color="#1e1e2e")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.grab_set()

        # ── build content first so we know the real size ──────────────────
        self._build()

        # ── true center after content is rendered ─────────────────────────
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self):
        # ── outer card with border ────────────────────────────────────────
        card = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=16,
                            border_color="#3a3a5c", border_width=2)
        card.pack(padx=0, pady=0, fill="both", expand=True)

        # ── header ────────────────────────────────────────────────────────
        ctk.CTkLabel(card, text="💳  Choose Payment",
                     font=("Segoe UI", 20, "bold"),
                     text_color="#ffffff").pack(pady=(24, 0))

        ctk.CTkLabel(card, text=self._label,
                     font=("Segoe UI", 11),
                     text_color="#8888aa").pack(pady=(3, 0))

        # ── amount badge ──────────────────────────────────────────────────
        amt_f = ctk.CTkFrame(card, fg_color="#0d2e1a", corner_radius=10)
        amt_f.pack(padx=30, pady=12, fill="x")
        ctk.CTkLabel(amt_f, text=fmt_php(self._cost),
                     font=("Segoe UI", 28, "bold"),
                     text_color="#2ecc71").pack(pady=10)

        # ── section label ─────────────────────────────────────────────────
        ctk.CTkLabel(card, text="Select payment method",
                     font=("Segoe UI", 11),
                     text_color="#8888aa").pack(pady=(6, 4))

        # ── 2 × 2 payment tile grid ───────────────────────────────────────
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(padx=24, pady=(0, 4), fill="x")

        for idx, (txt, val) in enumerate(self.METHODS):
            row, col = divmod(idx, 2)
            grid.columnconfigure(col, weight=1)

            tile = ctk.CTkFrame(grid,
                                fg_color="#2a2a3e",
                                corner_radius=10,
                                border_width=2,
                                border_color="#3a3a5c",
                                cursor="hand2",
                                width=160, height=60)
            tile.grid(row=row, column=col, padx=6, pady=5, sticky="nsew")
            tile.pack_propagate(False)

            tl = ctk.CTkLabel(tile, text=txt,
                              font=("Segoe UI", 13, "bold"),
                              text_color="#cccccc")
            tl.pack(expand=True)

            self._tiles[val]     = tile
            self._tile_lbls[val] = tl

            def _click(e=None, v=val):
                self._method.set(v)
                self._refresh()

            tile.bind("<Button-1>", _click)
            tl.bind("<Button-1>",   _click)

        self._refresh()

        # ── action buttons ────────────────────────────────────────────────
        ctk.CTkButton(card,
                      text="✔  Pay & Start Session",
                      font=("Segoe UI", 13, "bold"),
                      fg_color="#00d4ff", hover_color="#0099bb",
                      text_color="#000000",
                      corner_radius=10, height=44,
                      command=self._confirm).pack(fill="x", padx=24, pady=(14, 6))

        ctk.CTkButton(card,
                      text="✖  Cancel",
                      font=("Segoe UI", 12),
                      fg_color="#2a2a3e", hover_color="#3a3a5c",
                      text_color="#aaaaaa",
                      corner_radius=10, height=38,
                      command=self._cancel).pack(fill="x", padx=24, pady=(0, 20))

    def _refresh(self):
        sel = self._method.get()
        for val, tile in self._tiles.items():
            on = (val == sel)
            tile.configure(border_color="#00d4ff" if on else "#3a3a5c",
                           fg_color="#0d1a2e"     if on else "#2a2a3e")
            self._tile_lbls[val].configure(
                text_color="#00d4ff" if on else "#cccccc")

    def _confirm(self):
        m = self._method.get()
        self.grab_release()
        self.destroy()
        self._on_confirm(m)

    def _cancel(self):
        self.grab_release()
        self.destroy()
        self._on_cancel()


# ──────────────────────────────────────────────────────────────────────────────
#  Customer Dashboard
# ──────────────────────────────────────────────────────────────────────────────
class CustomerDashboard(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=T.BG, corner_radius=0)
        self.app = app
        self.session      = None
        self.computer     = None
        self.tier         = None          # chosen minutes
        self._job         = None
        self._float_win   = None          # FloatingTimer reference
        self._session_end = None          # epoch when session expires
        self._payment_method = None
        self._build()

    # ─────────────────────────────────────────────────────────── build UI ──
    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=T.CARD, corner_radius=0, height=60)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        hi = ctk.CTkFrame(hdr, fg_color=T.CARD, corner_radius=0)
        hi.pack(fill="both", expand=True, padx=20)
        uf = ctk.CTkFrame(hi, fg_color=T.CARD, corner_radius=0)
        uf.pack(side="left", fill="y", pady=10)
        self.htitle = lbl(uf, "Welcome", T.FL, bold=True); self.htitle.pack(anchor="w")
        self.hsub   = lbl(uf, "Customer Dashboard", color=T.DIM, size=T.FS-2); self.hsub.pack(anchor="w")
        self.logout_btn = btn(hi, "Sign Out", self.app.logout, "secondary")
        self.logout_btn.pack(side="right", pady=12)

        self.content = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        self.content.pack(fill="both", expand=True, padx=20, pady=20)
        self.sf  = ctk.CTkFrame(self.content, fg_color=T.BG, corner_radius=0)
        self.sel = ctk.CTkFrame(self.content, fg_color=T.BG, corner_radius=0)

    # ──────────────────────────────────────────────────────────────── load ──
    def load(self):
        if not self.app.user:
            return
        self.htitle.configure(text=f"Welcome, {self.app.user['username']}")
        self.session = DB.active_session(self.app.user["id"])

        # restore timer from DB if session exists
        if self.session:
            saved_end = DB.get_session_timer(self.app.user["id"])
            self._session_end = saved_end if saved_end else time.time() + 3600
            remaining = max(0, int(self._session_end - time.time()))

            if remaining <= 0:
                # time already expired while app was closed — force end
                self._force_end_expired()
                return

            self.hsub.configure(text="Session In Progress")
            self.logout_btn.pack_forget()

            # If we came back from "buy more", show session view
            self._show_session()
        else:
            self.hsub.configure(text="Customer Dashboard")
            self.logout_btn.pack(side="right", pady=12)
            self._show_select()

    # ─────────────────────────────────────────────── time selection screen ──
    def _show_select(self):
        self.sf.pack_forget()
        for w in self.sel.winfo_children(): w.destroy()
        avail = [c for c in DB.computers() if c["status"] == "available"]

        if not avail:
            f = ctk.CTkFrame(self.sel, fg_color=T.BG, corner_radius=0); f.pack(expand=True)
            lbl(f, "🖥️", T.FH).pack(pady=(0, 10))
            lbl(f, "No Computers Available", T.FT, bold=True).pack()
            lbl(f, "All computers are in use.", color=T.DIM).pack(pady=(10, 0))
        else:
            self.computer = avail[0]
            c = ctk.CTkFrame(self.sel, fg_color=T.BG, corner_radius=0); c.pack(expand=True)
            lbl(c, "🖥️", T.FH).pack(pady=(0, 10))
            lbl(c, f"You are using {self.computer['name']}", T.FT, bold=True).pack()

            rf = ctk.CTkFrame(c, fg_color=T.BG, corner_radius=0); rf.pack(pady=(15, 25))
            lbl(rf, f"⚡ {fmt_php(HOURLY_RATE)} / hour", color=T.CYAN, size=T.FL, bold=True).pack()

            tc = card(c); tc.pack(fill="x", pady=(0, 20))
            th = ctk.CTkFrame(tc, fg_color=T.CARD, corner_radius=0)
            th.pack(fill="x", padx=20, pady=(15, 10))
            lbl(th, "⏱️ Select Estimated Usage Time", bold=True).pack(anchor="w")
            lbl(th, "Choose how long you plan to use the PC", color=T.MUT, size=T.FS-2).pack(anchor="w")

            tg = ctk.CTkFrame(tc, fg_color=T.CARD, corner_radius=0)
            tg.pack(fill="x", padx=15, pady=(0, 15))
            tiers = [("15 min", 15), ("30 min", 30), ("1 hour", 60),  ("1.5 hrs", 90),
                     ("2 hours", 120), ("3 hours", 180), ("5 hours", 300), ("8 hours", 480)]
            self.tbtn = {}
            for i, (lt, mins) in enumerate(tiers):
                cost = round(mins * MINUTE_RATE, 2)
                r, col = divmod(i, 4)
                bf = ctk.CTkFrame(tg, fg_color=T.INP, border_color=T.BDR,
                                  border_width=2, corner_radius=6)
                bf.grid(row=r, column=col, padx=5, pady=5, sticky="nsew")
                tg.columnconfigure(col, weight=1)
                inn = ctk.CTkFrame(bf, fg_color=T.INP, corner_radius=0)
                inn.pack(expand=True, fill="both", padx=15, pady=12)
                ll = lbl(inn, lt, size=T.FS-2); ll.pack()
                cl = lbl(inn, fmt_php(cost), color=T.GRN, size=T.FL, bold=True); cl.pack()
                self.tbtn[mins] = (bf, ll, cl)
                for w in [bf, inn, ll, cl]:
                    w.bind("<Button-1>", lambda e, m=mins: self._pick(m))
                    w.configure(cursor="hand2")

            nt = ctk.CTkFrame(tc, fg_color=T.INP, corner_radius=6)
            nt.pack(fill="x", padx=15, pady=(0, 15))
            lbl(nt, "Estimate only — billed on actual usage.", color=T.MUT, size=T.FS-2).pack(pady=8)

            self.sbtn = btn(c, "⚡ Start Session", self._on_start_clicked)
            self.sbtn.pack(fill="x", pady=(5, 0), ipady=8)
            self.sbtn.configure(state="disabled")

        self.sel.pack(fill="both", expand=True)

    def _pick(self, mins):
        self.tier = mins
        for m, (f, ll, cl) in self.tbtn.items():
            f.configure(border_color=T.CYAN if m == mins else T.BDR)
            ll.configure(text_color=T.CYAN if m == mins else T.TXT)
        self.sbtn.configure(state="normal")

    # ────────────────────────────────────────────── start button → payment ──
    def _on_start_clicked(self):
        if not self.computer or not self.app.user or not self.tier:
            return
        cost  = round(self.tier * MINUTE_RATE, 2)
        label = f"{self.tier} min  •  {self.computer['name']}"
        PaymentModal(
            root       = self.app,
            cost       = cost,
            label      = label,
            on_confirm = self._after_payment,
            on_cancel  = lambda: None,
        )

    # ────────────────────────────────────────────── after payment confirmed ──
    def _after_payment(self, method: str):
        self._payment_method = method
        cost = round(self.tier * MINUTE_RATE, 2)

        # create DB session
        if not self.session:
            self.session = DB.start_session(
                self.app.user["id"],
                self.computer["id"],
                self.tier,
            )

        # compute end time and persist
        self._session_end = time.time() + (self.tier * 60)
        DB.save_session_timer(self.app.user["id"], self._session_end)

        # update UI state
        self.app.customer_can_exit = False
        self.logout_btn.pack_forget()
        self.hsub.configure(text="Session In Progress")

        # unlock: minimize main window and show floating timer
        self._unlock_and_float()

    # ───────────────────────────────────────────── unlock / float / relock ──
    def _unlock_and_float(self):
        """Minimize main app and spawn floating countdown."""
        remaining = max(0, int(self._session_end - time.time()))

        # close old float if exists
        self._destroy_float()

        # minimize / hide main window so customer can use PC freely
        self.app.iconify()

        self._float_win = FloatingTimer(
            master           = self.app,
            remaining_seconds= remaining,
            on_expired       = self._on_time_expired,
            on_buy_more      = self._on_buy_more,
            on_logout        = self._on_float_logout,
        )

    def _destroy_float(self):
        if self._float_win:
            try:
                self._float_win.stop()
                self._float_win.destroy()
            except Exception:
                pass
            self._float_win = None

    def _relock(self):
        """Restore main window fullscreen and bring it to front."""
        self._destroy_float()
        self.app.deiconify()
        self.app.lift()
        self.app.focus_force()
        self.app.attributes("-topmost", True)

    # ──────────────────────────────────────────────────── timer callbacks ──
    def _on_time_expired(self):
        """Called by FloatingTimer when countdown hits zero."""
        self._relock()
        # show session screen so they can end & pay
        self._show_session()
        self.hsub.configure(text="⚠️ Time Expired — Please End Session")

    def _on_buy_more(self, remaining_seconds: int):
        """Customer taps '+ Buy More' on float — relock and show time picker."""
        self._relock()
        # keep existing session, just show time selector again
        self._show_buy_more(remaining_seconds)

    def _on_float_logout(self):
        """Customer taps 'Sign Out' on float — relock then show end session."""
        self._relock()
        self._show_session()

    # ───────────────────────────────────────────────────── buy more screen ──
    def _show_buy_more(self, remaining_seconds: int):
        """Show the time-selection screen to extend an active session."""
        self.sel.pack_forget()
        self.sf.pack_forget()
        for w in self.sel.winfo_children(): w.destroy()

        c = ctk.CTkFrame(self.sel, fg_color=T.BG, corner_radius=0); c.pack(expand=True)
        lbl(c, "⏱️", T.FH).pack(pady=(0, 10))

        h = remaining_seconds // 3600
        m = (remaining_seconds % 3600) // 60
        s = remaining_seconds % 60
        lbl(c, f"Remaining: {h:02}:{m:02}:{s:02}", T.FT, bold=True, color=T.CYAN).pack()
        lbl(c, "Add more time to your session", color=T.DIM, size=T.FS-2).pack(pady=(4, 16))

        tc = card(c); tc.pack(fill="x", pady=(0, 20))
        th = ctk.CTkFrame(tc, fg_color=T.CARD, corner_radius=0)
        th.pack(fill="x", padx=20, pady=(15, 10))
        lbl(th, "⏱️ Add Time", bold=True).pack(anchor="w")

        tg = ctk.CTkFrame(tc, fg_color=T.CARD, corner_radius=0)
        tg.pack(fill="x", padx=15, pady=(0, 15))
        tiers = [("15 min", 15), ("30 min", 30), ("1 hour", 60),  ("1.5 hrs", 90),
                 ("2 hours", 120), ("3 hours", 180), ("5 hours", 300), ("8 hours", 480)]
        self.tbtn = {}
        self.tier = None
        for i, (lt, mins) in enumerate(tiers):
            cost = round(mins * MINUTE_RATE, 2)
            r, col = divmod(i, 4)
            bf = ctk.CTkFrame(tg, fg_color=T.INP, border_color=T.BDR,
                              border_width=2, corner_radius=6)
            bf.grid(row=r, column=col, padx=5, pady=5, sticky="nsew")
            tg.columnconfigure(col, weight=1)
            inn = ctk.CTkFrame(bf, fg_color=T.INP, corner_radius=0)
            inn.pack(expand=True, fill="both", padx=15, pady=12)
            ll = lbl(inn, lt, size=T.FS-2); ll.pack()
            cl = lbl(inn, fmt_php(cost), color=T.GRN, size=T.FL, bold=True); cl.pack()
            self.tbtn[mins] = (bf, ll, cl)
            for w in [bf, inn, ll, cl]:
                w.bind("<Button-1>", lambda e, m=mins: self._pick(m))
                w.configure(cursor="hand2")

        self.sbtn = btn(c, "⚡ Add Time", self._on_add_time_clicked)
        self.sbtn.pack(fill="x", pady=(5, 0), ipady=8)
        self.sbtn.configure(state="disabled")

        btn(c, "⏹️ End Session & Pay", self._end, "danger").pack(
            fill="x", pady=(8, 0), ipady=8)

        self.sel.pack(fill="both", expand=True)

    def _on_add_time_clicked(self):
        if not self.tier:
            return
        cost  = round(self.tier * MINUTE_RATE, 2)
        label = f"+{self.tier} min extension"
        PaymentModal(
            root       = self.app,
            cost       = cost,
            label      = label,
            on_confirm = self._after_add_time,
            on_cancel  = lambda: None,
        )

    def _after_add_time(self, method: str):
        """Extend session_end and re-launch float."""
        self._session_end += self.tier * 60
        DB.save_session_timer(self.app.user["id"], self._session_end)
        self._unlock_and_float()

    # ──────────────────────────────────────────────────── active session UI ──
    def _show_session(self):
        self.sel.pack_forget()
        for w in self.sf.winfo_children(): w.destroy()
        if not self.session: return
        pcs = DB.computers()
        pc = next((p for p in pcs if p["id"] == self.session["computer_id"]), None)
        if not pc: return

        c = ctk.CTkFrame(self.sf, fg_color=T.BG, corner_radius=0); c.pack(expand=True)
        lbl(c, "🖥️", T.FH).pack(pady=(0, 10))
        lbl(c, f"You are using {pc['name']}", T.FT, bold=True).pack()
        st = datetime.fromtimestamp(self.session["start_time"] / 1000)
        lbl(c, f"Started at {st.strftime('%I:%M %p')}", color=T.DIM).pack(pady=(5, 20))

        tc = card(c); tc.pack(fill="x", pady=(0, 20))
        ti = ctk.CTkFrame(tc, fg_color=T.CARD, corner_radius=0)
        ti.pack(fill="x", padx=30, pady=25)

        tf = ctk.CTkFrame(ti, fg_color=T.CARD, corner_radius=0); tf.pack(side="left", expand=True)
        lbl(tf, "TIME REMAINING", color=T.MUT, size=T.FS-2).pack()
        self.tlbl = lbl(tf, "00:00:00", T.FH, bold=True); self.tlbl.pack()

        ctk.CTkFrame(ti, fg_color=T.BDR, width=1, corner_radius=0).pack(
            side="left", fill="y", padx=20, pady=5)

        cf2 = ctk.CTkFrame(ti, fg_color=T.CARD, corner_radius=0); cf2.pack(side="left", expand=True)
        lbl(cf2, "CURRENT COST", color=T.MUT, size=T.FS-2).pack()
        self.clbl = lbl(cf2, "₱0.00", T.FH, color=T.GRN, bold=True); self.clbl.pack()

        sf2 = ctk.CTkFrame(tc, fg_color=T.CARD, corner_radius=0); sf2.pack(pady=(0, 15))
        lbl(sf2, "● Session Active", color=T.GRN, size=T.FS-2, bold=True).pack(side="left")
        self.mlbl = lbl(sf2, "  •  0 min", color=T.MUT, size=T.FS-2)
        self.mlbl.pack(side="left", padx=(5, 0))

        rc = card(c); rc.pack(fill="x", pady=(0, 20))
        rh = ctk.CTkFrame(rc, fg_color=T.CARD, corner_radius=0)
        rh.pack(fill="x", padx=20, pady=(15, 10))
        lbl(rh, f"⚡ Rate: {fmt_php(HOURLY_RATE)}/hour", color=T.CYAN, bold=True).pack(anchor="w")
        for lt, mins in [("30 min", 30), ("1 hour", 60), ("2 hours", 120),
                         ("3 hours", 180), ("5 hours", 300)]:
            rr = ctk.CTkFrame(rc, fg_color=T.INP, corner_radius=0)
            rr.pack(fill="x", padx=15, pady=2)
            lbl(rr, lt, color=T.DIM, size=T.FS-2).pack(side="left", padx=10, pady=6)
            lbl(rr, fmt_php(round(mins * MINUTE_RATE, 2)), size=T.FS-2, bold=True).pack(
                side="right", padx=10, pady=6)

        nf = ctk.CTkFrame(rc, fg_color=T.CARD, corner_radius=0)
        nf.pack(fill="x", padx=15, pady=(5, 15))
        lbl(nf, "Billed per minute (minimum 1 minute)", color=T.MUT, size=T.FS-2).pack()

        # action buttons
        btn_row = ctk.CTkFrame(c, fg_color=T.BG, corner_radius=0)
        btn_row.pack(fill="x", pady=(0, 0))

        btn(btn_row, "🔓 Resume (unlock PC)", self._unlock_and_float, "secondary").pack(
            side="left", expand=True, fill="x", padx=(0, 6), ipady=8)
        btn(btn_row, "⏹️ End Session & Pay", self._end, "danger").pack(
            side="left", expand=True, fill="x", ipady=8)

        self.sf.pack(fill="both", expand=True)
        self._tick()

    # ──────────────────────────────────────────────────── countdown tick ──
    def _tick(self):
        if not self.session or not self._session_end:
            return

        remaining = int(self._session_end - time.time())

        if remaining <= 0:
            if self.tlbl.winfo_exists():
                self.tlbl.configure(text="00:00:00", text_color="#ff4444")
            self._force_end_expired()
            return

        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60

        if self.tlbl.winfo_exists():
            self.tlbl.configure(
                text=f"{h:02}:{m:02}:{s:02}",
                text_color="#ff4444" if remaining <= 60 else T.TXT,
            )

        # cost based on elapsed usage
        total_secs  = self.tier * 60 if self.tier else 3600
        elapsed_sec = total_secs - remaining
        elapsed_min = max(1, elapsed_sec // 60)

        if self.clbl.winfo_exists():
            self.clbl.configure(text=fmt_php(round(elapsed_min * MINUTE_RATE, 2)))
        if self.mlbl.winfo_exists():
            self.mlbl.configure(text=f"  •  {elapsed_min} min")

        self._job = self.after(1000, self._tick)

    # ────────────────────────────────────────────── end session & billing ──
    def _force_end_expired(self):
        """Auto-end session when time runs out."""
        self._relock()
        if self.session:
            self._end()

    def _end(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self._destroy_float()

        if not self.session:
            return

        result = DB.end_session(self.session["id"])
        self.session     = None
        self.tier        = None
        self._session_end = None
        DB.set_computer(result["computer_id"], "available")
        self._billing(result)

    def _billing(self, result):
        d = ctk.CTkToplevel(self)
        d.overrideredirect(True)
        d.configure(fg_color=T.CARD)
        d.transient(self); d.grab_set()
        d.update_idletasks()
        x = d.winfo_screenwidth() // 2 - 210
        y = d.winfo_screenheight() // 2 - 260
        d.geometry(f"420x520+{x}+{y}")
        d.attributes("-topmost", True)

        pcs = DB.computers()
        pc = next((p for p in pcs if p["id"] == result["computer_id"]), None)

        hdr = ctk.CTkFrame(d, fg_color=T.CARD, corner_radius=0)
        hdr.pack(fill="x", padx=20, pady=20)
        lbl(hdr, "🧾 Billing Summary", T.FT, bold=True).pack(anchor="w")
        lbl(hdr, "Review your session and complete payment",
            color=T.DIM, size=T.FS-2).pack(anchor="w")

        det = ctk.CTkFrame(d, fg_color=T.INP, border_color=T.BDR,
                           border_width=1, corner_radius=6)
        det.pack(fill="x", padx=20, pady=(0, 20))
        for lt, v in [("Computer", pc["name"] if pc else "Unknown"),
                      ("Duration", f"{result['duration']} minutes")]:
            rr = ctk.CTkFrame(det, fg_color=T.INP, corner_radius=0)
            rr.pack(fill="x", padx=15, pady=10)
            lbl(rr, lt, color=T.DIM, size=T.FS-2).pack(side="left")
            lbl(rr, v, bold=True).pack(side="right")
        tr = ctk.CTkFrame(det, fg_color=T.INP, corner_radius=0)
        tr.pack(fill="x", padx=15, pady=(5, 15))
        lbl(tr, "Total Amount", bold=True).pack(side="left")
        lbl(tr, fmt_php(result["cost"]), color=T.GRN, size=T.FL, bold=True).pack(side="right")

        mf = ctk.CTkFrame(d, fg_color=T.CARD, corner_radius=0)
        mf.pack(fill="x", padx=20, pady=(0, 20))
        lbl(mf, "Select Payment Method", color=T.DIM, size=T.FS-2).pack(anchor="w", pady=(0, 10))
        method = ctk.StringVar(value="cash")
        mb = ctk.CTkFrame(mf, fg_color=T.CARD, corner_radius=0); mb.pack(fill="x")
        for txt, val in [("💵 Cash", "cash"), ("📱 GCash", "gcash"),
                         ("💜 PayMaya", "paymaya"), ("💳 Card", "card")]:
            ctk.CTkRadioButton(mb, text=txt, variable=method, value=val,
                               text_color=T.TXT, fg_color=T.CYAN, hover_color=T.CDARK,
                               font=(T.FF, T.FS)).pack(side="left", expand=True, padx=8, pady=5)

        def pay():
            rcpt = DB.pay(self.session["id"] if self.session else result["id"],
                          self.app.user["id"],
                          result["cost"], method.get())
            DB.set_computer(result["computer_id"], "available")
            self.app.customer_can_exit = True

            for w in d.winfo_children(): w.destroy()
            sf = ctk.CTkFrame(d, fg_color=T.CARD, corner_radius=0); sf.pack(expand=True)
            lbl(sf, "✅", T.FH).pack(pady=(20, 10))
            lbl(sf, "Payment Successful!", T.FT, bold=True).pack()
            lbl(sf, f"Receipt No: {rcpt}", color=T.DIM).pack(pady=(10, 0))
            lbl(sf, "What would you like to do next?", color=T.MUT, size=T.FS-2).pack(pady=(6, 16))

            def buy_again():
                d.destroy()
                self.hsub.configure(text="Customer Dashboard")
                self.logout_btn.pack(side="right", pady=12)
                self._show_select()

            def do_logout():
                d.destroy()
                self.app.logout()

            btn(sf, "🔄 Buy Another Session", buy_again).pack(
                fill="x", padx=30, pady=(0, 8), ipady=6)
            btn(sf, "🚪 Log Out", do_logout, "secondary").pack(
                fill="x", padx=30, ipady=6)

        btn(d, f"Pay {fmt_php(result['cost'])}", pay).pack(
            fill="x", padx=20, pady=20, ipady=4)

    # ─────────────────────────────────────────────────────────── cleanup ──
    def cleanup(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self._destroy_float()