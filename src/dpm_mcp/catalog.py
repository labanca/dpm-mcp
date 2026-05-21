"""Datapackage catalog: discover, parse, cache, and search frictionless descriptors
across multiple GitHub orgs/users.

Design goals:
    * **Lazy.** Catalog is built on first request and cached in memory with a TTL.
      Restart the process to wipe.
    * **No external infra.** Pure in-process state; no SQLite/Redis/etc.
    * **Cheap to query.** After build, all filtering happens in memory.
    * **Read-only.** Same guarantees as the rest of dpm-mcp — only GETs go out.

Catalog entries surface only the fields that help an agent decide whether a
package is relevant (name, title, description, resources, schema field names
and descriptions). Resource data is not part of the catalog — call
``download_datapackage`` once a relevant package is identified.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field

from .auth import raw_headers, resolve_token
from .github import GitHubError, find_datapackage_repos
from .models import RepoDatapackage

logger = logging.getLogger(__name__)

DEFAULT_TTL = int(os.getenv("DPM_MCP_CATALOG_TTL_SECONDS", "3600"))
"""How long a built catalog is considered fresh, in seconds."""

DEFAULT_DESCRIPTOR_MAX_BYTES = 5 * 1024 * 1024
"""Hard cap on descriptor size when fetching, to avoid hostile/very-large files."""

DEFAULT_FETCH_CONCURRENCY = 8


# ----- models -----


class FieldEntry(BaseModel):
    name: str
    type: str | None = None
    title: str | None = None
    description: str | None = None


class ResourceEntry(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    format: str | None = None
    fields: list[FieldEntry] = Field(default_factory=list)


class CatalogEntry(BaseModel):
    """Single datapackage entry in the catalog."""

    name: str
    """The package's own ``name`` from its descriptor, or repo name as fallback."""

    full_name: str
    """``owner/repo``."""

    owner: str
    repo: str
    title: str | None = None
    description: str | None = None
    html_url: str
    datapackage_url: str
    """Raw URL of the descriptor on the default branch."""

    datapackage_path: str
    """Filename of the descriptor: ``datapackage.json`` / ``.yaml`` / ``.yml``."""

    default_branch: str
    private: bool = False
    archived: bool = False
    fork: bool = False
    resources: list[ResourceEntry] = Field(default_factory=list)
    error: str | None = None
    """Set when the descriptor failed to fetch/parse — entry still listed so the agent sees it."""


class CatalogSummary(BaseModel):
    """High-level view of the catalog suitable for a single agent turn."""

    total: int
    """Total datapackages indexed."""

    with_error: int
    """Count of entries where the descriptor failed to load."""

    by_owner: dict[str, int]
    sources: list[str]
    refreshed_at: float
    """Unix timestamp of the last successful build."""

    age_seconds: float
    """Seconds since last build."""

    ttl_seconds: int
    resource_count: int
    common_resource_names: list[str]
    """Resource names that appear in many packages (good for cross-package joins)."""


# ----- source parsing -----


def parse_sources(sources: list[str]) -> list[tuple[str, str]]:
    """Parse source strings.

    Accepted forms:
        ``org:NAME``      → organisation
        ``user:NAME``     → user account
        ``NAME``          → defaults to org

    >>> parse_sources(["org:splor-mg", "user:foo", "bar"])
    [('org', 'splor-mg'), ('user', 'foo'), ('org', 'bar')]
    """
    parsed: list[tuple[str, str]] = []
    for raw in sources:
        s = raw.strip()
        if not s:
            continue
        if ":" in s:
            kind, _, name = s.partition(":")
            kind = kind.strip().lower()
            name = name.strip()
            if kind not in {"org", "user"}:
                raise ValueError(
                    f"Invalid source kind {kind!r} in {raw!r}; use 'org:NAME' or 'user:NAME'."
                )
            if not name:
                raise ValueError(f"Empty source name in {raw!r}.")
            parsed.append((kind, name))
        else:
            parsed.append(("org", s))
    return parsed


# ----- descriptor fetching / parsing -----


def _parse_descriptor(content: bytes, filename: str) -> dict[str, Any]:
    if filename.endswith(".json"):
        return json.loads(content)
    return yaml.safe_load(content)


