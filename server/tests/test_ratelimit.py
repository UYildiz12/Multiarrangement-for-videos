"""
Rate limiting: the sliding-window limiter with a fake clock, and 429s end to end.
"""

import pytest

from app.ratelimit import (
    DEFAULT,
    KEY_GENERATION,
    STUDY_CREATION,
    UPLOADS,
    SlidingWindowLimiter,
    client_ip,
    rate_limiter,
    rule_for,
)


class FakeClock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_limiter_blocks_after_limit_and_resets_after_window():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    key = ("rule", "203.0.113.1")

    for _ in range(3):
        assert limiter.hit(key, limit=3, window=60) == 0
    assert limiter.hit(key, limit=3, window=60) == pytest.approx(60)

    clock.now += 30
    assert limiter.hit(key, limit=3, window=60) == pytest.approx(30)

    clock.now += 30.5
    assert limiter.hit(key, limit=3, window=60) == 0


def test_limiter_window_slides_with_each_request():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    key = ("rule", "203.0.113.1")

    assert limiter.hit(key, 2, 60) == 0  # t=1000
    clock.now += 40
    assert limiter.hit(key, 2, 60) == 0  # t=1040
    clock.now += 10
    assert limiter.hit(key, 2, 60) == pytest.approx(10)  # first hit expires at t=1060
    clock.now += 10.5
    assert limiter.hit(key, 2, 60) == 0


def test_limiter_tracks_clients_and_rules_separately():
    limiter = SlidingWindowLimiter(clock=FakeClock())
    assert limiter.hit(("a", "ip1"), 1, 60) == 0
    assert limiter.hit(("a", "ip1"), 1, 60) > 0
    assert limiter.hit(("a", "ip2"), 1, 60) == 0
    assert limiter.hit(("b", "ip1"), 1, 60) == 0


def test_limiter_memory_stays_bounded():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_keys=50, sweep_interval=60, clock=clock)
    for i in range(200):
        limiter.hit(("rule", f"10.0.{i // 250}.{i % 250}"), 5, 60)
    assert len(limiter) == 50  # least recently used clients are evicted

    clock.now += 120
    limiter.hit(("rule", "fresh-client"), 5, 60)  # triggers a sweep of expired windows
    assert len(limiter) == 1


def test_rule_selection():
    assert rule_for("POST", "/api/v1/experimenter/generate-key") is KEY_GENERATION
    assert rule_for("POST", "/api/v1/studies") is STUDY_CREATION
    assert rule_for("POST", "/api/v1/studies/") is STUDY_CREATION
    assert rule_for("POST", "/api/v1/public/demo/start") is STUDY_CREATION
    assert rule_for("POST", "/api/v1/studies/abc/stimuli") is UPLOADS
    assert rule_for("POST", "/api/v1/studies/abc/uploads") is UPLOADS
    assert rule_for("GET", "/api/v1/studies/abc/stimuli") is DEFAULT
    assert rule_for("POST", "/api/v1/sessions/abc/trials") is DEFAULT
    assert rule_for("GET", "/health") is DEFAULT


def _scope(*forwarded: bytes) -> dict:
    return {
        "headers": [(b"x-forwarded-for", value) for value in forwarded],
        "client": ("10.0.0.1", 1234),
    }


def test_client_ip_uses_entry_appended_by_trusted_proxy(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    # "1.2.3.4" was supplied by the client; Railway appended the real address.
    assert client_ip(_scope(b"1.2.3.4, 203.0.113.7")) == "203.0.113.7"
    assert client_ip(_scope(b"203.0.113.7")) == "203.0.113.7"
    assert client_ip(_scope(b"1.2.3.4", b"203.0.113.7")) == "203.0.113.7"  # repeated header lines
    assert client_ip(_scope(b" , ")) == "10.0.0.1"
    assert client_ip({"headers": [], "client": ("10.0.0.2", 80)}) == "10.0.0.2"
    assert client_ip({"headers": []}) == "unknown"


def test_client_ip_respects_trusted_proxy_hops(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    assert client_ip(_scope(b"1.2.3.4, 203.0.113.7, 10.0.0.5")) == "203.0.113.7"
    assert client_ip(_scope(b"203.0.113.7")) == "10.0.0.1"  # too few entries: use the peer

    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    assert client_ip(_scope(b"1.2.3.4, 203.0.113.7")) == "10.0.0.1"


def test_forged_forwarded_for_entries_do_not_reset_the_budget(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_KEYGEN_PER_HOUR", "1")
    url = "/api/v1/experimenter/generate-key"
    assert client.post(url, headers={"X-Forwarded-For": "1.1.1.1, 203.0.113.7"}).status_code == 200
    assert client.post(url, headers={"X-Forwarded-For": "2.2.2.2, 203.0.113.7"}).status_code == 429


def test_key_generation_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_KEYGEN_PER_HOUR", "2")
    for _ in range(2):
        assert client.post("/api/v1/experimenter/generate-key").status_code == 200

    blocked = client.post("/api/v1/experimenter/generate-key")
    assert blocked.status_code == 429
    assert 3500 <= int(blocked.headers["Retry-After"]) <= 3600
    assert "Too many requests" in blocked.json()["detail"]

    # A different client address (as appended by the proxy) has its own budget.
    other = client.post(
        "/api/v1/experimenter/generate-key",
        headers={"X-Forwarded-For": "198.51.100.9"},
    )
    assert other.status_code == 200


def test_rate_limit_resets_after_window(client, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(rate_limiter, "clock", clock)
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "3")

    for _ in range(3):
        assert client.get("/health").status_code == 200
    blocked = client.get("/health")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"

    clock.now += 61
    assert client.get("/health").status_code == 200


def test_study_creation_has_its_own_budget(client, monkeypatch, sample_study_data):
    monkeypatch.setenv("RATE_LIMIT_STUDIES_PER_HOUR", "1")
    assert client.post("/api/v1/studies", json=sample_study_data).status_code == 201
    assert client.post("/api/v1/studies", json=sample_study_data).status_code == 429
    assert client.get("/api/v1/studies").status_code == 200


def test_zero_disables_a_rule(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_KEYGEN_PER_HOUR", "0")
    for _ in range(8):
        assert client.post("/api/v1/experimenter/generate-key").status_code == 200


def test_429_keeps_cors_and_security_headers(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "1")
    origin = "http://localhost:3000"
    client.get("/health", headers={"Origin": origin})
    blocked = client.get("/health", headers={"Origin": origin})
    assert blocked.status_code == 429
    assert blocked.headers["access-control-allow-origin"] == origin
    assert blocked.headers["x-content-type-options"] == "nosniff"
