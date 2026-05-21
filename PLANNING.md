# dpm-mcp — Planning

Living document. Reflects current scope, what's shipped, what's pending, and
the active design constraints. For decision rationale and conversation
history, see [`HISTORY.md`](HISTORY.md).

Last updated: 2026-05-21.

---

## Mission

Expose [splor-mg/dpm](https://github.com/splor-mg/dpm) download capabilities
as an MCP server so any MCP-capable agent (Claude Code, Claude Desktop,
Cursor, custom SDK clients) can:

- discover the SPLOR-MG frictionless datapackage catalog,
- inspect a datapackage's metadata without downloading data,
- download one or many datapackages (descriptor + selected resources),
- accept a `data.toml` manifest identical to upstream `dpm install`.

## Hard constraints (invariants)

1. **Read-only.** Never issue writes (POST/PUT/PATCH/DELETE) to any remote.
   No pushes, no uploads, no repo modifications.
2. **Tokens are secrets.** `GITHUB_TOKEN` and `DPM_MCP_AUTH_TOKEN` are never
   logged, never echoed in tool responses, never persisted.
3. **Compatibility with upstream `data.toml`.** `token = "ENV_VAR_NAME"` is
   indirection (env var name), not a literal PAT — must keep working.
4. **MCP-client agnostic.** Skills are a Claude-only optimization; everything
   the agent *needs* must be reachable through MCP tools/prompts.

## Current architecture

```
┌─────────────────────────────┐
│ MCP client (Claude, etc.)   │
└─────────────┬───────────────┘
              │ stdio | streamable-http (Bearer)
              ▼
┌─────────────────────────────┐
│ dpm-mcp (FastMCP)           │
│  • discovery tools          │
│  • download tools           │
│  • install_from_toml        │
│  • catalog cache (in-mem)   │
└─────────────┬───────────────┘
              │ GET only (httpx)
              ▼
   api.github.com / raw.githubusercontent.com
```

### Modules

| File | Purpose |
| --- | --- |
| `src/dpm_mcp/server.py` | FastMCP instance, tool registration, HTTP runner + bearer middleware mount. |
| `src/dpm_mcp/auth.py` | PAT resolution: literal → env var name → `GITHUB_TOKEN`. |
| `src/dpm_mcp/http_auth.py` | Starlette middleware for `DPM_MCP_AUTH_TOKEN` (constant-time compare). |
| `src/dpm_mcp/url_utils.py` | GitHub URL parsing (repo URL ↔ raw URL ↔ descriptor URL). |
| `src/dpm_mcp/github.py` | Org/user repo discovery + datapackage detection. |
| `src/dpm_mcp/datapackage.py` | `inspect_datapackage` and `download_datapackage` (frictionless + httpx). |
| `src/dpm_mcp/toml_loader.py` | `install_from_toml` parser, DPM-compatible. |
| `src/dpm_mcp/catalog.py` | In-memory TTL catalog: build, cache, filter, summarize. |
| `src/dpm_mcp/models.py` | Pydantic models for tool responses. |
| `skills/*.md` | Claude-only skill skeletons (workflow + domain knowledge). |

### Transports

- `stdio` (default — for local MCP clients).
- `streamable-http` on `0.0.0.0:8000`, mounts `/mcp` plus `/health`.
- `sse` is wired but not the primary deployment target.

## Tools shipped

| Tool | Purpose |
| --- | --- |
| `get_catalog_summary` | Cached orientation: counts, owners, top resources. |
| `search_datapackages` | Filter the cached catalog by query/resource/field/owner. |
| `list_org_datapackages` | Raw listing (one GitHub org). |
| `list_user_datapackages` | Raw listing (one GitHub user). |
| `inspect_datapackage` | Metadata + resource schemas, no data download. |
| `download_datapackage` | Single repo or descriptor → descriptor + resources to disk. |
| `bulk_download` | Many sources in one call (good for whole-org pulls). |
| `install_from_toml` | Upstream `data.toml` manifest support. |

Plus an `mcp.resource("dpm-mcp://about")` describing the discovery flow.

## Skills shipped (Claude clients only)

| Skill | When agent invokes it |
| --- | --- |
| `skills/splor-dpm-conventions.md` | Any `dpm-mcp` discovery/download question. |
| `skills/splor-temporal-analysis.md` | Cross-year comparisons over `dados-<sistema>-<YYYY>`. |
| `skills/splor-sisor.md` | SISOR execução / QDD / obras. |
| `skills/splor-sigplan.md` | SIGPLAN planejamento / programas / indicadores. |

All skills contain TODO markers for team-specific knowledge.

## Deployment

- Multi-stage `Dockerfile` (python:3.11-slim + uv builder → slim runtime).
- Designed for **EasyPanel** "App via Git" deploy, port 8000.
- Bearer auth required for streamable-http (`DPM_MCP_AUTH_TOKEN`).
- `GITHUB_TOKEN` is server-fixed (not passed per-call) in HTTP deployments.

## What's done

- [x] Plan + initial scaffolding (`pyproject.toml`, `uv.lock`).
- [x] Auth resolution (literal PAT / env var name / `GITHUB_TOKEN`).
- [x] GitHub org/user discovery with datapackage detection.
- [x] `inspect_datapackage` (frictionless-based, custom HTTP session).
- [x] `download_datapackage` (httpx streaming, embeds commit SHA in descriptor).
- [x] `bulk_download`.
- [x] `install_from_toml` (DPM-compatible manifest).
- [x] HTTP transport with bearer middleware + `/health` route.
- [x] Multi-stage Dockerfile + EasyPanel deployment recipe.
- [x] Catalog (`catalog.py`) with TTL cache, parallel discovery, error capture.
- [x] `search_datapackages` and `get_catalog_summary` MCP tools.
- [x] 4 skill skeletons + `skills/README.md` install guide.
- [x] 29/29 unit tests passing.
- [x] Smoke test against `splor-mg` (12 packages, 93 resources, 0 errors).
- [x] README documents all tools, env vars, EasyPanel deploy, skills.

## Roadmap / pending

Priorities approximate; reorder as needed.

### Near-term

- [ ] **Deploy to EasyPanel** and validate the streamable-http transport
      end-to-end with a real Claude Code session.
- [ ] **Fill TODOs in `skills/*.md`** with team-specific conventions
      (canonical column names, real gotchas, SISOR↔SIGPLAN join keys).
- [ ] **Improve `search_datapackages` ranking.** Free-text query currently
      AND-matches across name + title + resource names + field names. A "sisor"
      query also matched a SIGPLAN package via a field name. Add a per-field
      score (name > title > resource_name > field_name) and surface ranking
      in results.
- [ ] **GitHub Actions CI.** `uv sync` + `pytest` + `ruff check` on PRs.

### Medium-term

- [ ] **MCP Prompts** equivalent to the four skills, for non-Claude clients.
- [ ] **Tests for HTTP middleware** (`http_auth.py`).
- [ ] **Test against private repos** (manual; needs a fixture PAT).
- [ ] **Catalog persistence option** (SQLite/JSON on disk) for cold-start
      latency on serverless hosts. Current in-memory TTL is fine for
      EasyPanel's long-lived container but won't survive restarts.
- [ ] **Surface descriptor freshness in summary** — propagate `remote.sha` /
      commit date into `CatalogEntry` so the agent can warn about stale data.

### Longer-term / speculative

- [ ] **Port `dpm load` / `dpm concat`** from upstream — currently we only
      mirror discovery + download.
- [ ] **Pagination for very large catalogs** if SPLOR ever exceeds a few hundred
      packages.
- [ ] **Download progress reporting** for the MCP client (FastMCP supports
      progress notifications).
- [ ] **CHANGELOG.md** once we cut a `0.1.0` release.

## Out of scope (explicitly)

- Writing/pushing to any remote (see invariant #1).
- Running analytical SQL on downloaded data — that's the client's job
  (DuckDB / pandas / polars).
- Replacing SISOR / SIGPLAN as systems of record. Downloads are snapshots;
  legal/audit references must cite upstream directly.
- Exposing the raw `dpm` CLI — `dpm-mcp` re-implements only the read-side
  surface area needed by agents.

## Picking up the work (cold start)

If you're a fresh session — read this, then `HISTORY.md`, then start.

1. `uv sync && uv run pytest` — confirm baseline (expect 29/29).
2. **The next thing on the list** is *deploy to EasyPanel*. Dockerfile,
   bearer auth, `/health` endpoint, env-var docs are all already in place.
   What's missing is the actual App-service creation in EasyPanel by the
   user, then a Claude Code session pointing at `https://<domain>/mcp` to
   validate end-to-end.
3. After that, **fill skills/*.md TODOs** — only the user has the domain
   knowledge needed for that.
4. Then search ranking + CI (see roadmap below).

Useful entry points for orientation:

- `README.md` — public-facing usage + env vars + EasyPanel recipe.
- `HISTORY.md` — decision log + verbatim auto-memory (carries across PCs).
- `src/dpm_mcp/server.py` — every MCP tool registration is here.
- `src/dpm_mcp/catalog.py` — newest module; the catalog cache + search logic.
- `skills/` — Claude-only workflow knowledge.

## Open questions

- Do we want a project-level vs user-level recommendation for installing
  skills inside SPLOR machines? (Currently `skills/README.md` documents both.)
- For private repos: keep `GITHUB_TOKEN` only server-side, or also accept a
  per-call PAT from trusted clients? (Today both work; need a policy.)
- Should `bulk_download` cap concurrency more conservatively for unauthenticated
  callers to avoid 60 req/hour exhaustion? (Currently 8.)
