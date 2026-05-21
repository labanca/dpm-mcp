"""Datapackage download and inspection.

Mirrors the behaviour of ``dpm install`` from the upstream DPM package, with
two extensions:

* The source can be a raw descriptor URL **or** a GitHub repo URL; the latter
  is auto-resolved to its ``datapackage.json`` on the default (or given) branch.
* Auth uses a real PAT directly (not an env-var name) — the env-var indirection
  remains supported for ``data.toml`` compatibility.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Iterable

import httpx
from frictionless import Package, system

from .auth import raw_headers, resolve_token
from .github import find_datapackage_in_repo, get_commit_info
from .models import DatapackageInfo, DownloadResult, ResourceInfo
from .url_utils import is_likely_datapackage_url, parse_github_url

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
DEFAULT_CHUNK = 1 << 16  # 64 KiB


class DatapackageError(RuntimeError):
    pass


async def resolve_descriptor_url(
    source: str,
    *,
    ref: str | None = None,
    token: str | None = None,
) -> str:
    """Given any user-provided source string, return the URL to a datapackage descriptor.

    Handles:
      * raw descriptor URL (``datapackage.json``/``.yaml``)
      * GitHub repo URL (``https://github.com/owner/repo``)
      * GitHub blob/tree URL pointing at the descriptor
      * arbitrary URL pointing at the descriptor (passes through)
    """
    if is_likely_datapackage_url(source):
        return source

    gh = parse_github_url(source)
    if gh is None:
        return source

    if gh.path and is_likely_datapackage_url(gh.path):
        from .url_utils import to_raw_url

        return to_raw_url(gh, gh.path, branch=ref or gh.ref)

    found = await find_datapackage_in_repo(
        gh.owner,
        gh.repo,
        ref=ref or gh.ref,
        token=token,
    )
    if not found:
        raise DatapackageError(
            f"No datapackage.json/.yaml found in {gh.owner}/{gh.repo} "
            f"(ref={ref or gh.ref or 'default branch'})."
        )
    _, raw_url = found
    return raw_url


def _http_client_with_session(token: str | None) -> httpx.Client:
    return httpx.Client(headers=raw_headers(token), timeout=DEFAULT_TIMEOUT, follow_redirects=True)


def _load_package_via_frictionless(descriptor_url: str, token: str | None) -> Package:
    """Load a frictionless ``Package`` using an authenticated session for private repos."""
    import requests  # frictionless uses requests under the hood

    session = requests.Session()
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers["User-Agent"] = "dpm-mcp/0.1"

    with system.use_context(http_session=session):
        package = Package(descriptor_url)
    return package


async def inspect_datapackage(
    source: str,
    *,
    ref: str | None = None,
    token: str | None = None,
) -> DatapackageInfo:
    """Load a datapackage descriptor and return its metadata (no resource download)."""
    resolved = resolve_token(token)
    descriptor_url = await resolve_descriptor_url(source, ref=ref, token=token)

    def _load() -> Package:
        package = _load_package_via_frictionless(descriptor_url, resolved)
        package.dereference()
        return package

    package = await asyncio.to_thread(_load)

    resources = [
        ResourceInfo(
            name=r.name or "",
            path=r.path,
            format=r.format,
            mediatype=getattr(r, "mediatype", None),
            bytes=getattr(r, "bytes", None) or None,
            description=getattr(r, "description", None),
        )
        for r in package.resources
    ]
    return DatapackageInfo(
        name=package.name,
        title=getattr(package, "title", None),
        description=getattr(package, "description", None),
        version=getattr(package, "version", None),
        licenses=getattr(package, "licenses", None),
        homepage=getattr(package, "homepage", None),
        resources=resources,
    )


def _safe_package_name(package: Package, fallback_source: str) -> str:
    name = package.name
    if name:
        return name
    gh = parse_github_url(fallback_source)
    if gh is not None:
        return gh.repo
    parts = [p for p in fallback_source.rstrip("/").split("/") if p]
    for candidate in reversed(parts[:-1] if parts and "." in parts[-1] else parts):
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate)
        if cleaned and cleaned not in {"main", "master", "HEAD"}:
            return cleaned
    return "datapackage"


async def download_datapackage(
    source: str,
    *,
    output_dir: str | Path = "datapackages",
    resources: Iterable[str] | None = None,
    package_name: str | None = None,
    ref: str | None = None,
    token: str | None = None,
) -> DownloadResult:
    """Download a single datapackage descriptor + selected resources.

    Args:
        source: descriptor URL or GitHub repo URL.
        output_dir: parent directory where ``<package_name>/`` will be created.
        resources: optional iterable of resource names to keep (others skipped).
        package_name: override the subfolder name. Defaults to ``package.name``.
        ref: optional branch/tag/commit (only meaningful for GitHub repo URLs).
        token: PAT (literal), env var name, or ``None``.
    """
    resolved = resolve_token(token)
    descriptor_url = await resolve_descriptor_url(source, ref=ref, token=token)

    def _load() -> Package:
        package = _load_package_via_frictionless(descriptor_url, resolved)
        package.dereference()
        return package

    package = await asyncio.to_thread(_load)

    name = package_name or _safe_package_name(package, descriptor_url)
    pkg_dir = Path(output_dir) / name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    available = list(package.resource_names)
    requested = list(resources) if resources else available
    keep = [r for r in requested if r in available]
    skipped_requested = [r for r in requested if r not in available]

    for unwanted in [r for r in available if r not in keep]:
        package.remove_resource(unwanted)

    gh = parse_github_url(descriptor_url)
    remote: dict | None = None
    if gh is not None and gh.ref:
        remote = await get_commit_info(gh, token=token)
        if remote:
            package.custom.update({"remote": remote})

    descriptor_path = pkg_dir / "datapackage.json"
    await asyncio.to_thread(package.to_json, str(descriptor_path))

    if not package.resources:
        return DownloadResult(
            package_name=name,
            output_dir=str(pkg_dir),
            descriptor_path=str(descriptor_path),
            downloaded_resources=[],
            skipped_resources=skipped_requested,
            bytes_downloaded=0,
            source=descriptor_url,
            remote=remote,
        )

    downloaded: list[str] = []
    total_bytes = 0
    async with httpx.AsyncClient(
        headers=raw_headers(resolved),
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:
        for resource in package.resources:
            if not resource.path or isinstance(resource.path, list):
                logger.info(f"Skipping non-file resource '{resource.name}'")
                continue
            remote_url = f"{resource.basepath}/{resource.path}"
            local_path = pkg_dir / resource.path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            written = await _stream_to_file(client, remote_url, local_path)
            downloaded.append(resource.name)
            total_bytes += written
            logger.info(
                f"Downloaded resource '{resource.name}' ({written} bytes) -> {local_path}"
            )

    return DownloadResult(
        package_name=name,
        output_dir=str(pkg_dir),
        descriptor_path=str(descriptor_path),
        downloaded_resources=downloaded,
        skipped_resources=skipped_requested,
        bytes_downloaded=total_bytes,
        source=descriptor_url,
        remote=remote,
    )


async def _stream_to_file(client: httpx.AsyncClient, url: str, path: Path) -> int:
    written = 0
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        with open(path, "wb") as fh:
            async for chunk in response.aiter_bytes(chunk_size=DEFAULT_CHUNK):
                fh.write(chunk)
                written += len(chunk)
    return written
