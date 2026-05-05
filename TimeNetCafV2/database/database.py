"""
database/database.py — JSON-backed persistence layer.

All reads and writes to timenet_data.json go through this module.
"""

import json
import os
import time
import random

DATA_FILE = "timenet_cafe.json"


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def now_ms() -> int:
    """Current time in milliseconds since epoch."""
    return int(time.time() * 1000)


def generate_receipt_no() -> str:
    ts  = str(int(time.time() * 1000))[-6:]
    rnd = str(random.randint(0, 999)).zfill(3)
    return f"RCPT-{ts}-{rnd}"


def generate_voucher_code() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code  = "".join(random.choices(chars, k=8))
    return f"TN-{code}"


def format_currency(amount: float) -> str:
    return f"₱{amount:,.2f}"


# ─────────────────────────────────────────────
#  STORAGE
# ─────────────────────────────────────────────

class Storage:
    """Single-file JSON store for users, computers, sessions, and payments."""

    def __init__(self):
        self.data: dict = {
            "users":     [],
            "computers": [],
            "sessions":  [],
            "payments":  [],
        }
        self.load()
        self._seed_defaults()

    # ── Persistence ───────────────────────────

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    self.data = json.load(f)
            except Exception:
                pass  # corrupt file → start fresh

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def _seed_defaults(self):
        """Create the default admin user and 8 PCs on first run."""
        if not self.data["users"]:
            self.data["users"].append({
                "id":       "admin-1",
                "username": "admin",
                "password": "admin123",
                "role":     "admin",
            })
        if not self.data["computers"]:
            for i in range(1, 9):
                self.data["computers"].append({
                    "id":               f"pc-{i}",
                    "name":             f"PC {str(i).zfill(2)}",
                    "status":           "available",
                    "currentSessionId": None,
                })
        self.save()

    # ── Users ──────────────────────────────────

    def get_users(self) -> list:
        return self.data["users"]

    def save_users(self, users: list):
        self.data["users"] = users
        self.save()

    # ── Computers ─────────────────────────────

    def get_computers(self) -> list:
        return self.data["computers"]

    def save_computers(self, computers: list):
        self.data["computers"] = computers
        self.save()

    # ── Sessions ──────────────────────────────

    def get_sessions(self) -> list:
        return self.data["sessions"]

    def save_sessions(self, sessions: list):
        self.data["sessions"] = sessions
        self.save()

    # ── Payments ──────────────────────────────

    def get_payments(self) -> list:
        return self.data["payments"]

    def save_payments(self, payments: list):
        self.data["payments"] = payments
        self.save()


# Module-level singleton — import this everywhere
storage = Storage()