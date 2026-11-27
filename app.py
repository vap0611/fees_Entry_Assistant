"""
Fees Entry Assistant - Backend
Phase 5 & 6: Safety Features + Report Download (CSV) + Column Deletion.
"""

from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import os
import re

from sheet_config import SHEET_CONFIG
from month_logic import (
    determine_target_month,
    get_current_month_header
)
from gemini_service import (
    parse_admin_message,
    get_api_key
)
from mock_db import (
    prepare_payment_proposal,
    execute_confirmed_payment,
    execute_undo_payment,
    cancel_pending_action,
    reset_mock_data,
    get_mock_table_state,
    get_activity_log,
    get_pending_action,
    pop_pending_action,
    delete_month_column,
    generate_csv_report,
    add_new_student,
    pending_actions
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static"
)


@app.after_request
def set_security_headers(response):
    """Applies modern security headers (OWASP ASVS / Top 10 defenses)."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; "
        "img-src 'self' data:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response


@app.errorhandler(400)
def bad_request(e):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "error": "Bad request", "message": str(e)}), 400
    return "Bad Request", 400


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "error": "Endpoint not found"}), 404
    return render_template("index.html"), 404


@app.errorhandler(405)
def method_not_allowed(e):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "error": "Method not allowed"}), 405
    return "Method Not Allowed", 405


@app.errorhandler(500)
def internal_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "error": "An internal server error occurred."}), 500
    return "Internal Server Error", 500


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    """Returns configuration, safety limits, and Gemini status."""
    api_key = get_api_key()
    return jsonify({
        "status": "success",
        "config": SHEET_CONFIG,
        "current_month": get_current_month_header(),
        "has_gemini_key": bool(api_key),
        "gemini_mode": "gemini_api" if api_key else "heuristic_fallback"
    })


@app.route("/api/mock-table", methods=["GET"])
def get_mock_table():
    """Returns the live state of the 5-student mock table."""
    return jsonify(get_mock_table_state())


@app.route("/api/mock-reset", methods=["POST"])
def reset_mock():
    """Resets the mock table and session activity."""
    state = reset_mock_data()
    return jsonify({
        "status": "success",
        "message": "Mock data reset to original state.",
        "table": state
    })


@app.route("/api/activity-log", methods=["GET"])
def activity_log_endpoint():
    """Returns the session activity history."""
    return jsonify({
        "status": "success",
        "log": get_activity_log()
    })


# ==============================================================
# REPORT DOWNLOAD (CSV)
# ==============================================================

@app.route("/api/export-csv", methods=["GET"])
def export_csv():
    """Generates and downloads the current fee sheet report as a CSV file."""
    csv_content = generate_csv_report()
    filename = f"fees_report_{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )


# ==============================================================
# COLUMN DELETION API
# ==============================================================

@app.route("/api/columns/<path:month_name>", methods=["DELETE"])
def delete_column_endpoint(month_name):
    """Deletes a month column and clears corresponding payments."""
    cleaned = (month_name or "").strip()
    if not cleaned or len(cleaned) > 50:
        return jsonify({"status": "error", "reply": "⚠️ Invalid month column name."}), 400

    res = delete_month_column(cleaned)
    timestamp = datetime.now().strftime("%I:%M %p")
    
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "timestamp": timestamp,
        "table_updated": res["success"],
        "table": get_mock_table_state()
    }), (200 if res["success"] else 400)


@app.route("/api/columns/delete", methods=["POST"])
def delete_column_post():
    """Alternative POST endpoint for column deletion."""
    data = request.get_json() or {}
    month_name = (data.get("month_name") or "").strip()
    if not month_name or len(month_name) > 50:
        return jsonify({"status": "error", "reply": "⚠️ Month name is required (max 50 chars)."}), 400

    res = delete_month_column(month_name)
    timestamp = datetime.now().strftime("%I:%M %p")

    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "timestamp": timestamp,
        "table_updated": res["success"],
        "table": get_mock_table_state()
    }), (200 if res["success"] else 400)


# ==============================================================
# STUDENT MANAGEMENT: ADD NEW STUDENT
# ==============================================================

@app.route("/api/students", methods=["POST"])
def create_student():
    """Adds a new student to the fee sheet database."""
    data = request.get_json() or {}
    name = data.get("name")
    std = data.get("std", "")
    school = data.get("school", "")
    monthly_fee = data.get("monthly_fee", 0)

    res = add_new_student(name=name, std=std, school=school, monthly_fee=monthly_fee)
    timestamp = datetime.now().strftime("%I:%M %p")
    
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "student": res.get("student"),
        "timestamp": timestamp,
        "table_updated": res["success"],
        "table": get_mock_table_state()
    }), (200 if res["success"] else 400)


@app.route("/api/gemini-key", methods=["POST"])
def update_gemini_key():
    return jsonify({
        "error": "Forbidden: Frontend API key modification is disabled. Please configure GEMINI_API_KEY directly in the backend environment."
    }), 403


@app.route("/api/test-month-calc", methods=["POST"])
def test_month_calc():
    data = request.get_json() or {}
    last_paid_input = data.get("last_paid_month")
    state = get_mock_table_state()
    
    try:
        result = determine_target_month(
            last_paid_month=last_paid_input,
            existing_columns=state["months"]
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 400


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint with safety pre-checks:
    1. Check for command shortcuts ('undo', 'cancel', 'delete column <month>').
    2. Parse with Gemini NLU.
    3. Run safety checks (amount validation, duplicate check, gap warning).
    4. Prepare confirmation proposal.
    """
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Empty message"}), 400

    timestamp = datetime.now().strftime("%I:%M %p")
    clean_msg = message.lower().strip()

    # Chat Command Shortcut: Undo
    if clean_msg == "undo":
        undo_res = execute_undo_payment()
        return jsonify({
            "status": "success" if undo_res["success"] else "warning",
            "reply": undo_res["reply"],
            "timestamp": timestamp,
            "table_updated": undo_res["success"],
            "table": get_mock_table_state()
        })

    # Chat Command Shortcut: Cancel
    if clean_msg == "cancel" and pending_actions:
        latest_action_id = list(pending_actions.keys())[-1]
        cancel_res = cancel_pending_action(latest_action_id)
        return jsonify({
            "status": "info",
            "reply": cancel_res["reply"],
            "timestamp": timestamp,
            "table_updated": False,
            "table": get_mock_table_state()
        })

    # Chat Command Shortcut: Delete Column (e.g. "delete column Jan 2027", "remove Jan 2027 column")
    del_match = re.match(r"^(?:delete|remove)\s+(?:the\s+)?(?:column\s+)?([a-zA-Z]{3,9}\s+\d{4})(?:\s+column)?$", clean_msg, re.IGNORECASE)
    if not del_match:
        del_match = re.match(r"^(?:delete|remove)\s+column\s+(.+)$", clean_msg, re.IGNORECASE)
    if del_match:
        target_col = del_match.group(1).strip()
        res_del = delete_month_column(target_col)
        return jsonify({
            "status": "success" if res_del["success"] else "warning",
            "reply": res_del["reply"],
            "timestamp": timestamp,
            "table_updated": res_del["success"],
            "table": get_mock_table_state()
        })

    # Chat Command Shortcut: Add Student (e.g. "add student Rohan, std 5, Welspun, fee 1200")
    add_st_match = re.match(r"^add\s+student\s+(.+)$", message.strip(), re.IGNORECASE)
    if add_st_match:
        raw_args = add_st_match.group(1).strip()
        parts = [p.strip() for p in raw_args.split(",") if p.strip()]
        st_name = parts[0] if parts else ""
        st_std = ""
        st_school = ""
        st_fee = 0
        for part in parts[1:]:
            lower_p = part.lower()
            if re.search(r"(?:fee|fees)\s*[:=]?\s*(\d+)", lower_p):
                st_fee = int(re.search(r"(?:fee|fees)\s*[:=]?\s*(\d+)", lower_p).group(1))
            elif re.search(r"(?:std|class|grade)\s*[:=]?\s*([a-zA-Z0-9]+)", lower_p):
                st_std = re.search(r"(?:std|class|grade)\s*[:=]?\s*([a-zA-Z0-9]+)", part).group(1)
            elif re.search(r"(?:school)\s*[:=]?\s*(.+)", lower_p):
                st_school = re.search(r"(?:school)\s*[:=]?\s*(.+)", part, re.IGNORECASE).group(1)
            elif part.isdigit():
                st_fee = int(part)
            else:
                if not st_school:
                    st_school = part

        if st_name and st_fee > 0:
            res_add = add_new_student(name=st_name, std=st_std, school=st_school, monthly_fee=st_fee)
            return jsonify({
                "status": "success" if res_add["success"] else "warning",
                "reply": res_add["reply"],
                "timestamp": timestamp,
                "table_updated": res_add["success"],
                "table": get_mock_table_state()
            })
        else:
            return jsonify({
                "status": "info",
                "reply": "💡 To add a new student, click the **'+ Add Student'** button in the header bar, or type: `add student <Name>, std <Class>, school <School>, fee <Amount>` (e.g. `add student Aarav, std 5, Welspun, fee 1200`).",
                "timestamp": timestamp,
                "table_updated": False
            })

    # Step 1: Gemini NLU Extraction
    try:
        extracted = parse_admin_message(message)
    except Exception as e:
        return jsonify({
            "status": "error",
            "reply": "⚠️ Sorry, I had trouble understanding that message. Please try rephrasing (e.g., 'Student Dummy has paid 2000').",
            "timestamp": timestamp,
            "extracted": None
        })

    intent = extracted.get("intent", "unknown")
    student_name = extracted.get("student_name")
    amount = extracted.get("amount")

    # Step 2: Handle Unknown Intent
    if intent == "unknown" or not student_name:
        friendly_examples_reply = (
            "👋 I didn't recognize a fee payment in that message.\n\n"
            "Please try typing like one of these examples:\n"
            "• **`Student Dummy has paid 2000`**\n"
            "• **`Priya Sharma paid 1800`** *(Triggers Jan 2027 rollover!)*\n"
            "• **`Rohan Verma paid 1500`**\n"
            "• **`Aman Gupta Greenwood High paid 2200`**\n"
            "• Or type **`delete column <month>`** to remove a column."
        )
        return jsonify({
            "status": "warning",
            "reply": friendly_examples_reply,
            "timestamp": timestamp,
            "extracted": extracted,
            "table_updated": False
        })

    # Step 3: Handle Missing Amount
    if amount is None:
        missing_amount_reply = (
            f"I understood: Student = **{student_name}**, but how much did they pay?\n\n"
            f"👉 Please specify the amount paid (e.g., *'{student_name} paid 2000'*)."
        )
        return jsonify({
            "status": "info",
            "reply": missing_amount_reply,
            "timestamp": timestamp,
            "extracted": extracted,
            "table_updated": False
        })

    # Step 4: Safety Checks & Confirmation Proposal
    proposal = prepare_payment_proposal(student_name, amount, raw_message=message)
    current_table = get_mock_table_state()

    return jsonify({
        "status": proposal.get("status", "info"),
        "reply": proposal["reply"],
        "action_id": proposal.get("action_id"),
        "options": proposal.get("options", []),
        "summary": proposal.get("summary"),
        "timestamp": timestamp,
        "extracted": extracted,
        "table_updated": False,
        "table": current_table
    })


