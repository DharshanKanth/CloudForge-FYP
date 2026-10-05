"""Minimal in-process sliding-window rate limiter.

Intentionally dependency-free: it protects the auth endpoints from brute-force
loops on a single uvicorn worker. It is not a distributed limiter — horizontal
deployments should put a real limiter in front (nginx/ingress) instead.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_buckets: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(
    request: Request,
    scope: str,
    max_events: int = 10,
    window_seconds: float = 60.0,
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = f"{scope}:{client_ip}"
    now = time.monotonic()

    bucket = _buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()

    if len(bucket) >= max_events:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again shortly.",
        )
    bucket.append(now)
