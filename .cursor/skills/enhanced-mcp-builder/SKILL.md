---
name: enhanced-mcp-builder
description: Scaffold a complete Python MCP server from an external API, including API research, project structure, rich tool docstrings, Docker support, and client configuration. Use when building a new MCP server from scratch to integrate with an external REST API, or when the user says "build an MCP", "create an MCP server", or "integrate API X via MCP".
---

# Enhanced MCP Builder (Python / FastMCP)

End-to-end workflow for creating a production-ready Python MCP server
from an external REST API. Builds on the [mcp-builder](../mcp-builder/SKILL.md)
skill with concrete scaffolding templates, richer docstrings, Docker
support, and client configuration patterns.

## Phase 1: API Research

Before writing code, deeply understand the target API.

### 1.1 Gather API documentation

1. **Find the API reference** — search for `{service} API reference`,
   `{service} REST API docs`, `{service} OpenAPI spec github`.
2. **Fetch the OpenAPI spec** if available (YAML or JSON). This is the
   single best source for enumerating every endpoint.
3. **Fetch the official docs** via WebFetch or the docs MCP server if
   one exists (e.g. `user-airbyte-docs`).
4. **Fetch the MCP Python SDK README** for the latest patterns:
   `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`

### 1.2 Build the endpoint checklist

Create `docs/endpoints.md` with every API endpoint grouped by resource.
Mark which ones will be implemented in the first pass.

```markdown
## Sources
- [x] `GET /sources` — list sources
- [x] `GET /sources/{sourceId}` — get source by ID
- [ ] `POST /sources` — create source
- [ ] `PATCH /sources/{sourceId}` — update source
- [ ] `DELETE /sources/{sourceId}` — delete source
```

### 1.3 Scope the first pass

Ask the user (or infer) which endpoints to implement first.
Good default: **read-only operations on core resources** (list + get).

---

## Phase 2: Project Scaffolding

Use the `src/` layout with hatchling. See [project-scaffolding.md](reference/project-scaffolding.md) for the full template.

### Key files

```
{service}-mcp/
├── pyproject.toml          # hatchling, entry points, deps
├── src/{service}_mcp/
│   ├── __init__.py
│   ├── __main__.py          # python -m {service}_mcp
│   ├── server.py            # FastMCP + main_stdio / main_http
│   ├── config.py            # pydantic-settings
│   ├── client.py            # async httpx client + token mgmt
│   ├── errors.py            # centralised error handler
│   ├── formatters.py        # ResponseFormat, pagination, epoch→human
│   └── tools/
│       ├── __init__.py      # register_all()
│       ├── health.py
│       ├── {resource_a}.py
│       └── {resource_b}.py
├── docs/                    # UPPERCASE governance, lowercase content
├── scripts/                 # CLI smoke tests
├── Dockerfile               # stdio
├── Dockerfile.http          # streamable HTTP
├── .env.example
└── .gitignore
```

### pyproject.toml essentials

```toml
[project.scripts]
{service}-mcp     = "{service}_mcp.server:main_stdio"
{service}-mcp-http = "{service}_mcp.server:main_http"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{service}_mcp"]
```

### Core dependencies

```toml
dependencies = [
    "mcp[cli]>=1.1.0",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "python-dotenv>=1.0",
]
```

---

## Phase 3: Core Runtime Modules

### config.py

Use `pydantic-settings` to load from env vars / `.env`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )
    {service}_api_url: str = "https://api.example.com/v1"
    {service}_client_id: str = ""
    {service}_client_secret: str = ""
    {service}_access_token: str = ""
    http_host: str = "127.0.0.1"
    http_port: int = 8080
```

### client.py

Implement an async httpx client with:
- **Token exchange** via client credentials (if the API uses OAuth).
- **In-memory token cache** with a safety margin before expiry.
- **Automatic 401 retry** — clear cache, re-auth, retry once.
- **Singleton** via `get_client()`.

### errors.py

Map HTTP status codes to actionable, LLM-friendly messages:
- 400 → "Bad request — the API rejected the input."
- 401 → "Unauthorized — token invalid or expired."
- 404 → "Not found — double-check the resource ID."
- 429 → "Rate limited — wait before retrying."
- Timeout → "Request timed out. Is the server running?"
- ConnectError → "Could not connect. Verify URL and server status."

### formatters.py

- `ResponseFormat` enum (markdown / json).
- `to_json()` — pretty-print with `default=str`.
- `epoch_to_human()` — epoch seconds to `YYYY-MM-DD HH:MM:SS UTC`.
- `paginated_response()` — renders items in markdown or JSON with
  count, offset, has_more, next offset.

### server.py

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("{service}_mcp")

from {service}_mcp.tools import register_all
register_all(mcp)

def main_stdio() -> None:
    mcp.run()

def main_http() -> None:
    from {service}_mcp.config import get_settings
    s = get_settings()
    mcp.settings.host = s.http_host
    mcp.settings.port = s.http_port
    mcp.run(transport="streamable-http")
```

---

## Phase 4: Tool Implementation

### Naming

`{service}_{action}_{resource}` in snake_case. Always prefix with
the service name.

### Input models

Pydantic `BaseModel` with `ConfigDict(str_strip_whitespace=True, extra="forbid")`.
Every `Field` has a `description`. Use `ge`, `le`, `min_length`, etc.

### Rich docstrings

This is critical — the docstring is the **only** thing the LLM sees.
See [rich-docstrings.md](reference/rich-docstrings.md) for the full template.

Every tool docstring must include:

1. **One-line summary** — what the tool does.
2. **Context** — explains the domain concept the tool operates on.
3. **When to Use** — concrete scenarios.
4. **When NOT to Use** — redirects to the correct alternative tool.
5. **Returns** — field list for both markdown and JSON formats.
6. **Pagination** (list tools) — limit/offset range and defaults.
7. **Filters** (if applicable) — all combinable filter options.
8. **Examples** — concrete parameter objects.
9. **Error Handling** (get tools) — common error codes.

### Annotations

Every `@mcp.tool()` decorator must include:
```python
annotations={
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

---

## Phase 5: Docker and Client Configuration

See [docker-and-clients.md](reference/docker-and-clients.md) for
complete templates.

### Dockerfile (stdio)

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "{service}-mcp"]
```

### Client configs

Every client (Cursor, Claude Desktop) needs two options:
- **Option A — uv**: `"command": "uv"` with `--directory` arg.
- **Option B — Docker**: `"command": "docker"` with `--name`,
  `--rm`, `-i`, and `-e` flags for env vars.

Docker configs must use `host.docker.internal` instead of
`localhost` to reach the host machine.

---

## Phase 6: Documentation

### Naming convention

| Type | Case | Examples |
|------|------|----------|
| Root governance | UPPERCASE | `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` |
| Content files | lowercase kebab | `endpoints.md`, `authentication.md`, `architecture.md`, `local-setup.md` |

### Required docs

- `README.md` — intro, features, tool list, prerequisites (uv OR Docker), quickstart, client configs (uv + Docker), env vars, doc links.
- `docs/endpoints.md` — full API endpoint checklist.
- `docs/authentication.md` — credential setup, token flow.
- `docs/architecture.md` — package layout, data flow diagram (Mermaid).

---

## Phase 7: Verification

1. `uv sync` — install deps.
2. Import check — `python -c "from {service}_mcp.server import mcp; print(len(mcp._tool_manager.list_tools()))"`.
3. Compile check — `python -m py_compile src/{service}_mcp/server.py`.
4. Docker build — `docker build -t {service}-mcp:latest .`.
5. Smoke test — send a JSON-RPC `initialize` message via stdin to the Docker container.
