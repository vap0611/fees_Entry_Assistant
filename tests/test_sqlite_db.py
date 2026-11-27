import pytest
import sqlite3
import os
import io
import csv
import sqlite_db


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Uses an isolated temporary database for each test."""
    test_db_path = str(tmp_path / "test_fees.db")
    monkeypatch.setattr(sqlite_db, "DB_PATH", test_db_path)
    monkeypatch.setattr(sqlite_db, "DATA_DIR", str(tmp_path))
    sqlite_db.init_db(force_reseed=True)
    yield
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass


class TestSQLiteDb:
    def test_init_db_creates_tables_and_seeds(self):
        state = sqlite_db.get_table_state()
        assert len(state["months"]) >= 3
        assert state["total_students"] >= 1

    def test_add_student_valid(self):
        res = sqlite_db.add_student_db(name="Rohan Verma", std="5", school="Greenwood", monthly_fee=1500)
        assert res["success"] is True
        assert res["student"]["name"] == "Rohan Verma"
        assert res["student"]["monthly_fee"] == 1500

    def test_add_student_validation_failures(self):
        # Empty name
        res1 = sqlite_db.add_student_db(name="", monthly_fee=1000)
        assert res1["success"] is False
        assert "required" in res1["reply"].lower()

        # Name too long
        res2 = sqlite_db.add_student_db(name="A" * 105, monthly_fee=1000)
        assert res2["success"] is False

        # Negative fee
        res3 = sqlite_db.add_student_db(name="Valid Name", monthly_fee=-50)
        assert res3["success"] is False

        # Exceeds maximum fee
        res4 = sqlite_db.add_student_db(name="Valid Name", monthly_fee=999_999_999)
        assert res4["success"] is False

    def test_add_month_column_if_missing_does_not_crash(self):
        # This specifically tests the previously crashing sqlite3.ProgrammingError bug!
        res1 = sqlite_db.add_month_column_if_missing("Jan 2030")
        assert res1 is True
        # Column now exists, adding again returns False
        res2 = sqlite_db.add_month_column_if_missing("Jan 2030")
        assert res2 is False
        months = sqlite_db.get_month_columns()
        assert "Jan 2030" in months

    def test_record_and_undo_payment_with_entry_id(self):
        students = sqlite_db.get_all_students_with_payments()
        sid = students[0]["id"]
        entry_id = "test_entry_123"

        sqlite_db.record_payment_db(student_id=sid, month_header="Oct 2026", amount=900, entry_id=entry_id)
        
        # Verify recorded
        st_after = sqlite_db.get_all_students_with_payments()
        st0 = next(s for s in st_after if s["id"] == sid)
        assert st0["payments"].get("Oct 2026") == 900

        # Undo using entry_id
        undo_res = sqlite_db.undo_payment_db(entry_id=entry_id)
        assert undo_res["success"] is True

        # Verify cleared
        st_undone = sqlite_db.get_all_students_with_payments()
        st0_undone = next(s for s in st_undone if s["id"] == sid)
        assert "Oct 2026" not in st0_undone["payments"]

    def test_undo_nonexistent_entry_id_does_not_crash_or_delete_other_payments(self):
        # This specifically tests the previously crashing bug!
        students = sqlite_db.get_all_students_with_payments()
        sid = students[0]["id"]
        sqlite_db.record_payment_db(student_id=sid, month_header="Oct 2026", amount=900, entry_id="real_entry")

        res = sqlite_db.undo_payment_db(entry_id="nonexistent_entry_id")
        assert res["success"] is False
        assert "already undone or not found" in res["reply"].lower()

        # Verify real_entry was NOT accidentally deleted!
        st_after = sqlite_db.get_all_students_with_payments()
        st0 = next(s for s in st_after if s["id"] == sid)
        assert st0["payments"].get("Oct 2026") == 900

    def test_delete_month_column_db(self):
        months = sqlite_db.get_month_columns()
        assert "Dec 2026" in months
        del_res = sqlite_db.delete_month_column_db("Dec 2026")
        assert del_res["success"] is True
        assert "Dec 2026" not in sqlite_db.get_month_columns()

    def test_check_recent_duplicate_db(self):
        students = sqlite_db.get_all_students_with_payments()
        sid = students[0]["id"]
        
        is_dup, _ = sqlite_db.check_recent_duplicate_db(sid, 900, window_seconds=60)
        assert is_dup is False

        sqlite_db.record_payment_db(student_id=sid, month_header="Oct 2026", amount=900, entry_id="dup_test")
        
        # Immediate check should trigger duplicate
        is_dup, diff = sqlite_db.check_recent_duplicate_db(sid, 900, window_seconds=60)
        assert is_dup is True
        assert 0 <= diff <= 5

    def test_csv_injection_sanitization(self):
        assert sqlite_db.sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
        assert sqlite_db.sanitize_csv_cell("+12345") == "'+12345"
        assert sqlite_db.sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
        assert sqlite_db.sanitize_csv_cell("Normal Name") == "Normal Name"
        assert sqlite_db.sanitize_csv_cell(1200) == 1200

    def test_generate_csv_report_from_db(self):
        sqlite_db.add_student_db(name="=FormulaStudent", std="5", school="@HackSchool", monthly_fee=1000)
        csv_content = sqlite_db.generate_csv_report_from_db()
        assert "'=FormulaStudent" in csv_content
        assert "'@HackSchool" in csv_content
        assert "TOTALS" in csv_content
