"""
Fees Entry Assistant - Backend API
Includes:
- Complete Session & CSRF Authentication, RBAC (admin/staff/viewer), Account Lockout,
  Backup Recovery Codes, Password Reset, and RFC 6238 TOTP 2FA.
- Conversational Fee Entry (Gemini AI / Rule Fallback), 2-Step Confirmation,
  1-Click Undo, Duplicate & Gap Alerts.
- Full Student CRUD, Direct Cell Payments, Month Management, Analytics & CSV Export.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import re

from flask import Flask, Response, g, jsonify, render_template, request, session

import auth
import sqlite_db
from gemini_service import get_api_key, parse_admin_message
from mock_db import (
    add_new_student,
    cancel_pending_action,
    delete_month_column,
    execute_confirmed_payment,
    execute_undo_payment,
    generate_csv_report,
    get_activity_log,
    get_mock_table_state,
    get_pending_action,
    pending_actions,
    prepare_payment_proposal,
    reset_mock_data,
)
from month_logic import determine_target_month, get_current_month_header
from sheet_config import SHEET_CONFIG

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)

app.secret_key = auth.get_or_create_flask_secret(sqlite_db.DATA_DIR)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FORCE_HTTPS", "false").lower() in ("true", "1"),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)


# ==============================================================================
# SECURITY MIDDLEWARE (CSRF PROTECTION & HTTP HEADERS)
# ==============================================================================

@app.before_request
def enforce_csrf_on_authenticated_mutations():
    """
    Enforces CSRF protection for all mutating API requests on authenticated sessions.
    Unauthenticated requests to protected endpoints pass through to @login_required (401).
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
        if "user_id" in session:
            if not auth.verify_csrf_token():
                return jsonify({
                    "status": "error",
                    "error": "Invalid or missing CSRF token. Please refresh the page.",
                    "code": "CSRF_FAILED"
                }), 403
    return None


