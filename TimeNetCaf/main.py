import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from database.database import init_database
from ui.theme import T
from auth.login import LoginFrame
from auth.register import RegisterFrame
from dashboard.customer import CustomerDashboard
from dashboard.admin import AdminDashboard

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TimeNetCafeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_database()
        self.title("TimeNet Café Management System")
        self.overrideredirect(True)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.configure(fg_color=T.BG)
        self.attributes("-topmost", True)

        self.user = None
        self.customer_can_exit = True

        self.lf  = LoginFrame(self, self)
        self.rf  = RegisterFrame(self, self)
        self.cdb = CustomerDashboard(self, self)
        self.adb = AdminDashboard(self, self)

        self.show_login()

    def _esc(self, _=None):
        if self.user and self.user.get("role") == "admin":
            self.destroy()
        elif not self.user:
            self.destroy()
        elif not self.customer_can_exit:
            CTkMessagebox(title="Blocked",
                          message="Please end your session and pay before closing.",
                          icon="warning")

    def show_login(self):
        self._hide(); self.lf.clear(); self.lf.pack(fill="both", expand=True)
        self.bind("<Escape>", self._esc)

    def show_register(self):
        self._hide(); self.rf.clear(); self.rf.pack(fill="both", expand=True)

    def login(self, user):
        self.user = user; self._hide()
        if user["role"] == "admin":
            self.adb.pack(fill="both", expand=True); self.adb.load()
            self.bind("<Escape>", self._esc)
        else:
            self.cdb.pack(fill="both", expand=True); self.cdb.load()
            self.unbind("<Escape>")

    def logout(self):
        self.cdb.cleanup(); self.adb.cleanup()
        self.user = None; self.show_login()

    def _hide(self):
        for f in [self.lf, self.rf, self.cdb, self.adb]:
            f.pack_forget()



if __name__ == "__main__":
    app = TimeNetCafeApp()
    app.mainloop()