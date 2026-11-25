import pytest
import auth
import sqlite_db
from app import app


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Configures an isolated SQLite DB and resets rate limiter for each auth test."""
    test_db_path = str(tmp_path / "test_auth_fees.db")
    monkeypatch.setattr(sqlite_db, "DB_PATH", test_db_path)
    monkeypatch.setattr(sqlite_db, "DATA_DIR", str(tmp_path))
    auth.auth_rate_limiter.reset()
    sqlite_db.init_db(force_reseed=True)
    app.config["TESTING"] = True
    return tmp_path


class TestAuthenticationAndRBAC:
    def test_unauthenticated_requests_rejected_with_401(self, isolated_env):
        with app.test_client() as client:
            status = client.get("/api/auth/status").get_json()
            assert status["authenticated"] is False
            assert status["needs_setup"] is True

            for endpoint in ["/api/mock-table", "/api/analytics", "/api/activity-log", "/api/export-csv", "/api/users"]:
                res = client.get(endpoint)
                assert res.status_code == 401, f"{endpoint} should require auth"

            for endpoint in ["/api/students", "/api/chat", "/api/payments", "/api/mock-reset"]:
                res = client.post(endpoint, json={})
                assert res.status_code == 401, f"POST {endpoint} should require auth"

    def test_registration_password_policy_and_csrf_protection(self, isolated_env):
        with app.test_client() as client:
            # Weak password rejected
            weak = client.post("/api/auth/register", json={
                "full_name": "Kiya Admin",
                "username": "kiya",
                "email": "kiya@school.com",
                "password": "weak"
            })
            assert weak.status_code == 400

            # First user registered becomes admin and gets recovery codes
            ok = client.post("/api/auth/register", json={
                "full_name": "Kiya Admin",
                "username": "kiya",
                "email": "kiya@school.com",
                "password": "StrongPassword123"
            })
            assert ok.status_code == 201
            data = ok.get_json()
            assert data["user"]["role"] == "admin"
            assert len(data["recovery_codes"]) == 6
            csrf = data["csrf_token"]

            # CSRF enforcement: mutating without X-CSRF-Token returns 403
            no_csrf = client.post("/api/students", json={"name": "Blocked", "monthly_fee": 500})
            assert no_csrf.status_code == 403
            assert no_csrf.get_json()["code"] == "CSRF_FAILED"

            # With X-CSRF-Token succeeds
            with_csrf = client.post(
                "/api/students",
                json={"name": "Allowed Student", "monthly_fee": 500},
                headers={"X-CSRF-Token": csrf}
            )
            assert with_csrf.status_code == 200

    def test_login_lockout_and_admin_unlock(self, isolated_env):
        with app.test_client() as admin_client:
            reg = admin_client.post("/api/auth/register", json={
                "full_name": "Root Admin",
                "username": "rootadmin",
                "email": "root@school.com",
                "password": "AdminPassword123"
            })
            admin_csrf = reg.get_json()["csrf_token"]

            # Create a staff member
            admin_client.post("/api/users", json={
                "full_name": "Staff Member",
                "username": "staff1",
                "email": "staff1@school.com",
                "password": "StaffPassword123",
                "role": "staff"
            }, headers={"X-CSRF-Token": admin_csrf})

        # Anonymous client triggers 5 failed logins on staff1 -> account locks
        with app.test_client() as attacker_client:
            for attempt in range(4):
                res = attacker_client.post("/api/auth/login", json={
                    "identifier": "staff1",
                    "password": "WrongPassword1"
                })
                assert res.status_code == 401

            locked_res = attacker_client.post("/api/auth/login", json={
                "identifier": "staff1",
                "password": "WrongPassword1"
            })
            assert locked_res.status_code == 429

            # Even correct password is blocked while locked
            still_locked = attacker_client.post("/api/auth/login", json={
                "identifier": "staff1",
                "password": "StaffPassword123"
            })
            assert still_locked.status_code == 429

        # Admin unlocks staff1
        with app.test_client() as admin_client:
            login = admin_client.post("/api/auth/login", json={
                "identifier": "rootadmin",
                "password": "AdminPassword123"
            })
            csrf = login.get_json()["csrf_token"]
            users = admin_client.get("/api/users").get_json()["users"]
            staff_obj = next(u for u in users if u["username"] == "staff1")
            assert staff_obj["is_locked"] is True

            unlock_res = admin_client.patch(
                f"/api/users/{staff_obj['id']}",
                json={"unlock": True},
                headers={"X-CSRF-Token": csrf}
            )
            assert unlock_res.status_code == 200

        # Staff can log in again
        with app.test_client() as staff_client:
            ok_login = staff_client.post("/api/auth/login", json={
                "identifier": "staff1",
                "password": "StaffPassword123"
            })
            assert ok_login.status_code == 200

    def test_rbac_viewer_and_staff_restrictions(self, isolated_env):
        with app.test_client() as admin_c:
            reg = admin_c.post("/api/auth/register", json={
                "full_name": "Admin User",
                "username": "adminu",
                "email": "adminu@school.com",
                "password": "AdminPassword123"
            })
            a_csrf = reg.get_json()["csrf_token"]

            admin_c.post("/api/users", json={
                "full_name": "Viewer User",
                "username": "vieweru",
                "email": "viewer@school.com",
                "password": "ViewerPassword123",
                "role": "viewer"
            }, headers={"X-CSRF-Token": a_csrf})

            admin_c.post("/api/users", json={
                "full_name": "Staff User",
                "username": "staffu",
                "email": "staffu@school.com",
                "password": "StaffPassword123",
                "role": "staff"
            }, headers={"X-CSRF-Token": a_csrf})

        # Viewer checks
        with app.test_client() as vc:
            v_login = vc.post("/api/auth/login", json={"identifier": "vieweru", "password": "ViewerPassword123"})
            v_csrf = v_login.get_json()["csrf_token"]
            assert vc.get("/api/mock-table").status_code == 200
            assert vc.get("/api/analytics").status_code == 200
            assert vc.get("/api/export-csv").status_code == 200
            assert vc.post("/api/students", json={"name": "Nope", "monthly_fee": 100}, headers={"X-CSRF-Token": v_csrf}).status_code == 403
            assert vc.post("/api/chat", json={"message": "Alex paid 900"}, headers={"X-CSRF-Token": v_csrf}).status_code == 403
            assert vc.get("/api/users").status_code == 403

        # Staff checks: can write students/payments, cannot reset DB or delete columns or manage users
        with app.test_client() as sc:
            s_login = sc.post("/api/auth/login", json={"identifier": "staffu", "password": "StaffPassword123"})
            s_csrf = s_login.get_json()["csrf_token"]
            assert sc.post(
                "/api/students",
                json={"name": "Staff Added", "monthly_fee": 900},
                headers={"X-CSRF-Token": s_csrf}
            ).status_code == 200
            assert sc.post("/api/columns/delete", json={"month_name": "Dec 2026"}, headers={"X-CSRF-Token": s_csrf}).status_code == 403
            assert sc.post("/api/mock-reset", headers={"X-CSRF-Token": s_csrf}).status_code == 403
            assert sc.get("/api/users").status_code == 403

    def test_totp_2fa_and_recovery_password_reset(self, isolated_env):
        with app.test_client() as c:
            reg = c.post("/api/auth/register", json={
                "full_name": "TwoFA Admin",
                "username": "twofa",
                "email": "twofa@school.com",
                "password": "InitPassword123"
            })
            csrf = reg.get_json()["csrf_token"]
            assert len(reg.get_json()["recovery_codes"]) == 6

            # Setup 2FA
            setup = c.post("/api/auth/2fa/setup", headers={"X-CSRF-Token": csrf})
            assert setup.status_code == 200
            secret = setup.get_json()["secret"]
            assert "otpauth://totp/" in setup.get_json()["otpauth_uri"]

            # Verify 2FA with valid TOTP code
            totp_code = auth.generate_totp_code(secret)
            verify = c.post("/api/auth/2fa/verify", json={"code": totp_code}, headers={"X-CSRF-Token": csrf})
            assert verify.status_code == 200
            fresh_codes = verify.get_json()["recovery_codes"]

            # Logout
            c.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})

            # Login triggers 2FA challenge
            login_step1 = c.post("/api/auth/login", json={"identifier": "twofa", "password": "InitPassword123"})
            assert login_step1.status_code == 200
            assert login_step1.get_json()["status"] == "2fa_required"
            ch_token = login_step1.get_json()["challenge_token"]

            # Invalid TOTP rejected
            bad_2fa = c.post("/api/auth/login/2fa", json={"challenge_token": ch_token, "code": "000000"})
            assert bad_2fa.status_code == 401

            # Valid TOTP unlocks session
            good_2fa = c.post("/api/auth/login/2fa", json={"challenge_token": ch_token, "code": auth.generate_totp_code(secret)})
            assert good_2fa.status_code == 200
            new_csrf = good_2fa.get_json()["csrf_token"]

            # Logout again and test recovery code password reset
            c.post("/api/auth/logout", headers={"X-CSRF-Token": new_csrf})
            reset_res = c.post("/api/auth/reset-password", json={
                "identifier": "twofa",
                "recovery_code": fresh_codes[0],
                "new_password": "RotatedPassword999"
            })
            assert reset_res.status_code == 200

            # Same recovery code cannot be reused
            reuse_res = c.post("/api/auth/reset-password", json={
                "identifier": "twofa",
                "recovery_code": fresh_codes[0],
                "new_password": "AnotherPassword123"
            })
            assert reuse_res.status_code == 400

            # Old password rejected, new password works
            old_pw = c.post("/api/auth/login", json={"identifier": "twofa", "password": "InitPassword123"})
            assert old_pw.status_code == 401
            new_pw = c.post("/api/auth/login", json={"identifier": "twofa", "password": "RotatedPassword999"})
            assert new_pw.status_code == 200
            assert new_pw.get_json()["status"] == "2fa_required"

    def test_logout_all_invalidates_other_sessions(self, isolated_env):
        browser_a = app.test_client()
        browser_b = app.test_client()

        browser_a.post("/api/auth/register", json={
            "full_name": "Multi Session",
            "username": "multisess",
            "email": "multi@school.com",
            "password": "StrongPassword123"
        })
        login_b = browser_b.post("/api/auth/login", json={
            "identifier": "multisess",
            "password": "StrongPassword123"
        })
        csrf_b = login_b.get_json()["csrf_token"]

        assert browser_a.get("/api/mock-table").status_code == 200
        assert browser_b.get("/api/mock-table").status_code == 200

        # Browser B signs out all devices
        assert browser_b.post("/api/auth/logout-all", headers={"X-CSRF-Token": csrf_b}).status_code == 200

        # Browser A's previously valid cookie is now rejected!
        assert browser_a.get("/api/mock-table").status_code == 401
