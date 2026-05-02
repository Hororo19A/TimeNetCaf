import customtkinter as ctk
from ui.theme import T
from ui.widget import lbl, btn, Entry, card
from database.database import DB


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=T.BG, corner_radius=0)
        self.app = app
        self._build()

    def _build(self):
        c = ctk.CTkFrame(self, fg_color=T.BG)
        c.place(relx=.5, rely=.5, anchor="center")
        outer = card(c); outer.pack(padx=20, pady=20)
        inner = ctk.CTkFrame(outer, fg_color=T.CARD, corner_radius=0)
        inner.pack(padx=40, pady=40)

        lbl(inner, "🖥️", T.FH).pack(pady=(0, 10))
        lbl(inner, "TimeNet Café", T.FT, bold=True).pack()
        lbl(inner, "Sign in to manage your sessions", color=T.DIM, size=T.FS-2).pack(pady=(5, 20))

        self.err = lbl(inner, "", color=T.RED, size=T.FS-2)
        self.err.pack(pady=(0, 10))

        lbl(inner, "Username", color=T.DIM, size=T.FS-2).pack(anchor="w")
        self.u = Entry(inner, "Enter your username", width=300)
        self.u.pack(pady=(5, 15), ipady=4)

        lbl(inner, "Password", color=T.DIM, size=T.FS-2).pack(anchor="w")
        self.p = Entry(inner, "Enter your password", show="•", width=300)
        self.p.pack(pady=(5, 20), ipady=4)
        self.p.bind("<Return>", lambda _: self._login())

        btn(inner, "Sign In", self._login, width=300).pack(fill="x", pady=(0, 5))

        row = ctk.CTkFrame(inner, fg_color=T.CARD); row.pack(pady=(15, 0))
        lbl(row, "Don't have an account? ", color=T.DIM, size=T.FS-2).pack(side="left")
        r = ctk.CTkLabel(row, text="Register here", text_color=T.CYAN,
                         font=(T.FF, T.FS-2), cursor="hand2")
        r.pack(side="left")
        r.bind("<Button-1>", lambda _: self.app.show_register())

    def _login(self):
        u, p = self.u.val(), self.p.val()
        if not u or not p:
            self.err.configure(text="Please enter username and password"); return
        user = DB.auth(u, p)
        if user:
            self.err.configure(text=""); self.app.login(user)
        else:
            self.err.configure(text="Invalid username or password")

    def clear(self):
        self.u.delete(0, "end")
        self.p.delete(0, "end")
        self.err.configure(text="")