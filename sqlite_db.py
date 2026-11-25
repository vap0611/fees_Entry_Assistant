"""
SQLite Database Layer for Fees Entry Assistant
Provides complete ACID persistence for:
- Students, Month Columns, Fee Payments & Activity Audit Logs
- Users, Roles, Brute-Force Lockouts, TOTP 2FA, Recovery Codes & Auth Audit Logs
- Real-Time Analytics & CSV Export
"""

import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from month_logic import (
    find_last_paid_month,
    format_month_header,
    get_current_month_header,
    parse_month_header,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.environ.get("VERCEL"):
    DATA_DIR = "/tmp"
    DB_PATH = "/tmp/fees.db"
    ORIGINAL_DB = os.path.join(BASE_DIR, "data", "fees.db")
    if not os.path.exists(DB_PATH) and os.path.exists(ORIGINAL_DB):
        import shutil
        try:
            shutil.copy2(ORIGINAL_DB, DB_PATH)
        except Exception:
            pass
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "fees.db")

CSV_PATH = os.path.join(BASE_DIR, "data", "students.csv")
EXAMPLE_CSV_PATH = os.path.join(BASE_DIR, "data", "students.example.csv")

INITIAL_MONTHS = ["Oct 2026", "Nov 2026", "Dec 2026"]
VALID_PAYMENT_MODES = ("Cash", "UPI", "Bank Transfer", "Card", "Cheque")
VALID_ROLES = ("admin", "staff", "viewer")


def get_db():
    """Returns a SQLite connection with foreign keys enabled and row access by name."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_column(conn, table, column_name, column_definition):
    """Safely adds a missing column to an existing SQLite table."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_definition}")


def init_db(force_reseed=False):
    """
    Creates SQLite tables, runs safe schema migrations, and builds indexes.
    Seeds initial ledger data from CSV if students table is empty or force_reseed=True.
    Note: force_reseed preserves users, auth_audit_logs, and app_settings!
    """
    conn = get_db()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    std TEXT DEFAULT '',
                    school TEXT DEFAULT '',
                    monthly_fee INTEGER NOT NULL DEFAULT 0,
                    guardian_phone TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS month_columns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month_header TEXT UNIQUE NOT NULL,
                    order_index INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS fee_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    month_header TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    entry_id TEXT,
                    payment_mode TEXT DEFAULT 'Cash',
                    note TEXT DEFAULT '',
                    recorded_by TEXT DEFAULT 'System',
                    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id, month_header)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id TEXT PRIMARY KEY,
                    time TEXT NOT NULL,
                    student TEXT NOT NULL,
                    school TEXT DEFAULT '',
                    amount INTEGER DEFAULT 0,
                    month TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    actor TEXT DEFAULT 'System',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    full_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'staff',
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT DEFAULT '',
                    session_version INTEGER NOT NULL DEFAULT 1,
                    totp_secret TEXT DEFAULT '',
                    totp_enabled INTEGER NOT NULL DEFAULT 0,
                    recovery_codes_json TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_audit_logs (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ip_address TEXT DEFAULT '',
                    detail TEXT DEFAULT '',
                    success INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Safe migrations for pre-existing fees.db databases
            _ensure_column(conn, "students", "guardian_phone", "TEXT DEFAULT ''")
            _ensure_column(conn, "students", "notes", "TEXT DEFAULT ''")
            _ensure_column(conn, "students", "status", "TEXT NOT NULL DEFAULT 'active'")
            _ensure_column(conn, "fee_payments", "payment_mode", "TEXT DEFAULT 'Cash'")
            _ensure_column(conn, "fee_payments", "note", "TEXT DEFAULT ''")
            _ensure_column(conn, "fee_payments", "recorded_by", "TEXT DEFAULT 'System'")
            _ensure_column(conn, "activity_logs", "actor", "TEXT DEFAULT 'System'")

            # Default settings
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('allow_self_registration', 'true')"
            )

            # Performance indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_students_name ON students(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_students_status ON students(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_student ON fee_payments(student_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_month ON fee_payments(month_header)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_logs(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_audit_time ON auth_audit_logs(created_at DESC)")

        # Check if students exist; if not or if forced, seed ledger data from CSV
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students")
        student_count = cur.fetchone()[0]

        if student_count == 0 or force_reseed:
            seed_initial_data(conn, force=force_reseed)
    finally:
        conn.close()


