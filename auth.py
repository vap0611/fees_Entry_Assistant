"""
Authentication, RBAC, CSRF, Rate Limiting, Recovery Codes & RFC 6238 TOTP 2FA Module
for Fees Entry Assistant.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import struct
import time
from collections import defaultdict
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import sqlite_db

# In-memory short-lived 2FA login challenge store (TTL: 5 minutes)
_two_fa_challenges = {}
_CHALLENGE_TTL_SECONDS = 300
_MAX_CHALLENGES = 500


# ==============================================================================
# SECRET KEY MANAGEMENT
# ==============================================================================

def get_or_create_flask_secret(data_dir):
    """
    Retrieves FLASK_SECRET_KEY from environment, or reads/creates a persistent
    random 64-char hex secret file in data_dir with 0600 permissions.
    Falls back to volatile random bytes on read-only file systems.
    """
    env_secret = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if len(env_secret) >= 24:
        return env_secret

    secret_file = os.path.join(data_dir, ".flask_secret")
    if os.path.exists(secret_file):
        try:
            with open(secret_file, "r", encoding="utf-8") as f:
                stored = f.read().strip()
            if len(stored) >= 24:
                return stored
        except OSError:
            pass

    generated = secrets.token_hex(32)
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(generated)
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return generated


# ==============================================================================
# PASSWORD VALIDATION & HASHING
# ==============================================================================

def validate_username(username):
    """Validates username format: 3-32 chars, letters, digits, underscores, dots, hyphens."""
    if not username or not isinstance(username, str):
        return False, "Username is required."
    cleaned = username.strip()
    if not re.match(r"^[a-zA-Z0-9_.-]{3,32}$", cleaned):
        return False, "Username must be 3-32 characters (letters, digits, _, ., - only)."
    return True, cleaned.lower()


def validate_email(email):
    """Validates optional or required email address format."""
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    cleaned = email.strip().lower()
    if len(cleaned) > 120 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
        return False, "Please enter a valid email address."
    return True, cleaned


def validate_password_strength(password):
    """
    Enforces strong password policy:
    - 8 to 128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one digit."
    return True, None


def hash_password(password):
    """Hashes password securely using Werkzeug PBKDF2/Scrypt."""
    return generate_password_hash(password)


def verify_password(password_hash, password):
    """Constant-time password hash check."""
    if not password_hash or not password:
        return False
    return check_password_hash(password_hash, password)


# ==============================================================================
# BACKUP RECOVERY CODES
# ==============================================================================

def generate_recovery_codes(count=6):
    """Generates readable single-use backup recovery codes and their SHA-256 hashes."""
    plain_codes = []
    hashed_codes = []
    for _ in range(count):
        part1 = secrets.token_hex(2).upper()
        part2 = secrets.token_hex(2).upper()
        code = f"{part1}-{part2}"
        plain_codes.append(code)
        hashed_codes.append(hash_recovery_code(code))
    return plain_codes, hashed_codes


def hash_recovery_code(code):
    """Normalizes and hashes a recovery code using SHA-256."""
    normalized = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ==============================================================================
# RFC 6238 TOTP TWO-FACTOR AUTHENTICATION (ZERO EXTERNAL DEPS)
# ==============================================================================

def generate_totp_secret():
    """Generates a 160-bit Base32 TOTP secret key."""
    raw_bytes = secrets.token_bytes(20)
    return base64.b32encode(raw_bytes).decode("ascii").rstrip("=")


def _normalize_b32(secret):
    s = re.sub(r"\s+", "", str(secret or "").upper())
    padding = (-len(s)) % 8
    return s + ("=" * padding)


def generate_totp_code(secret, for_time=None, period=30, digits=6):
    """Computes RFC 6238 HMAC-SHA1 TOTP code."""
    if for_time is None:
        for_time = int(time.time())
    key = base64.b32decode(_normalize_b32(secret), casefold=True)
    counter = int(for_time // period)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % (10 ** digits)).zfill(digits)


def verify_totp_code(secret, code, window=1):
    """Verifies a 6-digit TOTP code allowing +-1 time step drift (30s window)."""
    if not secret or not code:
        return False
    cleaned_code = re.sub(r"\s+", "", str(code))
    if not re.match(r"^\d{6}$", cleaned_code):
        return False
    now = int(time.time())
    for step in range(-window, window + 1):
        expected = generate_totp_code(secret, for_time=now + step * 30)
        if hmac.compare_digest(expected, cleaned_code):
            return True
    return False


def get_totp_provisioning_uri(username, secret, issuer="FeesEntryAssistant"):
    """Builds standard otpauth:// URI for Google Authenticator / Authy / Bitwarden."""
    label = quote(f"{issuer}:{username}")
    issuer_enc = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_enc}&algorithm=SHA1&digits=6&period=30"


