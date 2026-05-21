import pytest

from dpm_mcp.catalog import (
    CatalogEntry,
    FieldEntry,
    ResourceEntry,
    filter_entries,
    parse_sources,
    summarize,
)


def _make_entry(
    *,
    owner: str = "splor-mg",
    repo: str = "dados-sisor-2024",
    name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    resources: list[ResourceEntry] | None = None,
    private: bool = False,
    archived: bool = False,
    error: str | None = None,
) -> CatalogEntry:
    return CatalogEntry(
        name=name or repo,
        full_name=f"{owner}/{repo}",
        owner=owner,
        repo=repo,
        title=title,
        description=description,
        html_url=f"https://github.com/{owner}/{repo}",
        datapackage_url=f"https://raw.githubusercontent.com/{owner}/{repo}/main/datapackage.json",
        datapackage_path="datapackage.json",
        default_branch="main",
        private=private,
        archived=archived,
        resources=resources or [],
        error=error,
    )


def test_parse_sources_org_user_default() -> None:
    assert parse_sources(["org:splor-mg", "user:labanca", "another"]) == [
        ("org", "splor-mg"),
        ("user", "labanca"),
        ("org", "another"),
    ]


def test_parse_sources_strips_and_ignores_blanks() -> None:
    assert parse_sources(["  org:splor-mg  ", "", "user:foo"]) == [
        ("org", "splor-mg"),
        ("user", "foo"),
    ]


def test_parse_sources_invalid_kind() -> None:
    with pytest.raises(ValueError, match="Invalid source kind"):
        parse_sources(["team:x"])


def test_parse_sources_empty_name() -> None:
    with pytest.raises(ValueError, match="Empty source name"):
        parse_sources(["org:"])


def test_filter_by_query_multi_word_and() -> None:
    entries = [
        _make_entry(repo="dados-sisor-2024", title="SISOR execução orçamentária 2024"),
        _make_entry(repo="dados-sigplan-2024", title="SIGPLAN planejamento 2024"),
        _make_entry(repo="ementario", title="Ementário"),
    ]
    result = filter_entries(entries, query="sisor 2024")
    assert [e.repo for e in result] == ["dados-sisor-2024"]


def test_filter_by_resource_name() -> None:
    entries = [
        _make_entry(
            repo="ementario",
            resources=[ResourceEntry(name="uo"), ResourceEntry(name="fonte")],
        ),
        _make_entry(
            repo="dados-loa",
            resources=[ResourceEntry(name="volumes")],
        ),
    ]
    result = filter_entries(entries, has_resource="uo")
    assert [e.repo for e in result] == ["ementario"]


def test_filter_by_field_name() -> None:
    res = ResourceEntry(
        name="empenho",
        fields=[
            FieldEntry(name="cd_uo", type="string"),
            FieldEntry(name="vl_liquido", type="number"),
        ],
    )
    entries = [
        _make_entry(repo="dados-sisor-2024", resources=[res]),
        _make_entry(repo="ementario", resources=[ResourceEntry(name="uo")]),
    ]
    assert [e.repo for e in filter_entries(entries, field_name="vl_liquido")] == [
        "dados-sisor-2024"
    ]


def test_filter_excludes_archived_by_default() -> None:
    entries = [
        _make_entry(repo="active"),
        _make_entry(repo="old", archived=True),
    ]
    assert [e.repo for e in filter_entries(entries)] == ["active"]
    assert {e.repo for e in filter_entries(entries, include_archived=True)} == {
        "active",
        "old",
    }


def test_filter_excludes_private_when_requested() -> None:
    entries = [
        _make_entry(repo="pub"),
        _make_entry(repo="priv", private=True),
    ]
    assert {e.repo for e in filter_entries(entries, include_private=False)} == {"pub"}


def test_filter_limit_zero_means_unlimited() -> None:
    entries = [_make_entry(repo=f"r{i}") for i in range(50)]
    assert len(filter_entries(entries, limit=0)) == 50
    assert len(filter_entries(entries, limit=10)) == 10


def test_summarize_aggregates_owners_and_resources() -> None:
    entries = [
        _make_entry(owner="splor-mg", repo="dados-sisor-2024", resources=[
            ResourceEntry(name="empenho"),
            ResourceEntry(name="uo"),
        ]),
        _make_entry(owner="splor-mg", repo="ementario", resources=[
            ResourceEntry(name="uo"),
        ]),
        _make_entry(owner="other-org", repo="dados-x", error="boom"),
    ]
    summary = summarize(
        entries,
        sources=["org:splor-mg", "org:other-org"],
        age_seconds=12.5,
        refreshed_at=1_700_000_000.0,
        ttl_seconds=3600,
    )
    assert summary.total == 3
    assert summary.with_error == 1
    assert summary.by_owner == {"splor-mg": 2, "other-org": 1}
    assert summary.resource_count == 3
    assert summary.common_resource_names[0] == "uo"
