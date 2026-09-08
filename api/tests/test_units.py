"""Fast unit tests for pure helpers (no DB, no network)."""
import pytest


# ---------------- pricing ----------------
def test_llm_cost_and_fallbacks():
    from app.core.pricing import image_cost, llm_cost, research_cost, voice_cost

    assert llm_cost("claude-sonnet-4-5", 1_000_000, 1_000_000) == pytest.approx(18.0)
    assert llm_cost("stub", 5000, 5000) == 0.0
    assert llm_cost("totally-unknown-model", 1_000_000, 0) == 0.0  # -> stub table
    assert voice_cost("elevenlabs", 1000) == pytest.approx(0.30)
    assert voice_cost("stub", 9999) == 0.0
    assert image_cost("openai", 3) == pytest.approx(0.12)
    assert research_cost("tavily", 2) == pytest.approx(0.016)


# ---------------- security ----------------
def test_password_hash_and_verify():
    from app.core.security import hash_password, verify_password

    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    from app.core.security import create_access_token, decode_token

    tok = create_access_token("42", {"role": "admin"})
    payload = decode_token(tok)
    assert payload["sub"] == "42" and payload["role"] == "admin"


def test_secret_encryption_roundtrip():
    from app.core.security import decrypt_secret, encrypt_secret

    enc = encrypt_secret("refresh-token-xyz")
    assert enc != "refresh-token-xyz"
    assert decrypt_secret(enc) == "refresh-token-xyz"


# ---------------- retry / backoff ----------------
def test_backoff_growth_and_cap():
    from app.workflows.retry import backoff_seconds

    assert backoff_seconds(1, base=2) == 2
    assert backoff_seconds(3, base=2) == 8
    assert backoff_seconds(20, base=2, cap=60) == 60


def test_run_with_retry_stops_on_non_retryable():
    from app.core.errors import AppError, ErrorCode
    from app.workflows.retry import run_with_retry

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise AppError("nope", code=ErrorCode.VALIDATION)

    with pytest.raises(AppError):
        run_with_retry(fn, max_attempts=5, base_sec=0)
    assert calls["n"] == 1


def test_run_with_retry_recovers():
    from app.core.errors import AppError, ErrorCode
    from app.workflows.retry import run_with_retry

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise AppError("blip", code=ErrorCode.PROVIDER_UNAVAILABLE)
        return "ok"

    assert run_with_retry(fn, max_attempts=5, base_sec=0) == "ok"
    assert calls["n"] == 3


# ---------------- topics scoring ----------------
def test_topic_fingerprint_ignores_stopwords_and_order():
    from app.services.topics import fingerprint

    assert fingerprint("The History of the Paperclip") == fingerprint("paperclip history")
    assert fingerprint("A") != fingerprint("B")


def test_topic_score_bounds():
    from app.services.topics import DEFAULT_WEIGHTS, score_topic

    hi = score_topic(
        {"estimated_interest": 100, "uniqueness_score": 100, "search_potential": 100,
         "retention_potential": 100, "competition": 0, "difficulty": 0},
        DEFAULT_WEIGHTS,
    )
    lo = score_topic(
        {"estimated_interest": 0, "uniqueness_score": 0, "search_potential": 0,
         "retention_potential": 0, "competition": 100, "difficulty": 100},
        DEFAULT_WEIGHTS,
    )
    assert hi == 100.0
    assert 0.0 <= lo <= hi


# ---------------- metadata helpers ----------------
def test_metadata_helpers():
    from app.services.metadata import _build_chapters, _clean_tags, _fmt_ts

    assert _clean_tags(["  A ", "a", "B", "", "a"]) == ["a", "b"]
    assert len(_clean_tags([f"tag{i}" for i in range(40)])) == 15
    assert _fmt_ts(0) == "0:00"
    assert _fmt_ts(75) == "1:15"
    assert _fmt_ts(3661) == "1:01:01"

    durs = [("Intro", 15.0), ("Body", 20.0), ("End", 15.0)]
    chapters = _build_chapters(durs, ["Intro", "Body", "End"])
    assert [c["start"] for c in chapters] == [0.0, 15.0, 35.0]
    # too few / zero-length -> no chapters
    assert _build_chapters([("a", 5.0), ("b", 5.0)], []) == []
    assert _build_chapters([("a", 0.0), ("b", 0.0), ("c", 0.0)], []) == []


# ---------------- notification status mapping ----------------
def test_notification_status_mapping():
    from app.core.enums import NotificationStatus
    from app.services.notifications import _map_status

    assert _map_status("delivered", default=NotificationStatus.SENT) == NotificationStatus.DELIVERED
    assert _map_status("undelivered", default=NotificationStatus.SENT) == NotificationStatus.FAILED
    assert _map_status("weird", default=NotificationStatus.QUEUED) == NotificationStatus.QUEUED


def test_notification_templates_cover_every_event():
    from app.core.enums import NotificationEvent
    from app.services.notifications import TEMPLATES, render_template

    for ev in NotificationEvent:
        assert ev in TEMPLATES
        name, body = render_template(ev, {"title": "T", "job_public_id": "job_x"})
        assert name and len(body) > 5


# ---------------- provider registry ----------------
def test_registry_rejects_unknown_provider(monkeypatch):
    from app.core.errors import AppError
    from app.providers import registry

    monkeypatch.setattr(registry.settings, "youtube_provider", "bogus")
    registry.get_youtube.cache_clear()
    with pytest.raises(AppError):
        registry.get_youtube()
    registry.get_youtube.cache_clear()


# ---------------- ffmpeg path escaping ----------------
def test_escape_filter_path():
    from app.utils.ffmpeg import escape_filter_path

    assert escape_filter_path("/tmp/a:b'c") == "/tmp/a\\:b\\'c"


# ---------------- oauth state ----------------
def test_oauth_state_roundtrip_and_tamper():
    from app.core.errors import AppError
    from app.services.youtube_oauth import sign_state, verify_state

    assert verify_state(sign_state(7)) == 7
    with pytest.raises(AppError):
        verify_state("garbage.token.here")
