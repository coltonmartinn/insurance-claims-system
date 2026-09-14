"""Health check endpoint used by the hosting platform to know the process
is alive and can actually talk to its database."""


def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
