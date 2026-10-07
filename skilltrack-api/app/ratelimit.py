"""Small in-process sliding-window rate limiter.

Counts are kept per server process. With N instances behind a load balancer the effective limit is up to
N times higher, which is fine for slowing down guessing; use a shared store such as Redis if it must be exact.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, message: str):
        self.limit = limit
        self.window = window_seconds
        self.message = message
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
            return deque()
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            self._hits[key].append(now)

    def check(self, key: str) -> None:
        """Count this call and refuse it when the key has used up its allowance."""
        with self._lock:
            now = time.monotonic()
            hits = self._prune(key, now)
            if len(hits) >= self.limit:
                retry = max(1, int(self.window - (now - hits[0])))
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, self.message, headers={"Retry-After": str(retry)})
            self._hits[key].append(now)

    def raise_if_blocked(self, key: str) -> None:
        if self.blocked(key):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, self.message, headers={"Retry-After": str(self.window)})


# Wrong passwords per email address (counted on failure only, so normal sign-ins are never limited)
login_failures = RateLimiter(10, 60, "Too many failed sign-in attempts. Wait a minute and try again.")
# Exam-key attempts per student (keys are short, so guessing has to be slowed down)
exam_start = RateLimiter(8, 60, "Too many attempts to start the exam. Wait a minute and try again.")
# Public verification requests per IP
verify_rate = RateLimiter(20, 60, "Too many verification requests. Wait a minute and try again.")
