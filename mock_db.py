"""
Mock Database for Fees Entry Assistant
Backed by SQLite (data/fees.db) for robust ACID persistence.
"""

import difflib
import re
import uuid
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
import sqlite_db

# Initialize SQLite database on module import
sqlite_db.init_db(force_reseed=False)

# In-flight confirmation proposals with TTL expiration to prevent memory leaks
pending_actions = {}
ACTION_TTL_SECONDS = 900  # 15 minutes
MAX_PENDING_ACTIONS = 200


def clean_expired_actions():
    """Removes stale pending proposals to prevent memory exhaustion."""
    now = datetime.now()
    expired_ids = [
        aid for aid, act in list(pending_actions.items())
        if (now - act.get("created_at", now)).total_seconds() > ACTION_TTL_SECONDS
    ]
    for aid in expired_ids:
        pending_actions.pop(aid, None)
    if len(pending_actions) > MAX_PENDING_ACTIONS:
        sorted_by_time = sorted(pending_actions.items(), key=lambda x: x[1].get("created_at", datetime.min))
        for aid, _ in sorted_by_time[:len(pending_actions) - MAX_PENDING_ACTIONS]:
            pending_actions.pop(aid, None)


def normalize_string(s):
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def get_student_label(student):
    parts = []
    if student.get("std"):
        parts.append(f"Std {student['std']}")
    if student.get("school"):
        parts.append(student["school"])
    extra = f" ({', '.join(parts)})" if parts else ""
    return f"{student['name']}{extra}"


def get_mock_table_state():
    """Returns current live table state directly from SQLite."""
    return sqlite_db.get_table_state()


def reset_mock_data():
    """Resets SQLite database using the available seed CSV."""
    pending_actions.clear()
    sqlite_db.init_db(force_reseed=True)
    return sqlite_db.get_table_state()


def get_activity_log():
    """Returns activity log from SQLite."""
    return sqlite_db.get_activity_logs_db()


def log_activity(student, school, amount, month, status, note=""):
    """Logs an activity entry to SQLite."""
    return sqlite_db.log_activity_db(
        student=student,
        school=school,
        amount=amount,
        month=month,
        status=status,
        note=note
    )


def get_pending_action(action_id):
    clean_expired_actions()
    act = pending_actions.get(action_id)
    if act:
        if (datetime.now() - act.get("created_at", datetime.now())).total_seconds() > ACTION_TTL_SECONDS:
            pending_actions.pop(action_id, None)
            return None
    return act


def save_pending_action(action_id, data):
    clean_expired_actions()
    data["created_at"] = datetime.now()
    pending_actions[action_id] = data


def pop_pending_action(action_id):
    clean_expired_actions()
    return pending_actions.pop(action_id, None)


def add_new_student(name, std="", school="", monthly_fee=0):
    """Adds a new student to SQLite."""
    return sqlite_db.add_student_db(name=name, std=std, school=school, monthly_fee=monthly_fee)


def delete_month_column(month_name):
    """Deletes a month column and clears associated payments in SQLite."""
    return sqlite_db.delete_month_column_db(month_name)


def generate_csv_report():
    """Generates complete CSV report directly from SQLite."""
    return sqlite_db.generate_csv_report_from_db()


def find_matching_students(student_name_query, raw_message=""):
    """
    Finds matching students from SQLite.
    Supports exact match, substring match, fuzzy match, and intelligent disambiguation
    using school name or class/std from the user's raw message.
    """
    students = sqlite_db.get_all_students_with_payments()
    clean_query = normalize_string(student_name_query)
    clean_msg = normalize_string(raw_message)

    # 1. Exact Name Match
    exact_matches = [
        s for s in students 
        if normalize_string(s["name"]) == clean_query
    ]

    # 2. Substring Match
    if not exact_matches:
        exact_matches = [
            s for s in students 
            if clean_query in normalize_string(s["name"]) or normalize_string(s["name"]) in clean_query
        ]

    # 3. Fuzzy Suggestions if No Match
    if not exact_matches:
        unique_names = list({s["name"] for s in students})
        close_matches = difflib.get_close_matches(student_name_query, unique_names, n=3, cutoff=0.5)
        return {
            "status": "not_found",
            "matches": [],
            "suggestions": close_matches
        }

    # 4. Single Match Found
    if len(exact_matches) == 1:
        return {
            "status": "single_match",
            "student": exact_matches[0],
            "matches": exact_matches
        }

    # 5. Multiple Matches: Disambiguate by School or Class/Std
    disambiguated = []
    for s in exact_matches:
        norm_school = normalize_string(s.get("school", ""))
        norm_std = normalize_string(str(s.get("std", "")))

        # Check School match
        if norm_school and norm_school in clean_msg:
            disambiguated.append(s)
            continue

        # Check Std / Class match (e.g. "class 5", "std 5", "5th", "5", "lkg", "ukg")
        if norm_std:
            std_patterns = [
                f"std {norm_std}", f"class {norm_std}", f"grade {norm_std}",
                f"{norm_std}th", f"{norm_std}st", f"{norm_std}nd", f"{norm_std}rd"
            ]
            if norm_std in ["lkg", "ukg"]:
                std_patterns.append(norm_std)
            if any(p in clean_msg for p in std_patterns) or norm_std in clean_msg.split():
                disambiguated.append(s)

    if len(disambiguated) == 1:
        return {
            "status": "single_match",
            "student": disambiguated[0],
            "matches": disambiguated
        }

    return {
        "status": "multiple_matches",
        "matches": exact_matches
    }


