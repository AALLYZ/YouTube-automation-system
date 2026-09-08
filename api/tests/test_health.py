def test_health_reports_db_and_redis(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["database"]["ok"] is True
    assert "redis" in body["checks"]
    assert body["providers"]["ai"] == "stub"


def test_root(client):
    assert client.get("/").json()["service"] == "youtube-automation"
