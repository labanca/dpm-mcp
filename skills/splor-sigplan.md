---
name: splor-sigplan
description: How to work with SPLOR-MG SIGPLAN datapackages (planejamento - programas, ações, localizadores, indicadores, planejamento histórico). Use when the user asks about SIGPLAN data, planejamento, programas governamentais, ações, indicadores, localizadores, PPAG (plano plurianual), or planning-side budget data. Covers the standard resources, how to bridge planejamento with execução (SISOR), and conventions.
---

# Working with SPLOR-MG SIGPLAN datapackages

SIGPLAN is the **state planning system** (programas, ações, localizadores,
indicadores) — the planning counterpart to SISOR's execution. Datapackages
follow the `dados-sigplan-planejamento[-<ano>]` and
`dados-sigplan-historico` naming.

## Known resources (from current snapshot)

<!-- TODO(team): replace these one-liners with authoritative descriptions -->

| Resource | What it is (one line) |
| --- | --- |
| `programas_planejamento` | Governmental programs. |
| `acoes_planejamento` | Actions inside programs. |
| `localizadores_todos_planejamento` | Localizadores (territorial / functional locators). |
| `indicadores_planejamento` | Indicators attached to programs/actions. |

Verify in `inspect_datapackage` — schemas vary.

## Bridging planejamento ↔ execução

A common request is "how much was planned vs executed for program X". The
shape of that question:

1. Identify the program code from SIGPLAN (`programas_planejamento.cd_programa`
   — verify the actual field name).
2. Identify the corresponding ações (`acoes_planejamento` filtered by the
   program code).
3. Use those codes against SISOR's QDD resources (likely on `cd_acao`).
4. Join client-side.

<!-- TODO(team): document canonical join keys between planejamento and SISOR -->

## Histórico vs yearly

- `dados-sigplan-planejamento-<YYYY>` — single-year planning snapshot.
- `dados-sigplan-historico` — multi-year accumulator. Use this when the user
  wants trend analysis without manually concatenating years (see
  [[splor-temporal-analysis]]).

## Indicators

`indicadores_planejamento` typically has:

<!-- TODO(team): confirm field set, especially metas-vs-realizado convention -->

- Indicator code + label
- Meta planejada
- Realizado (when available)
- Periodicity (often annual)

Be careful: realizado may lag the planning data by one full exercise. Check
the descriptor's commit date.

## Common pitfalls

<!-- TODO(team): fill from real incidents -->

- Programs can be reorganized between exercises (codes reused for different
  programs over time) — when crossing years, always check program continuity
  with the user, don't assume `cd_programa` is stable.
- Localizadores can be territorial, functional, or both depending on the
  exercise's reform of the planning structure.
