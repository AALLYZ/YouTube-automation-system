from sqlalchemy import select


def test_list_users_requires_admin(client, db):
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    editor = User(email="ed@example.com", password_hash=hash_password("x" * 8), role="editor")
    db.add(editor)
    db.commit()
    tok = create_access_token(str(editor.id))
    assert client.get("/api/admin/users", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_admin_creates_and_lists_users(client, auth):
    r = client.post(
        "/api/admin/users",
        json={"email": "New.Person@example.com", "password": "temp-pass-123", "role": "editor"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "new.person@example.com"
    assert r.json()["role"] == "editor"

    users = client.get("/api/admin/users", headers=auth).json()
    assert {u["email"] for u in users} >= {"admin@example.com", "new.person@example.com"}

    # the created user can sign in
    assert client.post(
        "/api/auth/login", json={"email": "new.person@example.com", "password": "temp-pass-123"}
    ).status_code == 200


def test_create_user_rejects_duplicate(client, auth):
    client.post("/api/admin/users", json={"email": "d@example.com", "password": "password123"}, headers=auth)
    r = client.post("/api/admin/users", json={"email": "d@example.com", "password": "password123"}, headers=auth)
    assert r.status_code == 400 and r.json()["error_code"] == "VALIDATION"


def test_update_role_and_active(client, auth):
    uid = client.post(
        "/api/admin/users", json={"email": "u2@example.com", "password": "password123"}, headers=auth
    ).json()["id"]

    r = client.patch(f"/api/admin/users/{uid}", json={"role": "viewer", "is_active": False}, headers=auth)
    assert r.status_code == 200
    assert r.json()["role"] == "viewer" and r.json()["is_active"] is False

    # deactivated user cannot log in
    assert client.post(
        "/api/auth/login", json={"email": "u2@example.com", "password": "password123"}
    ).status_code == 401


def test_cannot_remove_last_admin_or_self(client, auth, db):
    from app.models.user import User

    admin = db.execute(select(User).where(User.email == "admin@example.com")).scalar_one()

    demote = client.patch(f"/api/admin/users/{admin.id}", json={"role": "editor"}, headers=auth)
    assert demote.status_code == 400
    deact = client.patch(f"/api/admin/users/{admin.id}", json={"is_active": False}, headers=auth)
    assert deact.status_code == 400
