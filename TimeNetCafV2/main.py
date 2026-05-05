"""
main.py — TimeNet Cafe entry point.

Instantiates the root Tk window (App), wires up all page transitions,
and manages kiosk lock / unlock state.
"""

import tkinter as tk

from ui.theme import GRACE_SECONDS, ADMIN_EXIT_PIN
from ui.widget import apply_ttk_style
from auth.login import LoginPage, AuthState
from auth.register import RegisterPage
from dashboard.customer import CustomerDashboard
from dashboard.admin import AdminDashboard
from dashboard.lockscreen import AdminPinDialog, GraceOverlay


# ═══════════════════════════════════════════════════════════════
#  APPLICATION ROOT
# ═══════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TimeNet Cafe")
        self.configure(bg="#0f172a")  # BG — avoids circular import at module level

        self._locked       = True
        self._grace_overlay = None

        self._apply_lock()
        apply_ttk_style(self)

        self.container = tk.Frame(self, bg="#0f172a")
        self.container.pack(fill="both", expand=True)

        self.current_frame = None
        self.show_login()

        # Ctrl+Shift+Q → admin PIN exit (works even in fullscreen)
        self.bind_all("<Control-Shift-Q>", lambda e: self._admin_exit())

    # ── Admin forced exit ──────────────────────────────────────

    def _admin_exit(self):
        AdminPinDialog(self, on_success=self.destroy)

    # ── Lock / Unlock helpers ──────────────────────────────────

    def _apply_lock(self):
        """Enter fullscreen kiosk mode."""
        self._locked = True
        self.overrideredirect(False)
        self.update_idletasks()
        self.attributes("-fullscreen", True)
        self.overrideredirect(True)
        self.lift()
        self.focus_force()

    def unlock_for_session(self):
        """
        Release kiosk mode when a paid session starts.
        Shrinks the window to a small timer widget in the bottom-right corner.
        """
        self._locked = False
        self.attributes("-fullscreen", False)
        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        w, h = 280, 150
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{sw - w - 12}+{sh - h - 48}")

    def unlock_for_grace(self, on_grace_expired):
        self.after(100, lambda: self._create_grace_overlay(on_grace_expired))

    def _create_grace_overlay(self, on_grace_expired):
        self._grace_overlay = GraceOverlay(self, GRACE_SECONDS, on_grace_expired)

    def relock(self):
        """Re-enter kiosk mode (called when grace period ends or on logout)."""
        if self._grace_overlay:
            try:
                self._grace_overlay.destroy()
            except Exception:
                pass
            self._grace_overlay = None

        self.attributes("-topmost", False)
        self.overrideredirect(False)
        self.update_idletasks()
        self.resizable(True, True)
        self._apply_lock()

    # ── Frame / page switching ─────────────────────────────────

    def switch_frame(self, frame_cls, *args, **kwargs):
        if self.current_frame:
            self.current_frame.destroy()
        frame = frame_cls(self.container, self, *args, **kwargs)
        frame.pack(fill="both", expand=True)
        self.current_frame = frame

    def show_login(self):
        self.switch_frame(LoginPage)

    def show_register(self):
        self.switch_frame(RegisterPage)

    def show_customer_dashboard(self):
        self.switch_frame(CustomerDashboard)

    def show_admin_dashboard(self):
        self.switch_frame(AdminDashboard)

    def logout(self):
        AuthState.logout()
        if not self._locked:
            self.relock()
        self.show_login()


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()