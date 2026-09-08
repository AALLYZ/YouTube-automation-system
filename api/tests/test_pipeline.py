import pytest

from app.core.errors import AppError, ErrorCode


@pytest.fixture()
def channel_with_topics(client, auth):
    cid = client.post(
        "/api/channels",
        json={"name": "Pipeline Co", "niche": "tiny history", "video_length_min": 1},
        headers=auth,
    ).json()["id"]
    client.post(f"/api/channels/{cid}/topics:generate", json={"count": 5}, headers=auth)
    return cid


def _steps(client, auth, job):
    jr = client.get(f"/api/jobs/{job}", headers=auth).json()
    return jr, {s["stage"]: s for s in jr["steps"]}


def test_full_pipeline_auto_mode_completes(client, auth, channel_with_topics):
    cid = channel_with_topics
    r = client.post(
        "/api/jobs", json={"channel_id": cid, "mode": "AUTO", "test_run": True}, headers=auth
    )
    assert r.status_code == 201, r.text
    job = r.json()["public_id"]

    jr, steps = _steps(client, auth, job)
    assert jr["status"] == "COMPLETED", jr
    assert jr["progress_pct"] == 100
    assert jr["current_stage"] == "COMPLETE"
    for stage in ("TOPIC", "RESEARCH", "SCRIPT", "SCRIPT_QA", "VOICE", "VISUALS", "SUBTITLES",
                  "TIMELINE", "RENDER", "THUMBNAIL", "METADATA", "FINAL_QA", "UPLOAD", "COMPLETE"):
        assert steps[stage]["status"] == "SUCCEEDED", (stage, steps.get(stage))

    v = client.get(f"/api/jobs/{job}/video", headers=auth)
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    up = client.get(f"/api/jobs/{job}/upload", headers=auth).json()
    assert up["youtube_video_id"].startswith("stub")

    events = {n["event"] for n in client.get(f"/api/notifications?channel_id={cid}", headers=auth).json()}
    assert {"job_started", "video_ready", "published"} <= events


def test_approval_gate_pauses_then_resumes(client, auth, channel_with_topics):
    cid = channel_with_topics
    job = client.post(
        "/api/jobs", json={"channel_id": cid, "mode": "APPROVAL_REQUIRED", "test_run": True}, headers=auth
    ).json()["public_id"]

    jr, steps = _steps(client, auth, job)
    assert jr["status"] == "WAITING_APPROVAL"
    assert jr["current_stage"] == "APPROVAL_GATE"
    assert "UPLOAD" not in steps
    assert steps["FINAL_QA"]["status"] == "SUCCEEDED"

    ap = client.post(f"/api/jobs/{job}:approve", headers=auth)
    assert ap.status_code == 200, ap.text
    jr, steps = _steps(client, auth, job)
    assert jr["status"] == "COMPLETED"
    assert steps["APPROVAL_GATE"]["status"] == "SUCCEEDED"
    assert steps["UPLOAD"]["status"] == "SUCCEEDED"


def test_reject_cancels_job(client, auth, channel_with_topics):
    job = client.post(
        "/api/jobs",
        json={"channel_id": channel_with_topics, "mode": "APPROVAL_REQUIRED", "test_run": True},
        headers=auth,
    ).json()["public_id"]
    r = client.post(f"/api/jobs/{job}:reject", json={"reason": "not good enough"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


def test_pipeline_resumes_after_scripts_draft(client, auth, channel_with_topics):
    cid = channel_with_topics
    client.put(f"/api/channels/{cid}/settings", json={"approval_mode": "AUTO"}, headers=auth)
    topics = client.get(f"/api/channels/{cid}/topics", headers=auth).json()
    draft = client.post(
        f"/api/channels/{cid}/scripts:draft",
        json={"topic_id": topics[0]["id"], "test_run": True},
        headers=auth,
    ).json()
    job = draft["job_public_id"]

    # job has RESEARCH/SCRIPT/SCRIPT_QA steps already; running the pipeline resumes from VOICE
    done = client.post(f"/api/jobs/{job}:run", json={}, headers=auth)
    assert done.status_code == 200, done.text
    jr, steps = _steps(client, auth, job)
    assert jr["status"] == "COMPLETED"
    research_steps = [s for s in jr["steps"] if s["stage"] == "RESEARCH"]
    assert len(research_steps) == 1  # not re-run
    assert steps["VOICE"]["status"] == "SUCCEEDED"


def test_pipeline_retries_retryable_stage(client, auth, channel_with_topics, monkeypatch):
    from app.workflows import pipeline

    real = pipeline.run_voice
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise AppError("transient TTS blip", code=ErrorCode.PROVIDER_UNAVAILABLE)
        return real(*a, **kw)

    monkeypatch.setattr(pipeline, "run_voice", flaky)

    job = client.post(
        "/api/jobs", json={"channel_id": channel_with_topics, "mode": "AUTO", "test_run": True}, headers=auth
    ).json()["public_id"]

    jr, _ = _steps(client, auth, job)
    assert jr["status"] == "COMPLETED"
    assert calls["n"] == 3
    voice_steps = sorted((s for s in jr["steps"] if s["stage"] == "VOICE"), key=lambda s: s["attempt"])
    assert [s["status"] for s in voice_steps] == ["FAILED", "FAILED", "SUCCEEDED"]


def test_pipeline_fails_then_retry_recovers(client, auth, channel_with_topics, monkeypatch):
    from app.workflows import pipeline

    real = pipeline.run_final_qa
    fail = {"on": True}

    def maybe_fail(*a, **kw):
        if fail["on"]:
            from app.core.errors import StageError

            raise StageError("injected QA failure", stage="FINAL_QA", code=ErrorCode.QA_FAILED)
        return real(*a, **kw)

    monkeypatch.setattr(pipeline, "run_final_qa", maybe_fail)

    job = client.post(
        "/api/jobs", json={"channel_id": channel_with_topics, "mode": "AUTO", "test_run": True}, headers=auth
    ).json()["public_id"]
    jr, steps = _steps(client, auth, job)
    assert jr["status"] == "FAILED"
    assert jr["error_code"] == "QA_FAILED"
    assert steps["FINAL_QA"]["status"] == "FAILED"
    # non-retryable -> exactly one attempt
    assert len([s for s in jr["steps"] if s["stage"] == "FINAL_QA"]) == 1
    events = {n["event"] for n in client.get(f"/api/notifications?job_id={jr['id']}", headers=auth).json()}
    assert "error" in events

    fail["on"] = False
    rr = client.post(f"/api/jobs/{job}:retry", json={}, headers=auth)
    assert rr.status_code == 200, rr.text
    jr, steps = _steps(client, auth, job)
    assert jr["status"] == "COMPLETED"
    assert steps["UPLOAD"]["status"] == "SUCCEEDED"
