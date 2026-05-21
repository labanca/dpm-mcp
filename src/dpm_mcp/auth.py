"""PAT resolution for GitHub access.

Resolution order (first non-empty wins):
1. Explicit token string passed by the caller (treated as the literal token).
2. Environment variable name passed by the caller (DPM-style indirection).
3. ``GITHUB_TOKEN`` from the process environment.
4. ``None`` — unauthenticated; public repos only, 60 req/hour rate limit.

The MCP server is strictly read-only: tokens are used only for ``Authorization``
headers on GET requests to ``api.github.com``, ``github.com``, and
``raw.githubusercontent.com``. They are never logged or persisted.
"""

from __future__ import annotations

import os
import re

_LIKELY_TOKEN_RE = re.compile(r"^(gh[pousr]_|github_pat_)[A-Za-z0-9_]+$")
"""Matches GitHub PAT prefixes (classic and fine-grained)."""


def resolve_token(token: str | None = None) -> str | None:
    """Resolve a GitHub token using DPM-compatible indirection.

    Args:
        token: Either a literal PAT, the name of an env var that holds a PAT,
            or ``None`` to fall back to ``GITHUB_TOKEN``.

    Returns:
        The resolved token string, or ``None`` if no token is available.
    """
    if token:
        if _LIKELY_TOKEN_RE.match(token):
            return token
        env_value = os.getenv(token)
        if env_value:
            return env_value
        if token.isupper() and "_" in token:
            return None
        return token

    return os.getenv("GITHUB_TOKEN") or None


def github_headers(token: str | None) -> dict[str, str]:
    """Build standard headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dpm-mcp/0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def raw_headers(token: str | None) -> dict[str, str]:
    """Build headers for raw content downloads (api.github.com or raw.githubusercontent.com)."""
    headers = {"User-Agent": "dpm-mcp/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
