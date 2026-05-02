import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import time
from datetime import datetime, timedelta
from ui.theme import T
from ui.widget import lbl, btn, Entry, card
from database.database import DB, fmt_php


class AdminDashboard(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=T.BG, corner_radius=0)
        self.app = app
        self.tab  = "overview"
        self._rjob = None
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=T.CARD, corner_radius=0, height=60)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        hi = ctk.CTkFrame(hdr, fg_color=T.CARD, corner_radius=0)
        hi.pack(fill="both", expand=True, padx=20)
        uf = ctk.CTkFrame(hi, fg_color=T.CARD, corner_radius=0)
        uf.pack(side="left", fill="y", pady=10)
        lbl(uf, "🛡️ Admin Portal", T.FL, bold=True).pack(anchor="w")
        lbl(uf, "TimeNet Café", color=T.DIM, size=T.FS-2).pack(anchor="w")
        btn(hi, "Sign Out", self.app.logout, "secondary").pack(side="right", pady=12)

        tb = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        tb.pack(fill="x", padx=20, pady=(15, 0))
        tc = ctk.CTkFrame(tb, fg_color=T.CARD, border_color=T.BDR,
                          border_width=1, corner_radius=6)
        tc.pack(side="left")
        self.t1 = ctk.CTkButton(tc, text="📊 Overview & PCs",
                                 fg_color=T.BDR, text_color=T.TXT, hover_color=T.BDR,
                                 font=(T.FF, T.FS, "bold"), corner_radius=4, width=165)
        self.t1.pack(side="left", padx=2, pady=2)
        self.t1.configure(command=lambda: self._tab("overview"))
        self.t2 = ctk.CTkButton(tc, text="📈 Reports & Income",
                                 fg_color=T.CARD, text_color=T.DIM, hover_color=T.BDR,
                                 font=(T.FF, T.FS), corner_radius=4, width=165)
        self.t2.pack(side="left", padx=2, pady=2)
        self.t2.configure(command=lambda: self._tab("reports"))

        self.content = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        self.content.pack(fill="both", expand=True, padx=20, pady=20)
        self.ov = ctk.CTkFrame(self.content, fg_color=T.BG, corner_radius=0)
        self.rp = ctk.CTkFrame(self.content, fg_color=T.BG, corner_radius=0)

    def _tab(self, name):
        self.tab = name
        if name == "overview":
            self.t1.configure(fg_color=T.BDR, text_color=T.TXT, font=(T.FF, T.FS, "bold"))
            self.t2.configure(fg_color=T.CARD, text_color=T.DIM, font=(T.FF, T.FS))
            self.rp.pack_forget(); self._overview()
        else:
            self.t2.configure(fg_color=T.BDR, text_color=T.TXT, font=(T.FF, T.FS, "bold"))
            self.t1.configure(fg_color=T.CARD, text_color=T.DIM, font=(T.FF, T.FS))
            self.ov.pack_forget(); self._reports()

    def load(self):
        self._tab("overview"); self._start_refresh()

    def _start_refresh(self):
        if self._rjob: self.after_cancel(self._rjob)
        self._do_refresh()

    def _do_refresh(self):
        if self.tab == "overview": self._overview()
        self._rjob = self.after(5000, self._do_refresh)

    def _overview(self):
        for w in self.ov.winfo_children(): w.destroy()

        ac = card(self.ov); ac.pack(fill="x", pady=(0, 20))
        ah = ctk.CTkFrame(ac, fg_color=T.CARD, corner_radius=0)
        ah.pack(fill="x", padx=20, pady=15)
        tf = ctk.CTkFrame(ah, fg_color=T.CARD, corner_radius=0); tf.pack(side="left")
        lbl(tf, "📡 Live Sessions Monitor", T.FL, bold=True).pack(side="left")
        active = DB.all_active_sessions()
        ctk.CTkLabel(tf, text=f"  {len(active)} Active  ",
                     fg_color=T.CYAN, text_color=T.BG,
                     font=(T.FF, T.FS-2, "bold"),
                     corner_radius=4).pack(side="left", padx=(10, 0))

        if not active:
            lbl(ac, "No active sessions.", color=T.DIM).pack(padx=20, pady=(0, 20))
        else:
            sg = ctk.CTkFrame(ac, fg_color=T.CARD, corner_radius=0)
            sg.pack(fill="x", padx=15, pady=(0, 15))
            pcs = DB.computers()
            for i, s in enumerate(active[:8]):
                pc  = next((p for p in pcs if p["id"] == s["computer_id"]), None)
                dur = int((time.time() * 1000 - s["start_time"]) / 60000)
                sc  = ctk.CTkFrame(sg, fg_color=T.INP, border_color=T.BDR,
                                   border_width=1, corner_radius=6)
                sc.grid(row=i // 4, column=i % 4, padx=5, pady=5, sticky="nsew")
                sg.columnconfigure(i % 4, weight=1)
                inn = ctk.CTkFrame(sc, fg_color=T.INP, corner_radius=0)
                inn.pack(fill="both", expand=True, padx=15, pady=10)
                lbl(inn, pc["name"] if pc else "?", bold=True).pack(anchor="w")
                lbl(inn, f"...{s['user_id'][-4:]}", color=T.MUT, size=T.FS-2).pack(anchor="w")
                tf2 = ctk.CTkFrame(inn, fg_color=T.INP, corner_radius=0); tf2.pack(anchor="e")
                lbl(tf2, f"{dur}m", color=T.CYAN, size=T.FL, bold=True).pack()

        pc_card = card(self.ov); pc_card.pack(fill="both", expand=True)
        ph = ctk.CTkFrame(pc_card, fg_color=T.CARD, corner_radius=0)
        ph.pack(fill="x", padx=20, pady=15)
        lbl(ph, "🖥️ Computer Management", T.FL, bold=True).pack(side="left")
        af = ctk.CTkFrame(ph, fg_color=T.CARD, corner_radius=0); af.pack(side="right")
        self.npe = Entry(af, "New PC Name", width=180)
        self.npe.pack(side="left", padx=(0, 10), ipady=4)
        btn(af, "+ Add PC", self._add_pc).pack(side="left")

        pg = ctk.CTkFrame(pc_card, fg_color=T.CARD, corner_radius=0)
        pg.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        sc_map = {"available": T.GRN, "occupied": T.RED, "maintenance": T.YEL}
        for i, pc in enumerate(DB.computers()):
            r, col = divmod(i, 4)
            cc = ctk.CTkFrame(pg, fg_color=T.INP, border_color=T.BDR,
                              border_width=1, corner_radius=6)
            cc.grid(row=r, column=col, padx=5, pady=5, sticky="nsew")
            pg.columnconfigure(col, weight=1)
            inn = ctk.CTkFrame(cc, fg_color=T.INP, corner_radius=0)
            inn.pack(fill="both", expand=True, padx=15, pady=12)
            tr = ctk.CTkFrame(inn, fg_color=T.INP, corner_radius=0); tr.pack(fill="x")
            lbl(tr, pc["name"], bold=True).pack(side="left")
            lbl(tr, "●", color=sc_map.get(pc["status"], T.BDR), size=T.FS-2).pack(side="right")
            lbl(inn, pc["status"].upper(), color=sc_map.get(pc["status"], T.MUT),
                size=T.FS-2).pack(anchor="w")
            bf = ctk.CTkFrame(inn, fg_color=T.INP, corner_radius=0)
            bf.pack(fill="x", pady=(10, 0))
            occ = pc["status"] == "occupied"
            mt  = "🔧 Fixing" if pc["status"] == "maintenance" else "🔧 Maintain"
            ctk.CTkButton(bf, text=mt, fg_color=T.CARD, text_color=T.TXT,
                          hover_color=T.BDR, font=(T.FF, T.FS-2), corner_radius=4,
                          state="disabled" if occ else "normal",
                          command=lambda cid=pc["id"]: self._maint(cid)
                          ).pack(side="left", expand=True, fill="x", padx=(0, 5))
            ctk.CTkButton(bf, text="🗑️", fg_color=T.CARD, text_color=T.RED,
                          hover_color=T.BDR, font=(T.FF, T.FS-2), corner_radius=4, width=40,
                          state="disabled" if occ else "normal",
                          command=lambda cid=pc["id"], name=pc["name"]: self._del_pc(cid, name)
                          ).pack(side="right")

        self.ov.pack(fill="both", expand=True)

    def _add_pc(self):
        name = self.npe.val()
        if not name: return
        if DB.add_computer(name):
            self.npe.delete(0, "end"); self._overview()
        else:
            CTkMessagebox(title="Error", message="PC name already exists", icon="cancel")

    def _maint(self, cid):
        pcs = DB.computers()
        pc  = next((p for p in pcs if p["id"] == cid), None)
        if pc:
            DB.set_computer(cid, "available" if pc["status"] == "maintenance" else "maintenance")
            self._overview()

    def _del_pc(self, cid, name):
        msg = CTkMessagebox(title="Confirm", message=f"Delete {name}?",
                            icon="question", option_1="Cancel", option_2="Delete")
        if msg.get() == "Delete":
            DB.del_computer(cid); self._overview()

    def _reports(self):
        for w in self.rp.winfo_children(): w.destroy()
        sessions = DB.all_sessions()
        payments = DB.all_payments()
        done     = [s for s in sessions if s["status"] == "completed"]
        today_ms = int(datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        td_sess  = [s for s in done if (s.get("end_time") or 0) >= today_ms]
        td_pay   = [p for p in payments if p["timestamp"] >= today_ms]
        income   = sum(p["amount"] for p in td_pay)
        hrs      = sum(s.get("duration", 0) for s in td_sess) / 60

        sf = ctk.CTkFrame(self.rp, fg_color=T.BG, corner_radius=0)
        sf.pack(fill="x", pady=(0, 20))
        for i, (lt, v, ic, col) in enumerate([
            ("Today's Sessions", str(len(td_sess)), "👥", T.CYAN),
            ("Hours Used Today",  f"{hrs:.1f} hrs",  "⏱️", T.PUR),
            ("Today's Income",    fmt_php(income),   "📈", T.GRN),
        ]):
            sc = card(sf); sc.pack(side="left", expand=True, fill="both",
                                   padx=(0 if i == 0 else 10, 0))
            inn = ctk.CTkFrame(sc, fg_color=T.CARD, corner_radius=0)
            inn.pack(fill="both", expand=True, padx=20, pady=20)
            hrow = ctk.CTkFrame(inn, fg_color=T.CARD, corner_radius=0); hrow.pack(fill="x")
            lbl(hrow, lt, color=T.DIM, size=T.FS-2).pack(side="left")
            lbl(hrow, ic, size=T.FL).pack(side="right")
            lbl(inn, v, T.FH, bold=True,
                color=col if "Income" in lt else T.TXT).pack(anchor="w", pady=(10, 0))

        cc = card(self.rp); cc.pack(fill="both", expand=True)
        ch = ctk.CTkFrame(cc, fg_color=T.CARD, corner_radius=0)
        ch.pack(fill="x", padx=20, pady=15)
        lbl(ch, "Income Overview (Last 7 Days)", T.FL, bold=True).pack(side="left")
        btn(ch, "📥 Export CSV", self._export, "secondary").pack(side="right")

        cb = ctk.CTkFrame(cc, fg_color=T.CARD, corner_radius=0)
        cb.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        max_i = 0; daily = []
        for i in range(6, -1, -1):
            date = datetime.now() - timedelta(days=i)
            ds   = int(date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
            de   = ds + 86400000
            dp   = [p for p in payments if ds <= p["timestamp"] < de]
            inc  = sum(p["amount"] for p in dp)
            max_i = max(max_i, inc)
            daily.append((date.strftime("%a"), inc))

        for day, inc in daily:
            rr = ctk.CTkFrame(cb, fg_color=T.CARD, corner_radius=0); rr.pack(fill="x", pady=3)
            lbl(rr, day, color=T.DIM, size=T.FS-2).pack(side="left", padx=(0, 10))
            bar_outer = ctk.CTkFrame(rr, fg_color=T.INP, corner_radius=4, height=20)
            bar_outer.pack(side="left", expand=True, fill="x", padx=(0, 10))
            bar_outer.pack_propagate(False)
            if max_i > 0:
                pct = max(0.01, inc / max_i)
                ctk.CTkFrame(bar_outer, fg_color=T.CYAN, corner_radius=4).place(
                    relx=0, rely=0.1, relwidth=pct, relheight=0.8)
            lbl(rr, fmt_php(inc), size=T.FS-2, bold=True).pack(side="right")

        self.rp.pack(fill="both", expand=True)

    def _export(self):
        sessions = DB.all_sessions()
        payments = DB.all_payments()
        done = [s for s in sessions if s["status"] == "completed"]
        fn   = f"timenet_report_{datetime.now().strftime('%Y-%m-%d')}.csv"
        with open(fn, "w") as f:
            f.write("Date,Session ID,Duration (min),Cost,Method,Receipt\n")
            for s in done:
                pay = next((p for p in payments if p["session_id"] == s["id"]), None)
                dt  = datetime.fromtimestamp(
                    (s.get("end_time") or 0) / 1000).strftime("%Y-%m-%d %H:%M")
                f.write(f"{dt},{s['id']},{s.get('duration',0)},{s.get('cost',0)},"
                        f"{pay['method'] if pay else 'N/A'},"
                        f"{pay['receipt_no'] if pay else 'N/A'}\n")
        CTkMessagebox(title="Done", message=f"Saved as {fn}", icon="check")

    def cleanup(self):
        if self._rjob: self.after_cancel(self._rjob); self._rjob = None