"""
SQLite Database Layer for Fees Entry Assistant
Provides complete persistence for students, month columns, payments, and activity logs.
"""

import os
import sqlite3
import csv
import io
import uuid
import re
import difflib
from datetime import datetime, timedelta

from sheet_config import SHEET_CONFIG
from month_logic import (
    determine_target_month,
    find_last_paid_month,
    get_next_month_header,
    get_current_month_header,
    parse_month_header,
    format_month_header
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


def get_db():
    """Returns a SQLite connection with foreign keys enabled and row access by name."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force_reseed=False):
    """Creates SQLite tables and indexes. Seeds initial data from CSV if empty."""
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                std TEXT DEFAULT '',
                school TEXT DEFAULT '',
                monthly_fee INTEGER NOT NULL DEFAULT 0,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast lookup
        conn.execute("CREATE INDEX IF NOT EXISTS idx_students_name ON students(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_student ON fee_payments(student_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_month ON fee_payments(month_header)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_logs(created_at DESC)")

    # Check if students exist; if not or if forced, seed from CSV
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM students")
    student_count = cur.fetchone()[0]

    if student_count == 0 or force_reseed:
        seed_initial_data(conn, force=force_reseed)

    conn.close()


def seed_initial_data(conn, force=False):
    """Seeds students from the local CSV or the safe example CSV."""
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
                header = next(reader, None)
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
            """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4())[:8],
                time_str,
                "System",
                "All",
                0,
                "—",
                "SQLite Ready",
                f"SQLite database initialized with {count} students from the configured seed CSV."
            )
        )


def get_month_columns():
    """Returns sorted list of month header strings."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT month_header FROM month_columns ORDER BY order_index ASC")
    rows = cur.fetchall()
    conn.close()
    return [r["month_header"] for r in rows]


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


def delete_month_column_db(month_name):
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
    with conn:
        cur = conn.cursor()
        # Count payments to be cleared
        cur.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM fee_payments WHERE month_header = ?", (match_col,))
        cleared_count, total_amount_cleared = cur.fetchone()

        # Delete payments
        conn.execute("DELETE FROM fee_payments WHERE month_header = ?", (match_col,))

        # Delete column
        conn.execute("DELETE FROM month_columns WHERE month_header = ?", (match_col,))

        # Re-index remaining columns
        cur.execute("SELECT id FROM month_columns ORDER BY order_index ASC")
        rows = cur.fetchall()
        for new_idx, row in enumerate(rows):
            conn.execute("UPDATE month_columns SET order_index = ? WHERE id = ?", (new_idx, row["id"]))

        # Log Activity
        time_str = datetime.now().strftime("%I:%M:%S %p")
        conn.execute(
            """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4())[:8],
                time_str,
                "All Students",
                "All",
                total_amount_cleared,
                match_col,
                "Col Deleted",
                f"Column '{match_col}' deleted from SQLite ({cleared_count} payments removed)"
            )
        )

    conn.close()
    return {
        "success": True,
        "reply": f"🗑️ Column **'{match_col}'** has been deleted from SQLite and all associated payments cleared.",
        "deleted_column": match_col,
        "table": get_table_state()
    }


