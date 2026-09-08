from app.core.config import settings


def test_login_success_and_me(client, admin_token):
    r = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == settings.admin_email.lower()


def test_login_bad_password(client, admin_token):
    r = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error_code"] == "AUTH_ERROR"


def test_protected_route_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/channels").status_code == 401
