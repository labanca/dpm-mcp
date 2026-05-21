---
name: splor-dpm-conventions
description: How to discover, inspect, and download SPLOR-MG datapackages through the dpm-mcp server. Use whenever the user asks about SPLOR data, wants to find a dataset, or needs to fetch data from splor-mg / dpm / frictionless datapackage repositories. Covers the discovery flow (catalog summary → search → inspect → download), naming conventions for SPLOR datapackages, and how to combine multiple datapackages.
---

# Working with SPLOR-MG datapackages via dpm-mcp

The `dpm-mcp` server exposes a catalog of frictionless datapackages published
across SPLOR-MG's GitHub repositories. Each repo has a `datapackage.json` (or
`.yaml`) at its root describing one or more **resources** (tables, typically
CSV).

## Discovery flow

**Never** ask "what datapackages exist" by listing every one in the system
prompt. Instead, use this drill-down:

1. **`get_catalog_summary()`** — one call, returns counts, owners, common
   resource names. Use this as your first orientation.
2. **`search_datapackages(query=..., has_resource=..., field_name=...)`** —
   narrow by free-text or by resource/field name. Free-text search is AND
   across words and matches package name/title/description plus every
   resource's name/description and schema field names/descriptions.
3. **`inspect_datapackage(source=<repo or descriptor URL>)`** — preview the
   metadata + resource list + schemas for a candidate, *without* downloading
   data.
4. **`download_datapackage(source=..., resources=[<names>], output_dir=...)`** —
   fetch only what's needed.

For a known repo URL, you can skip 1-3 and go straight to inspect/download.

## Naming conventions you'll see

<!-- TODO(team): confirm/extend this list -->

- `dados-<sistema>` (sometimes with `-<ano>` suffix) — extracts from a state
  system (SISOR, SIGPLAN, SIAFI, etc.).
- `dados-<sistema>-<YYYY>` — yearly snapshot. New repos are usually created
  per year rather than appended.
- `dados-<sistema>-historico` — multi-year accumulator.
- `armazem-siafi-*` — derived tables from "Armazém SIAFI".
- `ementario` — auxiliary lookup tables (UO, Fonte, etc.) used to enrich the
  numeric tables.
- `matriz-fonte-*` — mapping tables between funding-source codes.

## Combining datapackages

Many resources share names across packages (e.g., `base_qdd_plurianual`
appears in several SISOR datapackages). When the user asks for a cross-package
view:

1. Use `search_datapackages(has_resource="<name>")` to find every package
   exposing that resource.
2. Use the original DPM `concat` mental model (concatenate the same resource
   from each package) — currently not exposed as an MCP tool, but you can
   download each and concat client-side.

## Authentication

Private repos require a `GITHUB_TOKEN`. It is typically configured server-side
on the `dpm-mcp` host, so you usually don't pass `token=...` per call. If a
call returns 401/403, suggest the user check `GITHUB_TOKEN`.

## Output location

Default download dir is `./datapackages/<package-name>/`. Use the `output_dir`
parameter to override (always confirm with the user before writing outside the
current working directory).

## What dpm-mcp does NOT do

- It is **read-only.** It never pushes, never opens PRs, never edits remote
  files. If the user asks for that, say so and don't try.
- It does not run analytical SQL. After downloading, use the user's own tools
  (DuckDB, pandas, polars, etc.).
- It does not currently expose `dpm load` (DB loading) or `dpm concat` from
  upstream — only discovery + download.