@app.after_request
def set_security_headers(response):
    """Applies modern security headers (OWASP ASVS / Top 10 defenses)."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
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


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

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


# ==============================================================================
# ENTRY ROUTE
# ==============================================================================

@app.route("/")
def index():
    return render_template("index.html")


# ==============================================================================
# AUTHENTICATION, REGISTRATION, 2FA, RECOVERY & USER MANAGEMENT ROUTES
# ==============================================================================

@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Returns current authentication state, setup status, and session CSRF token."""
    csrf_token = auth.ensure_csrf_token()
    user = auth.get_authenticated_user()
    user_count = sqlite_db.get_user_count_db()
    allow_reg = sqlite_db.get_setting_db("allow_self_registration", "true") == "true"

    return jsonify({
        "status": "success",
        "authenticated": bool(user),
        "needs_setup": user_count == 0,
        "allow_self_registration": allow_reg,
        "csrf_token": csrf_token,
        "user": user
    })


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """
    Registers a new user account.
    - The very first account in SQLite automatically becomes 'admin'.
    - Subsequent accounts receive 'staff' role (if self-registration is enabled).
    - Issues 6 hashed single-use backup recovery codes.
    """
    ip = auth.get_client_ip()
    allowed, retry_after = auth.auth_rate_limiter.is_allowed(f"reg:{ip}", max_requests=12, window_seconds=300)
    if not allowed:
        return jsonify({
            "status": "error",
            "error": f"Too many registration attempts. Please try again in {retry_after}s."
        }), 429

    user_count = sqlite_db.get_user_count_db()
    allow_reg = sqlite_db.get_setting_db("allow_self_registration", "true") == "true"
    if user_count > 0 and not allow_reg:
        return jsonify({
            "status": "error",
            "error": "Self-registration is disabled. Contact your administrator to create an account."
        }), 403

    data = request.get_json() or {}
    ok_user, username_or_err = auth.validate_username(data.get("username"))
    if not ok_user:
        return jsonify({"status": "error", "error": username_or_err}), 400

    ok_email, email_or_err = auth.validate_email(data.get("email"))
    if not ok_email:
        return jsonify({"status": "error", "error": email_or_err}), 400

    full_name = (data.get("full_name") or "").strip()
    if len(full_name) < 2 or len(full_name) > 80:
        return jsonify({"status": "error", "error": "Full name must be between 2 and 80 characters."}), 400

    ok_pw, pw_err = auth.validate_password_strength(data.get("password"))
    if not ok_pw:
        return jsonify({"status": "error", "error": pw_err}), 400

    if sqlite_db.get_user_by_identifier_db(username_or_err):
        return jsonify({"status": "error", "error": "Username is already taken."}), 409
    if sqlite_db.get_user_by_identifier_db(email_or_err):
        return jsonify({"status": "error", "error": "Email address is already registered."}), 409

    assigned_role = "admin" if user_count == 0 else "staff"
    pw_hash = auth.hash_password(data["password"])
    plain_codes, hashed_codes = auth.generate_recovery_codes(6)

    user = sqlite_db.create_user_db(
        username=username_or_err,
        email=email_or_err,
        full_name=full_name,
        password_hash=pw_hash,
        role=assigned_role,
        recovery_codes_hashes=hashed_codes
    )
    sqlite_db.record_login_success_db(user["id"])
    auth.establish_user_session(user, remember_me=True)
    sqlite_db.log_auth_event_db(
        username=user["username"],
        event_type="REGISTER",
        ip_address=ip,
        detail=f"Registered as {assigned_role}" + (" (initial admin setup)" if user_count == 0 else ""),
        success=True
    )

    safe_user = auth.get_authenticated_user()
    return jsonify({
        "status": "success",
        "message": f"Account created successfully! Signed in as {assigned_role.title()}.",
        "user": safe_user,
        "csrf_token": session["csrf_token"],
        "recovery_codes": plain_codes
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """
    Authenticates user credentials with brute-force lockout and optional TOTP 2FA challenge.
    """
    ip = auth.get_client_ip()
    allowed, retry_after = auth.auth_rate_limiter.is_allowed(f"login:{ip}", max_requests=15, window_seconds=60)
    if not allowed:
        return jsonify({
            "status": "error",
            "error": f"Too many login attempts from your IP. Wait {retry_after}s and try again."
        }), 429

    data = request.get_json() or {}
    identifier = (data.get("identifier") or data.get("username") or "").strip()
    password = data.get("password") or ""
    remember_me = bool(data.get("remember_me", False))

    if not identifier or not password:
        return jsonify({"status": "error", "error": "Username/email and password are required."}), 400

    user = sqlite_db.get_user_by_identifier_db(identifier)
    if not user:
        sqlite_db.log_auth_event_db(identifier, "LOGIN_FAILED", ip, "Unknown username/email", False)
        return jsonify({"status": "error", "error": "Invalid username/email or password."}), 401

    if not user.get("is_active"):
        sqlite_db.log_auth_event_db(user["username"], "LOGIN_BLOCKED", ip, "Deactivated account", False)
        return jsonify({"status": "error", "error": "This account has been deactivated by an administrator."}), 403

    # Check account lockout window
    locked_until = user.get("locked_until") or ""
    if locked_until:
        try:
            lock_dt = datetime.fromisoformat(locked_until)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if lock_dt > now:
                remaining = int((lock_dt - now).total_seconds())
                sqlite_db.log_auth_event_db(user["username"], "LOGIN_LOCKED", ip, f"Locked for {remaining}s", False)
                return jsonify({
                    "status": "error",
                    "error": f"Account temporarily locked due to failed logins. Retry in {remaining} seconds."
                }), 429
        except ValueError:
            pass

    if not auth.verify_password(user["password_hash"], password):
        attempts, new_lock = sqlite_db.record_login_failure_db(user["id"], max_attempts=5, lock_minutes=5)
        sqlite_db.log_auth_event_db(
            user["username"], "LOGIN_FAILED", ip, f"Wrong password (attempt {attempts}/5)", False
        )
        if new_lock:
            return jsonify({
                "status": "error",
                "error": "Too many failed attempts. Account locked for 5 minutes."
            }), 429
        return jsonify({
            "status": "error",
            "error": f"Invalid username/email or password. ({5 - attempts} attempts remaining)"
        }), 401

    # Check if TOTP 2FA is enabled on account
    if user.get("totp_enabled") and user.get("totp_secret"):
        challenge_token = auth.create_2fa_challenge(user["id"], remember_me=remember_me)
        return jsonify({
            "status": "2fa_required",
            "challenge_token": challenge_token,
            "message": "Enter the 6-digit code from your authenticator app or a backup recovery code."
        }), 200

    sqlite_db.record_login_success_db(user["id"])
    auth.establish_user_session(user, remember_me=remember_me)
    sqlite_db.log_auth_event_db(user["username"], "LOGIN_SUCCESS", ip, "Password verified", True)

    return jsonify({
        "status": "success",
        "message": f"Welcome back, {user['full_name'] or user['username']}!",
        "user": auth.get_authenticated_user(),
        "csrf_token": session["csrf_token"]
    })


@app.route("/api/auth/login/2fa", methods=["POST"])
def auth_login_2fa():
    """Completes login using a 6-digit TOTP code or a single-use backup recovery code."""
    ip = auth.get_client_ip()
    allowed, retry_after = auth.auth_rate_limiter.is_allowed(f"2fa:{ip}", max_requests=15, window_seconds=60)
    if not allowed:
        return jsonify({"status": "error", "error": f"Too many attempts. Wait {retry_after}s."}), 429

    data = request.get_json() or {}
    token = (data.get("challenge_token") or "").strip()
    code = (data.get("code") or "").strip()

    challenge = auth.peek_2fa_challenge(token)
    if not challenge:
        return jsonify({"status": "error", "error": "2FA session expired. Please sign in again."}), 401

    user = sqlite_db.get_user_by_id_db(challenge["user_id"])
    if not user or not user.get("is_active"):
        auth.pop_2fa_challenge(token)
        return jsonify({"status": "error", "error": "Account unavailable."}), 403

    valid_totp = auth.verify_totp_code(user.get("totp_secret"), code)
    used_recovery = False
    if not valid_totp:
        code_hash = auth.hash_recovery_code(code)
        used_recovery = sqlite_db.consume_recovery_code_db(user["id"], code_hash)

    if not valid_totp and not used_recovery:
        exhausted = auth.increment_2fa_challenge_failure(token)
        sqlite_db.log_auth_event_db(user["username"], "2FA_FAILED", ip, "Invalid TOTP/recovery code", False)
        if exhausted:
            return jsonify({"status": "error", "error": "Too many invalid 2FA codes. Please log in again."}), 401
        return jsonify({"status": "error", "error": "Invalid 2FA or recovery code."}), 401

    auth.pop_2fa_challenge(token)
    sqlite_db.record_login_success_db(user["id"])
    auth.establish_user_session(user, remember_me=challenge["remember_me"])
    sqlite_db.log_auth_event_db(
        user["username"],
        "LOGIN_2FA_SUCCESS",
        ip,
        "Authenticated via backup recovery code" if used_recovery else "Authenticated via TOTP 2FA",
        True
    )

    return jsonify({
        "status": "success",
        "message": "2FA verification succeeded!",
        "user": auth.get_authenticated_user(),
        "csrf_token": session["csrf_token"],
        "used_recovery_code": used_recovery
    })


@app.route("/api/auth/reset-password", methods=["POST"])
def auth_reset_password():
    """Self-service password reset using a valid single-use backup recovery code."""
    ip = auth.get_client_ip()
    allowed, retry_after = auth.auth_rate_limiter.is_allowed(f"reset:{ip}", max_requests=8, window_seconds=300)
    if not allowed:
        return jsonify({"status": "error", "error": f"Rate limit exceeded. Try again in {retry_after}s."}), 429

    data = request.get_json() or {}
    identifier = (data.get("identifier") or "").strip()
    recovery_code = (data.get("recovery_code") or "").strip()
    new_password = data.get("new_password") or ""

    if not identifier or not recovery_code:
        return jsonify({"status": "error", "error": "Username/email and recovery code are required."}), 400

    ok_pw, pw_err = auth.validate_password_strength(new_password)
    if not ok_pw:
        return jsonify({"status": "error", "error": pw_err}), 400

    user = sqlite_db.get_user_by_identifier_db(identifier)
    if not user:
        sqlite_db.log_auth_event_db(identifier, "PASSWORD_RESET_FAILED", ip, "Unknown account", False)
        return jsonify({"status": "error", "error": "Invalid account or recovery code."}), 400

    code_hash = auth.hash_recovery_code(recovery_code)
    if not sqlite_db.consume_recovery_code_db(user["id"], code_hash):
        sqlite_db.log_auth_event_db(user["username"], "PASSWORD_RESET_FAILED", ip, "Invalid recovery code", False)
        return jsonify({"status": "error", "error": "Invalid account or recovery code."}), 400

    sqlite_db.update_user_password_db(user["id"], auth.hash_password(new_password))
    sqlite_db.log_auth_event_db(user["username"], "PASSWORD_RESET", ip, "Password reset via recovery code", True)

    return jsonify({
        "status": "success",
        "message": "Password reset successfully! You can now sign in with your new password."
    })


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Logs out current session and issues a fresh anonymous CSRF token."""
    user = auth.get_authenticated_user()
    if user:
        sqlite_db.log_auth_event_db(user["username"], "LOGOUT", auth.get_client_ip(), "User signed out", True)
    session.clear()
    csrf_token = auth.ensure_csrf_token()
    return jsonify({
        "status": "success",
        "message": "Signed out safely.",
        "csrf_token": csrf_token
    })


@app.route("/api/auth/logout-all", methods=["POST"])
@auth.login_required
def auth_logout_all():
    """Invalidates all active sessions for the current user across all browsers/devices."""
    user = g.current_user
    sqlite_db.increment_session_version_db(user["id"])
    sqlite_db.log_auth_event_db(
        user["username"], "LOGOUT_ALL", auth.get_client_ip(), "All device sessions invalidated", True
    )
    session.clear()
    csrf_token = auth.ensure_csrf_token()
    return jsonify({
        "status": "success",
        "message": "Signed out from all devices.",
        "csrf_token": csrf_token
    })


@app.route("/api/auth/me", methods=["GET", "PATCH"])
@auth.login_required
def auth_me():
    """Reads or updates the authenticated user's profile and security overview."""
    user_full = sqlite_db.get_user_by_id_db(g.current_user["id"])
    if request.method == "GET":
        try:
            rec_count = len(json.loads(user_full.get("recovery_codes_json") or "[]"))
        except ValueError:
            rec_count = 0
        return jsonify({
            "status": "success",
            "user": g.current_user,
            "security": {
                "totp_enabled": bool(user_full.get("totp_enabled")),
                "recovery_codes_remaining": rec_count,
                "last_login_at": user_full.get("last_login_at") or ""
            }
        })

    data = request.get_json() or {}
    full_name = data.get("full_name")
    email = data.get("email")

    if full_name is not None:
        cleaned_name = str(full_name).strip()
        if len(cleaned_name) < 2 or len(cleaned_name) > 80:
            return jsonify({"status": "error", "error": "Full name must be 2-80 characters."}), 400
    else:
        cleaned_name = None

    if email is not None:
        ok_em, email_or_err = auth.validate_email(email)
        if not ok_em:
            return jsonify({"status": "error", "error": email_or_err}), 400
        existing = sqlite_db.get_user_by_identifier_db(email_or_err)
        if existing and existing["id"] != g.current_user["id"]:
            return jsonify({"status": "error", "error": "Email is already used by another account."}), 409
        cleaned_email = email_or_err
    else:
        cleaned_email = None

    sqlite_db.update_user_db(g.current_user["id"], full_name=cleaned_name, email=cleaned_email)
    return jsonify({
        "status": "success",
        "message": "Profile updated successfully.",
        "user": auth.get_authenticated_user()
    })


@app.route("/api/auth/change-password", methods=["POST"])
@auth.login_required
def auth_change_password():
    """Changes user password after verifying current password and rotates session version."""
    data = request.get_json() or {}
    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""

    user_full = sqlite_db.get_user_by_id_db(g.current_user["id"])
    if not auth.verify_password(user_full["password_hash"], current_pw):
        sqlite_db.log_auth_event_db(
            user_full["username"], "CHANGE_PASSWORD_FAILED", auth.get_client_ip(), "Incorrect current password", False
        )
        return jsonify({"status": "error", "error": "Current password is incorrect."}), 401

    ok_pw, pw_err = auth.validate_password_strength(new_pw)
    if not ok_pw:
        return jsonify({"status": "error", "error": pw_err}), 400

    updated_user = sqlite_db.update_user_password_db(user_full["id"], auth.hash_password(new_pw))
    auth.establish_user_session(updated_user, remember_me=session.permanent)
    sqlite_db.log_auth_event_db(
        updated_user["username"], "CHANGE_PASSWORD", auth.get_client_ip(), "Password updated & sessions rotated", True
    )

    return jsonify({
        "status": "success",
        "message": "Password changed successfully. Other sessions were signed out.",
        "csrf_token": session["csrf_token"]
    })


@app.route("/api/auth/2fa/setup", methods=["POST"])
@auth.login_required
def auth_2fa_setup():
    """Generates a new TOTP secret in session for authenticator app enrollment."""
    secret = auth.generate_totp_secret()
    session["pending_totp_secret"] = secret
    uri = auth.get_totp_provisioning_uri(g.current_user["username"], secret)
    return jsonify({
        "status": "success",
        "secret": secret,
        "otpauth_uri": uri
    })


@app.route("/api/auth/2fa/verify", methods=["POST"])
@auth.login_required
def auth_2fa_verify():
    """Verifies TOTP token from authenticator app and enables 2FA on user account."""
    data = request.get_json() or {}
    code = (data.get("code") or "").strip()
    secret = session.get("pending_totp_secret")
    if not secret:
        return jsonify({"status": "error", "error": "No pending 2FA setup. Click Setup 2FA first."}), 400

    if not auth.verify_totp_code(secret, code):
        return jsonify({"status": "error", "error": "Invalid 6-digit verification code. Check your device clock."}), 400

    plain_codes, hashed_codes = auth.generate_recovery_codes(6)
    sqlite_db.set_user_totp_db(g.current_user["id"], secret, True, recovery_codes_hashes=hashed_codes)
    session.pop("pending_totp_secret", None)
    sqlite_db.log_auth_event_db(g.current_user["username"], "2FA_ENABLED", auth.get_client_ip(), "TOTP 2FA enabled", True)

    return jsonify({
        "status": "success",
        "message": "Two-Factor Authentication (2FA) is now enabled!",
        "recovery_codes": plain_codes,
        "user": auth.get_authenticated_user()
    })


@app.route("/api/auth/2fa/disable", methods=["POST"])
@auth.login_required
def auth_2fa_disable():
    """Disables TOTP 2FA after confirming password."""
    data = request.get_json() or {}
    password = data.get("password") or ""
    user_full = sqlite_db.get_user_by_id_db(g.current_user["id"])
    if not auth.verify_password(user_full["password_hash"], password):
        return jsonify({"status": "error", "error": "Password confirmation failed."}), 401

    sqlite_db.set_user_totp_db(user_full["id"], "", False)
    sqlite_db.log_auth_event_db(user_full["username"], "2FA_DISABLED", auth.get_client_ip(), "TOTP 2FA disabled", True)

    return jsonify({
        "status": "success",
        "message": "Two-Factor Authentication has been disabled.",
        "user": auth.get_authenticated_user()
    })


@app.route("/api/auth/recovery-codes/regenerate", methods=["POST"])
@auth.login_required
def auth_regenerate_recovery_codes():
    """Generates fresh backup recovery codes after password confirmation."""
    data = request.get_json() or {}
    password = data.get("password") or ""
    user_full = sqlite_db.get_user_by_id_db(g.current_user["id"])
    if not auth.verify_password(user_full["password_hash"], password):
        return jsonify({"status": "error", "error": "Password verification failed."}), 401

    plain_codes, hashed_codes = auth.generate_recovery_codes(6)
    sqlite_db.set_user_totp_db(
        user_full["id"],
        user_full.get("totp_secret") or "",
        bool(user_full.get("totp_enabled")),
        recovery_codes_hashes=hashed_codes
    )
    sqlite_db.log_auth_event_db(
        user_full["username"], "RECOVERY_CODES_ROTATED", auth.get_client_ip(), "Generated 6 fresh recovery codes", True
    )
    return jsonify({
        "status": "success",
        "recovery_codes": plain_codes
    })


# ==============================================================================
# ADMIN USER MANAGEMENT & SECURITY AUDIT LOGS
# ==============================================================================

@app.route("/api/users", methods=["GET", "POST"])
@auth.login_required
@auth.roles_required("admin")
def manage_users():
    """Admin endpoint to list or create team member accounts."""
    if request.method == "GET":
        allow_reg = sqlite_db.get_setting_db("allow_self_registration", "true") == "true"
        return jsonify({
            "status": "success",
            "users": sqlite_db.list_users_db(),
            "allow_self_registration": allow_reg
        })

    data = request.get_json() or {}
    ok_user, username_or_err = auth.validate_username(data.get("username"))
    if not ok_user:
        return jsonify({"status": "error", "error": username_or_err}), 400

    ok_email, email_or_err = auth.validate_email(data.get("email"))
    if not ok_email:
        return jsonify({"status": "error", "error": email_or_err}), 400

    full_name = (data.get("full_name") or "").strip()
    if len(full_name) < 2 or len(full_name) > 80:
        return jsonify({"status": "error", "error": "Full name must be 2-80 characters."}), 400

    ok_pw, pw_err = auth.validate_password_strength(data.get("password"))
    if not ok_pw:
        return jsonify({"status": "error", "error": pw_err}), 400

    role = (data.get("role") or "staff").strip().lower()
    if role not in sqlite_db.VALID_ROLES:
        return jsonify({"status": "error", "error": "Invalid role. Choose admin, staff, or viewer."}), 400

    if sqlite_db.get_user_by_identifier_db(username_or_err):
        return jsonify({"status": "error", "error": "Username already exists."}), 409
    if sqlite_db.get_user_by_identifier_db(email_or_err):
        return jsonify({"status": "error", "error": "Email already registered."}), 409

    plain_codes, hashed_codes = auth.generate_recovery_codes(6)
    created = sqlite_db.create_user_db(
        username=username_or_err,
        email=email_or_err,
        full_name=full_name,
        password_hash=auth.hash_password(data["password"]),
        role=role,
        recovery_codes_hashes=hashed_codes
    )
    sqlite_db.log_auth_event_db(
        g.current_user["username"],
        "ADMIN_CREATE_USER",
        auth.get_client_ip(),
        f"Created user '{created['username']}' ({role})",
        True
    )
    return jsonify({
        "status": "success",
        "message": f"Created {role} account '{created['username']}'.",
        "recovery_codes": plain_codes,
        "users": sqlite_db.list_users_db()
    }), 201


@app.route("/api/users/<int:user_id>", methods=["PATCH", "DELETE"])
@auth.login_required
@auth.roles_required("admin")
def modify_user(user_id):
    """Admin endpoint to update user role, activation status, unlock account, or remove user."""
    target = sqlite_db.get_user_by_id_db(user_id)
    if not target:
        return jsonify({"status": "error", "error": "User not found."}), 404

    if request.method == "DELETE":
        if target["id"] == g.current_user["id"]:
            return jsonify({"status": "error", "error": "You cannot delete your own active admin account."}), 400
        if target["role"] == "admin":
            admins = [u for u in sqlite_db.list_users_db() if u["role"] == "admin" and u["is_active"]]
            if len(admins) <= 1:
                return jsonify({"status": "error", "error": "Cannot delete the last active administrator."}), 400
        sqlite_db.delete_user_db(user_id)
        sqlite_db.log_auth_event_db(
            g.current_user["username"], "ADMIN_DELETE_USER", auth.get_client_ip(), f"Deleted '{target['username']}'", True
        )
        return jsonify({"status": "success", "users": sqlite_db.list_users_db()})

    data = request.get_json() or {}
    new_role = data.get("role")
    new_active = data.get("is_active")
    unlock = bool(data.get("unlock", False))

    if target["id"] == g.current_user["id"]:
        if new_active is False:
            return jsonify({"status": "error", "error": "You cannot deactivate your own account."}), 400
        if new_role and new_role != "admin":
            admins = [u for u in sqlite_db.list_users_db() if u["role"] == "admin" and u["is_active"]]
            if len(admins) <= 1:
                return jsonify({"status": "error", "error": "Cannot demote the last active administrator."}), 400

    if new_role is not None and new_role not in sqlite_db.VALID_ROLES:
        return jsonify({"status": "error", "error": "Invalid role specified."}), 400

    sqlite_db.update_user_db(
        user_id=user_id,
        role=new_role,
        is_active=new_active,
        unlock=unlock
    )
    if new_active is False or (new_role and new_role != target["role"]):
        sqlite_db.increment_session_version_db(user_id)

    sqlite_db.log_auth_event_db(
        g.current_user["username"],
        "ADMIN_UPDATE_USER",
        auth.get_client_ip(),
        f"Updated '{target['username']}' (role={new_role or target['role']}, active={new_active}, unlock={unlock})",
        True
    )
    return jsonify({"status": "success", "users": sqlite_db.list_users_db()})


@app.route("/api/settings/auth", methods=["PATCH"])
@auth.login_required
@auth.roles_required("admin")
def update_auth_settings():
    """Admin toggle for self-registration policy."""
    data = request.get_json() or {}
    allow_reg = bool(data.get("allow_self_registration", True))
    sqlite_db.set_setting_db("allow_self_registration", "true" if allow_reg else "false")
    sqlite_db.log_auth_event_db(
        g.current_user["username"],
        "SETTINGS_UPDATE",
        auth.get_client_ip(),
        f"Set allow_self_registration={allow_reg}",
        True
    )
    return jsonify({
        "status": "success",
        "allow_self_registration": allow_reg
    })


@app.route("/api/auth/logs", methods=["GET"])
@auth.login_required
@auth.roles_required("admin")
def get_auth_logs():
    """Returns authentication & security audit trail for Admins."""
    limit = min(int(request.args.get("limit", 100)), 300)
    return jsonify({
        "status": "success",
        "logs": sqlite_db.get_auth_audit_logs_db(limit=limit)
    })


# ==============================================================================
# PROTECTED CORE LEDGER, STUDENTS, PAYMENTS & ANALYTICS ENDPOINTS
# ==============================================================================

@app.route("/api/config", methods=["GET"])
@auth.login_required
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
@auth.login_required
def get_mock_table():
    """Returns the live state of the student ledger table."""
    return jsonify(get_mock_table_state())


@app.route("/api/mock-reset", methods=["POST"])
@auth.login_required
@auth.roles_required("admin")
def reset_mock():
    """Resets the ledger table and activity history (preserves user accounts)."""
    state = reset_mock_data()
    sqlite_db.log_activity_db(
        student="All Students",
        school="All",
        amount=0,
        month="—",
        status="Reset",
        note="Ledger reset to initial seed CSV state",
        actor=g.current_user["username"]
    )
    return jsonify({
        "status": "success",
        "message": "Mock data reset to original state.",
        "table": state
    })


@app.route("/api/activity-log", methods=["GET"])
@auth.login_required
def activity_log_endpoint():
    """Returns session activity history with optional status & text filters."""
    status_filter = request.args.get("status")
    search_query = request.args.get("search")
    try:
        limit = min(int(request.args.get("limit", 150)), 500)
    except ValueError:
        limit = 150
    return jsonify({
        "status": "success",
        "log": get_activity_log(limit=limit, status_filter=status_filter, search_query=search_query)
    })


@app.route("/api/analytics", methods=["GET"])
@auth.login_required
def get_analytics():
    """Returns detailed monthly revenue, collection rates, breakdowns, and pending defaulters."""
    target_month = request.args.get("month")
    return jsonify({
        "status": "success",
        "analytics": sqlite_db.get_analytics_db(target_month=target_month)
    })


@app.route("/api/export-csv", methods=["GET"])
@auth.login_required
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


# ==============================================================================
# MONTH COLUMN MANAGEMENT
# ==============================================================================

@app.route("/api/columns", methods=["POST"])
@auth.login_required
@auth.roles_required("admin", "staff")
def add_column_endpoint():
    """Creates a validated month column (e.g. 'Jan 2027')."""
    data = request.get_json() or {}
    month_name = (data.get("month_name") or "").strip()
    if not month_name or len(month_name) > 50:
        return jsonify({"status": "error", "reply": "⚠️ Valid month name is required (e.g. Jan 2027)."}), 400

    res = sqlite_db.add_month_column_validated_db(month_name, actor=g.current_user["username"])
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "month_header": res.get("month_header"),
        "table_updated": res["success"],
        "table": res.get("table", get_mock_table_state())
    }), (200 if res["success"] else 400)


