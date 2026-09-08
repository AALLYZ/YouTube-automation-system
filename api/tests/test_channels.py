def test_channel_crud_and_settings(client, auth):
    # create
    r = client.post("/api/channels", json={"name": "Space Facts", "niche": "astronomy"}, headers=auth)
    assert r.status_code == 201, r.text
    ch = r.json()
    assert ch["slug"] == "space-facts"
    assert ch["settings"]["approval_mode"] == "APPROVAL_REQUIRED"
    cid = ch["id"]

    # list
    r = client.get("/api/channels", headers=auth)
    assert any(c["id"] == cid for c in r.json())

    # patch
    r = client.patch(f"/api/channels/{cid}", json={"tone": "playful"}, headers=auth)
    assert r.json()["tone"] == "playful"

    # settings update
    r = client.put(
        f"/api/channels/{cid}/settings",
        json={"approval_mode": "AUTO", "daily_video_limit": 2, "topic_ai": {"temperature": 0.9}},
        headers=auth,
    )
    assert r.status_code == 200
    s = r.json()
    assert s["approval_mode"] == "AUTO"
    assert s["daily_video_limit"] == 2
    assert s["topic_ai"] == {"temperature": 0.9}

    # delete
    assert client.delete(f"/api/channels/{cid}", headers=auth).status_code == 204
    assert client.get(f"/api/channels/{cid}", headers=auth).status_code == 404


def test_duplicate_slug_rejected(client, auth):
    client.post("/api/channels", json={"name": "Dupe"}, headers=auth)
    r = client.post("/api/channels", json={"name": "Dupe"}, headers=auth)
    assert r.status_code == 400