def get_all_students_with_payments():
    """Fetches all students and attaches their payment records."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, name, std, school, monthly_fee FROM students ORDER BY id ASC")
    students_rows = cur.fetchall()

    cur.execute("SELECT student_id, month_header, amount FROM fee_payments")
    payments_rows = cur.fetchall()
    conn.close()

    # Map payments: { student_id: { month_header: amount } }
    payments_map = {}
    for p in payments_rows:
        sid = p["student_id"]
        if sid not in payments_map:
            payments_map[sid] = {}
        payments_map[sid][p["month_header"]] = p["amount"]

    students = []
    for s in students_rows:
        sid = s["id"]
        students.append({
            "id": sid,
            "name": s["name"],
            "std": s["std"] or "",
            "school": s["school"] or "",
            "monthly_fee": s["monthly_fee"],
            "payments": payments_map.get(sid, {})
        })

    return students


def get_table_state():
    """Returns the live state of the entire SQLite database."""
    months = get_month_columns()
    students = get_all_students_with_payments()
    total_base = sum(s["monthly_fee"] for s in students)
    return {
        "months": months,
        "students": students,
        "total_students": len(students),
        "total_base_fees": total_base
    }


def add_student_db(name, std="", school="", monthly_fee=0):
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

    conn = get_db()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO students (name, std, school, monthly_fee) VALUES (?, ?, ?, ?)",
                (cleaned_name, cleaned_std, cleaned_school, fee)
            )
            new_id = cur.lastrowid

            # Log Activity
            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    cleaned_name,
                    cleaned_school or "—",
                    fee,
                    "—",
                    "Added",
                    f"New student added in SQLite (ID: {new_id}, Std: {cleaned_std})"
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
        "payments": {}
    }

    parts = []
    if cleaned_std: parts.append(f"Std {cleaned_std}")
    if cleaned_school: parts.append(cleaned_school)
    label = f"{cleaned_name} ({', '.join(parts)})" if parts else cleaned_name

    reply = f"✅ Added new student **{label}** with base fee **₹{fee:,}** in SQLite."
    return {
        "success": True,
        "reply": reply,
        "student": new_student,
        "table": get_table_state()
    }


def record_payment_db(student_id, month_header, amount, entry_id=None):
    """Records or updates a fee payment in SQLite."""
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO fee_payments (student_id, month_header, amount, entry_id)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(student_id, month_header) DO UPDATE SET amount = excluded.amount, entry_id = excluded.entry_id""",
                (student_id, month_header, amount, entry_id)
            )
    finally:
        conn.close()


def undo_payment_db(entry_id=None):
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

            # Log Activity
            time_str = datetime.now().strftime("%I:%M:%S %p")
            conn.execute(
                """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:8],
                    time_str,
                    name,
                    school,
                    amount,
                    month,
                    "Undone",
                    f"Payment cell cleared via Undo in SQLite (Entry ID: {entry_id or 'latest'})."
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


def log_activity_db(student, school, amount, month, status, note=""):
    """Inserts an activity entry into SQLite."""
    conn = get_db()
    time_str = datetime.now().strftime("%I:%M:%S %p")
    log_id = str(uuid.uuid4())[:8]
    with conn:
        conn.execute(
            """INSERT INTO activity_logs (id, time, student, school, amount, month, status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, time_str, student, school or "—", amount or 0, month or "—", status, note)
        )
    conn.close()
    return log_id


def get_activity_logs_db(limit=100):
    """Retrieves activity logs ordered by newest first."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, time, student, school, amount, month, status, note
           FROM activity_logs ORDER BY created_at DESC LIMIT ?""",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "time": r["time"],
            "student": r["student"],
            "school": r["school"],
            "amount": r["amount"],
            "month": r["month"],
            "status": r["status"],
            "note": r["note"]
        }
        for r in rows
    ]


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

    # 1. Header row
    headers = ["Student Name", "Std", "School Name", "Base Fee (INR)"] + months
    writer.writerow(headers)

    # 2. Student rows
    totals = {m: 0 for m in months}
    total_base = 0

    for s in students:
        fee = s.get("monthly_fee", 0)
        total_base += fee
        row = [
            sanitize_csv_cell(s.get("name", "")),
            sanitize_csv_cell(s.get("std", "")),
            sanitize_csv_cell(s.get("school", "")),
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

    # 3. Blank row
    writer.writerow([])

    # 4. Summary Totals Row
    total_collected = sum(totals.values())
    summary_row = [
        "TOTALS",
        f"{len(students)} Students",
        f"Base Total: INR {total_base:,}",
        f"Collected: INR {total_collected:,}"
    ]
    for m in months:
        summary_row.append(totals[m])
    writer.writerow(summary_row)

    return output.getvalue()
