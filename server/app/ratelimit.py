"""
In-memory, per-client rate limiting.

The API runs as a single Railway instance, so a process-local sliding window
is enough: for each (rule, client IP) pair the limiter keeps the timestamps of
recent requests and rejects a request with 429 once the window is full.
Limits come from environment variables (see ``RULES``); 0 disables a rule.
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.limits import env_int


@dataclass(frozen=True)
class RateRule:
    name: str
    env_var: str
    default: int
    window_seconds: float

    def limit(self) -> int:
        return env_int(self.env_var, self.default)


KEY_GENERATION = RateRule("key_generation", "RATE_LIMIT_KEYGEN_PER_HOUR", 5, 3600)
STUDY_CREATION = RateRule("study_creation", "RATE_LIMIT_STUDIES_PER_HOUR", 30, 3600)
UPLOADS = RateRule("uploads", "RATE_LIMIT_UPLOADS_PER_HOUR", 300, 3600)
DEFAULT = RateRule("default", "RATE_LIMIT_DEFAULT_PER_MINUTE", 600, 60)
RULES = (KEY_GENERATION, STUDY_CREATION, UPLOADS, DEFAULT)

_UPLOAD_PATH = re.compile(r"^/api/v1/studies/[^/]+/(stimuli|uploads)$")


def rule_for(method: str, path: str) -> RateRule:
    """Pick the rate-limit rule for a request; each request counts once."""
    path = path.rstrip("/") or "/"
    if method == "POST":
        if path == "/api/v1/experimenter/generate-key":
            return KEY_GENERATION
        # The public demo also inserts a study (plus stimuli and a session).
        if path in ("/api/v1/studies", "/api/v1/public/demo/start"):
            return STUDY_CREATION
        if _UPLOAD_PATH.match(path):
            return UPLOADS
    return DEFAULT


def client_ip(scope: Scope) -> str:
    """Client address as seen by the trusted proxy in front of the API.

    Each proxy appends the address it received the request from to
    X-Forwarded-For, so with TRUSTED_PROXY_HOPS=N (default 1, Railway's edge
    proxy) the client is the N-th entry from the right; entries further left
    are client-supplied and can be forged. 0 ignores the header. Falls back to
    the TCP peer address when the header is missing or has fewer entries.
    """
    hops = env_int("TRUSTED_PROXY_HOPS", 1)
    if hops:
        values = [value.decode("latin-1") for name, value in scope.get("headers", []) if name == b"x-forwarded-for"]
        entries = [entry.strip() for entry in ",".join(values).split(",") if entry.strip()]
        if len(entries) >= hops:
            return entries[-hops]
    client = scope.get("client")
    return client[0] if client else "unknown"


class SlidingWindowLimiter:
    """Sliding-window request log keyed by (rule name, client).

    Memory stays bounded: each key holds at most ``limit`` timestamps, keys
    whose window has fully expired are swept periodically, and the least
    recently used keys are evicted beyond ``max_keys``.
    """

    def __init__(
        self,
        max_keys: int = 10_000,
        sweep_interval: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.clock = clock
        self._max_keys = max_keys
        self._sweep_interval = sweep_interval
        self._last_sweep = 0.0
        self._entries: OrderedDict[tuple[str, str], tuple[float, deque[float]]] = OrderedDict()
        self._lock = threading.Lock()

    def hit(self, key: tuple[str, str], limit: int, window: float) -> float:
        """Record one request for *key*.

        Returns 0 when the request is allowed, otherwise the number of seconds
        until the oldest request in the window expires.
        """
        with self._lock:
            now = self.clock()
            self._sweep(now)
            entry = self._entries.get(key)
            if entry is None:
                hits: deque[float] = deque()
                self._entries[key] = (window, hits)
            else:
                hits = entry[1]
                self._entries.move_to_end(key)

            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return max(hits[0] + window - now, 0.001)

            hits.append(now)
            while len(self._entries) > self._max_keys:
                self._entries.popitem(last=False)
            return 0.0

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < self._sweep_interval:
            return
        self._last_sweep = now
        expired = [
            key
            for key, (window, hits) in self._entries.items()
            if not hits or hits[-1] <= now - window
        ]
        for key in expired:
            del self._entries[key]

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


rate_limiter = SlidingWindowLimiter()


class RateLimitMiddleware:
    """ASGI middleware that answers 429 (with Retry-After) once a rule is exhausted."""

    def __init__(self, app: ASGIApp, limiter: SlidingWindowLimiter | None = None) -> None:
        self.app = app
        self.limiter = limiter if limiter is not None else rate_limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            rule = rule_for(scope["method"], scope["path"])
            limit = rule.limit()
            if limit > 0:
                retry_after = self.limiter.hit((rule.name, client_ip(scope)), limit, rule.window_seconds)
                if retry_after:
                    seconds = max(1, math.ceil(retry_after))
                    response = JSONResponse(
                        {"detail": f"Too many requests. Try again in {seconds} seconds."},
                        status_code=429,
                        headers={"Retry-After": str(seconds)},
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)