# ==============================================================================
# PENDING 2FA CHALLENGE TOKENS
# ==============================================================================

def _prune_challenges():
    now = datetime.now()
    expired = [
        tok for tok, data in list(_two_fa_challenges.items())
        if (now - data["created_at"]).total_seconds() > _CHALLENGE_TTL_SECONDS
    ]
    for tok in expired:
        _two_fa_challenges.pop(tok, None)
    if len(_two_fa_challenges) > _MAX_CHALLENGES:
        oldest = sorted(_two_fa_challenges.items(), key=lambda x: x[1]["created_at"])
        for tok, _ in oldest[:len(_two_fa_challenges) - _MAX_CHALLENGES]:
            _two_fa_challenges.pop(tok, None)


def create_2fa_challenge(user_id, remember_me=False):
    _prune_challenges()
    token = secrets.token_urlsafe(32)
    _two_fa_challenges[token] = {
        "user_id": user_id,
        "remember_me": bool(remember_me),
        "attempts": 0,
        "created_at": datetime.now()
    }
    return token


def peek_2fa_challenge(token):
    _prune_challenges()
    return _two_fa_challenges.get(token)


def increment_2fa_challenge_failure(token, max_attempts=5):
    data = _two_fa_challenges.get(token)
    if not data:
        return True
    data["attempts"] = data.get("attempts", 0) + 1
    if data["attempts"] >= max_attempts:
        _two_fa_challenges.pop(token, None)
        return True
    return False


def pop_2fa_challenge(token):
    _prune_challenges()
    return _two_fa_challenges.pop(token, None)


# ==============================================================================
# SLIDING WINDOW RATE LIMITER
# ==============================================================================

class SlidingWindowRateLimiter:
    """In-memory per-IP/key sliding-window rate limiter for auth endpoints."""

    def __init__(self):
        self._hits = defaultdict(list)

    def is_allowed(self, key, max_requests=15, window_seconds=60):
        now = time.time()
        cutoff = now - window_seconds
        recent = [ts for ts in self._hits[key] if ts > cutoff]
        if len(recent) >= max_requests:
            self._hits[key] = recent
            retry_after = max(1, int(recent[0] + window_seconds - now))
            return False, retry_after
        recent.append(now)
        self._hits[key] = recent
        return True, 0

    def reset(self, key=None):
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)


auth_rate_limiter = SlidingWindowRateLimiter()


def get_client_ip():
    """Returns client IP address cleanly."""
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded or request.remote_addr or "127.0.0.1"


# ==============================================================================
# CSRF & SESSION MANAGEMENT
# ==============================================================================

def ensure_csrf_token():
    """Returns existing per-session CSRF token or creates a cryptographically strong one."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf_token():
    """Validates X-CSRF-Token header against session csrf_token using constant-time compare."""
    expected = session.get("csrf_token")
    provided = request.headers.get("X-CSRF-Token", "")
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)


def establish_user_session(user, remember_me=False):
    """Establishes an authenticated Flask session and refreshes CSRF token."""
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["session_version"] = user.get("session_version", 1)
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = bool(remember_me)


def get_authenticated_user():
    """
    Validates current Flask session against SQLite user record:
    - Ensures user exists, is active, and session_version matches.
    Returns sanitized user dict or None.
    """
    uid = session.get("user_id")
    sess_ver = session.get("session_version")
    if not uid:
        return None

    user = sqlite_db.get_user_by_id_db(uid)
    if not user or not user.get("is_active"):
        session.clear()
        return None

    if user.get("session_version", 1) != sess_ver:
        session.clear()
        return None

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email") or "",
        "full_name": user.get("full_name") or user["username"],
        "role": user["role"],
        "totp_enabled": bool(user.get("totp_enabled")),
        "created_at": user.get("created_at") or "",
        "last_login_at": user.get("last_login_at") or ""
    }


def login_required(fn):
    """Decorator requiring a verified authenticated session."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_authenticated_user()
        if not user:
            return jsonify({
                "status": "error",
                "error": "Authentication required. Please sign in.",
                "code": "AUTH_REQUIRED"
            }), 401
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*allowed_roles):
    """Decorator enforcing RBAC authorization after login_required."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None) or get_authenticated_user()
            if not user:
                return jsonify({
                    "status": "error",
                    "error": "Authentication required.",
                    "code": "AUTH_REQUIRED"
                }), 401
            if user["role"] not in allowed_roles:
                return jsonify({
                    "status": "error",
                    "error": f"Insufficient permissions. Required role: {' or '.join(allowed_roles)}.",
                    "code": "FORBIDDEN"
                }), 403
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