def seed_initial_data(conn, force=False):
    """Seeds students from local CSV or example CSV without disturbing user accounts."""
    with conn:
        if force:
            conn.execute("DELETE FROM fee_payments")
            conn.execute("DELETE FROM month_columns")
            conn.execute("DELETE FROM students")
            conn.execute("DELETE FROM activity_logs")

        # 1. Seed Initial Month Columns
        for idx, month in enumerate(INITIAL_MONTHS):
            conn.execute(
                "INSERT OR IGNORE INTO month_columns (month_header, order_index) VALUES (?, ?)",
                (month, idx)
            )

        # 2. Seed Students from CSV
        csv_path = CSV_PATH if os.path.exists(CSV_PATH) else EXAMPLE_CSV_PATH
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if not row or not any(cell.strip() for cell in row):
                        continue
                    name = row[0].strip()
                    if not name or name.lower() == "total":
                        continue
                    std = row[1].strip() if len(row) > 1 else ""
                    school = row[2].strip() if len(row) > 2 else ""
                    fee_str = row[3].strip() if len(row) > 3 else "0"
                    try:
                        fee = int(float(fee_str.replace(",", "")))
                    except Exception:
                        fee = 0

                    conn.execute(
                        "INSERT INTO students (name, std, school, monthly_fee) VALUES (?, ?, ?, ?)",
                        (name, std, school, fee)
                    )

        # 3. Initial Log Entry
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students")
        count = cur.fetchone()[0]
        time_str = datetime.now().strftime("%I:%M:%S %p")
        conn.execute(
            """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4())[:8],
                time_str,
                "System",
                "All",
                0,
                "—",
                "SQLite Ready",
                f"SQLite database initialized with {count} students from configured seed CSV.",
                "System"
            )
        )


# ==============================================================================
# APP SETTINGS HELPERS
# ==============================================================================

def get_setting_db(key, default=""):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting_db(key, value):
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO app_settings (key, value, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
                (key, str(value))
            )
    finally:
        conn.close()


# ==============================================================================
# AUTHENTICATION & USER DATABASE OPERATIONS
# ==============================================================================

def get_user_count_db():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_user_by_id_db(user_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_identifier_db(identifier):
    """Finds user by username or email (case-insensitive)."""
    cleaned = (identifier or "").strip().lower()
    if not cleaned:
        return None
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
            (cleaned, cleaned)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_user_db(username, email, full_name, password_hash, role="staff", recovery_codes_hashes=None):
    """Creates a new user account in SQLite."""
    conn = get_db()
    try:
        with conn:
            cur = conn.cursor()
            rec_json = json.dumps(recovery_codes_hashes or [])
            cur.execute(
                """INSERT INTO users (username, email, full_name, role, password_hash, recovery_codes_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username.lower(), email.lower() if email else None, full_name.strip(), role, password_hash, rec_json)
            )
            uid = cur.lastrowid
        return get_user_by_id_db(uid)
    finally:
        conn.close()


def list_users_db():
    """Returns sanitized user list for Admin User Management."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, username, email, full_name, role, is_active,
                      failed_attempts, locked_until, totp_enabled, created_at, last_login_at
               FROM users ORDER BY id ASC"""
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        results = []
        for r in cur.fetchall():
            item = dict(r)
            is_locked = False
            if item.get("locked_until"):
                try:
                    locked_dt = datetime.fromisoformat(item["locked_until"])
                    is_locked = locked_dt > now
                except ValueError:
                    pass
            item["is_active"] = bool(item["is_active"])
            item["totp_enabled"] = bool(item["totp_enabled"])
            item["is_locked"] = is_locked
            results.append(item)
        return results
    finally:
        conn.close()


def update_user_db(user_id, full_name=None, email=None, role=None, is_active=None, unlock=False):
    """Updates user metadata, role, status, or clears account lockout."""
    conn = get_db()
    try:
        user = get_user_by_id_db(user_id)
        if not user:
            return None
        new_full_name = full_name.strip() if full_name is not None else user["full_name"]
        new_email = email.strip().lower() if email is not None else user["email"]
        new_role = role if role in VALID_ROLES else user["role"]
        new_active = int(bool(is_active)) if is_active is not None else user["is_active"]

        with conn:
            if unlock:
                conn.execute(
                    """UPDATE users
                       SET full_name = ?, email = ?, role = ?, is_active = ?,
                           failed_attempts = 0, locked_until = ''
                       WHERE id = ?""",
                    (new_full_name, new_email, new_role, new_active, user_id)
                )
            else:
                conn.execute(
                    """UPDATE users
                       SET full_name = ?, email = ?, role = ?, is_active = ?
                       WHERE id = ?""",
                    (new_full_name, new_email, new_role, new_active, user_id)
                )
        return get_user_by_id_db(user_id)
    finally:
        conn.close()


