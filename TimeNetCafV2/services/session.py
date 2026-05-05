"""
services/session.py — Session lifecycle: create, activate, end.
"""

from database.database import storage, now_ms, generate_receipt_no, generate_voucher_code
from services.billing import calc_cost


def create_session(user_id: str, computer_id: str, minutes: int, method: str) -> dict:
    """
    Build and persist a new session + payment record.

    For cash payments the session starts as 'pending_voucher' and a voucher
    code is generated.  For GCash / Maya the session is immediately 'active'.

    Returns a dict:
        {
            "session":      <session dict>,
            "payment":      <payment dict>,
            "voucher_code": <str | None>,
            "receipt_no":   <str>,
        }
    """
    is_cash      = method == "cash"
    cost         = calc_cost(minutes)
    session_id   = f"sess-{now_ms()}"
    receipt_no   = generate_receipt_no()
    voucher_code = generate_voucher_code() if is_cash else None

    new_session = {
        "id":           session_id,
        "userId":       user_id,
        "computerId":   computer_id,
        "startTime":    now_ms(),
        "duration":     minutes,
        "cost":         cost,
        "status":       "pending_voucher" if is_cash else "active",
        "voucherCode":  voucher_code,
        "paidUpfront":  True,
    }

    # Mark computer occupied
    computers = storage.get_computers()
    for c in computers:
        if c["id"] == computer_id:
            c["status"]           = "occupied"
            c["currentSessionId"] = session_id
    storage.save_computers(computers)

    # Persist session
    sessions = storage.get_sessions()
    sessions.append(new_session)
    storage.save_sessions(sessions)

    # Persist payment
    new_payment = {
        "id":        f"pay-{now_ms()}",
        "sessionId": session_id,
        "userId":    user_id,
        "amount":    cost,
        "method":    method,
        "timestamp": now_ms(),
        "receiptNo": receipt_no,
    }
    payments = storage.get_payments()
    payments.append(new_payment)
    storage.save_payments(payments)

    return {
        "session":      new_session,
        "payment":      new_payment,
        "voucher_code": voucher_code,
        "receipt_no":   receipt_no,
    }


def activate_voucher(code: str) -> dict | None:
    """
    Activate a pending_voucher session by its voucher code.

    Returns the updated session dict on success, or None if not found.
    """
    sessions = storage.get_sessions()
    target   = next(
        (s for s in sessions
         if s["status"] == "pending_voucher" and s.get("voucherCode") == code),
        None,
    )
    if not target:
        return None

    for s in sessions:
        if s["id"] == target["id"]:
            s["status"]    = "active"
            s["startTime"] = now_ms()
    storage.save_sessions(sessions)
    return target


def end_session(session_id: str):
    """Mark a session completed and free its computer."""
    sessions = storage.get_sessions()
    session  = None
    for s in sessions:
        if s["id"] == session_id:
            s["endTime"] = now_ms()
            s["status"]  = "completed"
            session      = s
    storage.save_sessions(sessions)

    if session:
        computers = storage.get_computers()
        for c in computers:
            if c["id"] == session["computerId"]:
                c["status"]           = "available"
                c["currentSessionId"] = None
        storage.save_computers(computers)


def get_active_session_for_user(user_id: str) -> dict | None:
    """Return the first 'active' session belonging to user_id, or None."""
    return next(
        (s for s in storage.get_sessions()
         if s.get("userId") == user_id and s["status"] == "active"),
        None,
    )


def get_first_available_computer() -> dict | None:
    """Return the first computer whose status is 'available', or None."""
    return next(
        (c for c in storage.get_computers() if c["status"] == "available"),
        None,
    )