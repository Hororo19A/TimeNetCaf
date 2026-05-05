"""
auth/login.py — Login page frame.
"""

import tkinter as tk
from database.database import storage
from ui.theme import BG, BG2, BG3, TEXT, TEXT2, CYAN, RED
from ui.widget import styled_frame, label, heading, entry, btn, separator


class AuthState:
    """Tiny in-process auth state singleton."""
    user = None

    @classmethod
    def login(cls, user_data: dict):
        cls.user = {k: v for k, v in user_data.items() if k != "password"}

    @classmethod
    def logout(cls):
        cls.user = None

    @classmethod
    def is_admin(cls) -> bool:
        return bool(cls.user and cls.user.get("role") == "admin")


class LoginPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = styled_frame(outer, bg=BG2)
        card.pack()

        heading(card, "🖥  TimeNet Cafe", size=20).pack(pady=(36, 6))
        label(card, "Sign in to manage your sessions",
              fg=TEXT2, font=("Segoe UI", 11)).pack(pady=(0, 22))
        separator(card).pack(fill="x", padx=30)

        form = styled_frame(card)
        form.pack(padx=40, pady=24, fill="x")

        self.err_lbl = label(form, "", fg=RED, bg=BG2,
                             wraplength=380, font=("Segoe UI", 10))
        self.err_lbl.pack(fill="x", pady=(0, 8))

        label(form, "Username", fg=TEXT2).pack(anchor="w")
        self.usr = tk.StringVar()
        entry(form, textvariable=self.usr, width=44).pack(
            fill="x", pady=(3, 12), ipady=5)

        label(form, "Password", fg=TEXT2).pack(anchor="w")
        self.pwd = tk.StringVar()
        entry(form, textvariable=self.pwd, show="•", width=44).pack(
            fill="x", pady=(3, 6), ipady=5)

        btn(form, "Sign In", command=self._login, bg=CYAN, fg=BG,
            font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(18, 4), ipady=8)

        separator(card).pack(fill="x", padx=30)
        footer = styled_frame(card)
        footer.pack(pady=16)
        label(footer, "Don't have an account? ", fg=TEXT2).pack(side="left")
        reg_btn = label(footer, "Register here", fg=CYAN, cursor="hand2",
                        font=("Segoe UI", 10, "underline"))
        reg_btn.pack(side="left")
        reg_btn.bind("<Button-1>", lambda _: self.app.show_register())

        self.bind_all("<Return>", lambda _: self._login())

    def _login(self):
        username = self.usr.get().strip()
        password = self.pwd.get().strip()
        if not username or not password:
            self.err_lbl.config(text="Please fill in all fields.")
            return

        users = storage.get_users()
        user  = next(
            (u for u in users
             if u["username"] == username and u["password"] == password),
            None,
        )
        if user:
            AuthState.login(user)
            if user["role"] == "admin":
                self.app.show_admin_dashboard()
            else:
                self.app.show_customer_dashboard()
        else:
            self.err_lbl.config(text="Invalid username or password.")