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
