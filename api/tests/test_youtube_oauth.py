import datetime as dt

import pytest

from app.core.security import decrypt_secret, encrypt_secret
from app.models.channel import Channel, YouTubeCredential
from app.services import youtube_oauth as oa


@pytest.fixture()
def google_configured(monkeypatch):
    monkeypatch.setattr(oa.settings, "google_client_id", "cid.apps.googleusercontent.com")
    monkeypatch.setattr(oa.settings, "google_client_secret", "secret")
    monkeypatch.setattr(oa.settings, "google_oauth_redirect", "http://localhost:3000/api/youtube/oauth/callback")


class _FakeCreds:
    def __init__(self):
        self.token = "access-abc"
        self.refresh_token = "refresh-xyz"
        self.expiry = dt.datetime.utcnow() + dt.timedelta(hours=1)
        self.scopes = oa.OAUTH_SCOPES


class _FakeFlow:
    def __init__(self):
        self.credentials = _FakeCreds()

    def fetch_token(self, code=None):
        assert code == "the-code"

    def authorization_url(self, **kw):
        return ("https://accounts.google.com/o/oauth2/auth?x=1", kw.get("state"))


def _channel(db):
    ch = Channel(name="OAuth Co", slug=f"oauth-{db.query(Channel).count()}", niche="x")
    db.add(ch)
    db.flush()
    return ch


def test_build_authorization_url_needs_config(db):
    from app.core.errors import AppError

    ch = _channel(db)
    with pytest.raises(AppError):
        oa.build_authorization_url(ch.id)


def test_build_authorization_url(db, google_configured, monkeypatch):
    ch = _channel(db)
    monkeypatch.setattr(oa, "_flow", lambda state=None: _FakeFlow())
    url, state = oa.build_authorization_url(ch.id)
    assert url.startswith("https://accounts.google.com")
    assert oa.verify_state(state) == ch.id


def test_complete_oauth_persists_encrypted_tokens(db, google_configured, monkeypatch):
    ch = _channel(db)
    state = oa.sign_state(ch.id)
    monkeypatch.setattr(oa, "_flow", lambda state=None: _FakeFlow())
    monkeypatch.setattr(oa, "_fetch_channel_identity", lambda creds: ("UC_test", "My Channel"))

    row = oa.complete_oauth(db, state=state, code="the-code")
    assert row.youtube_channel_id == "UC_test"
    assert row.channel_title == "My Channel"
    assert row.access_token_enc and row.access_token_enc != "access-abc"
    assert decrypt_secret(row.refresh_token_enc) == "refresh-xyz"

    status = oa.connection_status(db, ch)
    assert status["connected"] is True
    assert status["youtube_channel_title"] == "My Channel"


def test_credential_dict_refreshes_stale_token(db, google_configured, monkeypatch):
    ch = _channel(db)
    db.add(
        YouTubeCredential(
            channel_id=ch.id,
            youtube_channel_id="UC1",
            access_token_enc=encrypt_secret("old-token"),
            refresh_token_enc=encrypt_secret("refresh-1"),
            token_expiry=dt.datetime.utcnow() - dt.timedelta(minutes=5),  # expired
            scopes=" ".join(oa.OAUTH_SCOPES),
        )
    )
    db.flush()

    new_expiry = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
    monkeypatch.setattr(oa, "_refresh", lambda rt, scopes: ("fresh-token", new_expiry))

    cred = oa.credential_dict(db, ch)
    assert cred["token"] == "fresh-token"
    assert cred["refresh_token"] == "refresh-1"
    assert cred["client_id"] == "cid.apps.googleusercontent.com"

    row = oa.get_credential(db, ch)
    assert decrypt_secret(row.access_token_enc) == "fresh-token"


def test_credential_dict_none_when_not_connected(db):
    ch = _channel(db)
    assert oa.credential_dict(db, ch) is None


def test_disconnect(db, monkeypatch):
    ch = _channel(db)
    db.add(YouTubeCredential(channel_id=ch.id, refresh_token_enc=encrypt_secret("r")))
    db.flush()
    assert oa.disconnect(db, ch) is True
    assert oa.get_credential(db, ch) is None
    assert oa.disconnect(db, ch) is False
