# dpm-mcp — Conversation history, decisions, pending

Narrative log of design decisions and the discussions behind them. For the
current scope/roadmap snapshot see [`PLANNING.md`](PLANNING.md). For initial
prompt see [`initial-prompt.md`](initial-prompt.md).

Format: append-only. Each session block lists what was asked, what was
decided, and the rationale.

---

## Session 1 — Initial scaffolding (2026-05-21)

**Asked:** Build an MCP server wrapping [splor-mg/dpm](https://github.com/splor-mg/dpm)
so any MCP-capable agent can download frictionless datapackages. Must include
discovery of all datapackages in a GitHub org/user, single-URL repo download,
support DPM's parameterizations (resource filtering, output dir), preparation
for GitHub PAT / private repos. **Must never write/push/upload to remote.**
"Crie o planejamento e logo em seguida comece a implementação."

**Decisions:**

- **FastMCP from the official MCP Python SDK** instead of hand-rolling — most
  modern + maintained surface, supports stdio/SSE/streamable-http transports.
- **Python 3.11+, `uv`, hatchling backend.** Matches upstream DPM stack.
- **`httpx` async** for all HTTP. **`frictionless`** for descriptor inspection
  (uses upstream's own parsing rules — fewer drift bugs).
- **Pydantic v2 models** for every tool response — cleaner contracts for MCP
  schema introspection.
- **Token resolution chain** (`auth.py`): literal PAT (regex `^(gh[pousr]_|github_pat_)`)
  → env var name → process `GITHUB_TOKEN`. Keeps backward compatibility with
  upstream DPM's `data.toml` `token = "ENV_VAR_NAME"` indirection.
- **Read-only invariant:** module surface only uses `GET`. No POST/PUT/PATCH/DELETE
  anywhere. Documented in README + PLANNING + skills.

**Tools shipped:** `list_org_datapackages`, `list_user_datapackages`,
`inspect_datapackage`, `download_datapackage`, `bulk_download`,
`install_from_toml`.

**Fixes along the way:**

- Default package name was falling back to `"datapackage.json"` when fetching
  from a raw URL → now uses the GitHub **repo name** via `parse_github_url`.
- 403 warnings on private-repo content probing were noisy → demoted to debug
  level; only true 401s warn.
- 429 from GitHub now raises the same friendly "exceeded rate limit, provide
  `GITHUB_TOKEN`" message as 403.

---

## Session 2 — EasyPanel deployment (2026-05-21)

**Asked:** "Tenho um projeto onde subo as aplicações num EasyPanel, consigo
subir o MCP lá e você testar?" Followed by three preference choices.

**Decisions (via AskUserQuestion):**

| Question | Choice |
| --- | --- |
| Transport | `streamable-http` |
| Auth | Static bearer token |
| GitHub token | Server-fixed env var (not per-call) |

**Implementation:**

- Added `http_auth.py` — Starlette `BearerTokenMiddleware`, exempts `/health`,
  `/healthz`, `/readyz`, uses `hmac.compare_digest` for constant-time comparison.
- Added `_run_http()` to `server.py` — uvicorn on `0.0.0.0:8000`, mounts the
  FastMCP HTTP app and a `/health` route.
- Multi-stage `Dockerfile` (builder with `uv`, runtime non-root, `urllib`-based
  HEALTHCHECK).
- Env vars introduced: `DPM_MCP_TRANSPORT`, `DPM_MCP_HOST`, `DPM_MCP_PORT`,
  `DPM_MCP_AUTH_TOKEN`.

**Local Docker build failed** due to corporate proxy timeouts against
pypi/ghcr. Fix was `UV_HTTP_TIMEOUT=120` + `UV_CONCURRENT_DOWNLOADS=4` in the
Dockerfile. EasyPanel's own build environment is unaffected.

**Authorization given:** "apos terminar faça commit e push do trabalho."
Scope = this batch only; future pushes re-confirmed each time.

---

## Session 3 — Scaling to a large catalog (2026-05-21)

**Asked:** "Hoje tenho mais de 80 datapackages diferentes (mais de 100 contando
privados). Adicionar todos ao contexto não seria má prática? Quais técnicas se
usa nesse caso?"

**Discussion:** Options were stuffing the system prompt, MCP prompts (static),
or a lazy MCP tool that filters on demand. The user followed up with a question
about **Claude Skills** — "skill para cada datapackage, ou para grupos
temáticos / variações de ano (dados-sisor-2023, etc.)?"

**Decision: combine both layers.**

- **Layer A — MCP tools (universal):** lazy-loaded catalog with TTL cache, plus
  `search_datapackages` and `get_catalog_summary`. Works in any MCP client.
- **Layer B — Skills (Claude-only):** thematic, not per-datapackage. One skill
  per **subject area** (SISOR, SIGPLAN), one for **cross-cutting workflow**
  (`splor-temporal-analysis`), one for **conventions** (`splor-dpm-conventions`).
  Per-datapackage skills rejected — would balloon and duplicate what
  `inspect_datapackage` already returns.

**Reasoning for the two-layer split:**

- MCP tools must work for non-Claude clients (Cursor, custom SDK agents).
- Skills are great for stable workflow knowledge that doesn't change per
  release — they don't bloat context because Claude reads only the
  frontmatter `description` until the body is needed.
- Per-datapackage info is volatile (schemas evolve) → keep it in the live
  catalog, not in static markdown.

---

## Session 4 — Implementation (catalog + skills) (2026-05-21)

**Asked:** "sim implemente" (in response to the offer of catalog + 4 skill
skeletons).

**Implementation:**

- `src/dpm_mcp/catalog.py` — `CatalogEntry`, `ResourceEntry`, `FieldEntry`,
  `CatalogSummary` Pydantic models. `build_catalog` parallelizes discovery
  (`asyncio.Semaphore`) and bypasses frictionless for descriptor parsing (direct
  `json` / `yaml`) to keep memory low. `CatalogCache` is in-memory, TTL-bound
  (default 3600s), with double-checked locking around an `asyncio.Lock` for
  single-flight refresh.
- Default sources via `DPM_MCP_CATALOG_SOURCES` (e.g., `org:splor-mg`).
- Skills under `skills/` with YAML frontmatter (`name`, `description`) so
  Claude can decide relevance from the metadata alone. Every file marks
  team-knowledge gaps with `<!-- TODO(team): ... -->`.

**Smoke test (against splor-mg):** 12 packages, 93 resources, 0 errors.
`query="sisor"` returned 4 packages but one was `dados-sigplan-planejamento-2024`
matching via a shared field name → noted as a future ranking improvement.

**Tests:** 29/29 passing (catalog filtering, source parsing, summarize,
URL utils, auth, toml loader).

---

## Session 5 — Documentation pass (2026-05-21)

**Asked:** "Atualize o planning, readme e crie um documento com histórico
nosso de conversa, decisões e pendências."

**Changes:**

- Created `PLANNING.md` — single-source-of-truth for current state + roadmap.
- Created this `HISTORY.md` — narrative log of decisions and their rationale.
- Updated `README.md` to link both at the top of the doc.

---

## Pending items (forward-looking)

Maintained here for quick scan; mirrors the roadmap in `PLANNING.md`.

### Near-term

- [ ] **Deploy to EasyPanel** and run a real Claude Code session through it.
- [ ] **Fill `skills/*.md` TODOs** with team conventions (column meanings,
      canonical joins between SISOR↔SIGPLAN, real gotchas from past incidents).
- [ ] **Search ranking:** weight matches by field (name > title > resource > field).
- [ ] **CI (GitHub Actions):** `uv sync` + `pytest` + `ruff check` on PRs.

### Medium-term

- [ ] **MCP Prompts** mirroring the skills, for non-Claude clients.
- [ ] **Tests for `http_auth.py`** (bearer middleware behavior).
- [ ] **Private-repo validation** with a fixture PAT.
- [ ] **Surface descriptor freshness** (`remote.sha` + commit date) in catalog
      entries so the agent can warn about stale snapshots.

### Speculative

- [ ] **Port `dpm load` / `dpm concat`** from upstream.
- [ ] **Persistent catalog** (SQLite/JSON) for cold-start latency.
- [ ] **Progress notifications** during long downloads.
- [ ] **CHANGELOG.md** at the first tagged release.

## Conventions & user preferences captured

- Communication language: **PT-BR** in chat replies, **EN** in code/docs unless
  otherwise marked.
- Memory layer at `~/.claude/projects/.../memory/` records project facts (see
  the verbatim copies in the next section — they don't travel across machines).
- Push authorization is **per-batch** — never assume open-ended.

---

## Resume from another machine

Auto-memory lives at `~/.claude/projects/C--splor-mg-code-dpm-mcp/memory/` and
is **per-machine**. The relevant entries are copied below so a fresh Claude
session on a different PC can pick up cold.

### Project facts (from `project_dpm_mcp.md`)

> dpm-mcp wraps the SPLOR-MG `dpm` Python tool (https://github.com/splor-mg/dpm)
> as an MCP server. Built fresh in this repo (2026-05-20) — not a fork,
> separate codebase. Uses FastMCP from the official `mcp` Python SDK, `uv`
> for dependency management, `httpx` async, and `frictionless` (same library
> DPM uses) so descriptor parsing stays consistent with upstream.
>
> **Why:** SPLOR-MG team wants any MCP-capable agent (Claude Desktop, Claude
> Code, etc.) to discover and download data from their frictionless
> datapackages hosted across GitHub repos.
>
> **How to apply:**
> - Hard rule: the MCP must NEVER write/push/upload to any remote repository.
>   Only GET requests to GitHub. Design decisions must preserve this invariant.
> - PAT handling already implemented; user will decide later whether to
>   actually require it or stay on dev environment's git creds.
> - The original DPM `data.toml` format is the source of truth for the
>   `install_from_toml` tool — keep that compatibility.

### DPM token convention (from `reference_dpm_token_convention.md`)

> In the upstream `splor-mg/dpm` project, the `data.toml` `token` key's
> **value is the name of an environment variable** that holds the actual PAT
> — not the literal PAT itself. DPM does `os.getenv(source['token'])` to
> resolve it. In `dpm-mcp`, `dpm_mcp/auth.py::resolve_token` keeps this
> indirection for compatibility but also accepts literal PATs (detected by
> `ghp_`/`github_pat_` prefix) so MCP tool calls can pass a token directly.

### Upstream DPM (from `reference_dpm_upstream.md`)

> Upstream lives at https://github.com/splor-mg/dpm (mkdocs at
> https://splor-mg.github.io/dpm/). Key files when behaviour questions arise:
> `src/dpm/cli.py` (Typer entrypoints) and `src/dpm/install.py` (download
> logic — loads frictionless Package, filters resources, streams files,
> embeds commit SHA under `package.custom["remote"]`). Mirror
> `install.py::extract_source_package` when in doubt about download semantics.

### Setting up on the new PC

```bash
git clone https://github.com/labanca/dpm-mcp
cd dpm-mcp
uv sync                          # or: pip install -e .
cp .env.example .env             # add GITHUB_TOKEN if needed
uv run pytest                    # should be 29/29 passing
uv run dpm-mcp                   # stdio transport, sanity check
```

### Where to pick up

The next batch of work (top of the roadmap, see `PLANNING.md`):

1. **Deploy to EasyPanel** — Dockerfile is ready, just needs the user to
   actually create the App service in EasyPanel and set
   `DPM_MCP_AUTH_TOKEN` + `GITHUB_TOKEN`. Then validate end-to-end with a
   Claude Code session pointed at `https://<domain>/mcp`.
2. **Fill `skills/*.md` TODOs** with team-specific conventions — only the
   user has this knowledge (canonical column names, SISOR↔SIGPLAN join
   keys, real gotchas from past incidents).
3. **Search ranking improvement** in `search_datapackages` (weight name >
   title > resource_name > field_name) to fix the noted false positive
   where `query="sisor"` matched a SIGPLAN package.
4. **GitHub Actions CI** — `uv sync` + `pytest` + `ruff check` on PRs.

### Commits so far

```
a9b048d Add catalog discovery tools and skill skeletons
e37b611 Initial dpm-mcp implementation
721da89 Initial commit.
```

Remote is `https://github.com/labanca/dpm-mcp` (push origin/main).
