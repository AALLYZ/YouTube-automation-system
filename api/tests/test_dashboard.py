def test_overview_requires_auth(client):
    assert client.get("/api/overview").status_code == 401


def test_overview_shape(client, auth):
    r = client.get("/api/overview", headers=auth)
    assert r.status_code == 200
    d = r.json()
    for key in ("channels", "jobs", "recent_jobs", "cost", "youtube", "videos", "notifications", "providers"):
        assert key in d
    assert d["providers"]["ai"] == "stub"
    assert d["youtube"]["quota_daily_limit"] > 0


def test_logs_and_usage_after_pipeline(client, auth):
    cid = client.post(
        "/api/channels",
        json={"name": "Dash Co", "niche": "tiny history", "video_length_min": 1},
        headers=auth,
    ).json()["id"]
    client.post(f"/api/channels/{cid}/topics:generate", json={"count": 4}, headers=auth)
    job = client.post(
        "/api/jobs", json={"channel_id": cid, "mode": "AUTO", "test_run": True}, headers=auth
    ).json()

    jr = client.get(f"/api/jobs/{job['public_id']}", headers=auth).json()
    assert jr["status"] == "COMPLETED"

    logs = client.get(f"/api/logs?job_id={jr['id']}", headers=auth).json()
    events = {l["event"] for l in logs}
    assert "job.completed" in events
    assert any(e.startswith("stage.") for e in events)

    usage = client.get(f"/api/usage?job_id={jr['id']}", headers=auth).json()
    assert len(usage) >= 1
    assert any(u["provider"] == "youtube" for u in usage)

    ov = client.get("/api/overview", headers=auth).json()
    assert ov["jobs"]["by_status"].get("COMPLETED", 0) >= 1
    assert ov["videos"]["ready"] >= 1
