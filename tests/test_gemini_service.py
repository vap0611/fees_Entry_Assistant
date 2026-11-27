import pytest
import os
from gemini_service import (
    clean_student_name,
    parse_amount,
    heuristic_fallback_extractor,
    parse_admin_message,
    sanitize_error_message,
    set_api_key
)


class TestGeminiService:
    def test_clean_student_name(self):
        assert clean_student_name("Student Alex") == "Alex"
        assert clean_student_name("Child Jamie") == "Jamie"
        assert clean_student_name("Mr. Rohan Verma") == "Rohan Verma"
        assert clean_student_name("Alex has paid") == "Alex"
        assert clean_student_name(None) is None
        assert clean_student_name("") is None

    def test_parse_amount_numeric(self):
        assert parse_amount(2000) == 2000
        assert parse_amount(1500.5) == 1500.5
        assert parse_amount("₹2,000") == 2000
        assert parse_amount("Rs. 1,500") == 1500
        assert parse_amount("2500 INR") == 2500

    def test_parse_amount_invalid_or_overflow(self):
        assert parse_amount("no amount") is None
        assert parse_amount(None) is None
        assert parse_amount(0) is None
        assert parse_amount(-500) is None
        assert parse_amount(999_999_999) is None  # Exceeds 10,000,000 limit

    def test_heuristic_fallback_extractor_record_payment(self):
        res = heuristic_fallback_extractor("Student Dummy has paid 2000")
        assert res["intent"] == "record_payment"
        assert res["student_name"] == "Dummy"
        assert res["amount"] == 2000
        assert res["confidence"] == "high"

    def test_heuristic_fallback_extractor_from_phrase(self):
        res = heuristic_fallback_extractor("Received 1500 from Priya Sharma")
        assert res["intent"] == "record_payment"
        assert res["student_name"] == "Priya Sharma"
        assert res["amount"] == 1500

    def test_heuristic_fallback_extractor_unknown_message(self):
        res = heuristic_fallback_extractor("Good morning, how are you today?")
        assert res["intent"] == "unknown"
        assert res["student_name"] is None
        assert res["amount"] is None

    def test_sanitize_error_message_redacts_api_key(self):
        secret = "AIzaSySecretTestKey12345"
        err = f"Failed to connect to https://generativelanguage.googleapis.com/?key={secret}"
        cleaned = sanitize_error_message(err, secret)
        assert secret not in cleaned
        assert "[REDACTED" in cleaned

    def test_set_api_key_blocks_crlf_injection(self):
        with pytest.raises(ValueError):
            set_api_key("valid_key\nMALICIOUS_ENV=1")
        with pytest.raises(ValueError):
            set_api_key("short")
        with pytest.raises(ValueError):
            set_api_key("")
