---
name: splor-sisor
description: How to work with SPLOR-MG SISOR datapackages (execução orçamentária, quadro de detalhamento da despesa - QDD, despesa de investimento, detalhamento de obras). Use when the user asks about SISOR data, QDD, execução orçamentária, plurianual, investimento, obras SIAD, or related budget execution topics. Covers the known resources, common joins to ementário tables, and conventions for filtering by exercise/fonte/UO.
---

# Working with SPLOR-MG SISOR datapackages

SISOR is the **state budget execution system**. Datapackages built from it
typically follow `dados-sisor` / `dados-sisor-<ano>` naming and contain a
core set of resources for the quadro de detalhamento da despesa (QDD),
investment-side data, and obras (SIAD).

## Known resources (from current snapshot)

<!-- TODO(team): replace these one-liners with authoritative descriptions -->

| Resource | What it is (one line) |
| --- | --- |
| `base_qdd_plurianual` | QDD multi-annual budget detail. |
| `base_qdd_plurianual_invest` | QDD multi-annual, investment slice. |
| `base_orcam_despesa_item_fiscal` | Budget item fiscal detail. |
| `base_orcam_despesa_investimento` | Investment expense detail. |
| `base_detalhamento_obras` | Public works detail. |
| `base_obras_siad` | Works extracted from SIAD. |
| `base_categoria_pessoal` | Personnel category breakdown. |
| `base_intra_orcamentaria_detalhamento` | Intra-budget detail. |
| `base_intra_orcamentaria_repasse` | Intra-budget transfers. |
| `base_limite_cota` | Quota limit. |

Confirm field-level semantics with `inspect_datapackage` — schemas evolve and
this table is a starting hint, not authoritative documentation.

## Common joins with ementário

The `ementario` datapackage carries lookup tables (`uo`, `fonte`, etc.). To
get human-readable labels alongside SISOR codes:

```text
inspect_datapackage("https://github.com/splor-mg/ementario")
# pick uo and/or fonte
download_datapackage(
    "https://github.com/splor-mg/ementario",
    resources=["uo", "fonte"],
)
# then download the SISOR resource you need and join client-side
```

Typical join keys (verify in the schema!):

<!-- TODO(team): confirm canonical key names -->

- `cd_uo` (código da unidade orçamentária) ↔ `ementario.uo.codigo`
- `cd_fonte` ↔ `ementario.fonte.codigo`
- `cd_acao` ↔ planejamento / SIGPLAN tables

## Filtering conventions

When the user asks for "SISOR data for órgão X" or "fonte Y":

1. First identify the codes (via ementário or by asking the user).
2. Download the full resource and filter client-side — there's no remote
   filter parameter in dpm-mcp.

## Year selection

If the user doesn't specify a year:

- For "current execução", use the most recent `dados-sisor-<YYYY>` (verify by
  `search_datapackages(query="sisor")` and picking the highest year).
- For historical analysis, see [[splor-temporal-analysis]].

## Things to confirm with the user before downloading

<!-- TODO(team): fill from real cases -->

- Which exercise(s) — current year vs historical.
- Which resource(s) — full QDD can be large.
- Whether to include investment-side data or stick to costeio.

## What SISOR data is NOT

- It is **not real-time** — extracts are snapshots; check the descriptor
  `remote.sha` and commit date to know how stale it is.
- It is **not auditable replacement for the source system** — for legal
  reference always cite SISOR directly, not the dpm extract.
