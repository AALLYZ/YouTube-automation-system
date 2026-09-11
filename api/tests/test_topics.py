import pytest


@pytest.fixture()
def channel_id(client, auth):
    r = client.post(
        "/api/channels",
        json={"name": "Deep Space", "niche": "astrophysics", "audience": "space nerds"},
        headers=auth,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_generate_scores_and_dedupes(client, auth, channel_id):
    r = client.post(f"/api/channels/{channel_id}/topics:generate", json={"count": 8}, headers=auth)
    assert r.status_code == 200, r.text
    topics = r.json()
    assert len(topics) >= 3
    # sorted by score desc
    scores = [t["total_score"] for t in topics]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= t["total_score"] <= 100 for t in topics)

    # a second run never produces a topic whose normalized-title fingerprint
    # collides with one already stored for the channel
    from app.services.topics import fingerprint

    client.post(f"/api/channels/{channel_id}/topics:generate", json={"count": 8}, headers=auth)
    all_topics = client.get(f"/api/channels/{channel_id}/topics", headers=auth).json()
    fps = [fingerprint(t["title"]) for t in all_topics]
    assert len(fps) == len(set(fps))


def test_approve_and_reject(client, auth, channel_id):
    topics = client.post(
        f"/api/channels/{channel_id}/topics:generate", json={"count": 5}, headers=auth
    ).json()
    a, b = topics[0]["id"], topics[1]["id"]

    assert client.post(f"/api/topics/{a}:approve", headers=auth).json()["status"] == "APPROVED"
    rej = client.post(f"/api/topics/{b}:reject", json={"reason": "off-brand"}, headers=auth).json()
    assert rej["status"] == "REJECTED"
    assert rej["rejected_reason"] == "off-brand"

    approved = client.get(
        f"/api/channels/{channel_id}/topics?status=APPROVED", headers=auth
    ).json()
    assert [t["id"] for t in approved] == [a]


def test_trending_topics_are_original_and_tagged(client, auth, channel_id):
    r = client.post(
        f"/api/channels/{channel_id}/topics:from_trending",
        json={"region_code": "US", "max_results": 5, "count": 4},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    topics = r.json()
    assert len(topics) >= 1

    from app.providers.youtube.stub import _TRENDING_SEED

    trending_titles = {t for t, *_ in _TRENDING_SEED}
    for t in topics:
        assert t["source"] == "youtube_trending"
        assert t["source_ref"] and t["source_ref"]["trending_videos"]
        # the rewritten topic must not just be one of the trending titles verbatim
        assert t["title"] not in trending_titles

    # they show up alongside regular AI topics and can be approved like any other
    assert client.post(f"/api/topics/{topics[0]['id']}:approve", headers=auth).json()["status"] == "APPROVED"


def test_trending_topics_empty_returns_error(client, auth, channel_id, monkeypatch):
    from app.providers.youtube import stub as stub_mod

    monkeypatch.setattr(stub_mod, "_TRENDING_SEED", [])
    r = client.post(
        f"/api/channels/{channel_id}/topics:from_trending",
        json={"region_code": "US"},
        headers=auth,
    )
    assert r.status_code == 400


def test_link_topics_are_original_and_tagged(client, auth, channel_id, monkeypatch):
    import app.api.routes.topics as topics_routes

    fake_page = {
        "title": "10 Weird Facts About Black Holes You Never Knew",
        "text": "Black holes are regions of spacetime where gravity is so strong that nothing, "
        "not even light, can escape. This article covers formation, event horizons, and "
        "Hawking radiation in detail with several long quotes from physicists.",
        "domain": "example.com",
        "url": "https://example.com/black-holes-article",
    }
    monkeypatch.setattr(topics_routes, "extract_page", lambda url: fake_page)

    r = client.post(
        f"/api/channels/{channel_id}/topics:from_link",
        json={"url": "https://example.com/black-holes-article", "count": 4},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    topics = r.json()
    assert len(topics) >= 1
    for t in topics:
        assert t["source"] == "web_link"
        assert t["source_ref"] == {
            "url": fake_page["url"],
            "title": fake_page["title"],
            "domain": fake_page["domain"],
        }
        # the rewritten topic must not just be the source page's own title verbatim
        assert t["title"] != fake_page["title"]

    assert client.post(f"/api/topics/{topics[0]['id']}:approve", headers=auth).json()["status"] == "APPROVED"


def test_link_topics_rejects_bad_url(client, auth, channel_id):
    r = client.post(
        f"/api/channels/{channel_id}/topics:from_link",
        json={"url": "ftp://example.com/file"},
        headers=auth,
    )
    assert r.status_code == 400


def test_link_topics_blocks_private_addresses(client, auth, channel_id):
    r = client.post(
        f"/api/channels/{channel_id}/topics:from_link",
        json={"url": "http://127.0.0.1:8090/secret"},
        headers=auth,
    )
    assert r.status_code == 400
    assert "public address" in r.json()["message"]