def detect_payment_gap(student, existing_columns):
    """Detects if there is an unpaid month between filled months for a student."""
    payments = student.get("payments", {})
    if not payments:
        return False, None, None

    filled_indices = []
    for idx, col in enumerate(existing_columns):
        if payments.get(col) not in (None, "", 0):
            filled_indices.append((idx, col))

    if len(filled_indices) < 2:
        return False, None, None

    first_idx = filled_indices[0][0]
    last_idx = filled_indices[-1][0]

    for i in range(first_idx + 1, last_idx):
        col_month = existing_columns[i]
        if payments.get(col_month) in (None, "", 0):
            next_after_last, _, _, _ = get_next_month_header(filled_indices[-1][1])
            return True, col_month, next_after_last

    return False, None, None


def check_recent_duplicate(student_id, amount):
    """Checks recent payments in SQLite to prevent accidental duplicate entries within 60s."""
    window = SHEET_CONFIG.get("duplicate_window_seconds", 60)
    return sqlite_db.check_recent_duplicate_db(student_id, amount, window)


def extract_explicit_month(message):
    """
    Detects whether the user explicitly specified a target month in their message.
    e.g. 'Student Dummy paid 2000 for Dec 2026' -> 'Dec 2026'
         'Alex paid 900 in January 2027' -> 'Jan 2027'
    """
    if not message or not isinstance(message, str):
        return None

    # Match patterns like: (for|in|month of) (Month) (Year) or just (Month) (Year)
    pattern = r"(?:for|in|month\s+of)?\s*(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*[-/ ]?\s*(\d{4})"
    match = re.search(pattern, message, re.IGNORECASE)
    if match:
        month_str = match.group(1)
        year_str = match.group(2)
        try:
            y, m, _ = parse_month_header(f"{month_str} {year_str}")
            return format_month_header(y, m, "text")
        except ValueError:
            return None
    return None


