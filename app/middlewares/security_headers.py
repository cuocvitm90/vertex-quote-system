"""
Security Headers Middleware for Vertex Construction & PCCC
Enforces OWASP recommended HTTP response security headers.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Appends security hardening headers to all HTTP responses.
    """
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 1. Prevent MIME-sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Prevent Clickjacking
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # 3. Cross-Site Scripting (XSS) Filter Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 4. Control Referrer Information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 5. Disable sensitive browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 6. Hide server implementation details
        response.headers["Server"] = "Vertex-Secure-Engine"

        # 7. HTTPS Strict Transport Security (HSTS) if connection is secure
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