def delete_user_db(user_id):
    conn = get_db()
    try:
        with conn:
            cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def record_login_failure_db(user_id, max_attempts=5, lock_minutes=5):
    """Increments failed login attempts and locks account after max_attempts."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT failed_attempts FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return 0, None
        attempts = int(row["failed_attempts"] or 0) + 1
        locked_until = ""
        if attempts >= max_attempts:
            locked_dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=lock_minutes)
            locked_until = locked_dt.isoformat()
        with conn:
            conn.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, locked_until, user_id)
            )
        return attempts, locked_until
    finally:
        conn.close()


def record_login_success_db(user_id):
    """Resets failed attempts and stamps last_login_at."""
    conn = get_db()
    try:
        now_iso = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        with conn:
            conn.execute(
                """UPDATE users
                   SET failed_attempts = 0, locked_until = '', last_login_at = ?
                   WHERE id = ?""",
                (now_iso, user_id)
            )
    finally:
        conn.close()


def update_user_password_db(user_id, new_password_hash):
    """Updates password hash and rotates session_version to invalidate stale sessions."""
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """UPDATE users
                   SET password_hash = ?, session_version = session_version + 1,
                       failed_attempts = 0, locked_until = ''
                   WHERE id = ?""",
                (new_password_hash, user_id)
            )
        return get_user_by_id_db(user_id)
    finally:
        conn.close()


def increment_session_version_db(user_id):
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET session_version = session_version + 1 WHERE id = ?",
                (user_id,)
            )
    finally:
        conn.close()


def set_user_totp_db(user_id, secret, enabled, recovery_codes_hashes=None):
    conn = get_db()
    try:
        with conn:
            if recovery_codes_hashes is not None:
                conn.execute(
                    """UPDATE users
                       SET totp_secret = ?, totp_enabled = ?, recovery_codes_json = ?
                       WHERE id = ?""",
                    (secret, int(bool(enabled)), json.dumps(recovery_codes_hashes), user_id)
                )
            else:
                conn.execute(
                    "UPDATE users SET totp_secret = ?, totp_enabled = ? WHERE id = ?",
                    (secret, int(bool(enabled)), user_id)
                )
    finally:
        conn.close()


def consume_recovery_code_db(user_id, code_hash):
    """Checks and consumes a single-use backup recovery code hash."""
    user = get_user_by_id_db(user_id)
    if not user:
        return False
    try:
        codes = json.loads(user.get("recovery_codes_json") or "[]")
    except ValueError:
        codes = []

    if code_hash not in codes:
        return False

    codes.remove(code_hash)
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET recovery_codes_json = ? WHERE id = ?",
                (json.dumps(codes), user_id)
            )
        return True
    finally:
        conn.close()


def log_auth_event_db(username, event_type, ip_address="", detail="", success=True):
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO auth_audit_logs (id, username, event_type, ip_address, detail, success)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4())[:10], username or "anonymous", event_type, ip_address, detail, int(bool(success)))
            )
    finally:
        conn.close()


def get_auth_audit_logs_db(limit=100):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, username, event_type, ip_address, detail, success, created_at
               FROM auth_audit_logs ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        return [
            {
                "id": r["id"],
                "username": r["username"],
                "event_type": r["event_type"],
                "ip_address": r["ip_address"],
                "detail": r["detail"],
                "success": bool(r["success"]),
                "created_at": r["created_at"]
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


# ==============================================================================
# MONTH COLUMNS
# ==============================================================================

def get_month_columns():
    """Returns sorted list of month header strings."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT month_header FROM month_columns ORDER BY order_index ASC")
        rows = cur.fetchall()
        return [r["month_header"] for r in rows]
    finally:
        conn.close()


