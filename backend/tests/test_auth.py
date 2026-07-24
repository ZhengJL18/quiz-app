"""Tests for authentication (login, signup, token validation)."""


class TestAuth:
    def test_signup_and_login(self, client):
        """Register a new user and login."""
        # Signup
        resp = client.post("/api/v1/auth/signup", json={
            "username": "alice", "password": "password123"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["username"] == "alice"
        assert "access_token" in data

        # Login
        resp = client.post("/api/v1/auth/login", json={
            "username": "alice", "password": "password123"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        client.post("/api/v1/auth/signup", json={
            "username": "bob", "password": "password123"
        })
        resp = client.post("/api/v1/auth/login", json={
            "username": "bob", "password": "wrongpass1"
        })
        assert resp.status_code == 401

    def test_short_password_rejected(self, client):
        """Password < 8 chars is rejected."""
        resp = client.post("/api/v1/auth/signup", json={
            "username": "eve", "password": "short"
        })
        assert resp.status_code == 400

    def test_duplicate_username(self, client):
        """Duplicate username returns 409."""
        client.post("/api/v1/auth/signup", json={
            "username": "charlie", "password": "password123"
        })
        resp = client.post("/api/v1/auth/signup", json={
            "username": "charlie", "password": "another123"
        })
        assert resp.status_code == 409

    def test_me_endpoint(self, client, auth_headers):
        """GET /me returns current user."""
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    def test_protected_route_no_token(self, client):
        """Protected routes return 401 without token."""
        resp = client.get("/api/v1/subjects")
        assert resp.status_code == 401
