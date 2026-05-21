"""``data.toml`` parser compatible with the upstream DPM project.

Schema (subset relevant to download):

    title = "optional title"

    [packages.<package_name>]
    path = "https://.../datapackage.json"
    resources = ["resource_a", "resource_b"]  # optional, downloads all if omitted
    token = "ENV_VAR_NAME"                    # optional, env var name holding a PAT

Unknown keys are preserved and exposed in the parsed structure but ignored by
the downloader. Compatibility with the original DPM is preserved: ``token`` is
treated as an env var name (DPM-style).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class TomlSchemaError(ValueError):
    pass


def load_data_toml(path: str | Path) -> dict[str, Any]:
    """Load and lightly validate a ``data.toml`` manifest."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"data.toml not found: {path}")
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    packages = data.get("packages")
    if not isinstance(packages, dict) or not packages:
        raise TomlSchemaError(f"{path}: missing or empty [packages] table.")

    for name, pkg in packages.items():
        if not isinstance(pkg, dict):
            raise TomlSchemaError(f"{path}: [packages.{name}] must be a table.")
        if "path" not in pkg:
            raise TomlSchemaError(f"{path}: [packages.{name}] missing required key 'path'.")
        if "resources" in pkg and not isinstance(pkg["resources"], list):
            raise TomlSchemaError(
                f"{path}: [packages.{name}].resources must be an array of strings."
            )
    return data


def filter_packages(data: dict[str, Any], names: list[str] | None) -> dict[str, Any]:
    """Filter the parsed data.toml to only the requested package names."""
    if not names:
        return data
    available = set(data["packages"].keys())
    selected = set(names)
    missing = selected - available
    if missing:
        raise TomlSchemaError(
            f"Requested packages not in data.toml: {sorted(missing)}. "
            f"Available: {sorted(available)}"
        )
    return {
        **data,
        "packages": {k: v for k, v in data["packages"].items() if k in selected},
    }
