"""Bearer-token authentication middleware for the HTTP transports.

Activated only when ``DPM_MCP_AUTH_TOKEN`` is set. When unset, the HTTP
endpoint is open (use only for local development).
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = {"/health", "/healthz", "/readyz"}


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Reject requests lacking a valid ``Authorization: Bearer <token>`` header."""

    def __init__(self, app, token: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._token = token

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(value, self._token):
            return JSONResponse(
                {"error": "unauthorized", "detail": "missing or invalid bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="dpm-mcp"'},
            )
        return await call_next(request)