def add_month_column_if_missing(month_header):
    """Adds a month column to SQLite if not already present."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM month_columns WHERE month_header = ?", (month_header,))
        if cur.fetchone():
            return False

        with conn:
            cur.execute("SELECT COALESCE(MAX(order_index), -1) + 1 FROM month_columns")
            next_idx = cur.fetchone()[0]
            conn.execute(
                "INSERT INTO month_columns (month_header, order_index) VALUES (?, ?)",
                (month_header, next_idx)
            )
        return True
    finally:
        conn.close()


def add_month_column_validated_db(month_header, actor="System"):
    """Validates canonical month format (e.g. 'Jan 2027') and creates the column."""
    try:
        y, m_num, _ = parse_month_header(month_header)
        canonical = format_month_header(y, m_num, "text")
    except ValueError as e:
        return {"success": False, "reply": f"⚠️ {e}"}

    created = add_month_column_if_missing(canonical)
    if not created:
        return {"success": False, "reply": f"⚠️ Month column '{canonical}' already exists."}

    log_activity_db(
        student="All Students",
        school="All",
        amount=0,
        month=canonical,
        status="Col Added",
        note=f"Month column '{canonical}' created",
        actor=actor
    )
    return {
        "success": True,
        "reply": f"📅 Created month column **'{canonical}'**.",
        "month_header": canonical,
        "table": get_table_state()
    }


def delete_month_column_db(month_name, actor="System"):
    """
    Deletes a month column and its corresponding recorded payments in SQLite.
    Returns result dict with updated table state.
    """
    cleaned_month = month_name.strip()
    months = get_month_columns()

    # Case-insensitive match
    match_col = next((m for m in months if m.lower() == cleaned_month.lower()), None)
    if not match_col:
        try:
            y, m_num, _ = parse_month_header(cleaned_month)
            canonical = format_month_header(y, m_num, "text")
            match_col = next((m for m in months if m.lower() == canonical.lower()), None)
        except Exception:
            pass

    if not match_col:
        return {
            "success": False,
            "reply": f"⚠️ Column '{month_name}' was not found in the SQLite database."
        }

    conn = get_db()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM fee_payments WHERE month_header = ?",
                (match_col,)
            )
            cleared_count, total_amount_cleared = cur.fetchone()

            conn.execute("DELETE FROM fee_payments WHERE month_header = ?", (match_col,))
            conn.execute("DELETE FROM month_columns WHERE month_header = ?", (match_col,))

            cur.execute("SELECT id FROM month_columns ORDER BY order_index ASC")
            rows = cur.fetchall()
            for new_idx, row in enumerate(rows):
                conn.execute("UPDATE month_columns SET order_index = ? WHERE id = ?", (new_idx, row["id"]))

            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    "All Students",
                    "All",
                    total_amount_cleared,
                    match_col,
                    "Col Deleted",
                    f"Column '{match_col}' deleted ({cleared_count} payments removed)",
                    actor
                )
            )
    finally:
        conn.close()

    return {
        "success": True,
        "reply": f"🗑️ Column **'{match_col}'** has been deleted from SQLite and all associated payments cleared.",
        "deleted_column": match_col,
        "table": get_table_state()
    }


# ==============================================================================
# STUDENTS & PAYMENTS CRUD
# ==============================================================================

def get_all_students_with_payments():
    """Fetches all students and attaches their payments map plus detailed payment metadata."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, name, std, school, monthly_fee, guardian_phone, notes, status, created_at
               FROM students ORDER BY id ASC"""
        )
        students_rows = cur.fetchall()

        cur.execute(
            """SELECT student_id, month_header, amount, entry_id, payment_mode, note, recorded_by, paid_at
               FROM fee_payments"""
        )
        payments_rows = cur.fetchall()
    finally:
        conn.close()

    payments_map = {}
    payments_meta_map = {}
    for p in payments_rows:
        sid = p["student_id"]
        if sid not in payments_map:
            payments_map[sid] = {}
            payments_meta_map[sid] = {}
        payments_map[sid][p["month_header"]] = p["amount"]
        payments_meta_map[sid][p["month_header"]] = {
            "amount": p["amount"],
            "payment_mode": p["payment_mode"] or "Cash",
            "note": p["note"] or "",
            "recorded_by": p["recorded_by"] or "System",
            "paid_at": p["paid_at"] or "",
            "entry_id": p["entry_id"] or ""
        }

    students = []
    for s in students_rows:
        sid = s["id"]
        students.append({
            "id": sid,
            "name": s["name"],
            "std": s["std"] or "",
            "school": s["school"] or "",
            "monthly_fee": s["monthly_fee"],
            "guardian_phone": s["guardian_phone"] or "",
            "notes": s["notes"] or "",
            "status": s["status"] or "active",
            "created_at": s["created_at"] or "",
            "payments": payments_map.get(sid, {}),
            "payments_meta": payments_meta_map.get(sid, {})
        })

    return students


def get_table_state():
    """Returns the live state and KPI totals of the entire SQLite database."""
    months = get_month_columns()
    students = get_all_students_with_payments()
    active_students = [s for s in students if s.get("status", "active") == "active"]
    total_base = sum(s["monthly_fee"] for s in active_students)

    month_totals = {m: 0 for m in months}
    total_collected_all = 0
    for s in students:
        for m, amt in (s.get("payments") or {}).items():
            if isinstance(amt, (int, float)):
                total_collected_all += amt
                if m in month_totals:
                    month_totals[m] += amt

    # Determine focus month for pending count
    current_month = get_current_month_header()
    focus_month = current_month if current_month in months else (months[-1] if months else None)
    paid_focus = 0
    if focus_month:
        paid_focus = sum(
            1 for s in active_students
            if s.get("payments", {}).get(focus_month) not in (None, "", 0)
        )
    pending_count = max(0, len(active_students) - paid_focus)
    collected_focus = month_totals.get(focus_month, 0) if focus_month else 0
    collection_rate = round((collected_focus / total_base) * 100, 1) if total_base > 0 else 0.0

    return {
        "months": months,
        "students": students,
        "total_students": len(students),
        "active_students": len(active_students),
        "total_base_fees": total_base,
        "total_collected_all": total_collected_all,
        "focus_month": focus_month,
        "focus_collected": collected_focus,
        "collection_rate": collection_rate,
        "paid_count": paid_focus,
        "pending_count": pending_count,
        "month_totals": month_totals
    }


def add_student_db(name, std="", school="", monthly_fee=0, guardian_phone="", notes="", actor="System"):
    """Inserts a new student into SQLite with strict validation."""
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return {"success": False, "reply": "⚠️ Student name is required."}
    if len(cleaned_name) > 100:
        return {"success": False, "reply": "⚠️ Student name must be 100 characters or fewer."}

    try:
        raw_fee = str(monthly_fee).replace(",", "").strip()
        fee = int(float(raw_fee))
        if fee < 0:
            return {"success": False, "reply": "⚠️ Monthly fee cannot be negative."}
        if fee > 10_000_000:
            return {"success": False, "reply": "⚠️ Monthly fee cannot exceed ₹10,000,000."}
    except (ValueError, TypeError, OverflowError):
        return {"success": False, "reply": "⚠️ Please enter a valid number for monthly fee."}

    cleaned_std = (std or "").strip()[:20]
    cleaned_school = (school or "").strip()[:100]
    cleaned_phone = (guardian_phone or "").strip()[:25]
    cleaned_notes = (notes or "").strip()[:300]

    conn = get_db()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO students (name, std, school, monthly_fee, guardian_phone, notes, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'active')""",
                (cleaned_name, cleaned_std, cleaned_school, fee, cleaned_phone, cleaned_notes)
            )
            new_id = cur.lastrowid

            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    cleaned_name,
                    cleaned_school or "—",
                    fee,
                    "—",
                    "Added",
                    f"New student enrolled (ID: {new_id}, Std: {cleaned_std})",
                    actor
                )
            )
    finally:
        conn.close()

    new_student = {
        "id": new_id,
        "name": cleaned_name,
        "std": cleaned_std,
        "school": cleaned_school,
        "monthly_fee": fee,
        "guardian_phone": cleaned_phone,
        "notes": cleaned_notes,
        "status": "active",
        "payments": {},
        "payments_meta": {}
    }

    parts = []
    if cleaned_std:
        parts.append(f"Std {cleaned_std}")
    if cleaned_school:
        parts.append(cleaned_school)
    label = f"{cleaned_name} ({', '.join(parts)})" if parts else cleaned_name

    reply = f"✅ Added new student **{label}** with base fee **₹{fee:,}** in SQLite."
    return {
        "success": True,
        "reply": reply,
        "student": new_student,
        "table": get_table_state()
    }


