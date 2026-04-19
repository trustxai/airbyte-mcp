---
name: 001_airbyte_mcp_scaffolding
overview: Build `airbyte_mcp`, a FastMCP-based Python MCP server that wraps the Airbyte Public API (localhost `abctl`) with read-only tools for workspaces, sources, destinations, connections, and jobs. Ship two packaging entry points (`airbyte-mcp` stdio + `airbyte-mcp-http` streamable HTTP), a Dockerfile for stdio, an endpoint checklist, CLI test scripts, and full `README.md` + `docs/CONTRIBUTING.md`.
todos:
  - id: scaffold_project
    content: Create src/airbyte_mcp package layout, update pyproject.toml with dependencies + [project.scripts] entry points, refresh .gitignore, add .env.example, remove placeholder main.py
    status: completed
  - id: core_runtime
    content: Implement config.py (pydantic-settings), client.py (AirbyteClient with token exchange + cache + 401 retry), errors.py, formatters.py, server.py (FastMCP + main_stdio/main_http)
    status: completed
  - id: implement_tools
    content: Implement 11 read-only tools across tools/{health,workspaces,sources,destinations,connections,jobs}.py with Pydantic input models, docstrings, and read-only annotations; register via tools/__init__.py
    status: completed
  - id: scripts_folder
    content: Add scripts/get_token.py, scripts/list_workspaces.py, scripts/mcp_stdio_smoke.py + scripts/README.md
    status: completed
  - id: docs_folder
    content: Write docs/CONTRIBUTING.md, docs/SECURITY.md, docs/CHANGELOG.md (governance, UPPERCASE) and docs/endpoints.md, docs/authentication.md, docs/architecture.md (mermaid), docs/local-setup.md (content, lowercase kebab-case)
    status: completed
  - id: readme
    content: Rewrite README.md with intro, features, prerequisites, env setup, stdio + HTTP + Docker run instructions, tool list, links to docs/
    status: completed
  - id: docker
    content: Add Dockerfile (stdio, default CMD airbyte-mcp) and Dockerfile.http (streamable HTTP, EXPOSE 8000) plus .dockerignore
    status: completed
  - id: smoke_test
    content: Run uv sync, then `uv run airbyte-mcp --help` equivalent via MCP Inspector (`uv run mcp dev src/airbyte_mcp/server.py`) and the stdio smoke script against the user's local abctl instance to confirm tools return data
    status: completed
isProject: false
---

# Airbyte MCP Server — Implementation Plan

## 1. References and Design Principles

