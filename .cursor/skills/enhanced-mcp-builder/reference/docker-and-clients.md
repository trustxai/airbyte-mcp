# Docker and Client Configuration

## Dockerfile — stdio (default)

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "{service}-mcp"]
```

**Important**: copy `README.md` alongside `pyproject.toml` because
hatchling validates the `readme` field during `uv sync`.

## Dockerfile.http — streamable HTTP

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev
EXPOSE 8080
CMD ["uv", "run", "{service}-mcp-http"]
```

## .dockerignore

```
.git
.venv
__pycache__
*.pyc
.env
.mypy_cache
.ruff_cache
node_modules
.DS_Store
Thumbs.db
docs/
scripts/
*.md
!README.md
```

## Host Networking

When the target API runs on the host (e.g. via `abctl`, Docker
Compose, or a local dev server), `localhost` inside the container
refers to the container itself, not the host.

| Platform | Use instead of `localhost` |
|----------|--------------------------|
| macOS / Windows | `host.docker.internal` |
| Linux | Add `--network=host` to `docker run` |

## Client Configuration Templates

Every MCP client config should offer both uv and Docker options.

### Cursor — `.cursor/mcp.json`

**Option A — uv**

```json
{
  "mcpServers": {
    "{service}": {
      "command": "uv",
      "args": ["--directory", "/path/to/{service}-mcp", "run", "{service}-mcp"],
      "env": {
        "{SERVICE}_API_URL": "http://localhost:PORT/api/v1",
        "{SERVICE}_CLIENT_ID": "<your-client-id>",
        "{SERVICE}_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

**Option B — Docker**

```json
{
  "mcpServers": {
    "{service}": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--name", "{service}-mcp",
        "-e", "{SERVICE}_API_URL",
        "-e", "{SERVICE}_CLIENT_ID",
        "-e", "{SERVICE}_CLIENT_SECRET",
        "{service}-mcp:latest"
      ],
      "env": {
        "{SERVICE}_API_URL": "http://host.docker.internal:PORT/api/v1",
        "{SERVICE}_CLIENT_ID": "<your-client-id>",
        "{SERVICE}_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

### Claude Desktop — `claude_desktop_config.json`

Same structure as Cursor. Both options A and B apply identically.

### Claude Code — HTTP transport

**Option A — uv**

```bash
uv run {service}-mcp-http &
claude mcp add --transport http {service} http://127.0.0.1:8080/mcp
```

**Option B — Docker**

```bash
docker run -d --rm --name {service}-mcp-http \
  -p 8080:8080 \
  -e {SERVICE}_API_URL=http://host.docker.internal:PORT/api/v1 \
  -e {SERVICE}_CLIENT_ID=<id> \
  -e {SERVICE}_CLIENT_SECRET=<secret> \
  {service}-mcp-http:latest
claude mcp add --transport http {service} http://127.0.0.1:8080/mcp
```

### MCP Inspector

```bash
# Start server (either option)
uv run {service}-mcp-http
#   or: docker run --rm -p 8080:8080 --env-file .env {service}-mcp-http:latest

# In another terminal
npx @modelcontextprotocol/inspector
# Connect to http://127.0.0.1:8080/mcp
```

## Docker Notes

- `--rm` auto-removes the container on exit.
- `--name` gives the container a predictable name (avoids random
  Docker names like `dazzling_lumiere`). If a stale container
  remains, `docker rm -f {service}-mcp` clears it.
- `-e VAR` (no `=`) forwards the variable value from the parent
  env block — secrets stay in the MCP client config, not baked
  into the image.
- Always include `README.md` in the Dockerfile COPY (hatchling
  needs it).

## README Structure

The README should document both uv and Docker for:
1. Prerequisites (uv + Python OR Docker).
2. Quickstart (clone, configure `.env`, run).
3. Client Configuration (Cursor, Claude Desktop, Claude Code,
   MCP Inspector) — each with Option A / Option B.
4. Running Manually (all 4 combos: stdio/HTTP x uv/Docker).
5. Environment Variables table.
6. Links to detailed docs.
