"""
Gemini API Structured Extraction Service
Extracts intent, student_name, amount, and confidence from conversational messages.
"""

import os
import re
import json
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

SYSTEM_PROMPT = """You are a specialized structured data extractor for a school fees administration system.
The school administrator writes informal, conversational chat messages reporting student fee payments.

Your task is to analyze the user message and return ONLY a valid JSON object with EXACTLY these five fields:
1. "intent":
   - "record_payment" if the message reports, confirms, or asks to record a fee payment (or fees paid/received/done).
   - "unknown" if the message is greeting, question, chit-chat, or unrelated.
2. "student_name":
   - The student's name. Remove prefix words like "Student", "Child", "Mr.", "Ms.", "Master".
   - If no student name is found, set to null.
3. "amount":
   - A numeric value only (integer or float, e.g. 2000, 2500, 1800.50).
   - Clean out all currency symbols (₹, Rs, Rs., INR) and thousands commas ("2,000" -> 2000).
   - If the message has NO amount mentioned, set to null. DO NOT GUESS OR INVENT AN AMOUNT.
4. "payment_mode":
   - One of: "Cash", "UPI", "Bank Transfer", "Card", "Cheque".
   - Infer from keywords like GPay/PhonePe/Paytm/UPI -> "UPI", NEFT/IMPS/RTGS/bank -> "Bank Transfer", card -> "Card", cheque/check -> "Cheque", otherwise default to "Cash".
5. "confidence":
   - "high": Both student name and amount are clearly identified.
   - "medium": Partial information (e.g. name found but amount missing) or slightly ambiguous.
   - "low": Unclear intent or unknown message.

Rules:
- Output ONLY the raw JSON object. No markdown fences (no ```json), no explanations, no text before or after.
"""


def get_api_key():
    """Retrieves GEMINI_API_KEY from environment or .env file."""
    load_dotenv(ENV_PATH)
    return os.environ.get("GEMINI_API_KEY", "").strip()


def set_api_key(api_key):
    """
    Saves GEMINI_API_KEY safely.
    Validates against CRLF injection and preserves existing .env configuration.
    """
    cleaned = (api_key or "").strip()
    if not re.match(r"^[a-zA-Z0-9_\-]{10,128}$", cleaned):
        raise ValueError("Invalid Gemini API Key format. Must be 10-128 alphanumeric/dash characters.")

    os.environ["GEMINI_API_KEY"] = cleaned

    try:
        lines = []
        key_found = False
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        lines.append(f"GEMINI_API_KEY={cleaned}\n")
                        key_found = True
                    else:
                        lines.append(line)
        if not key_found:
            lines.append(f"GEMINI_API_KEY={cleaned}\n")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        # Gracefully tolerate read-only environments (e.g. Vercel / Docker read-only containers)
        pass


def sanitize_error_message(err_str, api_key=""):
    """Redacts any API keys or credential query parameters from error strings."""
    if not err_str:
        return ""
    cleaned = str(err_str)
    if api_key and api_key in cleaned:
        cleaned = cleaned.replace(api_key, "[REDACTED_API_KEY]")
    cleaned = re.sub(r"key=[a-zA-Z0-9_\-]+", "key=[REDACTED]", cleaned)
    return cleaned


def parse_amount(raw_amount):
    """Safely converts raw amount into float or int, or returns None."""
    if raw_amount is None:
        return None
    if isinstance(raw_amount, (int, float)):
        try:
            if raw_amount <= 0 or raw_amount > 10_000_000:
                return None
            return int(raw_amount) if raw_amount == int(raw_amount) else float(raw_amount)
        except (ValueError, OverflowError):
            return None

    raw_str = str(raw_amount).strip()
    cleaned = re.sub(r"[₹$€£\s,]|(?:rs\.?|inr)", "", raw_str, flags=re.IGNORECASE)
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if match:
        try:
            val = float(match.group(0))
            if 0 < val <= 10_000_000:
                return int(val) if val.is_integer() else val
        except (ValueError, OverflowError):
            return None
    return None


def clean_student_name(raw_name):
    """Cleans student name, removing prefix words like 'Student' and trailing action verbs."""
    if not raw_name:
        return None
    name = str(raw_name).strip()
    name = re.sub(r"^(?:student|child|mr\.?|ms\.?|master)\s+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+(?:has\s+paid|have\s+paid|has|have|paid|fees|fee|done|is)+$", "", name, flags=re.IGNORECASE)
    name = name.strip().strip(",.-:")
    return name if name else None


