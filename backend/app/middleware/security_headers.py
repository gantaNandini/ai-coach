"""
security_headers.py — HTTP security headers middleware.

Adds standard defence-in-depth HTTP headers to every response:
  - X-Content-Type-Options: prevents MIME-type sniffing
  - X-Frame-Options: prevents clickjacking
  - X-XSS-Protection: legacy XSS filter for older browsers
  - Strict-Transport-Security: forces HTTPS (prod only)
  - Content-Security-Policy: restricts resource origins
  - Referrer-Policy: controls referrer leakage
  - Permissions-Policy: disables unused browser features
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # HSTS — only set in production to avoid breaking local dev over HTTP
        if not getattr(settings, "DEBUG", True):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content-Security-Policy — permits the React SPA and API calls on the
        # same origin, Stripe.js from its CDN, and nothing else by default.
        # NOTE: /docs (Swagger UI) uses inline scripts — we skip CSP on the docs paths
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            return response

        csp_parts = [
            "default-src 'self'",
            # Scripts: self + Stripe (billing) + inline eval needed by Vite dev
            "script-src 'self' 'unsafe-inline' https://js.stripe.com",
            # Styles: self + inline (Tailwind)
            "style-src 'self' 'unsafe-inline'",
            # Images: self + data URIs (base64 inline images)
            "img-src 'self' data: https:",
            # Fonts: self
            "font-src 'self'",
            # API / XHR / fetch: self + Stripe + Ollama (localhost dev)
            "connect-src 'self' https://api.stripe.com",
            # iframes: Stripe Checkout embeds
            "frame-src https://js.stripe.com https://hooks.stripe.com",
            # Workers: none
            "worker-src 'none'",
            # Object / embed: none
            "object-src 'none'",
            # Base URI restricted to self
            "base-uri 'self'",
            # Form action restricted to self
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        return response
