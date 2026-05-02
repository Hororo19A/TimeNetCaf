import customtkinter as ctk
from ui.theme import T
from ui.widget import lbl, btn, Entry, card
from database.database import DB


class RegisterFrame(ctk.CTkFrame):
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
        lbl(inner, "Create Account", T.FT, bold=True).pack()
        lbl(inner, "Join TimeNet Café", color=T.DIM, size=T.FS-2).pack(pady=(5, 20))

        self.err = lbl(inner, "", color=T.RED, size=T.FS-2)
        self.err.pack(pady=(0, 10))

        fields = [("Username",         "Choose a username",  None),
                  ("Email",            "your@email.com",     None),
                  ("Password",         "Enter password",     "•"),
                  ("Confirm Password", "Confirm password",   "•")]
        self.entries = {}
        for label, ph, sh in fields:
            lbl(inner, label, color=T.DIM, size=T.FS-2).pack(anchor="w")
            e = Entry(inner, ph, show=sh, width=300)
            e.pack(pady=(5, 10), ipady=4)
            self.entries[label] = e

        btn(inner, "Create Account", self.register_user, width=300).pack(fill="x", pady=(0, 5))

        row = ctk.CTkFrame(inner, fg_color=T.CARD); row.pack(pady=(15, 0))
        lbl(row, "Already have an account? ", color=T.DIM, size=T.FS-2).pack(side="left")
        r = ctk.CTkLabel(row, text="Sign in here", text_color=T.CYAN,
                         font=(T.FF, T.FS-2), cursor="hand2")
        r.pack(side="left")
        r.bind("<Button-1>", lambda _: self.app.show_login())

    def register_user(self):
        u  = self.entries["Username"].val()
        em = self.entries["Email"].val()
        pw = self.entries["Password"].val()
        cf = self.entries["Confirm Password"].val()
        if not all([u, em, pw, cf]):
            self.err.configure(text="Please fill in all fields"); return
        if pw != cf:
            self.err.configure(text="Passwords do not match"); return
        if len(pw) < 6:
            self.err.configure(text="Password must be at least 6 characters"); return
        user = DB.create_user(u, em, pw)
        if user:
            self.err.configure(text=""); self.app.login(user)
        else:
            self.err.configure(text="Username or email already exists")

    def clear(self):
        for e in self.entries.values():
            e.delete(0, "end")
        self.err.configure(text="")