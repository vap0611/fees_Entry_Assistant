import pytest
import sqlite_db
import auth
from app import app


class CsrfClientWrapper:
    """Thin test client wrapper that sends X-CSRF-Token on mutating requests."""

    def __init__(self, flask_client, csrf_token=""):
        self._client = flask_client
        self.csrf_token = csrf_token

    def get(self, *args, **kwargs):
        return self._client.get(*args, **kwargs)

    def _with_csrf(self, kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self.csrf_token
        kwargs["headers"] = headers
        return kwargs

    def post(self, *args, **kwargs):
        return self._client.post(*args, **self._with_csrf(kwargs))

    def patch(self, *args, **kwargs):
        return self._client.patch(*args, **self._with_csrf(kwargs))

    def delete(self, *args, **kwargs):
        return self._client.delete(*args, **self._with_csrf(kwargs))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Sets up Flask test client with an isolated SQLite DB and an authenticated Admin session."""
    test_db_path = str(tmp_path / "test_api_fees.db")
    monkeypatch.setattr(sqlite_db, "DB_PATH", test_db_path)
    monkeypatch.setattr(sqlite_db, "DATA_DIR", str(tmp_path))
    auth.auth_rate_limiter.reset()
    sqlite_db.init_db(force_reseed=True)

    app.config["TESTING"] = True
    with app.test_client() as raw_client:
        reg = raw_client.post("/api/auth/register", json={
            "full_name": "Test Admin",
            "username": "testadmin",
            "email": "admin@test.local",
            "password": "StrongPassword123"
        })
        assert reg.status_code == 201
        csrf = reg.get_json()["csrf_token"]
        yield CsrfClientWrapper(raw_client, csrf)


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
        assert "collection_rate" in data
        assert "pending_count" in data
        assert len(data["students"]) > 0

    def test_reset_mock_table_preserves_users(self, client):
        res = client.post("/api/mock-reset")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert "table" in data
        # Admin session must remain valid after reset
        me = client.get("/api/auth/me")
        assert me.status_code == 200

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

    def test_create_edit_detail_delete_student(self, client):
        payload = {
            "name": "Karan Singhania",
            "std": "7",
            "school": "DPS",
            "monthly_fee": 1800,
            "guardian_phone": "+91 9876543210",
            "notes": "Morning batch"
        }
        res = client.post("/api/students", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        sid = data["student"]["id"]
        assert data["student"]["guardian_phone"] == "+91 9876543210"

        # Detail
        detail = client.get(f"/api/students/{sid}")
        assert detail.status_code == 200
        assert detail.get_json()["student"]["name"] == "Karan Singhania"

        # Update
        upd = client.patch(f"/api/students/{sid}", json={"monthly_fee": 2100, "status": "active"})
        assert upd.status_code == 200
        assert upd.get_json()["student"]["monthly_fee"] == 2100

        # Delete
        deleted = client.delete(f"/api/students/{sid}")
        assert deleted.status_code == 200
        assert deleted.get_json()["status"] == "success"

        missing = client.get(f"/api/students/{sid}")
        assert missing.status_code == 404

    def test_create_student_validation_failure(self, client):
        payload = {"name": "", "monthly_fee": 1000}
        res = client.post("/api/students", json=payload)
        assert res.status_code == 400
        data = res.get_json()
        assert data["status"] == "error"

    def test_direct_payment_upsert_and_delete_cell(self, client):
        table = client.get("/api/mock-table").get_json()
        sid = table["students"][0]["id"]

        res = client.post("/api/payments", json={
            "student_id": sid,
            "month_header": "Oct 2026",
            "amount": 1450,
            "payment_mode": "UPI",
            "note": "GPay #881"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"

        # Verify metadata saved in student detail
        det = client.get(f"/api/students/{sid}").get_json()
        oct_row = next(h for h in det["history"] if h["month"] == "Oct 2026")
        assert oct_row["amount"] == 1450
        assert oct_row["payment_mode"] == "UPI"
        assert oct_row["recorded_by"] == "testadmin"

        # Clear cell
        cleared = client.delete("/api/payments", json={"student_id": sid, "month_header": "Oct 2026"})
        assert cleared.status_code == 200
        assert cleared.get_json()["status"] == "success"

    def test_analytics_endpoint(self, client):
        res = client.get("/api/analytics")
        assert res.status_code == 200
        analytics = res.get_json()["analytics"]
        assert "summary" in analytics
        assert "monthly_breakdown" in analytics
        assert "school_breakdown" in analytics
        assert "pending_students" in analytics

    def test_add_and_delete_column(self, client):
        added = client.post("/api/columns", json={"month_name": "Jan 2027"})
        assert added.status_code == 200
        assert added.get_json()["month_header"] == "Jan 2027"

        res = client.post("/api/columns/delete", json={"month_name": "Dec 2026"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        res2 = client.post("/api/columns/delete", json={"month_name": "Dec 2026"})
        assert res2.status_code == 400
        assert res2.get_json()["status"] == "error"

        res3 = client.post("/api/columns/delete", json={"month_name": ""})
        assert res3.status_code == 400

    def test_chat_empty_message(self, client):
        res = client.post("/api/chat", json={"message": ""})
        assert res.status_code == 400

    def test_chat_fee_flow_proposal_confirm_and_undo(self, client):
        res = client.post("/api/chat", json={"message": "Jamie paid 1100 via UPI"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "confirmation_required"
        assert data["summary"]["payment_mode"] == "UPI"
        action_id = data["action_id"]

        res_conf = client.post("/api/action/confirm", json={"action_id": action_id, "choice": "confirm"})
        assert res_conf.status_code == 200
        data_conf = res_conf.get_json()
        assert data_conf["status"] == "success"
        entry_id = data_conf["entry_id"]

        res_undo = client.post("/api/action/undo", json={"entry_id": entry_id})
        assert res_undo.status_code == 200
        assert res_undo.get_json()["status"] == "success"

    def test_chat_honors_explicit_month_and_pending_command(self, client):
        res = client.post("/api/chat", json={"message": "Jamie paid 1100 for Dec 2026"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "confirmation_required"
        assert "Dec 2026" in data["reply"]

        pending_res = client.post("/api/chat", json={"message": "pending fees"})
        assert pending_res.status_code == 200
        assert "Pending Summary" in pending_res.get_json()["reply"]

    def test_chat_disambiguation_multiple_students(self, client):
        res = client.post("/api/chat", json={"message": "Alex paid 900"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ambiguous_name"
        assert "Alex" in data["reply"]

        res2 = client.post("/api/chat", json={"message": "Alex Std 5 paid 1300"})
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2["status"] == "confirmation_required"

    def test_gemini_key_endpoint_forbidden(self, client):
        res = client.post("/api/gemini-key", json={"api_key": "AIzaSyTestValidKey123456789"})
        assert res.status_code == 403
        data = res.get_json()
        assert "Forbidden" in data["error"]