@app.route("/api/columns/<path:month_name>", methods=["DELETE"])
@auth.login_required
@auth.roles_required("admin")
def delete_column_endpoint(month_name):
    """Deletes a month column and clears corresponding payments."""
    cleaned = (month_name or "").strip()
    if not cleaned or len(cleaned) > 50:
        return jsonify({"status": "error", "reply": "⚠️ Invalid month column name."}), 400

    res = delete_month_column(cleaned, actor=g.current_user["username"])
    timestamp = datetime.now().strftime("%I:%M %p")
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "timestamp": timestamp,
        "table_updated": res["success"],
        "table": get_mock_table_state()
    }), (200 if res["success"] else 400)


@app.route("/api/columns/delete", methods=["POST"])
@auth.login_required
@auth.roles_required("admin")
def delete_column_post():
    """Alternative POST endpoint for column deletion."""
    data = request.get_json() or {}
    month_name = (data.get("month_name") or "").strip()
    if not month_name or len(month_name) > 50:
        return jsonify({"status": "error", "reply": "⚠️ Month name is required (max 50 chars)."}), 400

    res = delete_month_column(month_name, actor=g.current_user["username"])
    timestamp = datetime.now().strftime("%I:%M %p")
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "timestamp": timestamp,
        "table_updated": res["success"],
        "table": get_mock_table_state()
    }), (200 if res["success"] else 400)


