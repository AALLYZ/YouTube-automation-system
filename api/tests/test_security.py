import logging

import pytest

from app.core.logging import RedactingFilter


def _redact(msg: str) -> str:
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, (), None)
    RedactingFilter().filter(rec)
    return rec.getMessage()


def test_log_redaction_scrubs_secrets():
    assert "[REDACTED]" in _redact("using key sk-ant-api03-abcdefghijklmnopqrstuvwx")
    assert "AKIA" not in _redact('Authorization: "Bearer supersecrettoken12345"')
    assert "[REDACTED]" in _redact("api_key=abcdef1234567890")
    assert "hello world" == _redact("hello world")


def test_storage_root_jail(tmp_path):
    from app.providers.storage.local import LocalStorage

    st = LocalStorage(root=str(tmp_path))
    with pytest.raises(ValueError):
        st.open_path("../../etc/passwd")
    with pytest.raises(ValueError):
        st.exists("../secrets")


def test_rate_limit_login(client, monkeypatch):
    from app.core import ratelimit

    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(ratelimit.settings, "rate_limit_login_per_min", 3)
    ratelimit._limiter._buckets.clear()

    codes = [
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert 429 in codes[3:]
    ratelimit._limiter._buckets.clear()


def test_admin_routes_require_admin_role(client, db):
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    editor = User(email="editor@example.com", password_hash=hash_password("x"), role="editor")
    db.add(editor)
    db.commit()
    tok = create_access_token(str(editor.id))
    r = client.get("/api/admin/retention", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_admin_config_snapshot_has_no_secrets(client, auth):
    r = client.get("/api/admin/config", headers=auth)
    assert r.status_code == 200
    blob = r.text.lower()
    for leaky in ("api_key", "secret", "password", "token"):
        assert leaky not in blob