def get_student_detail_db(student_id):
    """Returns enriched student profile, chronological payment history, and summary metrics."""
    months = get_month_columns()
    students = get_all_students_with_payments()
    student = next((s for s in students if s["id"] == student_id), None)
    if not student:
        return None

    payments_meta = student.get("payments_meta", {})
    history = []
    total_paid = 0
    paid_months = 0

    for m in months:
        meta = payments_meta.get(m)
        if meta:
            amt = meta["amount"]
            total_paid += amt
            paid_months += 1
            history.append({
                "month": m,
                "status": "paid",
                "amount": amt,
                "payment_mode": meta["payment_mode"],
                "note": meta["note"],
                "recorded_by": meta["recorded_by"],
                "paid_at": meta["paid_at"],
                "entry_id": meta["entry_id"]
            })
        else:
            history.append({
                "month": m,
                "status": "pending",
                "amount": 0,
                "payment_mode": "",
                "note": "",
                "recorded_by": "",
                "paid_at": "",
                "entry_id": ""
            })

    # Include any payments whose months might be outside sorted list
    for m, meta in payments_meta.items():
        if m not in months:
            total_paid += meta["amount"]
            paid_months += 1
            history.append({
                "month": m,
                "status": "paid",
                "amount": meta["amount"],
                "payment_mode": meta["payment_mode"],
                "note": meta["note"],
                "recorded_by": meta["recorded_by"],
                "paid_at": meta["paid_at"],
                "entry_id": meta["entry_id"]
            })

    return {
        "student": student,
        "history": history,
        "total_paid": total_paid,
        "paid_months_count": paid_months,
        "pending_months_count": max(0, len(months) - paid_months),
        "last_paid_month": find_last_paid_month(student.get("payments", {}), months)
    }


def update_student_db(student_id, name=None, std=None, school=None, monthly_fee=None,
                      guardian_phone=None, notes=None, status=None, actor="System"):
    """Updates an existing student's profile details."""
    students = get_all_students_with_payments()
    existing = next((s for s in students if s["id"] == student_id), None)
    if not existing:
        return {"success": False, "reply": "⚠️ Student not found."}

    new_name = existing["name"]
    if name is not None:
        cleaned_name = str(name).strip()
        if not cleaned_name:
            return {"success": False, "reply": "⚠️ Student name cannot be empty."}
        if len(cleaned_name) > 100:
            return {"success": False, "reply": "⚠️ Student name must be 100 characters or fewer."}
        new_name = cleaned_name

    new_fee = existing["monthly_fee"]
    if monthly_fee is not None:
        try:
            fee = int(float(str(monthly_fee).replace(",", "").strip()))
            if fee < 0 or fee > 10_000_000:
                return {"success": False, "reply": "⚠️ Monthly fee must be between ₹0 and ₹10,000,000."}
            new_fee = fee
        except (ValueError, TypeError, OverflowError):
            return {"success": False, "reply": "⚠️ Invalid monthly fee value."}

    new_std = str(std).strip()[:20] if std is not None else existing["std"]
    new_school = str(school).strip()[:100] if school is not None else existing["school"]
    new_phone = str(guardian_phone).strip()[:25] if guardian_phone is not None else existing["guardian_phone"]
    new_notes = str(notes).strip()[:300] if notes is not None else existing["notes"]
    new_status = status if status in ("active", "inactive") else existing["status"]

    conn = get_db()
    try:
        with conn:
            conn.execute(
                """UPDATE students
                   SET name = ?, std = ?, school = ?, monthly_fee = ?,
                       guardian_phone = ?, notes = ?, status = ?
                   WHERE id = ?""",
                (new_name, new_std, new_school, new_fee, new_phone, new_notes, new_status, student_id)
            )
            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    new_name,
                    new_school or "—",
                    new_fee,
                    "—",
                    "Updated",
                    f"Student profile updated (Std: {new_std}, Status: {new_status})",
                    actor
                )
            )
    finally:
        conn.close()

    detail = get_student_detail_db(student_id)
    return {
        "success": True,
        "reply": f"✅ Updated student **{new_name}**.",
        "student": detail["student"] if detail else None,
        "detail": detail,
        "table": get_table_state()
    }


