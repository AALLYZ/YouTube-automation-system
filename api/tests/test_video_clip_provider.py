"""Unit tests for the real Replicate text-to-video provider (HTTP calls mocked)."""
import httpx
import pytest

from app.core.errors import AppError
from app.providers.video_clip import replicate as replicate_mod


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code
        self.text = str(self._json)

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://test")
            raise httpx.HTTPStatusError(
                "boom", request=req, response=httpx.Response(self.status_code, request=req)
            )

    def json(self):
        return self._json


class _FakeStream:
    def __init__(self, content: bytes):
        self._content = content

    def raise_for_status(self):
        pass

    def iter_bytes(self):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def configured(monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "replicate_api_token", "tok_test")
    monkeypatch.setattr(app_settings, "replicate_video_model", "owner/model")
    monkeypatch.setattr(replicate_mod.time, "sleep", lambda s: None)
    return app_settings


def test_replicate_video_clip_generate_success(tmp_path, configured, monkeypatch):
    calls = {"post": 0, "get": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] += 1
        assert url == f"{replicate_mod._BASE}/models/owner/model/predictions"
        assert json == {"input": {"prompt": "a cat surfing"}}
        return _FakeResponse({"id": "p1", "urls": {"get": "http://poll/p1"}, "status": "starting"})

    poll_responses = [
        {"id": "p1", "status": "processing"},
        {"id": "p1", "status": "succeeded", "output": "http://cdn/out.mp4", "metrics": {"predict_time": 7.5}},
    ]

    def fake_get(url, headers=None, timeout=None):
        calls["get"] += 1
        assert url == "http://poll/p1"
        return _FakeResponse(poll_responses.pop(0))

    def fake_stream(method, url, timeout=None):
        assert method == "GET"
        assert url == "http://cdn/out.mp4"
        return _FakeStream(b"FAKEVIDEOBYTES")

    monkeypatch.setattr(replicate_mod.httpx, "post", fake_post)
    monkeypatch.setattr(replicate_mod.httpx, "get", fake_get)
    monkeypatch.setattr(replicate_mod.httpx, "stream", fake_stream)

    provider = replicate_mod.ReplicateVideoClip()
    out_path = str(tmp_path / "clip.mp4")
    res = provider.generate(prompt="a cat surfing", out_path=out_path, duration_sec=4.0)

    assert open(out_path, "rb").read() == b"FAKEVIDEOBYTES"
    assert res.path == out_path
    assert res.license == "replicate-generated"
    assert res.usage.provider == "replicate"
    assert res.usage.model == "owner/model"
    assert res.usage.seconds == 7.5
    assert res.usage.est_cost_usd > 0
    assert calls["post"] == 1
    assert calls["get"] == 2


def test_replicate_video_clip_requires_token(monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "replicate_api_token", None)
    with pytest.raises(AppError):
        replicate_mod.ReplicateVideoClip()


def test_replicate_video_clip_failed_status_raises(tmp_path, configured, monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({"id": "p1", "urls": {"get": "http://poll/p1"}, "status": "starting"})

    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse({"id": "p1", "status": "failed", "error": "model exploded"})

    monkeypatch.setattr(replicate_mod.httpx, "post", fake_post)
    monkeypatch.setattr(replicate_mod.httpx, "get", fake_get)

    provider = replicate_mod.ReplicateVideoClip()
    with pytest.raises(AppError, match="failed"):
        provider.generate(prompt="x", out_path=str(tmp_path / "clip.mp4"))


def test_replicate_video_clip_rate_limit_maps_to_rate_limit_error(tmp_path, configured, monkeypatch):
    from app.core.errors import ErrorCode

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({"detail": "too many requests"}, status_code=429)

    monkeypatch.setattr(replicate_mod.httpx, "post", fake_post)

    provider = replicate_mod.ReplicateVideoClip()
    with pytest.raises(AppError) as exc_info:
        provider.generate(prompt="x", out_path=str(tmp_path / "clip.mp4"))
    assert exc_info.value.code == ErrorCode.PROVIDER_RATE_LIMIT
