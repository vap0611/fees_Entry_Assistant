# Bug Fix Log: Fees Entry Assistant

This document provides a detailed log of every defect identified during the production audit, the technical root cause, files modified, the implemented remediation, and verified retest results.

---

### Bug #1: SQLite Connection Closed Inside Context Manager (`add_month_column_if_missing`)
- **Severity**: Critical
- **Affected File**: `sqlite_db.py`
- **Root Cause**: `conn.close()` was invoked inside the `with conn:` block. Upon exiting the context manager, Python's `sqlite3` driver attempted to commit transactions on an already closed connection, raising `sqlite3.ProgrammingError: Cannot operate on a closed database`.
- **Symptoms**: Creating a new month column (e.g. paying into `Jan 2027` or any new month) crashed the request with an HTTP 500 error.
- **Fix Implemented**: Restructured database functions to separate transaction context `with conn:` from connection management using `try ... finally: conn.close()`.
- **Retest Result**: Verified via unit test `test_add_month_column_if_missing_does_not_crash` and live integration test. New columns and year rollovers succeed without errors.

---

### Bug #2: Premature Connection Close and Destructive Fallback in `undo_payment_db`
- **Severity**: Critical
- **Affected File**: `sqlite_db.py`
- **Root Cause**:
  1. `conn.close()` was called inside `with conn:` when `row` was None, throwing `sqlite3.ProgrammingError`.
  2. If an `entry_id` was provided but had already been undone or was invalid, the previous code fell back to querying `ORDER BY id DESC LIMIT 1`, which silently deleted another student's most recent payment!
- **Symptoms**: API crashed on invalid undo requests, or silently deleted unrelated student fees.
- **Fix Implemented**:
  1. Handled connection cleanup in `finally` block.
  2. If an `entry_id` is supplied, query strictly for that ID. If not found, return a clean error without modifying any database records.
- **Retest Result**: Verified via `test_undo_nonexistent_entry_id_does_not_crash_or_delete_other_payments` and live API testing.

---

### Bug #3: Timezone Mismatch Disabling 60-Second Duplicate Alert
- **Severity**: High
- **Affected Files**: `mock_db.py`, `sqlite_db.py`
- **Root Cause**: SQLite `CURRENT_TIMESTAMP` defaults to UTC, whereas `datetime.now()` returned the local host timezone (e.g. IST +5:30). Comparing `paid_dt >= datetime.now() - 60s` compared UTC against local time, causing the condition to always evaluate to `False`.
- **Symptoms**: Paying the exact same fee for the same student within 10 seconds never triggered the duplicate payment warning.
- **Fix Implemented**: Added `check_recent_duplicate_db` in `sqlite_db.py` utilizing SQLite's native `CAST(strftime('%s', 'now') AS INTEGER) - CAST(strftime('%s', paid_at) AS INTEGER)`. Both are calculated in SQLite's UTC epoch, guaranteeing 100% timezone-independent consistency.
- **Retest Result**: Verified via `test_check_recent_duplicate_db` and live server test: duplicate warning triggered 7 seconds after initial payment.

---

### Bug #4: Explicit Month Mentions in Chat Ignored
- **Severity**: Medium
- **Affected File**: `mock_db.py`
- **Root Cause**: `prepare_payment_proposal` always computed target month as `determine_target_month(last_paid_month)`, completely ignoring whether the user explicitly typed a month (e.g., "Jamie paid 1100 for Dec 2026").
- **Symptoms**: Could not override or target specific months as documented in the feature list.
- **Fix Implemented**: Added `extract_explicit_month(raw_message)` using regex to detect month and year combinations. If present, it validates the month and assigns it directly to `target_month`.
- **Retest Result**: Verified via `test_chat_honors_explicit_month`. Submitting "Jamie paid 1100 for Dec 2026" sets target month to Dec 2026.

---

### Bug #5: Action Verbs Incompletely Stripped from Student Names
- **Severity**: Medium
- **Affected File**: `gemini_service.py`
- **Root Cause**: `clean_student_name` used a single-word regex `r"\s+(?:has|have|paid|fees|fee|done|is)$"`. For phrases like `"Alex has paid"`, it stripped `" paid"`, leaving `"Alex has"`.
- **Symptoms**: Student name was extracted as `"Alex has"`, causing database student lookup to fail.
- **Fix Implemented**: Updated regex to `r"\s+(?:has\s+paid|have\s+paid|has|have|paid|fees|fee|done|is)+$"`.
- **Retest Result**: Verified via `test_clean_student_name`. `"Alex has paid"` correctly resolves to `"Alex"`.

---

### Bug #6: Insecure Client-Side API Key Input Option (CWE-200 / CWE-284)
- **Severity**: High (Security Architecture)
- **Affected Files**: `templates/index.html`, `static/js/app.js`, `app.py`
- **Root Cause**: An in-browser modal and client HTTP endpoint (`/api/gemini-key`) allowed unauthenticated frontend visitors to submit or overwrite server-level API keys.
- **Symptoms**: Exposing secret key management in client-facing forms presents credential tampering and sniffing vulnerabilities.
- **Fix Implemented**: Completely removed the API key button and modal from the frontend UI. Decommissioned the client-side `/api/gemini-key` endpoint (returns HTTP 403 Forbidden). API keys are now strictly enforced server-side via the backend environment variable (`GEMINI_API_KEY`).
- **Retest Result**: Verified removal of all frontend UI triggers, verified HTTP 403 rejection on endpoint, and verified server-side environment variable resolution.

---

### Bug #7: Potential Attribute Breakout in Column Delete Button
- **Severity**: Medium (Frontend Safety)
- **Affected File**: `static/js/app.js`
- **Root Cause**: Header generation used inline `onclick="confirmDeleteColumn('${escapeHtml(m)}')"` which is vulnerable to quote escaping issues and violates CSP script-src policies.
- **Fix Implemented**: Replaced inline `onclick` with `data-month="${escapeHtml(m)}"` and added delegated event listener on `liveTableHeader`.
- **Retest Result**: Verified clicking column trash icon triggers confirmation modal and successfully deletes month column.

---

### Bug #8: Accessibility Viewport Zoom Restriction
- **Severity**: Low (Accessibility / WCAG 2.1)
- **Affected File**: `templates/index.html`
- **Root Cause**: Viewport `<meta>` tag had `maximum-scale=1.0, user-scalable=no`.
- **Fix Implemented**: Removed scaling restrictions, changing tag to `<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">`.
- **Retest Result**: Viewport scaling now functional on mobile and desktop browsers.