def _resource_entry_from_raw(raw: dict[str, Any]) -> ResourceEntry:
    name = raw.get("name") or ""
    schema = raw.get("schema") if isinstance(raw.get("schema"), dict) else None
    fields: list[FieldEntry] = []
    if schema and isinstance(schema.get("fields"), list):
        for f in schema["fields"]:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            fields.append(
                FieldEntry(
                    name=f["name"],
                    type=f.get("type"),
                    title=f.get("title"),
                    description=f.get("description"),
                )
            )
    fmt = raw.get("format")
    if not fmt and isinstance(raw.get("path"), str):
        m = re.search(r"\.([A-Za-z0-9]+)$", raw["path"])
        if m:
            fmt = m.group(1).lower()
    return ResourceEntry(
        name=name,
        title=raw.get("title"),
        description=raw.get("description"),
        format=fmt,
        fields=fields,
    )


async def _fetch_descriptor(
    client: httpx.AsyncClient,
    url: str,
    max_bytes: int = DEFAULT_DESCRIPTOR_MAX_BYTES,
) -> bytes:
    response = await client.get(url)
    response.raise_for_status()
    content = response.content
    if len(content) > max_bytes:
        raise ValueError(f"Descriptor exceeds {max_bytes} bytes")
    return content


async def _build_entry(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    repo: RepoDatapackage,
) -> CatalogEntry:
    base = CatalogEntry(
        name=repo.repo,
        full_name=repo.full_name,
        owner=repo.owner,
        repo=repo.repo,
        html_url=repo.html_url,
        datapackage_url=repo.datapackage_url,
        datapackage_path=repo.datapackage_path,
        default_branch=repo.default_branch,
        private=repo.private,
        archived=repo.archived,
        fork=repo.fork,
    )

    async with semaphore:
        try:
            content = await _fetch_descriptor(client, repo.datapackage_url)
            data = _parse_descriptor(content, repo.datapackage_path)
        except Exception as e:
            logger.warning(f"Failed descriptor for {repo.full_name}: {e}")
            return base.model_copy(update={"error": f"{type(e).__name__}: {e}"})

    if not isinstance(data, dict):
        return base.model_copy(update={"error": "descriptor is not a mapping"})

    resources: list[ResourceEntry] = []
    raw_resources = data.get("resources")
    if isinstance(raw_resources, list):
        for r in raw_resources:
            if isinstance(r, dict):
                resources.append(_resource_entry_from_raw(r))

    return base.model_copy(
        update={
            "name": data.get("name") or repo.repo,
            "title": data.get("title"),
            "description": data.get("description"),
            "resources": resources,
        }
    )


