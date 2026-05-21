# dpm-mcp skills (skeletons)

These markdown files are **starting points** for Claude Code / Claude Desktop
skills that complement the `dpm-mcp` MCP server. They encode workflow
knowledge that doesn't change every release (domain conventions, how to combine
tools, common gotchas) — leaving the live catalog data to the MCP itself.

> **Skills are client-side.** They live on the agent's machine and only work
> in Claude clients (Claude Code, Claude Desktop, Claude.ai). For non-Claude
> MCP clients (Cursor, custom agents), the equivalent knowledge would need to
> be exposed via MCP prompts or baked into a project system prompt — these
> skill files can still be used as source material.

## Installation

### User-level (available in every session)

Copy the files into your user skills directory:

```powershell
# Windows
Copy-Item .\skills\*.md "$env:USERPROFILE\.claude\skills\" -Force

# macOS / Linux
cp skills/*.md ~/.claude/skills/
```

### Project-level (available only inside a given repo)

```bash
mkdir -p .claude/skills && cp /path/to/dpm-mcp/skills/*.md .claude/skills/
```

Restart Claude Code (or refresh skills) afterward.

## What's here

| File | When the agent invokes it |
| --- | --- |
| `splor-dpm-conventions.md` | Any question touching `dpm-mcp` discovery/download workflow. |
| `splor-temporal-analysis.md` | Cross-year comparisons over yearly-versioned datapackages. |
| `splor-sisor.md` | Anything about SISOR execução / quadro de detalhamento. |
| `splor-sigplan.md` | Anything about SIGPLAN planning data. |

**These are skeletons.** Every domain skill has TODO blocks where you should
fill in conventions only your team knows (column meanings, gotchas, business
rules, canonical analyses). Treat them as a starting structure, not finished
documentation.
