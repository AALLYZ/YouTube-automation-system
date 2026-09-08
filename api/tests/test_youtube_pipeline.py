import pytest


@pytest.fixture()
def rendered(client, auth):
    """A job with a finished media pipeline (video rendered), ready to publish."""
    cid = client.post(
        "/api/channels",
        json={"name": "Quota Docs", "niche": "space history", "video_length_min": 1},
        headers=auth,
    ).json()["id"]
    topics = client.post(
        f"/api/channels/{cid}/topics:generate", json={"count": 5}, headers=auth
    ).json()
    job = client.post(
        f"/api/channels/{cid}/scripts:draft",
        json={"topic_id": topics[0]["id"], "test_run": True},
        headers=auth,
    ).json()["job_public_id"]
    r = client.post(f"/api/jobs/{job}/media:run", headers=auth)
    assert r.status_code == 200, r.text
    return cid, job


def test_publish_pipeline_thumbnail_metadata_upload(client, auth, rendered):
    _cid, job = rendered
    r = client.post(f"/api/jobs/{job}/publish:run", headers=auth)
    assert r.status_code == 200, r.text
    res = r.json()["results"]

    assert res["thumbnail"]["concepts"] >= 1
    assert res["thumbnail"]["selected_key"]
    assert res["metadata"]["title"]
    assert res["metadata"]["title_options"] >= 1
    assert res["metadata"]["tags"] >= 1

    up = res["upload"]
    assert up["youtube_video_id"].startswith("stub")
    assert up["youtube_url"].startswith("https://youtu.be/")
    assert up["status"] in ("uploaded", "published", "scheduled")
    assert up["test_mode"] is True
    assert up["quota_units_used"] >= 1600
    assert up["quota_used_today"] >= 1600

    # job step states
    jr = client.get(f"/api/jobs/{job}", headers=auth).json()
    stages = {s["stage"]: s["status"] for s in jr["steps"]}
    assert stages["THUMBNAIL"] == "SUCCEEDED"
    assert stages["METADATA"] == "SUCCEEDED"
    assert stages["UPLOAD"] == "SUCCEEDED"
    assert jr["current_stage"] == "UPLOAD"

    # upload record is retrievable
    got = client.get(f"/api/jobs/{job}/upload", headers=auth)
    assert got.status_code == 200
    body = got.json()
    assert body["title"] == res["metadata"]["title"]
    assert body["youtube_video_id"] == up["youtube_video_id"]
    assert body["privacy_status"] == "private"


def test_upload_stage_requires_metadata_first(client, auth, rendered):
    _cid, job = rendered
    bad = client.post(f"/api/jobs/{job}/stages/upload:run", headers=auth)
    assert bad.status_code == 400
    assert bad.json()["error_code"] == "VALIDATION"

    unknown = client.post(f"/api/jobs/{job}/stages/bogus:run", headers=auth)
    assert unknown.status_code == 400


def test_youtube_status_not_connected(client, auth):
    cid = client.post(
        "/api/channels", json={"name": "Disconnected", "niche": "x"}, headers=auth
    ).json()["id"]
    r = client.get(f"/api/youtube/status?channel_id={cid}", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is False
    assert data["configured"] is False
    assert data["quota_daily_limit"] > 0


def test_oauth_start_needs_google_config(client, auth):
    cid = client.post(
        "/api/channels", json={"name": "NoOAuth", "niche": "x"}, headers=auth
    ).json()["id"]
    r = client.get(f"/api/youtube/oauth/start?channel_id={cid}", headers=auth)
    assert r.status_code == 400
    assert r.json()["error_code"] == "CONFIG_ERROR"


def test_oauth_callback_rejects_bad_state(client, auth):
    r = client.get("/api/youtube/oauth/callback?state=not-a-real-token&code=abc")
    assert r.status_code in (400, 401)
    assert "error" in r.text.lower()


def test_oauth_state_roundtrip():
    from app.core.errors import AppError
    from app.services.youtube_oauth import sign_state, verify_state

    state = sign_state(42)
    assert verify_state(state) == 42
    with pytest.raises(AppError):
        verify_state(state + "tamper")


def test_quota_guard_blocks_when_exceeded(db, monkeypatch):
    from app.core.errors import AppError
    from app.models.ops import ApiUsage
    from app.services import upload as upload_svc

    monkeypatch.setattr(upload_svc.settings, "yt_daily_quota_units", 1000)
    db.add(ApiUsage(provider="youtube", operation="videos.insert", units=900))
    db.flush()

    upload_svc.check_quota(db, 50)  # 900 + 50 <= 1000 ok
    with pytest.raises(AppError) as ei:
        upload_svc.check_quota(db, 200)  # 900 + 200 > 1000
    assert ei.value.code == "QUOTA_EXCEEDED"
