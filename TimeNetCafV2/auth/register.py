"""
auth/register.py — Registration page frame.
"""

import tkinter as tk
from database.database import storage, now_ms
from auth.login import AuthState
from ui.theme import BG, BG2, TEXT, TEXT2, CYAN, RED
from ui.widget import styled_frame, label, heading, entry, btn, separator


class RegisterPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = styled_frame(outer, bg=BG2)
        card.pack()

        heading(card, "🖥  Create Account", size=20).pack(pady=(36, 6))
        label(card, "Join TimeNet Cafe",
              fg=TEXT2, font=("Segoe UI", 11)).pack(pady=(0, 22))
        separator(card).pack(fill="x", padx=30)

        form = styled_frame(card)
        form.pack(padx=40, pady=24, fill="x")

        self.err_lbl = label(form, "", fg=RED, bg=BG2,
                             wraplength=400, font=("Segoe UI", 10))
        self.err_lbl.pack(fill="x", pady=(0, 8))

        self.fields: dict[str, tk.StringVar] = {}
        field_defs = [
            ("Username",         "username",        False),
            ("Password",         "password",        True),
            ("Confirm Password", "confirmPassword",  True),
        ]
        for lbl_text, key, secret in field_defs:
            label(form, lbl_text, fg=TEXT2).pack(anchor="w")
            var = tk.StringVar()
            self.fields[key] = var
            entry(form, textvariable=var,
                  show=("•" if secret else None), width=46).pack(
                fill="x", pady=(3, 12), ipady=5)

        btn(form, "Create Account", command=self._register,
            bg=CYAN, fg=BG,
            font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(6, 4), ipady=8)

        separator(card).pack(fill="x", padx=30)
        footer = styled_frame(card)
        footer.pack(pady=16)
        label(footer, "Already have an account? ", fg=TEXT2).pack(side="left")
        back = label(footer, "Sign in here", fg=CYAN, cursor="hand2",
                     font=("Segoe UI", 10, "underline"))
        back.pack(side="left")
        back.bind("<Button-1>", lambda _: self.app.show_login())

    def _register(self):
        data = {k: v.get().strip() for k, v in self.fields.items()}
        if not all(data.values()):
            self.err_lbl.config(text="Please fill in all fields.")
            return
        if data["password"] != data["confirmPassword"]:
            self.err_lbl.config(text="Passwords do not match.")
            return
        if len(data["password"]) < 6:
            self.err_lbl.config(text="Password must be at least 6 characters.")
            return

        users = storage.get_users()
        if any(u["username"] == data["username"] for u in users):
            self.err_lbl.config(text="Username already exists.")
            return

        new_user = {
            "id":       f"user-{now_ms()}",
            "username": data["username"],
            "password": data["password"],
            "role":     "customer",
        }
        storage.save_users([*users, new_user])
        AuthState.login(new_user)
        self.app.show_customer_dashboard()