- Use the **official MCP Python SDK** (`mcp[cli]` >= 1.1) with **FastMCP** high-level API — same pattern shown in the [Pydantic AI MCP server docs](https://pydantic.dev/docs/ai/mcp/server/) and the [official python-sdk README](https://github.com/modelcontextprotocol/python-sdk).
- Follow `.cursor/skills/mcp-builder/reference/python_mcp_server.md` — server name `airbyte_mcp`, tool names prefixed `airbyte_`, Pydantic input models, comprehensive docstrings, proper annotations, `async` httpx.
- Two-entry-point pattern (per user decision): `airbyte-mcp` for stdio, `airbyte-mcp-http` for streamable HTTP (ready to deploy, not wired into infra yet).

## 2. Target Project Structure

```
airbyte-mcp/
├── README.md                       # Setup (stdio + HTTP), tools list, usage examples
├── pyproject.toml                  # deps + [project.scripts] entry points
├── uv.lock
├── .python-version                 # 3.13
├── .env.example                    # AIRBYTE_API_URL, AIRBYTE_CLIENT_ID, AIRBYTE_CLIENT_SECRET
├── .gitignore                      # add .env
├── .dockerignore
├── Dockerfile                      # stdio image (primary)
├── Dockerfile.http                 # HTTP image scaffolded for future deployment
├── docs/
│   ├── CONTRIBUTING.md             # UPPERCASE (governance) — fork/clone/uv/run/test, commit style, PR flow
│   ├── SECURITY.md                 # UPPERCASE (governance) — how to report vulnerabilities, supported versions
│   ├── CHANGELOG.md                # UPPERCASE (governance) — Keep a Changelog format, seeded with [Unreleased]
│   ├── endpoints.md                # lowercase (content)    — full Airbyte API endpoint checklist (grouped)
│   ├── authentication.md           # lowercase (content)    — abctl local credentials → token exchange
│   ├── architecture.md             # lowercase (content)    — FastMCP layout, transports, token cache
│   └── local-setup.md              # lowercase (content)    — abctl install / status / credentials walkthrough
├── scripts/
│   ├── README.md
│   ├── get_token.py                # Exchange client_id/secret for access_token
│   ├── list_workspaces.py          # Direct httpx call against Airbyte API
│   └── mcp_stdio_smoke.py          # Spawn server via stdio, list + call tools
└── src/
    └── airbyte_mcp/
        ├── __init__.py
        ├── __main__.py             # `python -m airbyte_mcp` → stdio
        ├── server.py               # FastMCP instance + main_stdio / main_http
        ├── config.py               # Settings (pydantic-settings, .env aware)
        ├── client.py               # AirbyteClient: token caching + httpx
        ├── errors.py               # _handle_api_error
        ├── formatters.py           # markdown/json response helpers
        └── tools/
            ├── __init__.py         # register_all(mcp)
            ├── health.py
            ├── workspaces.py
            ├── sources.py
            ├── destinations.py
            ├── connections.py
            └── jobs.py
```

`main.py` at repo root gets replaced by the packaged module. Keeping `.vscode/` as-is.

## 3. Dependencies (pyproject.toml)

```toml
[project]
name = "airbyte-mcp"
version = "0.1.0"
description = "MCP server for the Airbyte Public API (self-managed / Cloud)."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "mcp[cli]>=1.1.0",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "python-dotenv>=1.0",
]

[project.scripts]
airbyte-mcp = "airbyte_mcp.server:main_stdio"
airbyte-mcp-http = "airbyte_mcp.server:main_http"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/airbyte_mcp"]
```

## 4. Core Runtime Modules

### `src/airbyte_mcp/config.py`
`Settings` via `pydantic-settings` loading from env / `.env`:
- `AIRBYTE_API_URL` (default `http://localhost:8000/api/public/v1`)
- `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET` (required)
- `AIRBYTE_ACCESS_TOKEN` (optional override; if set, skip token exchange)
- `HTTP_HOST` (default `127.0.0.1`), `HTTP_PORT` (default `8000`)

### `src/airbyte_mcp/client.py`
`AirbyteClient` — single shared async client:
- Token exchange via `POST {base}/applications/token` using client_credentials.
- In-memory cache `(token, expires_at)` with ~30s safety margin; refresh on expiry or on 401 (one retry, per Airbyte docs).
- `request(method, path, **kwargs)` helper used by all tools.
- Uses `httpx.AsyncClient` with 30s timeout.

### `src/airbyte_mcp/server.py`
```python
from mcp.server.fastmcp import FastMCP
from .tools import register_all

mcp = FastMCP("airbyte_mcp")
register_all(mcp)

def main_stdio() -> None:
    mcp.run()  # stdio default

def main_http() -> None:
    from .config import get_settings
    s = get_settings()
    mcp.settings.host = s.http_host
    mcp.settings.port = s.http_port
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main_stdio()
```

## 5. Tools to Implement (Basic Scope — User-Selected A–G)

All tools: `readOnlyHint=True`, `destructiveHint=False`, `idempotentHint=True`, `openWorldHint=True`. Each tool supports `response_format: "markdown" | "json"` and list tools support `limit` (1–100, default 20) + `offset`.

| Tool name | HTTP call | Purpose |
|---|---|---|
| `airbyte_health_check` | `GET /health` | Ping API; reports OK / not reachable |
| `airbyte_list_workspaces` | `GET /workspaces` | List workspaces with pagination |
| `airbyte_get_workspace` | `GET /workspaces/{id}` | Workspace details |
| `airbyte_list_sources` | `GET /sources` | Filter by `workspaceIds`, pagination |
| `airbyte_get_source` | `GET /sources/{id}` | Source details (masked secrets) |
| `airbyte_list_destinations` | `GET /destinations` | Filter + pagination |
| `airbyte_get_destination` | `GET /destinations/{id}` | Destination details |
| `airbyte_list_connections` | `GET /connections` | Filter + pagination |
| `airbyte_get_connection` | `GET /connections/{id}` | Connection details incl. streams |
| `airbyte_list_jobs` | `GET /jobs` | Filter by `connectionId`, `jobType`, `status`, date range |
| `airbyte_get_job` | `GET /jobs/{id}` | Job details including bytes/rows synced |

Auth/token exchange is **internal** — not exposed as an MCP tool.

## 6. Docs (Markdown)

**Naming convention**: UPPERCASE for governance files GitHub surfaces automatically (`README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`), lowercase kebab-case for ordinary content docs (`endpoints.md`, `authentication.md`, etc.). Matches the [MCP python-sdk](https://github.com/modelcontextprotocol/python-sdk) and [Airbyte docs](https://github.com/airbytehq/airbyte/tree/master/docs) repos.

### Governance (UPPERCASE)

- **`README.md`** — project intro, features, prerequisites (`abctl`, Python 3.13, uv), env setup, two run modes:
  - Local stdio via `uv run airbyte-mcp`
  - Docker stdio via `docker build -t airbyte-mcp . && docker run --rm -i --env-file .env airbyte-mcp`
  - HTTP via `uv run airbyte-mcp-http` (http://127.0.0.1:8000/mcp) + Claude Code `claude mcp add --transport http airbyte http://127.0.0.1:8000/mcp`
  - Tool list with short descriptions + link to `docs/endpoints.md`.
- **`docs/CONTRIBUTING.md`** — blend of MCP python-sdk CONTRIBUTING + standard OSS patterns: local dev with `uv sync`, running MCP Inspector (`uv run mcp dev src/airbyte_mcp/server.py`), running the stdio smoke script, commit style (Conventional Commits), branch naming, PR checklist.
- **`docs/SECURITY.md`** — supported versions table, how to privately report vulnerabilities (email / GitHub Security Advisory), response SLA, note that API tokens/secrets must never appear in issues or logs.
- **`docs/CHANGELOG.md`** — [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) format, seeded with `[Unreleased]` section and `[0.1.0] - YYYY-MM-DD` with initial "Added" entries.

### Content (lowercase kebab-case)

- **`docs/endpoints.md`** — grouped checklist of every Airbyte endpoint (Health, Workspaces, Sources, Destinations, Connections, Jobs, Streams, Permissions, Users, Organizations, Tags, Source/Destination Definitions). Implemented ones `[x]`, pending `[ ]`.
- **`docs/authentication.md`** — how to get client_id/client_secret with `abctl local credentials`; `POST /applications/token` sample; 15-min expiry handling (note the 1.8.x bug and 2.0.0 fix).
- **`docs/architecture.md`** — mermaid diagram: MCP client ↔ FastMCP ↔ AirbyteClient (token cache) ↔ Airbyte REST.
- **`docs/local-setup.md`** — `abctl local install`, `abctl local status`, `abctl local credentials`, how to confirm `http://localhost:8000`.

## 7. Scripts (`scripts/`)

- `get_token.py` — standalone httpx script that reads `.env` and prints an access token. Useful to confirm abctl credentials work.
- `list_workspaces.py` — direct Airbyte API smoke test (bypass MCP) to validate connectivity.
- `mcp_stdio_smoke.py` — uses `mcp.ClientSession` + `stdio_client` to spawn the packaged server and exercise every tool (patterned after the `.cursor/skills/mcp-builder/scripts/connections.py` helper and the python-sdk client snippet).
- `scripts/README.md` — how to run each (uv, env vars).

## 8. Docker

- **`Dockerfile`** (stdio): `python:3.13-slim` → `uv sync --frozen` → `CMD ["airbyte-mcp"]`. Uses `--env-file .env` at runtime.
- **`Dockerfile.http`**: same base, `EXPOSE 8000`, `CMD ["airbyte-mcp-http"]`. Documented in README as “ready to deploy on Fly.io / Railway / Render” but not wired up yet.

## 9. Architecture Flow (for `docs/architecture.md`)

```mermaid
flowchart LR
    subgraph Client
        IDE[IDE / Claude Code]
    end
    subgraph Transport
        Stdio["`airbyte-mcp` (stdio)"]
        Http["`airbyte-mcp-http` (streamable HTTP)"]
    end
    subgraph Server[airbyte_mcp package]
        FastMCP[FastMCP instance]
        Tools[Tool modules]
        ACClient[AirbyteClient + token cache]
    end
    Airbyte[Airbyte Public API]

    IDE -->|stdio| Stdio
    IDE -->|HTTP| Http
    Stdio --> FastMCP
    Http --> FastMCP
    FastMCP --> Tools --> ACClient --> Airbyte
    ACClient -.->|"POST /applications/token"| Airbyte
```

## 10. Out of Scope (tracked in `docs/endpoints.md` as TODO)

- Mutations on sources/destinations/connections (create/update/delete).
- `POST /jobs` (trigger sync) + `DELETE /jobs/{id}` (cancel).
- `GET /streams`, permissions, users, organizations, tags, source/destination definitions.
- OAuth initiation flows.
- Evaluation XML (mcp-builder Phase 4) — can follow in a later plan.