def delete_student_db(student_id, actor="System"):
    """Deletes a student and cascades fee payments."""
    students = get_all_students_with_payments()
    existing = next((s for s in students if s["id"] == student_id), None)
    if not existing:
        return {"success": False, "reply": "⚠️ Student not found."}

    conn = get_db()
    try:
        with conn:
            conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    existing["name"],
                    existing.get("school") or "—",
                    existing.get("monthly_fee", 0),
                    "—",
                    "Deleted",
                    f"Student removed from SQLite (ID: {student_id})",
                    actor
                )
            )
    finally:
        conn.close()

    return {
        "success": True,
        "reply": f"🗑️ Removed student **{existing['name']}** from ledger.",
        "table": get_table_state()
    }


def record_payment_db(student_id, month_header, amount, entry_id=None,
                      payment_mode="Cash", note="", recorded_by="System"):
    """Records or updates a fee payment in SQLite."""
    mode = payment_mode if payment_mode in VALID_PAYMENT_MODES else "Cash"
    cleaned_note = (note or "").strip()[:200]
    cleaned_actor = (recorded_by or "System").strip()[:50]

    conn = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO fee_payments (student_id, month_header, amount, entry_id, payment_mode, note, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, month_header) DO UPDATE SET
                     amount = excluded.amount,
                     entry_id = excluded.entry_id,
                     payment_mode = excluded.payment_mode,
                     note = excluded.note,
                     recorded_by = excluded.recorded_by,
                     paid_at = CURRENT_TIMESTAMP""",
                (student_id, month_header, amount, entry_id, mode, cleaned_note, cleaned_actor)
            )
    finally:
        conn.close()


def upsert_direct_payment_db(student_id, month_header, amount, payment_mode="Cash", note="", actor="System"):
    """Validates and saves a direct cell edit / payment from the ledger grid or student drawer."""
    try:
        amt = int(float(str(amount).replace(",", "").strip()))
        if amt <= 0 or amt > 10_000_000:
            return {"success": False, "reply": "⚠️ Amount must be between ₹1 and ₹10,000,000."}
    except (ValueError, TypeError, OverflowError):
        return {"success": False, "reply": "⚠️ Please enter a valid payment amount."}

    students = get_all_students_with_payments()
    student = next((s for s in students if s["id"] == student_id), None)
    if not student:
        return {"success": False, "reply": "⚠️ Student not found."}

    try:
        y, m_num, _ = parse_month_header(month_header)
        canonical_month = format_month_header(y, m_num, "text")
    except ValueError:
        return {"success": False, "reply": "⚠️ Invalid month format."}

    add_month_column_if_missing(canonical_month)
    entry_id = str(uuid.uuid4())[:8]
    mode = payment_mode if payment_mode in VALID_PAYMENT_MODES else "Cash"

    record_payment_db(
        student_id=student_id,
        month_header=canonical_month,
        amount=amt,
        entry_id=entry_id,
        payment_mode=mode,
        note=note,
        recorded_by=actor
    )

    log_activity_db(
        student=student["name"],
        school=student.get("school") or "—",
        amount=amt,
        month=canonical_month,
        status="Recorded",
        note=f"Direct cell entry ({mode})" + (f" - {note}" if note else ""),
        actor=actor
    )

    return {
        "success": True,
        "reply": f"✅ Recorded **₹{amt:,}** ({mode}) for **{student['name']}** in **{canonical_month}**.",
        "entry_id": entry_id,
        "updated_cell": {"student_id": student_id, "month": canonical_month, "amount": amt},
        "table": get_table_state()
    }


def delete_payment_cell_db(student_id, month_header, actor="System"):
    """Clears a specific student+month payment cell."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT fp.id, fp.amount, fp.month_header, s.name, s.school
               FROM fee_payments fp
               JOIN students s ON fp.student_id = s.id
               WHERE fp.student_id = ? AND LOWER(fp.month_header) = LOWER(?)""",
            (student_id, month_header.strip())
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "reply": "⚠️ No payment found for this cell."}

        with conn:
            conn.execute("DELETE FROM fee_payments WHERE id = ?", (row["id"],))
            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    row["name"],
                    row["school"] or "—",
                    row["amount"],
                    row["month_header"],
                    "Undone",
                    "Payment cell cleared directly from ledger",
                    actor
                )
            )
    finally:
        conn.close()

    return {
        "success": True,
        "reply": f"🗑️ Cleared **₹{row['amount']:,}** for **{row['name']}** in **{row['month_header']}**.",
        "table": get_table_state()
    }


def undo_payment_db(entry_id=None, actor="System"):
    """
    Clears the recorded payment associated with entry_id (or latest payment if entry_id is None).
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        if entry_id:
            cur.execute("""
                SELECT fp.id, fp.student_id, fp.month_header, fp.amount, s.name, s.school
                FROM fee_payments fp
                JOIN students s ON fp.student_id = s.id
                WHERE fp.entry_id = ?
            """, (entry_id,))
        else:
            cur.execute("""
                SELECT fp.id, fp.student_id, fp.month_header, fp.amount, s.name, s.school
                FROM fee_payments fp
                JOIN students s ON fp.student_id = s.id
                ORDER BY fp.id DESC LIMIT 1
            """)

        row = cur.fetchone()
        if not row:
            if entry_id:
                return {"success": False, "reply": f"⚠️ Entry '{entry_id}' was already undone or not found."}
            return {"success": False, "reply": "⚠️ No recent entry to undo in SQLite."}

        fp_id = row["id"]
        sid = row["student_id"]
        month = row["month_header"]
        amount = row["amount"]
        name = row["name"]
        school = row["school"] or "—"

        with conn:
            conn.execute("DELETE FROM fee_payments WHERE id = ?", (fp_id,))

            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    name,
                    school,
                    amount,
                    month,
                    "Undone",
                    f"Payment cell cleared via Undo in SQLite (Entry ID: {entry_id or 'latest'}).",
                    actor
                )
            )

        return {
            "success": True,
            "reply": f"Undone. **Cleared ₹{amount:,} for {name} in {month}.**",
            "cleared_cell": {
                "student_id": sid,
                "month": month
            },
            "table": get_table_state()
        }
    finally:
        conn.close()


