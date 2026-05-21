"""MCP server for dpm-mcp — exposes DPM functionality as MCP tools.

Tools exposed (all read-only):
    * ``list_org_datapackages`` / ``list_user_datapackages`` — discover datapackages
    * ``inspect_datapackage`` — peek metadata without downloading data
    * ``download_datapackage`` — download one datapackage (descriptor + resources)
    * ``bulk_download`` — download many datapackages in one call
    * ``install_from_toml`` — drop-in compatible with ``dpm install``

The MCP server is strictly read-only by design: it never issues write requests
to any remote (no POST/PUT/PATCH/DELETE against GitHub or any data host).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from . import __version__
from .datapackage import (
    DatapackageError,
    download_datapackage as _download_datapackage,
    inspect_datapackage as _inspect_datapackage,
)
from .github import GitHubError, find_datapackage_repos
from .models import (
    BulkDownloadResult,
    DatapackageInfo,
    DownloadResult,
    RepoDatapackage,
)
from .toml_loader import filter_packages, load_data_toml

load_dotenv()

logging.basicConfig(
    level=os.getenv("DPM_MCP_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("dpm_mcp")

mcp = FastMCP(
    "dpm-mcp",
    instructions=(
        "Download and inspect frictionless datapackages hosted in git repositories. "
        "Use list_org_datapackages / list_user_datapackages to discover available packages, "
        "inspect_datapackage to preview metadata, and download_datapackage to fetch data."
    ),
)


def _default_output_dir() -> str:
    return os.getenv("DPM_MCP_OUTPUT_DIR", "datapackages")


@mcp.tool()
async def list_org_datapackages(
    org: Annotated[str, Field(description="GitHub organization name, e.g. 'splor-mg'.")],
    token: Annotated[
        str | None,
        Field(
            description=(
                "Optional GitHub PAT, or name of an env var holding it. "
                "Falls back to $GITHUB_TOKEN."
            ),
        ),
    ] = None,
    include_archived: Annotated[
        bool,
        Field(description="Include archived repositories in the listing."),
    ] = False,
    include_forks: Annotated[
        bool,
        Field(description="Include forks in the listing."),
    ] = False,
) -> list[RepoDatapackage]:
    """List every repository in a GitHub org that exposes a frictionless datapackage."""
    try:
        return await find_datapackage_repos(
            org,
            kind="org",
            token=token,
            include_archived=include_archived,
            include_forks=include_forks,
        )
    except GitHubError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def list_user_datapackages(
    user: Annotated[str, Field(description="GitHub username.")],
    token: Annotated[str | None, Field(description="Optional PAT (literal or env var name).")] = None,
    include_archived: Annotated[bool, Field(description="Include archived repos.")] = False,
    include_forks: Annotated[bool, Field(description="Include forks.")] = False,
) -> list[RepoDatapackage]:
    """List every repository owned by a GitHub user that exposes a frictionless datapackage."""
    try:
        return await find_datapackage_repos(
            user,
            kind="user",
            token=token,
            include_archived=include_archived,
            include_forks=include_forks,
        )
    except GitHubError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def inspect_datapackage(
    source: Annotated[
        str,
        Field(
            description=(
                "URL to a datapackage descriptor (datapackage.json/.yaml) OR a GitHub repo URL. "
                "When given a repo URL, the descriptor is auto-discovered on the default branch."
            )
        ),
    ],
    ref: Annotated[
        str | None,
        Field(description="Optional branch, tag, or commit SHA (only relevant for repo URLs)."),
    ] = None,
    token: Annotated[str | None, Field(description="Optional PAT (literal or env var name).")] = None,
) -> DatapackageInfo:
    """Return datapackage metadata + list of resources, without downloading data."""
    try:
        return await _inspect_datapackage(source, ref=ref, token=token)
    except (DatapackageError, GitHubError) as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def download_datapackage(
    source: Annotated[
        str,
        Field(
            description=(
                "URL to a datapackage descriptor (datapackage.json/.yaml) OR a GitHub repo URL. "
                "Repo URLs are auto-resolved to their datapackage on the default branch."
            )
        ),
    ],
    output_dir: Annotated[
        str | None,
        Field(
            description=(
                "Parent directory where '<package_name>/' will be created. "
                "Defaults to $DPM_MCP_OUTPUT_DIR or './datapackages'."
            )
        ),
    ] = None,
    resources: Annotated[
        list[str] | None,
        Field(
            description=(
                "Optional list of resource names to download. If omitted, all resources are downloaded. "
                "Names not present in the descriptor are reported in 'skipped_resources'."
            )
        ),
    ] = None,
    package_name: Annotated[
        str | None,
        Field(
            description=(
                "Optional override for the destination folder name. "
                "Defaults to the datapackage's own 'name' field."
            )
        ),
    ] = None,
    ref: Annotated[
        str | None,
        Field(description="Optional branch/tag/commit SHA for GitHub repo URLs."),
    ] = None,
    token: Annotated[
        str | None,
        Field(
            description=(
                "Optional GitHub PAT (literal) or env var name holding one. "
                "Falls back to $GITHUB_TOKEN. Required for private repos."
            )
        ),
    ] = None,
) -> DownloadResult:
    """Download a frictionless datapackage and its resources to local disk."""
    try:
        return await _download_datapackage(
            source,
            output_dir=output_dir or _default_output_dir(),
            resources=resources,
            package_name=package_name,
            ref=ref,
            token=token,
        )
    except (DatapackageError, GitHubError) as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def bulk_download(
    sources: Annotated[
        list[str],
        Field(
            description=(
                "List of source URLs (descriptor URLs or GitHub repo URLs). "
                "Useful in combination with list_org_datapackages."
            )
        ),
    ],
    output_dir: Annotated[
        str | None,
        Field(description="Parent directory for downloads."),
    ] = None,
    resources: Annotated[
        list[str] | None,
        Field(
            description=(
                "Optional resource-name filter applied to every package. "
                "Resources missing in a given package are silently skipped per package."
            )
        ),
    ] = None,
    token: Annotated[str | None, Field(description="PAT or env var name.")] = None,
    continue_on_error: Annotated[
        bool,
        Field(description="When true, errors on individual packages are collected, not raised."),
    ] = True,
) -> BulkDownloadResult:
    """Download many datapackages. Partial failures are reported in the result."""
    target_dir = output_dir or _default_output_dir()
    result = BulkDownloadResult(total=len(sources))
    for src in sources:
        try:
            r = await _download_datapackage(
                src,
                output_dir=target_dir,
                resources=resources,
                token=token,
            )
            result.succeeded.append(r)
        except Exception as e:
            entry = {"source": src, "error": str(e), "error_type": type(e).__name__}
            if not continue_on_error:
                raise
            result.failed.append(entry)
    return result


@mcp.tool()
async def install_from_toml(
    descriptor_path: Annotated[
        str,
        Field(description="Path to a data.toml manifest (DPM-compatible)."),
    ],
    output_dir: Annotated[
        str | None,
        Field(description="Parent directory for downloads. Defaults to './datapackages'."),
    ] = None,
    packages: Annotated[
        list[str] | None,
        Field(description="Optional list of package names from the manifest to install."),
    ] = None,
    token: Annotated[
        str | None,
        Field(
            description=(
                "Optional PAT override. By default, each [packages.X].token entry is "
                "interpreted as an env var name (DPM-compatible). This argument takes precedence."
            )
        ),
    ] = None,
) -> BulkDownloadResult:
    """Install datapackages declared in a data.toml manifest (drop-in for ``dpm install``)."""
    data = load_data_toml(descriptor_path)
    data = filter_packages(data, packages)
    target_dir = output_dir or _default_output_dir()

    result = BulkDownloadResult(total=len(data["packages"]))
    for name, pkg in data["packages"].items():
        pkg_token = token if token is not None else pkg.get("token")
        try:
            r = await _download_datapackage(
                pkg["path"],
                output_dir=target_dir,
                resources=pkg.get("resources"),
                package_name=name,
                token=pkg_token,
            )
            result.succeeded.append(r)
        except Exception as e:
            result.failed.append(
                {
                    "source": pkg["path"],
                    "package_name": name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
    return result


@mcp.resource("dpm-mcp://about")
def about() -> str:
    """About this MCP server."""
    return (
        f"dpm-mcp {__version__}\n"
        f"Read-only MCP server for the SPLOR-MG Data Package Manager.\n"
        f"Downloads frictionless datapackages from git repositories.\n"
        f"\n"
        f"Auth: provide GITHUB_TOKEN in env (or pass 'token' per-call) to access "
        f"private repos and raise the API rate limit from 60 to 5000 req/hour.\n"
        f"\n"
        f"This server never writes, pushes, or uploads to any remote repository."
    )


def _run_http() -> None:
    """Run the streamable-http transport via uvicorn with optional bearer auth."""
    import uvicorn
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    from .http_auth import BearerTokenMiddleware

    host = os.getenv("DPM_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("DPM_MCP_PORT", "8000"))
    auth_token = os.getenv("DPM_MCP_AUTH_TOKEN") or None

    app = mcp.streamable_http_app()

    async def _health(_request) -> PlainTextResponse:  # type: ignore[no-untyped-def]
        return PlainTextResponse("ok")

    app.router.routes.append(Route("/health", _health, methods=["GET"]))

    if auth_token:
        app.add_middleware(BearerTokenMiddleware, token=auth_token)
        logger.info("Bearer-token auth enabled for HTTP transport.")
    else:
        logger.warning(
            "DPM_MCP_AUTH_TOKEN is not set — HTTP transport is exposed without auth. "
            "Do NOT use this configuration on a public URL."
        )

    logger.info(f"Starting dpm-mcp on http://{host}:{port} (transport=streamable-http)")
    uvicorn.run(app, host=host, port=port, log_level=os.getenv("DPM_MCP_LOG_LEVEL", "info").lower())


def main() -> None:
    """Entry point for the ``dpm-mcp`` CLI script."""
    transport = os.getenv("DPM_MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run()
    elif transport in {"streamable-http", "http"}:
        _run_http()
    elif transport == "sse":
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown DPM_MCP_TRANSPORT={transport!r}")


if __name__ == "__main__":
    main()
