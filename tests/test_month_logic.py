import pytest
from month_logic import (
    parse_month_header,
    format_month_header,
    get_next_month_header,
    find_last_paid_month,
    determine_target_month,
    get_current_month_header
)


class TestMonthLogic:
    def test_parse_month_header_text_format(self):
        y, m, fmt = parse_month_header("Oct 2026")
        assert y == 2026
        assert m == 10
        assert fmt == "text"

    def test_parse_month_header_full_name(self):
        y, m, fmt = parse_month_header("December 2026")
        assert y == 2026
        assert m == 12
        assert fmt == "text"

    def test_parse_month_header_date_format(self):
        y, m, fmt = parse_month_header("2026-11-01")
        assert y == 2026
        assert m == 11
        assert fmt == "date"

    def test_parse_month_header_invalid(self):
        with pytest.raises(ValueError):
            parse_month_header("InvalidMonth 2026")
        with pytest.raises(ValueError):
            parse_month_header("")
        with pytest.raises(ValueError):
            parse_month_header(None)

    def test_format_month_header(self):
        assert format_month_header(2026, 12, "text") == "Dec 2026"
        assert format_month_header(2027, 1, "text") == "Jan 2027"
        assert format_month_header(2026, 12, "date") == "2026-12-01"

    def test_get_next_month_header_consecutive(self):
        next_hdr, is_rollover, y, m = get_next_month_header("Oct 2026")
        assert next_hdr == "Nov 2026"
        assert is_rollover is False
        assert y == 2026
        assert m == 11

    def test_get_next_month_header_year_rollover(self):
        next_hdr, is_rollover, y, m = get_next_month_header("Dec 2026")
        assert next_hdr == "Jan 2027"
        assert is_rollover is True
        assert y == 2027
        assert m == 1

    def test_find_last_paid_month(self):
        payments = {
            "Oct 2026": 1000,
            "Nov 2026": 1000,
            "Dec 2026": 0,
            "Jan 2027": None
        }
        last_paid = find_last_paid_month(payments)
        assert last_paid == "Nov 2026"

    def test_find_last_paid_month_empty(self):
        assert find_last_paid_month({}) is None
        assert find_last_paid_month({"Oct 2026": 0}) is None

    def test_determine_target_month_no_previous_payment(self):
        res = determine_target_month(last_paid_month=None, existing_columns=["Oct 2026", "Nov 2026"])
        assert res["status"] == "success"
        assert res["last_paid_month"] is None
        assert res["is_year_rollover"] is False

    def test_determine_target_month_rollover_creates_column(self):
        existing = ["Oct 2026", "Nov 2026", "Dec 2026"]
        res = determine_target_month(last_paid_month="Dec 2026", existing_columns=existing)
        assert res["status"] == "success"
        assert res["target_month"] == "Jan 2027"
        assert res["is_year_rollover"] is True
        assert res["new_column_needed"] is True