def check_recent_duplicate_db(student_id, amount, window_seconds=60):
    """
    Checks recent payments in SQLite to prevent accidental duplicate entries within window_seconds.
    Uses SQLite's UTC strftime epoch to guarantee consistency regardless of host timezone.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT CAST(strftime('%s', 'now') AS INTEGER) - CAST(strftime('%s', paid_at) AS INTEGER) AS diff
            FROM fee_payments
            WHERE student_id = ? AND amount = ?
            ORDER BY paid_at DESC LIMIT 1
        """, (student_id, amount))
        row = cur.fetchone()
        if row and row["diff"] is not None:
            diff = row["diff"]
            if 0 <= diff <= window_seconds:
                return True, int(diff)
        return False, 0
    finally:
        conn.close()


# ==============================================================================
# ACTIVITY LOGS & ANALYTICS
# ==============================================================================

def log_activity_db(student, school, amount, month, status, note="", actor="System"):
    """Inserts an activity entry into SQLite."""
    conn = get_db()
    time_str = datetime.now().strftime("%I:%M:%S %p")
    log_id = str(uuid.uuid4())[:8]
    try:
        with conn:
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, time_str, student, school or "—", amount or 0, month or "—", status, note, actor or "System")
            )
    finally:
        conn.close()
    return log_id


