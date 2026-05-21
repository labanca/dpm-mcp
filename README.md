# dpm-mcp

**MCP server for the SPLOR-MG Data Package Manager.**

`dpm-mcp` exposes the download functionality of [splor-mg/dpm](https://github.com/splor-mg/dpm)
as [Model Context Protocol](https://modelcontextprotocol.io) tools, so any
MCP-capable agent (Claude Desktop, Claude Code, Cursor, custom agents, etc.)
can:

- discover all frictionless datapackages published by a GitHub org or user;
- inspect a datapackage's metadata without downloading data;
- download one or many datapackages (descriptor + selected resources) to disk;
- consume a `data.toml` manifest in exactly the same format the original `dpm install` uses.

**Read-only by design.** The server never issues writes (POST/PUT/PATCH/DELETE)
to any remote — no pushes, no uploads, no repo modifications.

---

## Requirements

- Python **3.11+**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

## Install

Clone this repo, then sync:

```bash
git clone https://github.com/splor-mg/dpm-mcp
cd dpm-mcp
uv sync
```

Or, with pip:

```bash
pip install -e .
```

## Configure (optional)

```bash
cp .env.example .env
# edit .env to add a GITHUB_TOKEN if you want private-repo access or higher rate limits
```

Environment variables read at startup:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GITHUB_TOKEN` | _unset_ | PAT for GitHub API + downloads. Required for private repos. |
| `DPM_MCP_OUTPUT_DIR` | `./datapackages` | Default download directory. |
| `DPM_MCP_TRANSPORT` | `stdio` | One of `stdio`, `sse`, `streamable-http`. |
| `DPM_MCP_LOG_LEVEL` | `INFO` | Standard Python logging level. |
| `DPM_MCP_CATALOG_SOURCES` | `org:splor-mg` | Comma-separated default sources for `search_datapackages` / `get_catalog_summary`. Items can be `org:NAME`, `user:NAME`, or a bare name (treated as org). |
| `DPM_MCP_CATALOG_TTL_SECONDS` | `3600` | How long the in-memory catalog is cached before refreshing on the next call. |

PAT scopes:
- Classic token: `repo` (private) or `public_repo` (public only).
- Fine-grained token: `Contents: Read`.

## Run

```bash
uv run dpm-mcp     # stdio transport, the default for MCP clients
```

For HTTP transport (remote deployments — see [Deploy on EasyPanel](#deploy-on-easypanel-or-any-docker-host)):

```bash
DPM_MCP_TRANSPORT=streamable-http DPM_MCP_AUTH_TOKEN=secret uv run dpm-mcp
```

---

## Wire into an MCP client

### Claude Code (CLI)

```bash
claude mcp add dpm-mcp \
  --scope user \
  -- uv --directory C:/splor-mg/code/dpm-mcp run dpm-mcp
```

Or edit `~/.claude.json` directly:

```json
{
  "mcpServers": {
    "dpm-mcp": {
      "command": "uv",
      "args": ["--directory", "C:/splor-mg/code/dpm-mcp", "run", "dpm-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxx_optional"
      }
    }
  }
}
```

### Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "dpm-mcp": {
      "command": "uv",
      "args": ["--directory", "C:/splor-mg/code/dpm-mcp", "run", "dpm-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxx_optional"
      }
    }
  }
}
```

### Cursor / Continue / other MCP clients

Any client that supports stdio MCP servers can use the same command:
`uv --directory <path-to-this-repo> run dpm-mcp`.

---

## Tools

### `get_catalog_summary(sources?, token?, force_refresh?)`

Returns an at-a-glance summary of the catalog (totals, packages per owner, most
common resource names, cache age). Use this as the **first** call when an agent
is orienting itself against a large catalog — it's small, cached, and tells you
what to drill into next.

```text
> what's in the splor-mg catalog?
```

If `sources` is omitted, the server falls back to `DPM_MCP_CATALOG_SOURCES`.

### `search_datapackages(query?, org?, user?, has_resource?, field_name?, ...)`

Filters the cached catalog without downloading any data. All filters are AND-ed:

- `query`: free-text — every word must appear (case-insensitive) somewhere in
  the package name, title, description, or any resource name / field name.
- `has_resource`: only packages exposing a resource by this name (case-insensitive
  substring match).
- `field_name`: only packages whose any resource schema has a field with this name.
- `org` / `user`: restrict to a specific owner. By default uses the catalog
  sources (see `DPM_MCP_CATALOG_SOURCES`).
- `include_private`, `include_archived`, `include_errors`, `limit`.

```text
> find datapackages in splor-mg related to "sisor"
> which packages expose a resource called "uo"?
```

Together with `inspect_datapackage` and `download_datapackage` this is the
recommended discovery flow when you have **dozens or hundreds** of datapackages
and don't want to bloat the agent context.

### `list_org_datapackages(org, token?, include_archived?, include_forks?)`

Returns every repository in a GitHub org that has a `datapackage.json`
(or `.yaml`/`.yml`) at the root of its default branch.

```text
> list every datapackage in splor-mg
```

### `list_user_datapackages(user, token?, ...)`

Same as above, for a user's repositories.

### `inspect_datapackage(source, ref?, token?)`

Returns descriptor metadata + resource list, without downloading data.
`source` accepts either a descriptor URL or a GitHub repo URL.

```text
> what's inside https://github.com/splor-mg/sisor-dados-2024 ?
```

### `download_datapackage(source, output_dir?, resources?, package_name?, ref?, token?)`

Downloads the descriptor + selected resources.

- `source`: descriptor URL **or** repo URL.
- `resources`: optional list of resource names to keep (others skipped).
- `package_name`: optional override for the destination subfolder name.
- `ref`: branch, tag, or commit SHA (repo URLs only).
- `token`: literal PAT or env-var name (DPM-style).

```text
> download base_qdd_plurianual from https://github.com/splor-mg/sisor-dados-2024
```

### `bulk_download(sources, output_dir?, resources?, token?, continue_on_error?)`

Downloads many datapackages in a single call — combine with
`list_org_datapackages` to grab a whole org.

```text
> list all datapackages in splor-mg then download them all to ./splor-data
```

### `install_from_toml(descriptor_path, output_dir?, packages?, token?)`

Installs from a `data.toml` manifest — the exact format `dpm install` expects:

```toml
[packages]

[packages.sisor]
path = "https://raw.githubusercontent.com/splor-mg/sisor-dados-2024/main/datapackage.json"
resources = ["base_qdd_plurianual"]

[packages.reest]
path = "https://raw.githubusercontent.com/splor-mg/dados-reestimativa/main/datapackage.json"
token = "GITHUB_TOKEN"     # name of an env var holding the PAT
```

```text
> install everything in data.toml into ./datapackages
```

---

## How auth resolves (per call)

For each tool call:

1. The `token` argument, if it looks like a literal PAT (`ghp_…`, `github_pat_…`), is used as-is.
2. Otherwise, if `token` matches the name of an env var, that env var's value is used.
3. Otherwise, `GITHUB_TOKEN` from the process environment is used.
4. Otherwise the request is sent unauthenticated (60 req/hour, public repos only).

This mirrors the original DPM's `data.toml` convention where `token =
"ENV_VAR_NAME"` is an indirection — making `data.toml` files written for `dpm`
work unchanged with `install_from_toml`.

---

## Deploy on EasyPanel (or any Docker host)

`dpm-mcp` ships with a multi-stage `Dockerfile` that produces a small image
running the `streamable-http` transport on port `8000` with a `/health`
endpoint.

### EasyPanel — App via Git

1. **Create a new "App" service** in your EasyPanel project, source = this Git repo (branch `main`).
2. **Build**: Dockerfile (default — no build args needed).
3. **Port**: expose `8000`.
4. **Environment variables**:

    | Key | Value | Notes |
    | --- | --- | --- |
    | `DPM_MCP_AUTH_TOKEN` | a long random string | **Required.** Bearer token clients must present. Generate with `openssl rand -hex 32`. |
    | `GITHUB_TOKEN` | your GitHub PAT | Needed for private repos / higher API rate limit. Mark as **secret**. |
    | `DPM_MCP_TRANSPORT` | `streamable-http` | (Dockerfile already sets this.) |
    | `DPM_MCP_HOST` | `0.0.0.0` | (Dockerfile already sets this.) |
    | `DPM_MCP_PORT` | `8000` | (Dockerfile already sets this.) |
    | `DPM_MCP_LOG_LEVEL` | `info` | Optional. |

5. **Domain**: attach a domain or use the EasyPanel-provided subdomain. Enable
   HTTPS — the bearer token only travels safely over TLS.
6. **Healthcheck**: HTTP GET `/health`, expects `200 ok` (already configured
   in the Dockerfile too).
7. **Deploy.** After it's up, `curl https://<your-domain>/health` should print
   `ok`. The MCP itself lives at `https://<your-domain>/mcp` and requires the
   bearer token.

### Local Docker test

```bash
docker build -t dpm-mcp .
docker run --rm -p 8000:8000 \
    -e DPM_MCP_AUTH_TOKEN=mysecret \
    -e GITHUB_TOKEN=ghp_xxx \
    dpm-mcp
# in another shell:
curl http://localhost:8000/health
```

### Add the deployed server to Claude Code

```bash
claude mcp add --transport http --scope user \
    dpm-mcp https://<your-domain>/mcp \
    --header "Authorization: Bearer <your DPM_MCP_AUTH_TOKEN>"
```

Or edit `~/.claude.json`:

```json
{
  "mcpServers": {
    "dpm-mcp": {
      "transport": "http",
      "url": "https://<your-domain>/mcp",
      "headers": { "Authorization": "Bearer <your DPM_MCP_AUTH_TOKEN>" }
    }
  }
}
```

Restart Claude Code and check with `claude mcp list`. Any MCP-capable agent
(Claude Desktop, Cursor, custom SDK clients) can connect the same way.

---

## Security model

- The server **never** issues writes against any remote (no POST/PUT/PATCH/DELETE
  to GitHub or any data host). Only GET requests.
- With `DPM_MCP_AUTH_TOKEN` set, every HTTP request except `/health` requires a
  matching `Authorization: Bearer <token>` header (constant-time compared).
- The `GITHUB_TOKEN` configured on the server **never** leaves the server: it
  is used only to sign outgoing requests to `api.github.com` and
  `raw.githubusercontent.com`. It is never echoed in tool responses.
- Keep TLS enabled in front of the container — the bearer token authenticates
  every call, so an interceptor with the token has full server access.

---

## Skills (Claude clients)

For Claude Code / Claude Desktop / Claude.ai users, this repo ships a set of
**skill skeletons** under [`skills/`](skills/). They encode workflow knowledge
that the MCP tools alone can't carry — naming conventions, how to combine
multiple datapackages, multi-year analysis patterns, SISOR/SIGPLAN domain hints.

Skills are **lazy-loaded by the agent** (Claude reads the `description`
frontmatter and pulls the full body only when relevant), so they don't bloat
your context window even as the catalog grows.

To install:

```powershell
# Windows — user-level (all sessions)
Copy-Item .\skills\*.md "$env:USERPROFILE\.claude\skills\" -Force
```

```bash
# macOS / Linux — user-level
cp skills/*.md ~/.claude/skills/
```

Project-level installation (`.claude/skills/` inside a given repo) is also
supported. See [`skills/README.md`](skills/README.md) for details — most files
contain TODO blocks where you should add team-specific conventions before
trusting the agent with them.

> **Non-Claude MCP clients** (Cursor, custom agents) don't load `.md` skills.
> If you need equivalent guidance there, port the contents of `skills/*.md`
> into your project system prompt or expose them as MCP prompts.

---

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
```

## License

MIT.
