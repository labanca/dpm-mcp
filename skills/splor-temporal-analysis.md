---
name: splor-temporal-analysis
description: Multi-year analysis pattern for SPLOR-MG datapackages that follow the dados-<sistema>-<YYYY> naming scheme. Use when the user asks for trends, year-over-year comparisons, or "all years" of a SPLOR dataset (SISOR, SIGPLAN, etc.). Covers finding every yearly snapshot, joining schemas across years, and handling schema drift.
---

# Temporal (multi-year) analysis across SPLOR datapackages

Most operational SPLOR-MG datapackages are **versioned by year** — one repo
per exercise (`dados-sisor-2023`, `dados-sisor-2024`, `dados-sisor-2025`).
There is sometimes also a `dados-<sistema>-historico` repo with accumulated
data. This skill is the pattern for working across years.

## Finding every year of a series

```text
search_datapackages(query="<sistema>")
```

You'll typically get:

- `dados-<sistema>` (the "current" / non-suffixed one — may shadow the latest
  year, confirm with the user).
- `dados-<sistema>-2023`, `dados-<sistema>-2024`, `dados-<sistema>-2025`, …
- `dados-<sistema>-historico` (if present).

Sort by year suffix to detect gaps. **Do not assume** that all years are
present — verify by listing.

## Joining schemas across years

<!-- TODO(team): document known schema drift between years -->

Schema can drift slightly between exercises (new fields added, codes
renumbered). Before concatenating:

1. `inspect_datapackage` on the earliest and latest year you intend to use.
2. Compare the `resources[].schema.fields` lists. Flag any field that exists
   in one and not the other to the user before proceeding.
3. Confirm with the user whether to (a) restrict to common fields, (b) outer
   join, or (c) treat each year separately.

## Download pattern

```text
bulk_download(
    sources=[
        "https://github.com/splor-mg/dados-<sistema>-2023",
        "https://github.com/splor-mg/dados-<sistema>-2024",
        "https://github.com/splor-mg/dados-<sistema>-2025",
    ],
    resources=["<resource_name>"],   # only what's needed
    output_dir="./<sistema>-multi-year",
)
```

The output will be `./<sistema>-multi-year/<package-name>/<resource>.csv` per
year. From there, concatenate client-side (DuckDB `UNION BY NAME`, pandas
`concat`, etc.).

## Gotchas

<!-- TODO(team): fill from real incidents -->

- **`dados-<sistema>` vs `dados-<sistema>-<YYYY>`**: confirm whether the
  unsuffixed repo is the current year or something else (it may be the
  upstream "live" extract).
- **Encerramento de exercício**: late entries can change the previous year's
  totals. If using "current year" data alongside closed years, document the
  cut-off date.
- **`-historico` repos**: may aggregate using different column names than the
  yearly ones — inspect both before assuming equivalence.

## What to surface to the user

When you find multiple years, **list them explicitly** with byte counts /
row counts (from descriptor `bytes`/`stats`) before downloading. A user who
asks for "all years of SISOR" often doesn't realize they're about to pull
multiple GB.
