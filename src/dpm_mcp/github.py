"""GitHub API integration: list repos containing datapackages, fetch commit info.

Strictly read-only. Only GET requests against api.github.com.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

import httpx

from .auth import github_headers, resolve_token
from .models import RepoDatapackage
from .url_utils import GitHubRef, is_commit_sha

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_CONCURRENCY = 8

DATAPACKAGE_FILENAMES = ("datapackage.json", "datapackage.yaml", "datapackage.yml")


class GitHubError(RuntimeError):
    """Raised for GitHub API errors that should surface to the caller."""


async def _get_json(client: httpx.AsyncClient, url: str, **kwargs) -> dict | list:
    response = await client.get(url, **kwargs)
    if response.status_code == 404:
        raise GitHubError(f"Not found: {url}")
    if response.status_code == 429 or (
        response.status_code == 403 and "rate limit" in response.text.lower()
    ):
        raise GitHubError(
            "GitHub API rate limit exceeded. Provide a GITHUB_TOKEN to raise the limit "
            "from 60 to 5000 requests/hour."
        )
    response.raise_for_status()
    return response.json()


async def list_repos(
    owner: str,
    *,
    kind: Literal["org", "user"] = "org",
    token: str | None = None,
    include_archived: bool = False,
    include_forks: bool = False,
    per_page: int = 100,
) -> list[dict]:
    """List all repositories for an org or user (paginated)."""
    resolved = resolve_token(token)
    headers = github_headers(resolved)

    if kind == "org":
        base = f"{API_BASE}/orgs/{owner}/repos"
    else:
        base = f"{API_BASE}/users/{owner}/repos"

    repos: list[dict] = []
    async with httpx.AsyncClient(headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        page = 1
        while True:
            params = {"per_page": per_page, "page": page, "type": "all"}
            try:
                batch = await _get_json(client, base, params=params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 and kind == "org":
                    logger.info(f"{owner} not found as org, retrying as user")
                    return await list_repos(
                        owner,
                        kind="user",
                        token=token,
                        include_archived=include_archived,
                        include_forks=include_forks,
                        per_page=per_page,
                    )
                raise GitHubError(f"Failed to list repos for {owner}: {e}") from e

            if not isinstance(batch, list) or not batch:
                break
            repos.extend(batch)
            if len(batch) < per_page:
                break
            page += 1

    if not include_archived:
        repos = [r for r in repos if not r.get("archived")]
    if not include_forks:
        repos = [r for r in repos if not r.get("fork")]
    return repos


async def _check_datapackage_in_repo(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    repo: dict,
) -> RepoDatapackage | None:
    owner = repo["owner"]["login"]
    name = repo["name"]
    default_branch = repo.get("default_branch") or "main"

    async with semaphore:
        for filename in DATAPACKAGE_FILENAMES:
            url = f"{API_BASE}/repos/{owner}/{name}/contents/{filename}"
            try:
                resp = await client.get(url, params={"ref": default_branch})
            except httpx.HTTPError as e:
                logger.debug(f"Error checking {owner}/{name}: {e}")
                return None
            if resp.status_code == 200:
                return RepoDatapackage(
                    owner=owner,
                    repo=name,
                    full_name=f"{owner}/{name}",
                    default_branch=default_branch,
                    description=repo.get("description"),
                    private=bool(repo.get("private")),
                    archived=bool(repo.get("archived")),
                    fork=bool(repo.get("fork")),
                    html_url=repo.get("html_url", f"https://github.com/{owner}/{name}"),
                    datapackage_path=filename,
                    datapackage_url=(
                        f"https://raw.githubusercontent.com/{owner}/{name}/"
                        f"{default_branch}/{filename}"
                    ),
                )
            if resp.status_code == 401:
                logger.warning(
                    f"Invalid GitHub token (401) while probing {owner}/{name}/{filename}"
                )
                return None
            if resp.status_code == 403:
                logger.debug(
                    f"No access to {owner}/{name}/{filename} (403). "
                    f"Provide a GITHUB_TOKEN with read access if you need this repo."
                )
                return None
    return None


async def find_datapackage_repos(
    owner: str,
    *,
    kind: Literal["org", "user"] = "org",
    token: str | None = None,
    include_archived: bool = False,
    include_forks: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[RepoDatapackage]:
    """Find all repos in an org/user that expose a frictionless datapackage at the root."""
    resolved = resolve_token(token)
    repos = await list_repos(
        owner,
        kind=kind,
        token=token,
        include_archived=include_archived,
        include_forks=include_forks,
    )
    if not repos:
        return []

    semaphore = asyncio.Semaphore(concurrency)
    headers = github_headers(resolved)
    async with httpx.AsyncClient(headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        results = await asyncio.gather(
            *(_check_datapackage_in_repo(client, semaphore, repo) for repo in repos)
        )
    return [r for r in results if r is not None]


async def get_default_branch(
    owner: str,
    repo: str,
    token: str | None = None,
) -> str:
    """Return the default branch name for a repo."""
    headers = github_headers(resolve_token(token))
    async with httpx.AsyncClient(headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        data = await _get_json(client, f"{API_BASE}/repos/{owner}/{repo}")
    return data.get("default_branch", "main")  # type: ignore[union-attr]


async def get_commit_info(ref: GitHubRef, token: str | None = None) -> dict | None:
    """Resolve a branch/tag/commit reference to a commit SHA."""
    if ref.ref is None:
        return None
    headers = github_headers(resolve_token(token))
    endpoint = "commits" if is_commit_sha(ref.ref) else "branches"
    url = f"{API_BASE}/repos/{ref.owner}/{ref.repo}/{endpoint}/{ref.ref}"
    async with httpx.AsyncClient(headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        try:
            data = await _get_json(client, url)
        except (GitHubError, httpx.HTTPStatusError):
            return None
    if endpoint == "commits":
        sha = data.get("sha")  # type: ignore[union-attr]
    else:
        sha = data.get("commit", {}).get("sha")  # type: ignore[union-attr]
    return {
        "host": ref.host,
        "user": ref.owner,
        "repo": ref.repo,
        "ref": ref.ref,
        "sha": sha,
    }


async def find_datapackage_in_repo(
    owner: str,
    repo: str,
    *,
    ref: str | None = None,
    token: str | None = None,
) -> tuple[str, str] | None:
    """Find which datapackage descriptor file exists in a repo root.

    Returns:
        Tuple of (filename, raw_url) if found, ``None`` otherwise.
    """
    resolved = resolve_token(token)
    headers = github_headers(resolved)
    branch = ref or await get_default_branch(owner, repo, token=token)

    async with httpx.AsyncClient(headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        for filename in DATAPACKAGE_FILENAMES:
            url = f"{API_BASE}/repos/{owner}/{repo}/contents/{filename}"
            resp = await client.get(url, params={"ref": branch})
            if resp.status_code == 200:
                raw = (
                    f"https://raw.githubusercontent.com/{owner}/{repo}/"
                    f"{branch}/{filename}"
                )
                return filename, raw
    return None
