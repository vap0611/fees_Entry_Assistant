# Application Security Report: Fees Entry Assistant

**Assessment Type**: Authorized White-Box Application Security Assessment & Threat Modeling  
**Date**: November 23, 2026  
**Standards Followed**: OWASP Top 10 (2021), OWASP ASVS v4.0, CWE/SANS Top 25  

---

## 1. Security Assessment Overview

A comprehensive vulnerability assessment was conducted on the **Fees Entry Assistant** repository. The assessment evaluated input handling, data storage, authentication/credential mechanisms, API security, and client-side rendering.

### Summary of Vulnerability Findings & Status

| Vulnerability ID | Title | OWASP Category | CWE | Severity | Status |
|---|---|---|---|---|---|
| **SEC-01** | Information Disclosure / API Key Leaked via Error Messages | A01:2021 - Broken Access Control / A04:2021 - Insecure Design | CWE-532, CWE-200 | **High** | **Remediated** |
| **SEC-02** | Stored and Reflected Cross-Site Scripting (XSS) in Markdown Formatter | A03:2021 - Injection | CWE-79 | **High** | **Remediated** |
| **SEC-03** | CSV Formula Injection (CWE-1236) in Export Functionality | A03:2021 - Injection | CWE-1236 | **Medium** | **Remediated** |
| **SEC-04** | Missing Defensive HTTP Security Headers | A05:2021 - Security Misconfiguration | CWE-693 | **Medium** | **Remediated** |
| **SEC-05** | Denial of Service via Unbounded State (`pending_actions` Memory Leak) | A04:2021 - Insecure Design | CWE-400, CWE-770 | **Medium** | **Remediated** |
| **SEC-06** | Configuration Overwrite & Potential CRLF Injection in `.env` | A05:2021 - Security Misconfiguration | CWE-93, CWE-113 | **Medium** | **Remediated** |
| **SEC-07** | Inadequate Numeric Range and String Length Validation | A04:2021 - Insecure Design | CWE-20, CWE-190 | **Low** | **Remediated** |

---

## 2. Vulnerability Details & Remediations

### SEC-01: API Key Leaked via URL Query Parameters & Exception Strings (CWE-532)
- **Root Cause**: The Google Gemini endpoint was queried with `?key={api_key}` in the URL string:
  ```python
  url = f"https://generativelanguage.googleapis.com/...generateContent?key={api_key}"
  ```
  When network calls failed or returned 4xx/5xx status codes, Python's `requests.exceptions.HTTPError` contained the complete URL with the raw API key. This error was converted to string `str(e)` and returned in the HTTP response (`fallback["warning"]`), exposing the secret key to client browsers and logs.
- **Remediation**:
  1. Switched authentication from URL query parameter to the secure `x-goog-api-key: {api_key}` HTTP header.
  2. Implemented `sanitize_error_message(err_str, api_key)` which redacts any detected key or `key=...` pattern before logging or returning to clients.
- **Verification**: Verified that error responses contain clean redacted URLs without secret tokens.

---

### SEC-02: Cross-Site Scripting (XSS) in Markdown Rendering (CWE-79)
- **Root Cause**: In `static/js/app.js`, `formatMarkdown(replyText)` only performed simple regex replacements (`**`, `*`, `` ` ``) without escaping HTML entities. The output was then injected directly into DOM elements via `innerHTML`. Since `replyText` contains student names, school names, and unknown query strings input by users, an attacker could supply `<img src=x onerror=alert(1)>` as a student name to achieve Stored XSS or Reflected XSS through chat responses.
- **Remediation**:
  Updated `formatMarkdown` to strictly pass the input string through `escapeHtml()` *before* applying regex markdown formatting:
  ```javascript
  function formatMarkdown(text) {
    if (!text) return '';
    const safe = escapeHtml(text);
    return safe
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code class="bg-slate-100 text-indigo-700 px-1 py-0.5 rounded font-mono text-xs">$1</code>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n• /g, '<br>• ')
      .replace(/\n/g, '<br>');
  }
  ```
- **Verification**: Tested inputs containing `<script>` and `<img>` tags; characters are safely encoded as `&lt;script&gt;` and rendered as inert text.

---

### SEC-03: CSV Formula Injection Defense (CWE-1236)
- **Root Cause**: `generate_csv_report_from_db()` in `sqlite_db.py` directly wrote user-entered text fields (`name`, `std`, `school`) into CSV output. If an entry started with formula prefix characters (`=`, `+`, `-`, `@`, `\t`, `\r`), spreadsheet viewers (Excel, Calc, Sheets) would execute the cell contents as an active formula (e.g. `=cmd|' /C calc'!A0` or data exfiltration formulas).
- **Remediation**: Added `sanitize_csv_cell(value)` to prepend a single apostrophe `'` to any cell whose first non-whitespace character is a formula trigger.
- **Verification**: Verified via test `test_csv_injection_sanitization` and `test_generate_csv_report_from_db`.

