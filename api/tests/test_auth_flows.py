import pytest

from app.core.config import settings


def _me(client, token):
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()


# ---------------- registration ----------------
def test_auth_config_reports_registration_open_when_no_users(client):
    assert client.get("/api/auth/config").json()["registration_enabled"] is True


def test_first_registered_user_becomes_admin(client):
    r = client.post("/api/auth/register", json={"email": "founder@example.com", "password": "hunter2hunter2"})
    assert r.status_code == 201, r.text
    assert _me(client, r.json()["access_token"])["role"] == "admin"


def test_registration_disabled_once_a_user_exists(client, admin_token):
    r = client.post("/api/auth/register", json={"email": "second@example.com", "password": "password123"})
    assert r.status_code == 400
    assert r.json()["error_code"] == "AUTH_ERROR"
    assert client.get("/api/auth/config").json()["registration_enabled"] is False


def test_registration_when_explicitly_enabled(client, admin_token, monkeypatch):
    from app.api.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes.settings, "auth_allow_registration", True)
    r = client.post("/api/auth/register", json={"email": "editor@example.com", "password": "password123"})
    assert r.status_code == 201
    assert _me(client, r.json()["access_token"])["role"] == "editor"


def test_register_rejects_short_password(client):
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "short"})
    assert r.status_code == 422


def test_register_rejects_duplicate_email(client, monkeypatch):
    from app.api.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes.settings, "auth_allow_registration", True)
    assert client.post("/api/auth/register", json={"email": "dupe@example.com", "password": "password123"}).status_code == 201
    r = client.post("/api/auth/register", json={"email": "dupe@example.com", "password": "password123"})
    assert r.status_code == 400 and r.json()["error_code"] == "VALIDATION"


# ---------------- forgot / reset ----------------
@pytest.fixture()
def a_user(client):
    client.post("/api/auth/register", json={"email": "u@example.com", "password": "originalpw123"})
    return "u@example.com"


def test_forgot_password_is_generic_and_returns_dev_token(client, a_user):
    r = client.post("/api/auth/forgot-password", json={"email": a_user})
    assert r.status_code == 200
    body = r.json()
    assert "reset" in body["message"].lower()
    assert body["reset_token"]  # returned because APP_ENV=test


def test_forgot_password_unknown_email_does_not_enumerate(client, a_user):
    known = client.post("/api/auth/forgot-password", json={"email": a_user}).json()
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json()
    assert known["message"] == unknown["message"]
    assert unknown["reset_token"] is None


def test_reset_password_end_to_end(client, a_user):
    token = client.post("/api/auth/forgot-password", json={"email": a_user}).json()["reset_token"]

    rr = client.post("/api/auth/reset-password", json={"token": token, "password": "brandnewpw456"})
    assert rr.status_code == 200

    assert client.post("/api/auth/login", json={"email": a_user, "password": "brandnewpw456"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": a_user, "password": "originalpw123"}).status_code == 401

    # token is single-use (its password fingerprint no longer matches)
    again = client.post("/api/auth/reset-password", json={"token": token, "password": "another1234"})
    assert again.status_code == 401


def test_reset_password_invalid_token(client):
    r = client.post("/api/auth/reset-password", json={"token": "not-a-token", "password": "whatever123"})
    assert r.status_code == 401
