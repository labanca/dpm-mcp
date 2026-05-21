"""Pydantic models for dpm-mcp tool inputs/outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceInfo(BaseModel):
    """Lightweight info about a resource inside a datapackage."""

    name: str
    path: str | list[str] | None = None
    format: str | None = None
    mediatype: str | None = None
    bytes: int | None = None
    description: str | None = None


class DatapackageInfo(BaseModel):
    """Lightweight info about a frictionless datapackage."""

    name: str | None = None
    title: str | None = None
    description: str | None = None
    version: str | None = None
    licenses: list[dict] | None = None
    homepage: str | None = None
    resources: list[ResourceInfo] = Field(default_factory=list)


class RepoDatapackage(BaseModel):
    """A repo that exposes a datapackage at a known path."""

    owner: str
    repo: str
    full_name: str
    default_branch: str
    description: str | None = None
    private: bool = False
    archived: bool = False
    fork: bool = False
    html_url: str
    datapackage_path: str = "datapackage.json"
    datapackage_url: str
    """Raw URL to the datapackage descriptor on the default branch."""


class DownloadResult(BaseModel):
    """Result of downloading one datapackage."""

    package_name: str
    output_dir: str
    descriptor_path: str
    downloaded_resources: list[str]
    skipped_resources: list[str] = Field(default_factory=list)
    bytes_downloaded: int = 0
    source: str
    remote: dict | None = None


class BulkDownloadResult(BaseModel):
    """Result of a bulk download operation."""

    succeeded: list[DownloadResult] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)
    total: int = 0
