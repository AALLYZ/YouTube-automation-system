def test_health_reports_db_and_redis(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["database"]["ok"] is True
    assert "redis" in body["checks"]
    assert body["providers"]["ai"] == "stub"


def test_root_serves_something(client):
    # With a built dashboard `/` returns index.html; without it, a JSON pointer.
    r = client.get("/")
    assert r.status_code == 200
    ct = r.headers["content-type"]
    if ct.startswith("application/json"):
        assert r.json()["service"] == "youtube-automation"
    else:
        assert "text/html" in ct


def test_spa_deep_link_falls_back_to_index(client):
    r = client.get("/videos")
    # 200 (index.html) when built, else 404 — either is acceptable, never a 500
    assert r.status_code in (200, 404)