# ==============================================================================
# STUDENT CRUD & DIRECT PAYMENT ENDPOINTS
# ==============================================================================

@app.route("/api/students", methods=["POST"])
@auth.login_required
@auth.roles_required("admin", "staff")
def create_student():
    """Adds a new student to the fee sheet database."""
    data = request.get_json() or {}
    res = add_new_student(
        name=data.get("name"),
        std=data.get("std", ""),
        school=data.get("school", ""),
        monthly_fee=data.get("monthly_fee", 0),
        guardian_phone=data.get("guardian_phone", ""),
        notes=data.get("notes", ""),
        actor=g.current_user["username"]
    )
    timestamp = datetime.now().strftime("%I:%M %p")
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "student": res.get("student"),
        "timestamp": timestamp,
        "table_updated": res["success"],
        "table": get_mock_table_state()
    }), (200 if res["success"] else 400)


@app.route("/api/students/<int:student_id>", methods=["GET", "PATCH", "DELETE"])
@auth.login_required
def student_detail_or_mutate(student_id):
    """Fetch full student payment history, edit student profile, or delete student."""
    if request.method == "GET":
        detail = sqlite_db.get_student_detail_db(student_id)
        if not detail:
            return jsonify({"status": "error", "error": "Student not found."}), 404
        return jsonify({"status": "success", **detail})

    if request.method == "PATCH":
        if g.current_user["role"] not in ("admin", "staff"):
            return jsonify({"status": "error", "error": "Insufficient permissions."}), 403
        data = request.get_json() or {}
        res = sqlite_db.update_student_db(
            student_id=student_id,
            name=data.get("name"),
            std=data.get("std"),
            school=data.get("school"),
            monthly_fee=data.get("monthly_fee"),
            guardian_phone=data.get("guardian_phone"),
            notes=data.get("notes"),
            status=data.get("status"),
            actor=g.current_user["username"]
        )
        return jsonify({
            "status": "success" if res["success"] else "error",
            "reply": res["reply"],
            "student": res.get("student"),
            "detail": res.get("detail"),
            "table_updated": res["success"],
            "table": res.get("table", get_mock_table_state())
        }), (200 if res["success"] else 400)

    # DELETE requires Admin
    if g.current_user["role"] != "admin":
        return jsonify({"status": "error", "error": "Only administrators can delete students."}), 403
    res = sqlite_db.delete_student_db(student_id, actor=g.current_user["username"])
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "table_updated": res["success"],
        "table": res.get("table", get_mock_table_state())
    }), (200 if res["success"] else 404)


