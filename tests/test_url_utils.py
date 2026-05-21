from dpm_mcp.url_utils import (
    is_commit_sha,
    is_likely_datapackage_url,
    parse_github_url,
    to_raw_url,
)


def test_parse_repo_url() -> None:
    ref = parse_github_url("https://github.com/splor-mg/sisor-dados-2024")
    assert ref is not None
    assert ref.owner == "splor-mg"
    assert ref.repo == "sisor-dados-2024"
    assert ref.kind == "repo"
    assert ref.ref is None


def test_parse_repo_url_with_dot_git() -> None:
    ref = parse_github_url("https://github.com/splor-mg/sisor-dados-2024.git")
    assert ref is not None
    assert ref.repo == "sisor-dados-2024"


def test_parse_blob_url() -> None:
    ref = parse_github_url(
        "https://github.com/splor-mg/sisor-dados-2024/blob/main/datapackage.json"
    )
    assert ref is not None
    assert ref.kind == "blob"
    assert ref.ref == "main"
    assert ref.path == "datapackage.json"


def test_parse_raw_url() -> None:
    ref = parse_github_url(
        "https://raw.githubusercontent.com/splor-mg/sisor-dados-2024/main/datapackage.json"
    )
    assert ref is not None
    assert ref.kind == "raw"
    assert ref.ref == "main"
    assert ref.path == "datapackage.json"


def test_parse_non_github_returns_none() -> None:
    assert parse_github_url("https://gitlab.com/foo/bar") is None
    assert parse_github_url("https://example.com/data.csv") is None


def test_to_raw_url() -> None:
    ref = parse_github_url("https://github.com/splor-mg/sisor-dados-2024")
    assert ref is not None
    assert (
        to_raw_url(ref, "datapackage.json", branch="main")
        == "https://raw.githubusercontent.com/splor-mg/sisor-dados-2024/main/datapackage.json"
    )


def test_is_commit_sha() -> None:
    assert is_commit_sha("d43b96af767a25371e89e69a68705bcdceece6ff")
    assert not is_commit_sha("main")
    assert not is_commit_sha("v1.2.3")


def test_is_likely_datapackage_url() -> None:
    assert is_likely_datapackage_url(
        "https://raw.githubusercontent.com/x/y/main/datapackage.json"
    )
    assert is_likely_datapackage_url("https://example.com/foo/datapackage.yaml")
    assert not is_likely_datapackage_url("https://example.com/data.csv")
