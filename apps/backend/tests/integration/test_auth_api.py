"""Integration tests for registration, login, and identity verification API endpoints."""

from __future__ import annotations

from app.core.security import create_access_token


class TestAuthAPI:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "student_id": "alice_smith",
                "password": "SecurePassword123!",
                "name": "Alice Smith",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["student"]["student_id"] == "alice_smith"
        assert data["student"]["name"] == "Alice Smith"
        # Verify password is not exposed in response
        assert "password" not in data["student"]
        assert "password_hash" not in data["student"]

    def test_register_duplicate_student_id_fails(self, client):
        payload = {
            "student_id": "duplicate_user",
            "password": "Password123!",
            "name": "User One",
        }
        resp1 = client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 422
        assert resp2.json()["error"] == "VALIDATION_ERROR"

    def test_register_invalid_student_id_format(self, client):
        # Disallowed characters like spaces or symbols
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "student_id": "bad student id with spaces!",
                "password": "Password123!",
                "name": "Bad User",
            },
        )
        assert resp.status_code == 422

    def test_login_success(self, client):
        # 1. Register student
        client.post(
            "/api/v1/auth/register",
            json={
                "student_id": "bob_marley",
                "password": "BuffaloSoldier1983!",
                "name": "Bob Marley",
            },
        )

        # 2. Login
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "student_id": "bob_marley",
                "password": "BuffaloSoldier1983!",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["student"]["student_id"] == "bob_marley"

    def test_login_wrong_password_fails(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "student_id": "charlie_brown",
                "password": "CorrectPassword123!",
                "name": "Charlie",
            },
        )

        resp = client.post(
            "/api/v1/auth/login",
            json={
                "student_id": "charlie_brown",
                "password": "WrongPassword!",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "AUTHENTICATION_ERROR"

    def test_login_nonexistent_student_fails(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "student_id": "ghost_student_404",
                "password": "AnyPassword123!",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "AUTHENTICATION_ERROR"

    def test_get_me_with_valid_token(self, client):
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "student_id": "diana_prince",
                "password": "WonderWoman2026!",
                "name": "Diana Prince",
            },
        )
        token = reg.json()["access_token"]

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["student_id"] == "diana_prince"
        assert resp.json()["name"] == "Diana Prince"

    def test_get_me_unauthorized_when_missing_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.json()["error"] == "AUTHENTICATION_ERROR"
        assert "WWW-Authenticate" in resp.headers

    def test_get_me_unauthorized_when_invalid_token(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer completely.fake.token"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "AUTHENTICATION_ERROR"

    def test_get_me_unauthorized_when_expired_token(self, client, container):
        expired_token = create_access_token(
            subject="expired_student",
            secret_key=container.settings.auth.secret_key,
            expires_delta_seconds=-100,
        )
        container.student_repo.get_or_create("expired_student")

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "AUTHENTICATION_ERROR"
        assert "expired" in resp.json()["message"].lower()