@app.route("/api/payments", methods=["POST", "DELETE"])
@auth.login_required
@auth.roles_required("admin", "staff")
def direct_payment():
    """Direct structured cell payment upsert or deletion from ledger grid."""
    data = request.get_json() or {}
    student_id = data.get("student_id")
    month_header = (data.get("month_header") or data.get("month") or "").strip()

    if not student_id or not month_header:
        return jsonify({"status": "error", "reply": "⚠️ Student ID and month are required."}), 400

    try:
        sid = int(student_id)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "reply": "⚠️ Invalid student ID."}), 400

    if request.method == "DELETE":
        res = sqlite_db.delete_payment_cell_db(sid, month_header, actor=g.current_user["username"])
        return jsonify({
            "status": "success" if res["success"] else "error",
            "reply": res["reply"],
            "table_updated": res["success"],
            "table": res.get("table", get_mock_table_state())
        }), (200 if res["success"] else 404)

    res = sqlite_db.upsert_direct_payment_db(
        student_id=sid,
        month_header=month_header,
        amount=data.get("amount"),
        payment_mode=data.get("payment_mode", "Cash"),
        note=data.get("note", ""),
        actor=g.current_user["username"]
    )
    return jsonify({
        "status": "success" if res["success"] else "error",
        "reply": res["reply"],
        "entry_id": res.get("entry_id"),
        "updated_cell": res.get("updated_cell"),
        "table_updated": res["success"],
        "table": res.get("table", get_mock_table_state())
    }), (200 if res["success"] else 400)


