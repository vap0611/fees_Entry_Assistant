"""
Month Calculation Logic & Business Rules
Supports both date format ('2026-12-01') and text format ('Dec 2026').
"""

from datetime import datetime
import re
from sheet_config import SHEET_CONFIG, col_number_to_letter

MONTH_MAP_NUM_TO_STR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

MONTH_MAP_STR_TO_NUM = {v: k for k, v in MONTH_MAP_NUM_TO_STR.items()}


def parse_month_header(header_str):
    """
    Parses a header string.
    Supports:
    1. '2026-12-01' (YYYY-MM-DD)
    2. 'Dec 2026' (MMM YYYY)
    Returns: (year, month_num, format_type)
    """
    if not header_str or not isinstance(header_str, str):
        raise ValueError("Month header must be a non-empty string.")

    cleaned = header_str.strip()

    # Check Date Format: YYYY-MM-DD
    match_date = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if match_date:
        year = int(match_date.group(1))
        month = int(match_date.group(2))
        if 1 <= month <= 12:
            return year, month, "date"

    # Check Text Format: MMM YYYY or Full Month YYYY (e.g. Dec 2026, December 2026, Dec-2026)
    match_text = re.match(
        r"^(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\s\-,]+(\d{4})$", 
        cleaned, 
        re.IGNORECASE
    )
    if match_text:
        month_prefix = match_text.group(1)[:3].capitalize()
        year = int(match_text.group(2))
        month = MONTH_MAP_STR_TO_NUM[month_prefix]
        return year, month, "text"

    raise ValueError(
        f"Invalid month header format: '{header_str}'. Expected '2026-12-01' (YYYY-MM-01) or 'Dec 2026' (MMM YYYY)."
    )


def format_month_header(year, month_num, format_type="date"):
    """
    Formats year and month into the specified format type.
    'date' -> '2026-12-01'
    'text' -> 'Dec 2026'
    """
    if format_type == "date":
        return f"{year:04d}-{month_num:02d}-01"
    else:
        return f"{MONTH_MAP_NUM_TO_STR[month_num]} {year}"


def get_current_month_header(now=None, format_type=None):
    """Returns the current month in standard header format."""
    if now is None:
        now = datetime.now()
    if format_type is None:
        format_type = SHEET_CONFIG.get("default_month_format", "text")
    return format_month_header(now.year, now.month, format_type)


def get_next_month_header(month_header_str):
    """
    Calculates consecutive month preserving the detected format.
    Handles year rollovers correctly (e.g. '2026-12-01' -> '2027-01-01', or 'Dec 2026' -> 'Jan 2027').
    Returns tuple: (next_month_header_str, is_year_rollover, next_year, next_month_num)
    """
    year, month_num, format_type = parse_month_header(month_header_str)

    if month_num == 12:
        next_month_num = 1
        next_year = year + 1
        is_year_rollover = True
    else:
        next_month_num = month_num + 1
        next_year = year
        is_year_rollover = False

    next_header = format_month_header(next_year, next_month_num, format_type)
    return next_header, is_year_rollover, next_year, next_month_num


def find_last_paid_month(payments_dict, existing_columns=None):
    """
    Finds the latest chronological month with a payment recorded.
    """
    if not payments_dict:
        return None

    valid_paid_months = []
    for month_key, amount in payments_dict.items():
        if amount not in (None, "", 0):
            try:
                y, m, _ = parse_month_header(month_key)
                valid_paid_months.append((y, m, month_key))
            except ValueError:
                continue

    if not valid_paid_months:
        return None

    valid_paid_months.sort(key=lambda item: (item[0], item[1]))
    return valid_paid_months[-1][2]


def determine_target_month(last_paid_month=None, existing_columns=None, now=None):
    """
    Determines next target month:
    - If last paid month exists, moves to consecutive month (handling year rollover).
    - If no payment, uses current month.
    - Determines if new column needed and column letter.
    """
    if existing_columns is None:
        existing_columns = SHEET_CONFIG["initial_month_columns"]

    fixed_count = SHEET_CONFIG["fixed_column_count"]

    # Detect prevailing format from existing columns if available
    prevailing_format = SHEET_CONFIG.get("default_month_format", "text")
    if existing_columns:
        try:
            _, _, prevailing_format = parse_month_header(existing_columns[0])
        except ValueError:
            pass

    if not last_paid_month or str(last_paid_month).strip().lower() in ("none", "null", ""):
        target_month = get_current_month_header(now, format_type=prevailing_format)
        reason = "Student has no previous payments recorded. Defaulting to current month."
        is_year_rollover = False
        prior_month = None
    else:
        prior_month = last_paid_month.strip()
        target_month, is_year_rollover, _, _ = get_next_month_header(prior_month)
        if is_year_rollover:
            reason = f"Previous paid month is '{prior_month}'. Rolled over year to '{target_month}'."
        else:
            reason = f"Previous paid month is '{prior_month}'. Advanced to consecutive month '{target_month}'."

    column_exists = target_month in existing_columns

    if column_exists:
        col_index = fixed_count + existing_columns.index(target_month)
        col_letter = col_number_to_letter(col_index)
        column_action = f"Write directly to existing Column {col_letter} ('{target_month}')."
        new_column_needed = False
        target_col_letter = col_letter
    else:
        new_col_index = fixed_count + len(existing_columns)
        new_col_letter = col_number_to_letter(new_col_index)
        column_action = f"Create new Column {new_col_letter} ('{target_month}') at the end of sheet, then record payment."
        new_column_needed = True
        target_col_letter = new_col_letter

    return {
        "status": "success",
        "last_paid_month": prior_month,
        "target_month": target_month,
        "is_year_rollover": is_year_rollover,
        "reason": reason,
        "column_exists": column_exists,
        "new_column_needed": new_column_needed,
        "target_column_letter": target_col_letter,
        "column_action": column_action,
        "existing_columns": list(existing_columns),
        "sheet_tab_name": SHEET_CONFIG["sheet_tab_name"]
    }
