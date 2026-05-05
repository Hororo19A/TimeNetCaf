"""
dashboard/admin.py — Admin dashboard (overview, live sessions, reports, CSV export).
"""

import csv
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from database.database import storage, now_ms, format_currency
from services.session import activate_voucher
from ui.theme import (
    BG, BG2, BG3, BORDER, TEXT, TEXT2,
    CYAN, GREEN, RED, YELLOW, PURPLE, BLUE,
)
from ui.widget import styled_frame, label, heading, entry, btn, separator


class AdminDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()
        self._load_data()
        self._poll()

    # ── Top-level shell ───────────────────────────────────────

    def _build(self):
        hdr = styled_frame(self, bg=BG2)
        hdr.pack(fill="x")
        inner = styled_frame(hdr, bg=BG2)
        inner.pack(fill="x", padx=30, pady=12)
        heading(inner, "🛡  Admin Portal — TimeNet Cafe",
                size=15, bg=BG2).pack(side="left")
        btn(inner, "Sign Out", command=self.app.logout,
            bg=BG3, fg=TEXT, pad=(14, 6),
            font=("Segoe UI", 10, "bold")).pack(side="right")
        separator(self).pack(fill="x")

        tab_bar = styled_frame(self, bg=BG2)
        tab_bar.pack(fill="x")
        tab_inner = styled_frame(tab_bar, bg=BG2)
        tab_inner.pack(anchor="center", pady=10)

        self.tab_btns: dict[str, tk.Button] = {}
        for tab_id, lbl_txt in [
            ("overview", "📊 Overview & PCs"),
            ("reports",  "📈 Reports & Income"),
        ]:
            b = btn(
                tab_inner, lbl_txt,
                command=lambda t=tab_id: self._switch_tab(t),
                bg=BG3 if tab_id == "overview" else BG2,
                fg=TEXT if tab_id == "overview" else TEXT2,
                pad=(20, 8), font=("Segoe UI", 11, "bold"),
            )
            b.pack(side="left", padx=6)
            self.tab_btns[tab_id] = b

        separator(self).pack(fill="x")

        self.tab_content = tk.Frame(self, bg=BG)
        self.tab_content.pack(fill="both", expand=True)
        self._current_tab = "overview"
        self._build_overview()

    def _switch_tab(self, tab_id: str):
        if tab_id == self._current_tab:
            return
        self._current_tab = tab_id
        for tid, b in self.tab_btns.items():
            b.config(
                bg=BG3 if tid == tab_id else BG2,
                fg=TEXT if tid == tab_id else TEXT2)
        for w in self.tab_content.winfo_children():
            w.destroy()
        if tab_id == "overview":
            self._build_overview()
        else:
            self._build_reports()
        self._load_data()

    # ── Overview tab ──────────────────────────────────────────

    def _build_overview(self):
        canvas = tk.Canvas(self.tab_content, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(self.tab_content, orient="vertical",
                               command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        wrapper = tk.Frame(canvas, bg=BG)
        win_id  = canvas.create_window((0, 0), window=wrapper, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        wrapper.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        self._ov_inner = tk.Frame(wrapper, bg=BG)
        self._ov_inner.pack(anchor="center", expand=True)

        self._build_voucher_section()
        self._build_live_sessions_section()
        self._build_computer_manager()

    # Voucher activation ───────────────────────────────────────

    def _build_voucher_section(self):
        card = styled_frame(self._ov_inner, bg=BG2)
        card.pack(padx=40, pady=(20, 10), fill="x", ipadx=10)

        heading(card, "🎫 Activate Voucher", size=14, bg=BG2).pack(
            anchor="w", padx=20, pady=(18, 4))
        label(card,
              "Enter a customer's cash voucher code to activate their PC session",
              fg=TEXT2, bg=BG2, font=("Segoe UI", 10)).pack(
            anchor="w", padx=20, pady=(0, 12))

        row = styled_frame(card, bg=BG2)
        row.pack(padx=20, pady=(0, 10), anchor="w")
        self.voucher_var = tk.StringVar()
        self.voucher_var.trace("w", lambda *_: self._uppercase_voucher())
        self.voucher_entry = entry(row, textvariable=self.voucher_var,
                                   width=40, font=("Courier", 13))
        self.voucher_entry.pack(side="left", padx=(0, 10), ipady=6)
        self.voucher_entry.insert(0, "Enter voucher code…")
        self.voucher_entry.bind("<FocusIn>", self._clear_placeholder)
        self.voucher_entry.bind("<Return>", lambda _: self._activate_voucher())
        btn(row, "Activate", command=self._activate_voucher,
            bg=PURPLE, fg=BG,
            font=("Segoe UI", 11, "bold")).pack(side="left", ipady=6, padx=2)

        self.voucher_msg = label(card, "", fg=GREEN, bg=BG2,
                                 font=("Segoe UI", 10))
        self.voucher_msg.pack(anchor="w", padx=20, pady=(0, 6))

        self.pending_frame = styled_frame(card, bg=BG2)
        self.pending_frame.pack(fill="x", padx=20, pady=(0, 18))

    def _clear_placeholder(self, _):
        if self.voucher_entry.get() == "Enter voucher code…":
            self.voucher_entry.delete(0, "end")

    def _uppercase_voucher(self):
        self.voucher_var.set(self.voucher_var.get().upper())

    def _activate_voucher(self):
        code = self.voucher_var.get().strip().upper()
        if not code or code == "ENTER VOUCHER CODE…":
            self.voucher_msg.config(
                text="⚠ Please enter a voucher code.", fg=YELLOW)
            return
        session = activate_voucher(code)
        if not session:
            self.voucher_msg.config(
                text="✗ Invalid or already used voucher code.", fg=RED)
            return
        computers = storage.get_computers()
        pc = next((c for c in computers
                   if c["id"] == session["computerId"]), None)
        self.voucher_var.set("")
        self.voucher_msg.config(
            text=f"✓ Activated! {pc['name'] if pc else 'PC'} is now active "
                 f"for {session.get('duration', '?')} minutes.",
            fg=GREEN,
        )
        self._load_data()

    # Live sessions monitor ────────────────────────────────────

    def _build_live_sessions_section(self):
        card = styled_frame(self._ov_inner, bg=BG2)
        card.pack(padx=40, pady=10, fill="x", ipadx=10)
        heading(card, "📡 Live Sessions Monitor", size=14, bg=BG2).pack(
            anchor="w", padx=20, pady=(18, 8))
        self.live_frame = styled_frame(card, bg=BG2)
        self.live_frame.pack(fill="x", padx=20, pady=(0, 18))

    # Computer manager ─────────────────────────────────────────

    def _build_computer_manager(self):
        card = styled_frame(self._ov_inner, bg=BG2)
        card.pack(padx=40, pady=10, fill="x", ipadx=10)

        top = styled_frame(card, bg=BG2)
        top.pack(fill="x", padx=20, pady=(18, 10))
        heading(top, "🖥  Computer Management", size=14, bg=BG2).pack(side="left")

        add_row = styled_frame(top, bg=BG2)
        add_row.pack(side="right")
        self.new_pc_var = tk.StringVar()
        entry(add_row, textvariable=self.new_pc_var, width=20,
              font=("Segoe UI", 10)).pack(side="left", padx=(0, 8), ipady=5)
        btn(add_row, "+ Add PC", command=self._add_computer,
            bg=CYAN, fg=BG, pad=(12, 5),
            font=("Segoe UI", 10, "bold")).pack(side="left")

        self.pc_grid = styled_frame(card, bg=BG2)
        self.pc_grid.pack(fill="x", padx=20, pady=(0, 18))

    # ── Reports tab ───────────────────────────────────────────

    def _build_reports(self):
        outer = tk.Frame(self.tab_content, bg=BG)
        outer.pack(fill="both", expand=True)
        f = tk.Frame(outer, bg=BG)
        f.pack(fill="both", expand=True, padx=60, pady=20)

        stat_row = tk.Frame(f, bg=BG)
        stat_row.pack(fill="x", pady=(0, 18))
        self.stat_cards: dict = {}
        for key, title, default, color in [
            ("sessions", "Today's Sessions",  "0",       BLUE),
            ("hours",    "Hours Used Today",  "0.0 hrs", PURPLE),
            ("income",   "Today's Income",    "₱0.00",   GREEN),
        ]:
            card = styled_frame(stat_row, bg=BG2)
            card.pack(side="left", expand=True, fill="x", padx=8)
            label(card, title, fg=TEXT2, bg=BG2,
                  font=("Segoe UI", 11)).pack(anchor="w", padx=18, pady=(18, 4))
            val_lbl = heading(card, default, size=26, fg=color, bg=BG2)
            val_lbl.pack(anchor="w", padx=18, pady=(0, 18))
            self.stat_cards[key] = val_lbl

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x", pady=(0, 10))
        heading(btn_row, "Session History", size=13, bg=BG).pack(side="left")
        btn(btn_row, "⬇ Export CSV", command=self._export_csv,
            bg=BG3, fg=TEXT, pad=(14, 6),
            font=("Segoe UI", 10, "bold")).pack(side="right")

        cols = ("Date", "PC", "Duration", "Cost", "Method", "Receipt")
        tree_frame = tk.Frame(f, bg=BG)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=cols,
                                 show="headings", height=16)
        widths = {"Date": 160, "PC": 80, "Duration": 100,
                  "Cost": 100, "Method": 90, "Receipt": 160}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths.get(col, 120), anchor="w")
        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

    # ── Data refresh ──────────────────────────────────────────

    def _load_data(self):
        computers = storage.get_computers()
        sessions  = storage.get_sessions()
        payments  = storage.get_payments()

        if self._current_tab == "overview":
            self._refresh_pending(sessions, computers)
            self._refresh_live(sessions, computers)
            self._refresh_pc_grid(computers)
        else:
            self._refresh_stats(sessions, payments)
            self._refresh_table(sessions, payments, computers)

    def _refresh_pending(self, sessions, computers):
        for w in self.pending_frame.winfo_children():
            w.destroy()
        pending = [s for s in sessions if s["status"] == "pending_voucher"]
        if not pending:
            return
        label(self.pending_frame,
              f"⏳ {len(pending)} Pending Voucher(s):",
              fg=YELLOW, bg=BG2,
              font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        for s in pending:
            pc  = next((c for c in computers
                        if c["id"] == s["computerId"]), None)
            row = styled_frame(self.pending_frame, bg=BG3)
            row.pack(fill="x", pady=2)
            label(row, s.get("voucherCode", "?"),
                  fg=YELLOW, bg=BG3,
                  font=("Courier", 11, "bold")).pack(
                side="left", padx=10, pady=4)
            label(row,
                  f"{pc['name'] if pc else '?'} • {s.get('duration', '?')} min",
                  fg=TEXT2, bg=BG3).pack(side="left")
            vc = s.get("voucherCode", "")
            btn(row, "Fill",
                command=lambda v=vc: self.voucher_var.set(v),
                bg=BG2, fg=PURPLE, pad=(6, 2)).pack(
                side="right", padx=6, pady=4)

    def _refresh_live(self, sessions, computers):
        for w in self.live_frame.winfo_children():
            w.destroy()
        active = [s for s in sessions if s["status"] == "active"]
        if not active:
            label(self.live_frame, "No active sessions at the moment.",
                  fg=TEXT2, bg=BG2).pack(anchor="w")
            return
        for s in active:
            pc   = next((c for c in computers
                         if c["id"] == s["computerId"]), None)
            remaining_min = max(
                0,
                (s["startTime"] + s.get("duration", 60) * 60_000 - now_ms())
                // 60_000,
            )
            row = styled_frame(self.live_frame, bg=BG3)
            row.pack(fill="x", pady=3)
            label(row, pc["name"] if pc else "?",
                  fg=TEXT, bg=BG3,
                  font=("Segoe UI", 10, "bold")).pack(
                side="left", padx=10, pady=6)
            label(row, f"{s.get('duration', '?')} min session",
                  fg=TEXT2, bg=BG3).pack(side="left")
            label(row, f"⏱ {remaining_min}m left",
                  fg=CYAN, bg=BG3,
                  font=("Segoe UI", 10, "bold")).pack(side="right", padx=10)

    def _refresh_pc_grid(self, computers):
        for w in self.pc_grid.winfo_children():
            w.destroy()
        cols = 4
        status_color = {
            "available":   GREEN,
            "occupied":    RED,
            "maintenance": YELLOW,
        }
        for idx, c in enumerate(computers):
            row_n, col_n = divmod(idx, cols)
            color  = status_color.get(c["status"], TEXT2)
            frame  = tk.Frame(self.pc_grid, bg=BG3, bd=1, relief="solid")
            frame.grid(row=row_n, column=col_n, padx=5, pady=5, sticky="nsew")
            self.pc_grid.columnconfigure(col_n, weight=1)

            label(frame, f"🖥  {c['name']}", fg=TEXT, bg=BG3,
                  font=("Segoe UI", 10, "bold")).pack(
                anchor="w", padx=10, pady=(10, 2))
            label(frame, c["status"].upper(), fg=color, bg=BG3,
                  font=("Segoe UI", 8)).pack(anchor="w", padx=10)

            occupied = c["status"] == "occupied"
            btn_row  = tk.Frame(frame, bg=BG3)
            btn_row.pack(fill="x", padx=8, pady=(6, 8))

            maint_lbl = "Fixing" if c["status"] == "maintenance" else "Maintain"
            mb = btn(btn_row, f"🔧 {maint_lbl}",
                     command=lambda cid=c["id"]: self._toggle_maintenance(cid),
                     bg=BG2,
                     fg=YELLOW if c["status"] == "maintenance" else TEXT2,
                     pad=(6, 3), font=("Segoe UI", 8))
            if occupied:
                mb.config(state="disabled")
            mb.pack(side="left", expand=True, fill="x", padx=(0, 3))

            db = btn(btn_row, "🗑",
                     command=lambda cid=c["id"], cn=c["name"]:
                         self._delete_computer(cid, cn),
                     bg=BG2, fg=RED, pad=(6, 3), font=("Segoe UI", 8))
            if occupied:
                db.config(state="disabled")
            db.pack(side="left")

    def _refresh_stats(self, sessions, payments):
        today    = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_ms = int(today.timestamp() * 1000)
        completed  = [s for s in sessions
                      if s["status"] == "completed"
                      and s.get("endTime", 0) >= today_ms]
        today_pay  = [p for p in payments if p["timestamp"] >= today_ms]
        income     = sum(p["amount"] for p in today_pay)
        total_min  = sum(s.get("duration", 0) for s in completed)

        self.stat_cards["sessions"].config(text=str(len(completed)))
        self.stat_cards["hours"].config(text=f"{total_min / 60:.1f} hrs")
        self.stat_cards["income"].config(text=format_currency(income))

    def _refresh_table(self, sessions, payments, computers):
        self.tree.delete(*self.tree.get_children())
        completed = sorted(
            [s for s in sessions if s["status"] == "completed"],
            key=lambda x: x.get("endTime", 0),
            reverse=True,
        )
        for s in completed:
            pay  = next((p for p in payments
                         if p["sessionId"] == s["id"]), None)
            pc   = next((c for c in computers
                         if c["id"] == s["computerId"]), None)
            date_str = (
                datetime.fromtimestamp(s["endTime"] / 1000)
                .strftime("%Y-%m-%d %H:%M")
                if s.get("endTime") else "—"
            )
            self.tree.insert("", "end", values=(
                date_str,
                pc["name"] if pc else "?",
                f"{s.get('duration', '?')} min",
                format_currency(s.get("cost", 0)),
                pay["method"].upper() if pay else "—",
                pay["receiptNo"] if pay else "—",
            ))

    # ── Computer management actions ───────────────────────────

    def _add_computer(self):
        name = self.new_pc_var.get().strip()
        if not name:
            messagebox.showwarning("Add PC", "Please enter a PC name.")
            return
        computers = storage.get_computers()
        if any(c["name"].lower() == name.lower() for c in computers):
            messagebox.showerror(
                "Add PC", "A computer with this name already exists.")
            return
        computers.append({
            "id":               f"pc-{now_ms()}",
            "name":             name,
            "status":           "available",
            "currentSessionId": None,
        })
        storage.save_computers(computers)
        self.new_pc_var.set("")
        self._load_data()

    def _delete_computer(self, cid: str, name: str):
        if not messagebox.askyesno("Delete", f"Delete {name}?"):
            return
        storage.save_computers(
            [c for c in storage.get_computers() if c["id"] != cid])
        self._load_data()

    def _toggle_maintenance(self, cid: str):
        computers = storage.get_computers()
        for c in computers:
            if c["id"] == cid:
                c["status"] = (
                    "available" if c["status"] == "maintenance"
                    else "maintenance"
                )
        storage.save_computers(computers)
        self._load_data()

    # ── CSV export ────────────────────────────────────────────

    def _export_csv(self):
        sessions  = storage.get_sessions()
        payments  = storage.get_payments()
        computers = storage.get_computers()
        completed = [s for s in sessions if s["status"] == "completed"]
        filename  = f"timenet_report_{datetime.now().strftime('%Y-%m-%d')}.csv"
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Date", "Session ID", "PC", "Duration (min)",
                    "Cost (PHP)", "Payment Method", "Receipt No",
                ])
                for s in completed:
                    pay = next((p for p in payments
                                if p["sessionId"] == s["id"]), None)
                    pc  = next((c for c in computers
                                if c["id"] == s["computerId"]), None)
                    writer.writerow([
                        datetime.fromtimestamp(s["endTime"] / 1000)
                        .strftime("%Y-%m-%d %H:%M")
                        if s.get("endTime") else "",
                        s["id"],
                        pc["name"] if pc else "?",
                        s.get("duration", ""),
                        s.get("cost", ""),
                        pay["method"] if pay else "",
                        pay["receiptNo"] if pay else "",
                    ])
            messagebox.showinfo("Export", f"Saved: {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ── Polling ───────────────────────────────────────────────

    def _poll(self):
        self._load_data()
        self.after(5_000, self._poll)