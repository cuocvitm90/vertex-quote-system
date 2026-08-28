"""
Advanced Rate Limiting Middleware for Vertex Construction & PCCC
Protects against brute-force attacks on auth endpoints, API abuse, and DDoS flooding.
Uses an in-memory Sliding Window / Token Bucket algorithm with automatic TTL cleanup.
"""
import time
import asyncio
from typing import Dict, List, Tuple
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitRule:
    def __init__(self, path_prefix: str, max_requests: int, window_seconds: int = 60):
        self.path_prefix = path_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds


class InMemoryRateLimiter:
    """
    Sliding window rate limiter storing timestamp logs per IP and route prefix.
    """
    def __init__(self):
        # Key: (ip, path_prefix) -> List of timestamps
        self._requests: Dict[Tuple[str, str], List[float]] = {}
        self._last_cleanup: float = time.time()
        self._cleanup_interval: float = 300.0  # clean every 5 minutes

        # Default rules
        self.rules: List[RateLimitRule] = [
            # Strict limit on login & register to prevent brute-force
            RateLimitRule("/api/auth/login", max_requests=100, window_seconds=60),
            RateLimitRule("/api/auth/register", max_requests=100, window_seconds=60),
            # Upload limits to prevent storage flooding
            RateLimitRule("/api/quotes/upload", max_requests=60, window_seconds=60),
            # General API limit
            RateLimitRule("/api/", max_requests=300, window_seconds=60)
        ]

    def _get_client_ip(self, request: Request) -> str:
        # Check X-Forwarded-For (if behind Reverse Proxy / Nginx / Load Balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _match_rule(self, path: str) -> RateLimitRule:
        for rule in self.rules:
            if path.startswith(rule.path_prefix):
                return rule
        # Fallback general rule
        return RateLimitRule(path_prefix="*", max_requests=200, window_seconds=60)

    def is_allowed(self, request: Request) -> Tuple[bool, int, int, int]:
        """
        Checks if request is allowed.
        Returns: (allowed: bool, remaining: int, limit: int, retry_after: int)
        """
        path = request.url.path

        # Ignore static assets and docs from rate limiting
        if path.startswith("/static") or path in ["/favicon.ico", "/docs", "/redoc", "/openapi.json"]:
            return True, 999, 999, 0

        client_ip = self._get_client_ip(request)
        rule = self._match_rule(path)
        key = (client_ip, rule.path_prefix)
        now = time.time()

        # Periodic cleanup of expired entries
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now)

        timestamps = self._requests.get(key, [])
        # Filter out timestamps outside window
        window_start = now - rule.window_seconds
        valid_timestamps = [t for t in timestamps if t > window_start]

        if len(valid_timestamps) >= rule.max_requests:
            # Over limit
            oldest = valid_timestamps[0]
            retry_after = max(1, int(oldest + rule.window_seconds - now))
            self._requests[key] = valid_timestamps
            return False, 0, rule.max_requests, retry_after

        # Allowed: add current timestamp
        valid_timestamps.append(now)
        self._requests[key] = valid_timestamps
        remaining = rule.max_requests - len(valid_timestamps)
        return True, remaining, rule.max_requests, 0

    def _cleanup(self, now: float):
        self._last_cleanup = now
        keys_to_delete = []
        for key, timestamps in self._requests.items():
            # Keep only items in the last 10 minutes
            valid = [t for t in timestamps if t > now - 600]
            if not valid:
                keys_to_delete.append(key)
            else:
                self._requests[key] = valid
        for k in keys_to_delete:
            del self._requests[k]


rate_limiter = InMemoryRateLimiter()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / ASGI Middleware enforcing Rate Limits.
    """
    async def dispatch(self, request: Request, call_next):
        # Allow CORS preflight requests without rate limiting
        if request.method == "OPTIONS":
            return await call_next(request)

        allowed, remaining, limit, retry_after = rate_limiter.is_allowed(request)


        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "status": "error",
                    "code": 429,
                    "detail": "Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng thử lại sau.",
                    "retry_after_seconds": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0"
                }
            )

        response: Response = await call_next(request)
        if limit < 999:
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
