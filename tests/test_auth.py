import pytest

from dpm_mcp.auth import github_headers, resolve_token


def test_resolve_explicit_literal_pat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert resolve_token("ghp_abcdefghijklmnopqrstuvwxyz0123456789") == (
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    )


def test_resolve_env_var_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "secret-value")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert resolve_token("MY_TOKEN") == "secret-value"


def test_resolve_falls_back_to_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fallback")
    assert resolve_token(None) == "fallback"


def test_resolve_returns_none_without_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert resolve_token(None) is None


def test_github_headers_includes_bearer() -> None:
    headers = github_headers("abc123")
    assert headers["Authorization"] == "Bearer abc123"


def test_github_headers_omits_authorization_when_no_token() -> None:
    headers = github_headers(None)
    assert "Authorization" not in headers
