"""URL parsing and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

GITHUB_HOSTS = {"github.com", "www.github.com"}
RAW_HOSTS = {"raw.githubusercontent.com"}
API_HOST = "api.github.com"

_COMMIT_SHA_RE = re.compile(r"^[a-f0-9]{40}$")


@dataclass(frozen=True)
class GitHubRef:
    """Parsed components of a GitHub URL."""

    host: str
    owner: str
    repo: str
    ref: str | None = None
    path: str | None = None
    kind: str = "repo"
    """One of: ``repo``, ``raw``, ``blob``, ``tree``."""

    @property
    def is_raw(self) -> bool:
        return self.kind == "raw"


def is_commit_sha(ref: str) -> bool:
    return bool(_COMMIT_SHA_RE.match(ref))


def parse_github_url(url: str) -> GitHubRef | None:
    """Parse a GitHub URL into structured parts. Returns ``None`` for non-GitHub URLs."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host in RAW_HOSTS:
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 3:
            return None
        owner, repo, ref, *rest = parts
        return GitHubRef(
            host=host,
            owner=owner,
            repo=_strip_dot_git(repo),
            ref=ref,
            path="/".join(rest) if rest else None,
            kind="raw",
        )

    if host in GITHUB_HOSTS:
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 2:
            return None
        owner, repo, *rest = parts
        repo = _strip_dot_git(repo)
        if not rest:
            return GitHubRef(host=host, owner=owner, repo=repo, kind="repo")
        kind = rest[0]
        if kind in {"blob", "tree", "raw"} and len(rest) >= 2:
            ref = rest[1]
            path = "/".join(rest[2:]) if len(rest) > 2 else None
            normalized_kind = "raw" if kind == "raw" else kind
            return GitHubRef(
                host=host,
                owner=owner,
                repo=repo,
                ref=ref,
                path=path,
                kind=normalized_kind,
            )
        return GitHubRef(host=host, owner=owner, repo=repo, kind="repo")

    return None


def to_raw_url(ref: GitHubRef, file_path: str, branch: str | None = None) -> str:
    """Build a raw.githubusercontent.com URL for a file in a repo."""
    use_ref = branch or ref.ref or "HEAD"
    return f"https://raw.githubusercontent.com/{ref.owner}/{ref.repo}/{use_ref}/{file_path.lstrip('/')}"


def _strip_dot_git(repo: str) -> str:
    return repo[:-4] if repo.endswith(".git") else repo


def is_likely_datapackage_url(url: str) -> bool:
    """Quick heuristic: does the URL look like it points to a frictionless descriptor?"""
    parsed = urlparse(url)
    last = parsed.path.rsplit("/", 1)[-1].lower()
    return last in {"datapackage.json", "datapackage.yaml", "datapackage.yml"}
