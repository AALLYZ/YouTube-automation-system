def test_health_deep_requires_auth(client):
    assert client.get("/api/health/deep").status_code == 401


def test_health_deep_all_stub_providers_ok(client, auth):
    r = client.get("/api/health/deep", headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ok"
    assert d["checks"]["database"]["ok"] is True
    assert d["checks"]["ffmpeg"]["ok"] is True

    prov = d["providers"]
    for name in ("storage", "ai", "research", "voice", "image", "stock", "youtube", "notifier"):
        assert prov[name]["ok"] is True, (name, prov[name])
    assert prov["ai"]["provider"] == "stub"
    assert "round-trip" in prov["storage"]["detail"]


def test_health_deep_reports_broken_provider(client, auth, monkeypatch):
    from app.providers import health as ph

    monkeypatch.setattr(ph.settings, "ai_provider", "anthropic")
    ph.registry.get_ai.cache_clear()

    d = client.get("/api/health/deep", headers=auth).json()
    assert d["providers"]["ai"]["ok"] is False
    assert d["status"] == "degraded"
    ph.registry.get_ai.cache_clear()