@app.route("/api/action/confirm", methods=["POST"])
def confirm_action():
    data = request.get_json() or {}
    action_id = data.get("action_id")
    choice = data.get("choice", "confirm")

    timestamp = datetime.now().strftime("%I:%M %p")

    # Case: Gap Choice ("fill_gap" or "continue_after")
    if choice in ("fill_gap", "continue_after"):
        action = get_pending_action(action_id)
        if not action:
            return jsonify({"status": "error", "reply": "⚠️ Action expired. Please type your message again."})

        chosen_month = action["gap_month"] if choice == "fill_gap" else action["next_after_last"]
        action["type"] = "confirm_payment"
        action["target_month"] = chosen_month

        reply = f"Enter **₹{action['amount']:,}** for **{action['student']['name']} ({action['student']['school']})** in **{chosen_month}**?"
        return jsonify({
            "status": "confirmation_required",
            "action_id": action_id,
            "reply": reply,
            "options": [
                {"label": "Confirm", "choice": "confirm", "primary": True},
                {"label": "Cancel", "choice": "cancel"}
            ],
            "timestamp": timestamp,
            "table_updated": False
        })

    # Case: Confirm Duplicate
    if choice == "confirm_duplicate":
        action = get_pending_action(action_id)
        if not action:
            return jsonify({"status": "error", "reply": "⚠️ Action expired."})
        action["type"] = "confirm_payment"
        exec_res = execute_confirmed_payment(action_id)
        return jsonify({
            "status": "success",
            "reply": exec_res["reply"],
            "entry_id": exec_res.get("entry_id"),
            "timestamp": timestamp,
            "table_updated": True,
            "table": get_mock_table_state(),
            "updated_cell": exec_res.get("updated_cell")
        })

    # Standard Confirm: write payment!
    exec_res = execute_confirmed_payment(action_id)
    if exec_res["success"]:
        return jsonify({
            "status": "success",
            "reply": exec_res["reply"],
            "entry_id": exec_res["entry_id"],
            "timestamp": timestamp,
            "table_updated": True,
            "table": get_mock_table_state(),
            "updated_cell": exec_res.get("updated_cell")
        })
    else:
        return jsonify({
            "status": "warning",
            "reply": exec_res["reply"],
            "timestamp": timestamp,
            "table_updated": False
        })


@app.route("/api/action/cancel", methods=["POST"])
def cancel_action():
    data = request.get_json() or {}
    action_id = data.get("action_id")
    timestamp = datetime.now().strftime("%I:%M %p")

    cancel_res = cancel_pending_action(action_id)
    return jsonify({
        "status": "info",
        "reply": cancel_res["reply"],
        "timestamp": timestamp,
        "table_updated": False
    })


@app.route("/api/action/undo", methods=["POST"])
def undo_action():
    data = request.get_json() or {}
    entry_id = data.get("entry_id")
    timestamp = datetime.now().strftime("%I:%M %p")

    undo_res = execute_undo_payment(entry_id)
    return jsonify({
        "status": "success" if undo_res["success"] else "warning",
        "reply": undo_res["reply"],
        "timestamp": timestamp,
        "table_updated": undo_res["success"],
        "table": get_mock_table_state()
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1")
    app.run(host="0.0.0.0", port=port, debug=debug)