def get_activity_logs_db(limit=150, status_filter=None, search_query=None):
    """Retrieves activity logs ordered by newest first with optional filters."""
    conn = get_db()
    try:
        cur = conn.cursor()
        sql = """SELECT id, time, student, school, amount, month, status, note, actor, created_at
                 FROM activity_logs"""
        clauses = []
        params = []
        if status_filter:
            clauses.append("LOWER(status) = LOWER(?)")
            params.append(status_filter.strip())
        if search_query:
            q = f"%{search_query.strip()}%"
            clauses.append("(student LIKE ? OR school LIKE ? OR month LIKE ? OR note LIKE ? OR actor LIKE ?)")
            params.extend([q, q, q, q, q])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "time": r["time"],
                "student": r["student"],
                "school": r["school"],
                "amount": r["amount"],
                "month": r["month"],
                "status": r["status"],
                "note": r["note"],
                "actor": r["actor"] or "System",
                "created_at": r["created_at"] or ""
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_analytics_db(target_month=None):
    """Computes full revenue, monthly progress, school/class distributions, mode share, and defaulters."""
    months = get_month_columns()
    students = get_all_students_with_payments()
    active_students = [s for s in students if s.get("status", "active") == "active"]
    total_base = sum(s["monthly_fee"] for s in active_students)

    current_month = get_current_month_header()
    if target_month and target_month in months:
        focus_month = target_month
    elif current_month in months:
        focus_month = current_month
    elif months:
        focus_month = months[-1]
    else:
        focus_month = current_month

    # Monthly breakdown
    monthly_breakdown = []
    total_collected_all = 0
    for m in months:
        collected_m = 0
        paid_m = 0
        for s in students:
            amt = s.get("payments", {}).get(m)
            if isinstance(amt, (int, float)) and amt > 0:
                collected_m += amt
                paid_m += 1
        total_collected_all += collected_m
        rate_m = round((collected_m / total_base) * 100, 1) if total_base > 0 else 0.0
        monthly_breakdown.append({
            "month": m,
            "expected": total_base,
            "collected": collected_m,
            "rate": rate_m,
            "paid_students": paid_m,
            "pending_students": max(0, len(active_students) - paid_m)
        })

    # Pending students for focus_month
    pending_students = []
    paid_focus_count = 0
    focus_collected = 0
    for s in active_students:
        amt = s.get("payments", {}).get(focus_month)
        if isinstance(amt, (int, float)) and amt > 0:
            paid_focus_count += 1
            focus_collected += amt
        else:
            pending_students.append({
                "id": s["id"],
                "name": s["name"],
                "std": s.get("std", ""),
                "school": s.get("school", ""),
                "monthly_fee": s.get("monthly_fee", 0),
                "guardian_phone": s.get("guardian_phone", ""),
                "last_paid_month": find_last_paid_month(s.get("payments", {}), months) or "Never"
            })

    # School & Class breakdowns
    school_map = {}
    std_map = {}
    mode_map = {}
    for s in active_students:
        sch = s.get("school") or "Unassigned"
        if sch not in school_map:
            school_map[sch] = {"school": sch, "students": 0, "base_total": 0, "collected_total": 0}
        school_map[sch]["students"] += 1
        school_map[sch]["base_total"] += s["monthly_fee"]

        st_cls = s.get("std") or "N/A"
        if st_cls not in std_map:
            std_map[st_cls] = {"std": st_cls, "students": 0, "base_total": 0, "collected_total": 0}
        std_map[st_cls]["students"] += 1
        std_map[st_cls]["base_total"] += s["monthly_fee"]

        for m, meta in (s.get("payments_meta") or {}).items():
            amt = meta.get("amount", 0)
            school_map[sch]["collected_total"] += amt
            std_map[st_cls]["collected_total"] += amt
            mode = meta.get("payment_mode") or "Cash"
            if mode not in mode_map:
                mode_map[mode] = {"mode": mode, "count": 0, "total": 0}
            mode_map[mode]["count"] += 1
            mode_map[mode]["total"] += amt

    focus_rate = round((focus_collected / total_base) * 100, 1) if total_base > 0 else 0.0

    return {
        "summary": {
            "total_students": len(students),
            "active_students": len(active_students),
            "inactive_students": len(students) - len(active_students),
            "total_base_fees": total_base,
            "total_collected_all": total_collected_all,
            "focus_month": focus_month,
            "focus_collected": focus_collected,
            "focus_expected": total_base,
            "focus_pending_amount": max(0, total_base - focus_collected),
            "focus_rate": focus_rate,
            "paid_count": paid_focus_count,
            "pending_count": len(pending_students)
        },
        "months": months,
        "monthly_breakdown": monthly_breakdown,
        "school_breakdown": sorted(school_map.values(), key=lambda x: x["base_total"], reverse=True),
        "std_breakdown": sorted(std_map.values(), key=lambda x: x["base_total"], reverse=True),
        "payment_mode_breakdown": sorted(mode_map.values(), key=lambda x: x["total"], reverse=True),
        "pending_students": pending_students
    }


def sanitize_csv_cell(value):
    """
    Prevents CSV Formula Injection (CWE-1236).
    If a string cell starts with =, +, -, @, tab, or carriage return,
    prefix with single quote so spreadsheet programs treat it strictly as text.
    """
    if isinstance(value, str) and value:
        stripped = value.strip()
        if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{value}"
    return value


def generate_csv_report_from_db():
    """Generates complete CSV report directly from SQLite with formula injection defense."""
    months = get_month_columns()
    students = get_all_students_with_payments()

    output = io.StringIO()
    writer = csv.writer(output)

    headers = ["Student Name", "Std", "School Name", "Status", "Guardian Phone", "Base Fee (INR)"] + months
    writer.writerow(headers)

    totals = {m: 0 for m in months}
    total_base = 0

    for s in students:
        fee = s.get("monthly_fee", 0)
        total_base += fee
        row = [
            sanitize_csv_cell(s.get("name", "")),
            sanitize_csv_cell(s.get("std", "")),
            sanitize_csv_cell(s.get("school", "")),
            sanitize_csv_cell(s.get("status", "active")),
            sanitize_csv_cell(s.get("guardian_phone", "")),
            fee
        ]
        payments = s.get("payments", {})
        for m in months:
            val = payments.get(m, "")
            if isinstance(val, (int, float)):
                totals[m] += val
                row.append(val)
            else:
                row.append("")
        writer.writerow(row)

    writer.writerow([])

    total_collected = sum(totals.values())
    summary_row = [
        "TOTALS",
        f"{len(students)} Students",
        f"Base Total: INR {total_base:,}",
        "",
        "",
        f"Collected: INR {total_collected:,}"
    ]
    for m in months:
        summary_row.append(totals[m])
    writer.writerow(summary_row)

    return output.getvalue()