@app.route("/api/gemini-key", methods=["POST"])
def update_gemini_key():
    """Explicitly blocked: API keys must be configured strictly in backend environment."""
    return jsonify({
        "error": (
            "Forbidden: Frontend API key modification is disabled. "
            "Please configure GEMINI_API_KEY directly in the backend environment."
        )
    }), 403


@app.route("/api/test-month-calc", methods=["POST"])
@auth.login_required
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
        return jsonify({"status": "error", "error": str(e)}), 400


# ==============================================================================
# CONVERSATIONAL CHAT & SAFETY PIPELINE
# ==============================================================================

@app.route("/api/chat", methods=["POST"])
@auth.login_required
@auth.roles_required("admin", "staff")
def chat():
    """
    Main chat endpoint with safety pre-checks and user attribution:
    1. Command shortcuts ('undo', 'cancel', 'delete column <month>', 'add student ...', 'pending fees').
    2. Parse with Gemini NLU / Rule Fallback (name, amount, payment_mode).
    3. Run safety checks (amount validation, duplicate check, gap warning).
    4. Prepare confirmation proposal.
    """
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Empty message"}), 400

    actor = g.current_user["username"]
    timestamp = datetime.now().strftime("%I:%M %p")
    clean_msg = message.lower().strip()

    # Chat Command Shortcut: Undo
    if clean_msg == "undo":
        undo_res = execute_undo_payment(actor=actor)
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
        cancel_res = cancel_pending_action(latest_action_id, actor=actor)
        return jsonify({
            "status": "info",
            "reply": cancel_res["reply"],
            "timestamp": timestamp,
            "table_updated": False,
            "table": get_mock_table_state()
        })

    # Chat Command Shortcut: Pending fees summary
    if clean_msg in ("pending", "pending fees", "defaulters", "unpaid", "who hasn't paid"):
        analytics = sqlite_db.get_analytics_db()
        s = analytics["summary"]
        pending = analytics["pending_students"]
        if not pending:
            reply = f"🎉 All active students have paid for **{s['focus_month']}**! (Collection: ₹{s['focus_collected']:,})"
        else:
            lines = "\n".join(
                f"• **{p['name']}** ({p['school'] or 'N/A'}, Std {p['std'] or '-'}): ₹{p['monthly_fee']:,}"
                for p in pending[:10]
            )
            more = f"\n*...and {len(pending) - 10} more in Analytics.*" if len(pending) > 10 else ""
            reply = (
                f"📊 **{s['focus_month']} Pending Summary** ({len(pending)} unpaid • ₹{s['focus_pending_amount']:,} due):\n"
                f"{lines}{more}"
            )
        return jsonify({
            "status": "info",
            "reply": reply,
            "timestamp": timestamp,
            "table_updated": False
        })

    # Chat Command Shortcut: Delete Column
    del_match = re.match(
        r"^(?:delete|remove)\s+(?:the\s+)?(?:column\s+)?([a-zA-Z]{3,9}\s+\d{4})(?:\s+column)?$",
        clean_msg, re.IGNORECASE
    )
    if not del_match:
        del_match = re.match(r"^(?:delete|remove)\s+column\s+(.+)$", clean_msg, re.IGNORECASE)
    if del_match:
        if g.current_user["role"] != "admin":
            return jsonify({
                "status": "error",
                "reply": "🔒 Only Administrators can delete month columns.",
                "timestamp": timestamp,
                "table_updated": False
            }), 403
        target_col = del_match.group(1).strip()
        res_del = delete_month_column(target_col, actor=actor)
        return jsonify({
            "status": "success" if res_del["success"] else "warning",
            "reply": res_del["reply"],
            "timestamp": timestamp,
            "table_updated": res_del["success"],
            "table": get_mock_table_state()
        })

    # Chat Command Shortcut: Add Student
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
            res_add = add_new_student(
                name=st_name, std=st_std, school=st_school, monthly_fee=st_fee, actor=actor
            )
            return jsonify({
                "status": "success" if res_add["success"] else "warning",
                "reply": res_add["reply"],
                "timestamp": timestamp,
                "table_updated": res_add["success"],
                "table": get_mock_table_state()
            })
        return jsonify({
            "status": "info",
            "reply": "💡 Click **'+ Add Student'** or type: `add student Aarav, std 5, Welspun, fee 1200`.",
            "timestamp": timestamp,
            "table_updated": False
        })

    # Step 1: NLU Extraction
    try:
        extracted = parse_admin_message(message)
    except Exception:
        return jsonify({
            "status": "error",
            "reply": "⚠️ Sorry, I had trouble understanding that message. Try: `'Alex paid 900 via UPI'`.",
            "timestamp": timestamp,
            "extracted": None
        })

    intent = extracted.get("intent", "unknown")
    student_name = extracted.get("student_name")
    amount = extracted.get("amount")
    payment_mode = extracted.get("payment_mode", "Cash")

    # Step 2: Handle Unknown Intent
    if intent == "unknown" or not student_name:
        friendly_examples_reply = (
            "👋 I didn't recognize a fee payment in that message.\n\n"
            "Try natural notes like:\n"
            "• **`Alex paid 900 via UPI`**\n"
            "• **`Jamie paid 1100 for Dec 2026`**\n"
            "• **`pending fees`** *(See unpaid students summary)*\n"
            "• **`delete column Jan 2027`** *(Admin only)*"
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
        return jsonify({
            "status": "info",
            "reply": f"I understood: Student = **{student_name}**, but how much did they pay? (e.g. *'{student_name} paid 1200'*)",
            "timestamp": timestamp,
            "extracted": extracted,
            "table_updated": False
        })

    # Step 4: Safety Checks & Confirmation Proposal
    proposal = prepare_payment_proposal(
        student_name, amount, raw_message=message, payment_mode=payment_mode, actor=actor
    )
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
@auth.login_required
@auth.roles_required("admin", "staff")
def confirm_action():
    data = request.get_json() or {}
    action_id = data.get("action_id")
    choice = data.get("choice", "confirm")
    actor = g.current_user["username"]
    timestamp = datetime.now().strftime("%I:%M %p")

    if choice in ("fill_gap", "continue_after"):
        action = get_pending_action(action_id)
        if not action:
            return jsonify({"status": "error", "reply": "⚠️ Action expired. Please type your message again."})

        chosen_month = action["gap_month"] if choice == "fill_gap" else action["next_after_last"]
        action["type"] = "confirm_payment"
        action["target_month"] = chosen_month
        mode = action.get("payment_mode", "Cash")
        student_info = f"{action['student']['name']} ({action['student']['school']})"
        reply = f"Enter **₹{action['amount']:,}** ({mode}) for **{student_info}** in **{chosen_month}**?"
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

    if choice == "confirm_duplicate":
        action = get_pending_action(action_id)
        if not action:
            return jsonify({"status": "error", "reply": "⚠️ Action expired."})
        action["type"] = "confirm_payment"
        exec_res = execute_confirmed_payment(action_id, actor=actor)
        return jsonify({
            "status": "success",
            "reply": exec_res["reply"],
            "entry_id": exec_res.get("entry_id"),
            "timestamp": timestamp,
            "table_updated": True,
            "table": get_mock_table_state(),
            "updated_cell": exec_res.get("updated_cell")
        })

    exec_res = execute_confirmed_payment(action_id, actor=actor)
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
    return jsonify({
        "status": "warning",
        "reply": exec_res["reply"],
        "timestamp": timestamp,
        "table_updated": False
    })


@app.route("/api/action/cancel", methods=["POST"])
@auth.login_required
@auth.roles_required("admin", "staff")
def cancel_action():
    data = request.get_json() or {}
    action_id = data.get("action_id")
    timestamp = datetime.now().strftime("%I:%M %p")
    cancel_res = cancel_pending_action(action_id, actor=g.current_user["username"])
    return jsonify({
        "status": "info",
        "reply": cancel_res["reply"],
        "timestamp": timestamp,
        "table_updated": False
    })


@app.route("/api/action/undo", methods=["POST"])
@auth.login_required
@auth.roles_required("admin", "staff")
def undo_action():
    data = request.get_json() or {}
    entry_id = data.get("entry_id")
    timestamp = datetime.now().strftime("%I:%M %p")
    undo_res = execute_undo_payment(entry_id, actor=g.current_user["username"])
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
