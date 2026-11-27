import pytest
import json
import sqlite_db
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Sets up Flask test client with an isolated temporary SQLite database."""
    test_db_path = str(tmp_path / "test_api_fees.db")
    monkeypatch.setattr(sqlite_db, "DB_PATH", test_db_path)
    monkeypatch.setattr(sqlite_db, "DATA_DIR", str(tmp_path))
    sqlite_db.init_db(force_reseed=True)

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestApiEndpoints:
    def test_index_route(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert b"Fees Entry Assistant" in res.data

    def test_security_headers(self, client):
        res = client.get("/")
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in res.headers

    def test_get_config(self, client):
        res = client.get("/api/config")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert "config" in data
        assert "current_month" in data

    def test_get_mock_table(self, client):
        res = client.get("/api/mock-table")
        assert res.status_code == 200
        data = res.get_json()
        assert "months" in data
        assert "students" in data
        assert len(data["students"]) > 0

    def test_reset_mock_table(self, client):
        res = client.post("/api/mock-reset")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert "table" in data

    def test_activity_log(self, client):
        res = client.get("/api/activity-log")
        assert res.status_code == 200
        data = res.get_json()
        assert "log" in data
        assert isinstance(data["log"], list)

    def test_export_csv(self, client):
        res = client.get("/api/export-csv")
        assert res.status_code == 200
        assert res.mimetype == "text/csv"
        assert "Content-Disposition" in res.headers
        assert b"Student Name" in res.data

    def test_create_student_success(self, client):
        payload = {
            "name": "Karan Singhania",
            "std": "7",
            "school": "DPS",
            "monthly_fee": 1800
        }
        res = client.post("/api/students", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert data["student"]["name"] == "Karan Singhania"
        assert data["student"]["monthly_fee"] == 1800

    def test_create_student_validation_failure(self, client):
        payload = {"name": "", "monthly_fee": 1000}
        res = client.post("/api/students", json=payload)
        assert res.status_code == 400
        data = res.get_json()
        assert data["status"] == "error"

    def test_delete_column_success_and_failure(self, client):
        # Successful deletion
        res = client.post("/api/columns/delete", json={"month_name": "Dec 2026"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        # Deleting already deleted column fails gracefully
        res2 = client.post("/api/columns/delete", json={"month_name": "Dec 2026"})
        assert res2.status_code == 400
        assert res2.get_json()["status"] == "error"

        # Empty month name fails
        res3 = client.post("/api/columns/delete", json={"month_name": ""})
        assert res3.status_code == 400

    def test_chat_empty_message(self, client):
        res = client.post("/api/chat", json={"message": ""})
        assert res.status_code == 400

    def test_chat_fee_flow_proposal_and_confirm(self, client):
        # Step 1: Send payment note
        res = client.post("/api/chat", json={"message": "Jamie paid 1100"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "confirmation_required"
        assert "action_id" in data
        action_id = data["action_id"]

        # Step 2: Confirm payment
        res_conf = client.post("/api/action/confirm", json={"action_id": action_id, "choice": "confirm"})
        assert res_conf.status_code == 200
        data_conf = res_conf.get_json()
        assert data_conf["status"] == "success"
        assert "entry_id" in data_conf
        entry_id = data_conf["entry_id"]

        # Step 3: Undo payment
        res_undo = client.post("/api/action/undo", json={"entry_id": entry_id})
        assert res_undo.status_code == 200
        assert res_undo.get_json()["status"] == "success"

    def test_chat_honors_explicit_month(self, client):
        # Note asks explicitly for Dec 2026
        res = client.post("/api/chat", json={"message": "Jamie paid 1100 for Dec 2026"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "confirmation_required"
        assert "Dec 2026" in data["reply"]

    def test_chat_disambiguation_multiple_students(self, client):
        # There are two students named Alex (Std 1 and Std 5)
        res = client.post("/api/chat", json={"message": "Alex paid 900"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ambiguous_name"
        assert "Alex" in data["reply"]

        # Specifying class resolves ambiguity
        res2 = client.post("/api/chat", json={"message": "Alex Std 5 paid 1300"})
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2["status"] == "confirmation_required"

    def test_gemini_key_endpoint_forbidden(self, client):
        # Frontend API key modification is forbidden (must be configured in backend environment only)
        res = client.post("/api/gemini-key", json={"api_key": "AIzaSyTestValidKey123456789"})
        assert res.status_code == 403
        data = res.get_json()
        assert "Forbidden" in data["error"]
