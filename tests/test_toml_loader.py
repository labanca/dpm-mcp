from pathlib import Path

import pytest

from dpm_mcp.toml_loader import TomlSchemaError, filter_packages, load_data_toml


def test_load_valid_data_toml(tmp_path: Path) -> None:
    path = tmp_path / "data.toml"
    path.write_text(
        '''
title = "test"

[packages.foo]
path = "https://example.com/datapackage.json"
resources = ["a", "b"]

[packages.bar]
path = "https://example.com/other/datapackage.json"
token = "MY_TOKEN"
'''
    )
    data = load_data_toml(path)
    assert set(data["packages"].keys()) == {"foo", "bar"}
    assert data["packages"]["foo"]["resources"] == ["a", "b"]
    assert data["packages"]["bar"]["token"] == "MY_TOKEN"


def test_missing_path_raises(tmp_path: Path) -> None:
    path = tmp_path / "data.toml"
    path.write_text(
        '''
[packages.foo]
resources = ["a"]
'''
    )
    with pytest.raises(TomlSchemaError):
        load_data_toml(path)


def test_filter_packages(tmp_path: Path) -> None:
    path = tmp_path / "data.toml"
    path.write_text(
        '''
[packages.foo]
path = "x"

[packages.bar]
path = "y"

[packages.baz]
path = "z"
'''
    )
    data = load_data_toml(path)
    filtered = filter_packages(data, ["foo", "baz"])
    assert set(filtered["packages"].keys()) == {"foo", "baz"}


def test_filter_packages_unknown_name_raises(tmp_path: Path) -> None:
    path = tmp_path / "data.toml"
    path.write_text('[packages.foo]\npath = "x"\n')
    data = load_data_toml(path)
    with pytest.raises(TomlSchemaError):
        filter_packages(data, ["nope"])