---

### SEC-04: HTTP Security Headers (CWE-693)
- **Root Cause**: The application did not emit HTTP response headers defending against clickjacking, MIME sniffing, or unauthorized resource loading.
- **Remediation**: Added an `@app.after_request` middleware applying the following headers to all HTTP responses:
  - `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none';`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: geolocation=(), camera=(), microphone=()`
- **Verification**: Verified via `test_security_headers` and curl response inspections.

---

### SEC-05: Denial of Service via State Memory Leak (CWE-400 / CWE-770)
- **Root Cause**: In `mock_db.py`, `pending_actions = {}` stored confirmation proposals indefinitely in memory. A sustained volume of chat messages or automated scraping could cause unbounded dictionary growth, resulting in server memory exhaustion.
- **Remediation**: Implemented `clean_expired_actions()` with a 15-minute Time-To-Live (TTL) window and a maximum size limit of 200 items. Pruning is automatically executed on action creation, lookup, and pop.
- **Verification**: Proposals older than 15 minutes expire cleanly, and oldest entries are trimmed when limits are reached.

---

### SEC-06: Safe Environment Variable & Key Management (CWE-93 / CWE-113)
- **Root Cause**: In `gemini_service.py`, `set_api_key` opened `.env` with `"w"`, which erased all other environment configuration (such as `PORT`, `FLASK_DEBUG`). Furthermore, unvalidated input allowed CRLF injection (`\n`) to inject new environment variables.
- **Remediation**:
  1. Added regex validation `^[a-zA-Z0-9_\-]{10,128}$` to reject newlines and malformed strings.
  2. Implemented non-destructive `.env` reading and rewriting: existing key-value pairs are preserved, only updating or appending `GEMINI_API_KEY`.
  3. Added `try ... except OSError` to gracefully tolerate read-only file systems (e.g. serverless containers).
- **Verification**: Verified via `test_set_api_key_blocks_crlf_injection`.

---

### SEC-07: Decommissioning Insecure Frontend API Key Management (CWE-200 / CWE-284)
- **Root Cause**: The application previously included an in-browser modal and client HTTP route (`/api/gemini-key`) allowing arbitrary client requests to submit API keys. In production architectures, secret credentials should never be accepted via client web forms.
- **Remediation**:
  1. Removed the API Key trigger button and modal `#modal-gemini-key` from the frontend interface.
  2. Blocked client-side modification on `/api/gemini-key` with HTTP 403 Forbidden.
  3. Enforced backend environment isolation: the Gemini API key is strictly loaded via server-side environment variables (`GEMINI_API_KEY`).
- **Verification**: Verified via `test_gemini_key_endpoint_forbidden`.

---

## 3. Dependency Security Audit (`pip-audit`)

An automated vulnerability scan of all installed packages was performed using `pip-audit`:

```text
Scanning virtual environment dependencies...
No known vulnerabilities found
```

All direct and transitive dependencies (`Flask 3.1.3`, `gunicorn 27.0.1`, `requests 2.34.2`, `pydantic 2.14.4`, `cryptography 50.0.2`, `werkzeug 3.1.9`) are up-to-date with 0 known CVEs.

---

## 4. Operational Security Recommendations

1. **Production Deployment with TLS**: Always terminate SSL/TLS (HTTPS) using a reverse proxy (Nginx, Cloudflare, or AWS ALB) in production.
2. **Access Control**: When transitioning from single-tenant internal tuition administration to multi-user environments, introduce role-based session authentication (e.g., Flask-Login or OAuth2).