def extract_with_gemini_api(message, api_key):
    """Calls Gemini API requesting strictly structured JSON using secure header auth."""
    import requests

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [{"text": message}]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.0
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=12)
    response.raise_for_status()

    res_json = response.json()
    candidates = res_json.get("candidates", [])
    if not candidates:
        raise ValueError("No response returned from Gemini.")

    text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return text_content


def extract_payment_mode(raw_mode_or_msg):
    """Normalizes payment mode from message or extracted field."""
    text = str(raw_mode_or_msg or "").lower()
    if any(kw in text for kw in ("upi", "gpay", "google pay", "phonepe", "paytm", "bhim", "qr")):
        return "UPI"
    if any(kw in text for kw in ("bank", "neft", "imps", "rtgs", "transfer", "online", "netbanking")):
        return "Bank Transfer"
    if any(kw in text for kw in ("card", "debit", "credit")):
        return "Card"
    if any(kw in text for kw in ("cheque", "check")):
        return "Cheque"
    return "Cash"


def heuristic_fallback_extractor(message):
    """
    Fallback parser providing the exact structured format when GEMINI_API_KEY is not set or network fails.
    """
    text = message.strip()
    clean_text = text.lower()

    # Detect Amount
    amount = None
    amt_match = re.search(r"(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)", text, re.IGNORECASE)
    if amt_match:
        raw_val = amt_match.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val >= 50 or "rs" in clean_text or "₹" in clean_text or "paid" in clean_text or "fees" in clean_text:
                amount = int(val) if val.is_integer() else val
        except ValueError:
            pass

    # Detect Student Name
    raw_name = None
    from_match = re.search(r"(?:received|got|taken)\s+(?:.*?)\s+from\s+([a-zA-Z\s]+)", text, re.IGNORECASE)
    paid_match = re.search(r"^(?:student\s+)?(.*?)(?:\s+has|\s+have)?\s+paid", text, re.IGNORECASE)
    fees_done_match = re.search(r"^(?:student\s+)?(.*?)(?:\s+fees|\s+fee)", text, re.IGNORECASE)

    if from_match:
        raw_name = from_match.group(1)
    elif paid_match:
        raw_name = paid_match.group(1)
    elif fees_done_match:
        raw_name = fees_done_match.group(1)

    name = clean_student_name(raw_name)
    payment_mode = extract_payment_mode(clean_text)

    payment_keywords = ["paid", "fees", "fee", "received", "done", "payment", "has paid"]
    has_payment_keyword = any(kw in clean_text for kw in payment_keywords)

    if has_payment_keyword or (name and amount):
        intent = "record_payment"
        if name and amount:
            confidence = "high"
        elif name:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        intent = "unknown"
        confidence = "low"

    return {
        "intent": intent,
        "student_name": name,
        "amount": amount,
        "payment_mode": payment_mode,
        "confidence": confidence,
        "source": "heuristic_fallback"
    }


def parse_admin_message(message):
    """
    Main extraction function.
    Returns:
    {
      "intent": "record_payment" | "unknown",
      "student_name": str | None,
      "amount": int | float | None,
      "payment_mode": "Cash" | "UPI" | "Bank Transfer" | "Card" | "Cheque",
      "confidence": "high" | "medium" | "low",
      "source": "gemini_api" | "heuristic_fallback"
    }
    """
    if not message or not isinstance(message, str):
        return {
            "intent": "unknown",
            "student_name": None,
            "amount": None,
            "payment_mode": "Cash",
            "confidence": "low",
            "source": "error"
        }

    api_key = get_api_key()

    if api_key:
        try:
            raw_json_str = extract_with_gemini_api(message, api_key)
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_json_str.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)

            parsed = json.loads(cleaned)

            intent = parsed.get("intent", "unknown")
            if intent not in ("record_payment", "unknown"):
                intent = "record_payment" if parsed.get("student_name") else "unknown"

            student_name = clean_student_name(parsed.get("student_name"))
            amount = parse_amount(parsed.get("amount"))
            raw_mode = parsed.get("payment_mode") or message
            payment_mode = extract_payment_mode(raw_mode)
            confidence = str(parsed.get("confidence", "medium")).lower()
            if confidence not in ("high", "medium", "low"):
                confidence = "medium"

            return {
                "intent": intent,
                "student_name": student_name,
                "amount": amount,
                "payment_mode": payment_mode,
                "confidence": confidence,
                "source": "gemini_api"
            }
        except Exception as e:
            # Safe fallback if API error or malformed JSON
            fallback = heuristic_fallback_extractor(message)
            safe_msg = sanitize_error_message(str(e), api_key)
            fallback["warning"] = f"Gemini API returned error: {safe_msg}. Using fallback."
            return fallback
    else:
        return heuristic_fallback_extractor(message)
