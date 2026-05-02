import sqlite3
import hashlib
import time
from typing import Tuple

DB_FILE     = "timenet_cafe.db"
HOURLY_RATE = 15.0
MINUTE_RATE = HOURLY_RATE / 60


def calc_cost(start_ms: int, end_ms: int) -> Tuple[int, float]:
    diff = end_ms - start_ms
    mins = max(1, (diff // 60000) + (1 if diff % 60000 > 0 else 0))
    return mins, round(mins * MINUTE_RATE, 2)


def fmt_php(amount: float) -> str:
    return f"₱{amount:,.2f}"


def gen_receipt() -> str:
    t = str(int(time.time() * 1000))
    return f"RCPT-{t[-6:]}-{int(t) % 1000:03d}"


def fmt_elapsed(start_ms: int) -> str:
    d = int(time.time() * 1000) - start_ms
    h = d // 3_600_000
    m = (d % 3_600_000) // 60_000
    s = (d % 60_000) // 1000
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def init_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('customer','admin')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS computers (
        id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('available','occupied','maintenance')),
        current_session_id TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, computer_id TEXT NOT NULL,
        start_time INTEGER NOT NULL, end_time INTEGER, duration INTEGER,
        cost REAL, status TEXT NOT NULL CHECK(status IN ('active','completed')),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(computer_id) REFERENCES computers(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, user_id TEXT NOT NULL,
        amount REAL NOT NULL, method TEXT NOT NULL CHECK(method IN ('cash','gcash','card')),
        timestamp INTEGER NOT NULL, receipt_no TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(id),
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    conn.commit()
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                  ("admin-1", "admin", "admin@timenet.local",
                   hashlib.sha256(b"admin123").hexdigest(), "admin"))
        conn.commit()
    c.execute("SELECT COUNT(*) FROM computers")
    if c.fetchone()[0] == 0:
        for i in range(1, 9):
            c.execute("INSERT INTO computers VALUES(?,?,?,?)",
                      (f"pc-{i}", f"PC {str(i).zfill(2)}", "available", None))
        conn.commit()
    conn.close()


class DB:
    @staticmethod
    def conn(): return sqlite3.connect(DB_FILE)

    @staticmethod
    def auth(username, password):
        with DB.conn() as cn:
            row = cn.execute(
                "SELECT id,username,email,role FROM users WHERE username=? AND password_hash=?",
                (username, hashlib.sha256(password.encode()).hexdigest())
            ).fetchone()
        return {"id": row[0], "username": row[1], "email": row[2], "role": row[3]} if row else None

    @staticmethod
    def create_user(username, email, password, role="customer"):
        with DB.conn() as cn:
            if cn.execute("SELECT id FROM users WHERE username=? OR email=?",
                          (username, email)).fetchone():
                return None
            uid = f"user-{int(time.time()*1000)}"
            cn.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                       (uid, username, email,
                        hashlib.sha256(password.encode()).hexdigest(), role))
        return {"id": uid, "username": username, "email": email, "role": role}

    @staticmethod
    def computers():
        with DB.conn() as cn:
            rows = cn.execute("SELECT id,name,status,current_session_id FROM computers").fetchall()
        return [{"id": r[0], "name": r[1], "status": r[2], "current_session_id": r[3]} for r in rows]

    @staticmethod
    def set_computer(cid, status, session_id=None):
        with DB.conn() as cn:
            cn.execute("UPDATE computers SET status=?,current_session_id=? WHERE id=?",
                       (status, session_id, cid))

    @staticmethod
    def add_computer(name):
        try:
            with DB.conn() as cn:
                cn.execute("INSERT INTO computers VALUES(?,?,?,?)",
                           (f"pc-{int(time.time()*1000)}", name, "available", None))
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def del_computer(cid):
        with DB.conn() as cn:
            cn.execute("DELETE FROM computers WHERE id=?", (cid,))

    @staticmethod
    def active_session(user_id):
        with DB.conn() as cn:
            row = cn.execute(
                "SELECT id,user_id,computer_id,start_time,end_time,duration,cost,status "
                "FROM sessions WHERE user_id=? AND status='active'", (user_id,)).fetchone()
        if row:
            return {"id": row[0], "user_id": row[1], "computer_id": row[2], "start_time": row[3],
                    "end_time": row[4], "duration": row[5], "cost": row[6], "status": row[7]}
        return None

    @staticmethod
    def all_active_sessions():
        with DB.conn() as cn:
            rows = cn.execute(
                "SELECT id,user_id,computer_id,start_time FROM sessions WHERE status='active'"
            ).fetchall()
        return [{"id": r[0], "user_id": r[1], "computer_id": r[2], "start_time": r[3]} for r in rows]

    @staticmethod
    def start_session(user_id, computer_id):
        sid = f"sess-{int(time.time()*1000)}"
        st  = int(time.time() * 1000)
        with DB.conn() as cn:
            cn.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)",
                       (sid, user_id, computer_id, st, None, None, None, "active"))
            cn.execute("UPDATE computers SET status='occupied',current_session_id=? WHERE id=?",
                       (sid, computer_id))
        return {"id": sid, "user_id": user_id, "computer_id": computer_id,
                "start_time": st, "status": "active"}

    @staticmethod
    def end_session(session_id):
        with DB.conn() as cn:
            row = cn.execute(
                "SELECT start_time,computer_id FROM sessions WHERE id=?", (session_id,)).fetchone()
            st, cid = row
            et  = int(time.time() * 1000)
            dur, cost = calc_cost(st, et)
            cn.execute("UPDATE sessions SET end_time=?,duration=?,cost=?,status='completed' WHERE id=?",
                       (et, dur, cost, session_id))
        return {"id": session_id, "end_time": et, "duration": dur, "cost": cost, "computer_id": cid}

    @staticmethod
    def all_sessions():
        with DB.conn() as cn:
            rows = cn.execute(
                "SELECT id,user_id,computer_id,start_time,end_time,duration,cost,status "
                "FROM sessions ORDER BY start_time DESC").fetchall()
        return [{"id": r[0], "user_id": r[1], "computer_id": r[2], "start_time": r[3],
                 "end_time": r[4], "duration": r[5], "cost": r[6], "status": r[7]} for r in rows]

    @staticmethod
    def pay(session_id, user_id, amount, method):
        rcpt = gen_receipt()
        with DB.conn() as cn:
            cn.execute("INSERT INTO payments VALUES(?,?,?,?,?,?,?)",
                       (f"pay-{int(time.time()*1000)}", session_id, user_id,
                        amount, method, int(time.time() * 1000), rcpt))
        return rcpt

    @staticmethod
    def all_payments():
        with DB.conn() as cn:
            rows = cn.execute(
                "SELECT id,session_id,user_id,amount,method,timestamp,receipt_no FROM payments"
            ).fetchall()
        return [{"id": r[0], "session_id": r[1], "user_id": r[2], "amount": r[3],
                 "method": r[4], "timestamp": r[5], "receipt_no": r[6]} for r in rows]


    def save_session_timer(user_id, end_time):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("UPDATE users SET session_end=? WHERE id=?", (end_time, user_id))
        conn.commit()
        conn.close()