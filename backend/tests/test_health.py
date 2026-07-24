"""Tests for health check endpoints."""


class TestHealth:
    def test_basic_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_detailed_health(self, client):
        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "database" in data["checks"]
        assert "latency_ms" in data["checks"]