async def build_catalog(
    sources: list[str],
    *,
    token: str | None = None,
    include_archived: bool = False,
    include_forks: bool = False,
    fetch_concurrency: int = DEFAULT_FETCH_CONCURRENCY,
) -> list[CatalogEntry]:
    """Discover datapackages across every configured source and fetch descriptors in parallel."""
    parsed = parse_sources(sources)

    discover_tasks = [
        find_datapackage_repos(
            owner,
            kind=kind,  # type: ignore[arg-type]
            token=token,
            include_archived=include_archived,
            include_forks=include_forks,
        )
        for kind, owner in parsed
    ]
    discoveries = await asyncio.gather(*discover_tasks, return_exceptions=True)

    all_repos: list[RepoDatapackage] = []
    for (kind, owner), result in zip(parsed, discoveries, strict=True):
        if isinstance(result, BaseException):
            logger.warning(f"Skipping {kind}:{owner}: {result}")
            continue
        all_repos.extend(result)

    if not all_repos:
        return []

    resolved = resolve_token(token)
    semaphore = asyncio.Semaphore(fetch_concurrency)
    async with httpx.AsyncClient(
        headers=raw_headers(resolved),
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        return await asyncio.gather(
            *(_build_entry(client, semaphore, r) for r in all_repos)
        )


# ----- cache -----


class CatalogCache:
    """In-memory catalog cache with TTL and a single-flight lock."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL) -> None:
        self.ttl = ttl_seconds
        self._entries: list[CatalogEntry] = []
        self._sources_key: tuple[str, ...] = ()
        self._built_at_monotonic: float = 0.0
        self._built_at_wall: float = 0.0
        self._lock = asyncio.Lock()

    async def get(
        self,
        sources: list[str],
        *,
        token: str | None = None,
        include_archived: bool = False,
        include_forks: bool = False,
        force_refresh: bool = False,
    ) -> list[CatalogEntry]:
        key = tuple(sorted(sources))
        if not force_refresh and self._fresh_for(key):
            return self._entries

        async with self._lock:
            if not force_refresh and self._fresh_for(key):
                return self._entries
            logger.info(
                f"Building catalog (sources={list(key)}, "
                f"include_archived={include_archived}, include_forks={include_forks})"
            )
            self._entries = await build_catalog(
                list(key),
                token=token,
                include_archived=include_archived,
                include_forks=include_forks,
            )
            self._sources_key = key
            self._built_at_monotonic = time.monotonic()
            self._built_at_wall = time.time()
            return self._entries

    def _fresh_for(self, key: tuple[str, ...]) -> bool:
        if not self._entries or self._sources_key != key:
            return False
        return (time.monotonic() - self._built_at_monotonic) < self.ttl

    @property
    def age_seconds(self) -> float:
        if not self._built_at_monotonic:
            return 0.0
        return time.monotonic() - self._built_at_monotonic

    @property
    def refreshed_at(self) -> float:
        return self._built_at_wall


_DEFAULT_CACHE: CatalogCache | None = None


def get_default_cache() -> CatalogCache:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = CatalogCache()
    return _DEFAULT_CACHE


# ----- filtering / summarization -----


def _entry_haystack(entry: CatalogEntry) -> str:
    parts: list[str] = [
        entry.name,
        entry.full_name,
        entry.title or "",
        entry.description or "",
    ]
    for r in entry.resources:
        parts.extend([r.name, r.title or "", r.description or ""])
        for f in r.fields:
            parts.extend([f.name, f.title or "", f.description or ""])
    return " ".join(parts).lower()


def _matches_query(entry: CatalogEntry, query: str) -> bool:
    blob = _entry_haystack(entry)
    terms = [t for t in query.lower().split() if t]
    return all(term in blob for term in terms) if terms else True


def filter_entries(
    entries: list[CatalogEntry],
    *,
    query: str | None = None,
    org: str | None = None,
    user: str | None = None,
    has_resource: str | None = None,
    field_name: str | None = None,
    include_private: bool = True,
    include_archived: bool = False,
    include_errors: bool = True,
    limit: int = 20,
) -> list[CatalogEntry]:
    """Pure in-memory filter — composes AND across every supplied predicate."""
    out: list[CatalogEntry] = []
    for e in entries:
        if not include_archived and e.archived:
            continue
        if not include_private and e.private:
            continue
        if not include_errors and e.error:
            continue
        if org and e.owner.lower() != org.lower():
            continue
        if user and e.owner.lower() != user.lower():
            continue
        if has_resource:
            needle = has_resource.lower()
            if not any(needle in r.name.lower() for r in e.resources):
                continue
        if field_name:
            needle = field_name.lower()
            if not any(
                needle in f.name.lower() for r in e.resources for f in r.fields
            ):
                continue
        if query and not _matches_query(e, query):
            continue
        out.append(e)
        if limit > 0 and len(out) >= limit:
            break
    return out


def summarize(
    entries: list[CatalogEntry],
    *,
    sources: list[str],
    age_seconds: float,
    refreshed_at: float,
    ttl_seconds: int,
    top_resources: int = 20,
) -> CatalogSummary:
    by_owner: dict[str, int] = {}
    for e in entries:
        by_owner[e.owner] = by_owner.get(e.owner, 0) + 1

    res_freq: dict[str, int] = {}
    for e in entries:
        for r in e.resources:
            if r.name:
                res_freq[r.name] = res_freq.get(r.name, 0) + 1

    common = sorted(res_freq.items(), key=lambda x: (-x[1], x[0]))[:top_resources]

    return CatalogSummary(
        total=len(entries),
        with_error=sum(1 for e in entries if e.error),
        by_owner=dict(sorted(by_owner.items(), key=lambda x: (-x[1], x[0]))),
        sources=sources,
        refreshed_at=refreshed_at,
        age_seconds=age_seconds,
        ttl_seconds=ttl_seconds,
        resource_count=sum(len(e.resources) for e in entries),
        common_resource_names=[name for name, _ in common],
    )