def prepare_payment_proposal(student_name, amount, raw_message="", choice=None):
    """
    Validates input, runs safety checks (amount, duplicate, gap),
    and creates a 2-step confirmation proposal.
    Honors explicit month requests when provided in raw_message.
    """
    if amount is None or amount <= 0:
        return {
            "status": "error",
            "reply": "⚠️ Amount must be greater than zero. Please enter a valid fee amount."
        }
    if amount > 10_000_000:
        return {
            "status": "error",
            "reply": "⚠️ Amount cannot exceed ₹10,000,000. Please enter a valid fee amount."
        }

    search_result = find_matching_students(student_name, raw_message)
    status = search_result["status"]

    if status == "not_found":
        suggestions = search_result.get("suggestions", [])
        if suggestions:
            suggest_str = ", ".join([f"**'{s}'**" for s in suggestions])
            reply = f"⚠️ Student **'{student_name}'** was not found in SQLite. Did you mean {suggest_str}?"
        else:
            students = sqlite_db.get_all_students_with_payments()
            names_list = ", ".join([f"**{s['name']}**" for s in students[:4]])
            reply = f"⚠️ Student **'{student_name}'** was not found. (Available: {names_list}...)."
        return {
            "status": "not_found",
            "reply": reply
        }

    if status == "multiple_matches":
        matches = search_result["matches"]
        options = []
        for s in matches:
            school_info = f"School: {s.get('school')}" if s.get('school') else "No school"
            std_info = f"Std: {s.get('std')}" if s.get('std') else ""
            details = ", ".join(filter(None, [school_info, std_info, f"Fee: ₹{s.get('monthly_fee', 0):,}"]))
            options.append(f"• **{s['name']}** ({details})")
        options_str = "\n".join(options)
        reply = (
            f"⚠️ Found {len(matches)} students named **'{student_name}'** in the database:\n"
            f"{options_str}\n\n"
            f"👉 Please specify the school or class as well (e.g. *'{student_name} {matches[0].get('school') or matches[0].get('std')} paid {amount}'*)."
        )
        return {
            "status": "ambiguous_name",
            "reply": reply
        }

    student = search_result["student"]
    student_label = get_student_label(student)
    current_months = sqlite_db.get_month_columns()

    # Gap Detection
    if not choice:
        has_gap, gap_month, next_after_last = detect_payment_gap(student, current_months)
        if has_gap:
            action_id = str(uuid.uuid4())[:8]
            save_pending_action(action_id, {
                "type": "gap_choice",
                "student": student,
                "amount": amount,
                "gap_month": gap_month,
                "next_after_last": next_after_last
            })
            reply = (
                f"⚠️ **Gap Warning:** **{gap_month}** is unpaid for **{student_label}**, "
                f"but later months are already recorded.\n\n"
                f"Where should this payment of **₹{amount:,}** be entered?"
            )
            return {
                "status": "gap_warning",
                "action_id": action_id,
                "reply": reply,
                "options": [
                    {"label": f"Fill Gap: {gap_month}", "choice": "fill_gap", "month": gap_month},
                    {"label": f"Continue: {next_after_last}", "choice": "continue_after", "month": next_after_last},
                    {"label": "Cancel", "choice": "cancel"}
                ]
            }

    # Target Month Calculation: Check explicit month first, otherwise consecutive
    explicit_month = extract_explicit_month(raw_message)
    if explicit_month:
        target_month = explicit_month
    else:
        last_paid = find_last_paid_month(student.get("payments", {}), current_months)
        calc = determine_target_month(last_paid_month=last_paid, existing_columns=current_months)
        target_month = calc["target_month"]

    # Duplicate Check
    if choice != "force_duplicate":
        is_dup, seconds_ago = check_recent_duplicate(student["id"], amount)
        if is_dup:
            action_id = str(uuid.uuid4())[:8]
            save_pending_action(action_id, {
                "type": "duplicate_confirm",
                "student": student,
                "amount": amount,
                "target_month": target_month
            })
            reply = (
                f"⚠️ **Duplicate Warning:** An entry of **₹{amount:,}** for **{student_label}** "
                f"was already recorded **{seconds_ago} seconds ago**.\n\n"
                f"Do you still want to enter another payment for **{target_month}**?"
            )
            return {
                "status": "duplicate_warning",
                "action_id": action_id,
                "reply": reply,
                "options": [
                    {"label": "Yes, Enter Payment", "choice": "confirm_duplicate"},
                    {"label": "Cancel", "choice": "cancel"}
                ]
            }

    is_large = amount > SHEET_CONFIG["large_amount_threshold"]
    large_note = f" ⚠️ *(Note: ₹{amount:,} is above standard limit of ₹{SHEET_CONFIG['large_amount_threshold']:,})*" if is_large else ""

    action_id = str(uuid.uuid4())[:8]
    save_pending_action(action_id, {
        "type": "confirm_payment",
        "student": student,
        "amount": amount,
        "target_month": target_month,
        "is_large": is_large
    })

    reply = f"Enter **₹{amount:,}** for **{student_label}** in **{target_month}**?{large_note}"

    return {
        "status": "confirmation_required",
        "action_id": action_id,
        "reply": reply,
        "summary": {
            "student_name": student["name"],
            "school": student["school"],
            "std": student.get("std", ""),
            "amount": amount,
            "target_month": target_month
        },
        "options": [
            {"label": "Confirm", "choice": "confirm", "primary": True},
            {"label": "Cancel", "choice": "cancel"}
        ]
    }


def execute_confirmed_payment(action_id):
    """Executes a confirmed payment and commits it to SQLite."""
    action = pop_pending_action(action_id)
    if not action:
        return {
            "success": False,
            "reply": "⚠️ This confirmation has expired. Please type your message again."
        }

    student = action["student"]
    amount = action["amount"]
    target_month = action["target_month"]

    # 1. Ensure month column exists in SQLite
    new_col_created = sqlite_db.add_month_column_if_missing(target_month)

    # 2. Record payment in SQLite
    entry_id = str(uuid.uuid4())[:8]
    sqlite_db.record_payment_db(
        student_id=student["id"],
        month_header=target_month,
        amount=amount,
        entry_id=entry_id
    )

    # 3. Log Activity
    sqlite_db.log_activity_db(
        student=student["name"],
        school=student.get("school") or (f"Std {student.get('std')}" if student.get('std') else "—"),
        amount=amount,
        month=target_month,
        status="Recorded",
        note=f"Recorded in SQLite ({'New column created' if new_col_created else 'Existing column'})"
    )

    student_label = get_student_label(student)
    rollover_note = " *(✨ Created new column with year rollover!)*" if new_col_created else ""
    reply = f"Done. **{student_label}: ₹{amount:,} entered for {target_month}.**{rollover_note}"

    return {
        "success": True,
        "reply": reply,
        "entry_id": entry_id,
        "student": student,
        "amount": amount,
        "target_month": target_month,
        "new_col_created": new_col_created,
        "updated_cell": {
            "student_id": student["id"],
            "month": target_month,
            "amount": amount
        },
        "table": sqlite_db.get_table_state()
    }


def execute_undo_payment(entry_id=None):
    """Clears a payment from SQLite."""
    return sqlite_db.undo_payment_db(entry_id)


def cancel_pending_action(action_id):
    """Cancels an in-flight confirmation."""
    action = pop_pending_action(action_id)
    if action:
        student = action.get("student", {})
        sqlite_db.log_activity_db(
            student=student.get("name", "Unknown"),
            school=student.get("school", "—"),
            amount=action.get("amount", 0),
            month=action.get("target_month", "—"),
            status="Cancelled",
            note="Admin cancelled confirmation."
        )
    return {
        "success": True,
        "reply": "❌ Payment entry cancelled."
    }
