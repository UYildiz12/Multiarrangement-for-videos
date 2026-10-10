"""
Small ASGI middlewares: request-size limit and security headers.
"""

from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.limits import format_bytes, max_request_bytes

SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
)


class SecurityHeadersMiddleware:
    """Add conservative security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend(header for header in SECURITY_HEADERS if header[0] not in present)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class RequestSizeLimitMiddleware:
    """Reject request bodies larger than MAX_REQUEST_BYTES with 413.

    Media files never travel through the API: browsers upload them straight
    to Supabase Storage with signed URLs, so API bodies are JSON documents
    (the largest are trial submissions with movement traces).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limit = max_request_bytes() if scope["type"] == "http" else 0
        if not limit:
            await self.app(scope, receive, send)
            return

        detail = f"Request body too large (limit {format_bytes(limit)})."
        declared = _content_length(scope)
        if declared is not None and declared > limit:
            await JSONResponse({"detail": detail}, status_code=413)(scope, receive, send)
            return

        # Bodies sent without Content-Length (chunked) are counted as they arrive.
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail=detail)
            return message

        await self.app(scope, limited_receive, send)
