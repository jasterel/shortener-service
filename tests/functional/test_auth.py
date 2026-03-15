import pytest


class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={
            "email": "alice@example.com",
            "username": "alice",
            "password": "password123",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "alice@example.com"
        assert data["username"] == "alice"
        assert "id" in data

        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client):
        payload = {"email": "dup@example.com", "username": "user1", "password": "pw"}
        client.post("/api/auth/register", json=payload)

        r = client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "username": "user2",
            "password": "pw",
        })
        assert r.status_code == 400
        assert "already" in r.json()["detail"].lower()

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={
            "email": "a@example.com",
            "username": "shared_name",
            "password": "pw",
        })
        r = client.post("/api/auth/register", json={
            "email": "b@example.com",
            "username": "shared_name",
            "password": "pw",
        })
        assert r.status_code == 400

    def test_register_invalid_email(self, client):
        r = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "username": "user",
            "password": "pw",
        })
        assert r.status_code == 422

    def test_register_missing_fields(self, client):
        r = client.post("/api/auth/register", json={"email": "x@example.com"})
        assert r.status_code == 422


class TestLogin:
    def test_login_success(self, client, registered_user):
        r = client.post("/api/auth/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, client, registered_user):
        r = client.post("/api/auth/login", json={
            "email": registered_user["email"],
            "password": "wrong_password",
        })
        assert r.status_code == 401
        assert "credentials" in r.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        r = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "somepassword",
        })
        assert r.status_code == 401

    def test_login_invalid_email_format(self, client):
        r = client.post("/api/auth/login", json={
            "email": "bad-email",
            "password": "pw",
        })
        assert r.status_code == 422
