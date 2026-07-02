# Airbyte MCP Server (airbyte-mcp)

MCP server for the [Airbyte Public API](https://reference.airbyte.com/reference/getting-started). Built with the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP).

Lets any MCP-compatible client (Cursor, Claude Desktop, Claude Code, MCP Inspector, etc.) interact with your Airbyte instance through natural language.

## Features

- 36 tools covering workspaces, sources, destinations, connections, jobs, refresh/clear, job logs, tags, streams, and connector definitions
- Read and write operations for core resources (create, update, delete)
- Job diagnostics via the internal Configuration API (self-managed): detailed failure reasons, per-stream stats, and structured logs
- Cloud full-text sync logs via `airbyte_get_cloud_sync_logs` (Airbyte Cloud only; parity with official Replication MCP)
- Automatic token exchange with in-memory caching and transparent 401 retry
- Markdown and JSON response formats on summary tools; JSON-only for log tools
- Pagination support (limit/offset) on all list tools
- Two transport modes: **stdio** (local) and **streamable HTTP** (remote)
- Works with self-managed Airbyte (abctl) and Airbyte Cloud

## Available Tools

| Tool | Description |
|---|---|
| **Health** | |
| `airbyte_health_check` | Ping the Airbyte API |
| **Workspaces** | |
| `airbyte_list_workspaces` | List workspaces with pagination |
| `airbyte_get_workspace` | Get workspace details by ID |
| **Sources** | |
| `airbyte_list_sources` | List source connectors (filter by workspace) |
| `airbyte_get_source` | Get source details by ID |
| `airbyte_create_source` | Create a new source connector |
| `airbyte_update_source` | Update an existing source |
| **Destinations** | |
| `airbyte_list_destinations` | List destination connectors (filter by workspace) |
| `airbyte_get_destination` | Get destination details by ID |
| `airbyte_create_destination` | Create a new destination connector |
| `airbyte_update_destination` | Update an existing destination |
| **Connections** | |
| `airbyte_list_connections` | List connections / pipelines (filter by workspace) |
| `airbyte_get_connection` | Get connection details including stream config |
| `airbyte_create_connection` | Create a new connection (pipeline) |
| `airbyte_update_connection` | Update an existing connection |
| **Jobs** | |
| `airbyte_list_jobs` | List jobs (filter by connection, type, status, dates) |
| `airbyte_get_job` | Get job details (status, duration, bytes/rows synced) |
| `airbyte_trigger_sync` | Trigger a sync or reset job |
| `airbyte_cancel_job` | Cancel a running job |
| `airbyte_trigger_refresh` | Trigger a per-stream refresh (internal API, self-managed) |
| `airbyte_trigger_clear` | Clear destination data for streams (internal API, self-managed) |
| `airbyte_wait_for_job` | Poll until a job reaches a terminal status (internal API) |
| **Job Logs (Internal API — self-managed only)** | |
| `airbyte_list_jobs_internal` | List all job types including refresh and clear |
| `airbyte_get_job_details` | Per-attempt stats, failure reasons, and stacktraces |
| `airbyte_get_job_logs` | Structured log entries for all attempts |
| `airbyte_get_attempt_logs` | Structured log entries for a specific attempt |
| **Job Logs (Cloud only — full text)** | |
| `airbyte_get_cloud_sync_logs` | Full-text sync logs with pagination (Cloud Config API) |
| **Streams** | |
| `airbyte_get_stream_properties` | Get stream properties for a source/destination pair |
| **Tags** | |
| `airbyte_list_tags` | List tags |
| `airbyte_create_tag` | Create a tag |
| `airbyte_update_tag` | Update a tag |
| `airbyte_delete_tag` | Delete a tag |
| **Connector Definitions** | |
| `airbyte_list_source_definitions` | List source connector definitions |
| `airbyte_get_source_definition` | Get a source connector definition |
| `airbyte_list_destination_definitions` | List destination connector definitions |
| `airbyte_get_destination_definition` | Get a destination connector definition |

See [docs/endpoints.md](docs/endpoints.md) for the full Airbyte API endpoint checklist.

## Prerequisites

- A running **Airbyte** instance — either:
  - Self-managed via [abctl](https://docs.airbyte.com/platform/deploying-airbyte/abctl/) (see [docs/local-setup.md](docs/local-setup.md))
  - [Airbyte Cloud](https://cloud.airbyte.com)
- One of the following to run the server:
  - **[uvx](https://docs.astral.sh/uv/)** (zero-install; runs the published package on demand — see [Run with uvx](#run-with-uvx-zero-install)), or
  - **[uv](https://docs.astral.sh/uv/)** + **Python 3.13+** (local clone / development), or
  - **[Docker](https://docs.docker.com/get-docker/)** (no Python / uv needed on the host)

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/trustxai/airbyte-mcp.git
cd airbyte-mcp
uv sync
```

### 2. Configure credentials

```bash
cp .env.example .env
```

For self-managed (abctl), retrieve credentials:

```bash
abctl local credentials
```

Edit `.env` with your `client-id` and `client-secret`. See [docs/authentication.md](docs/authentication.md) for details.

### 3. Run the server

#### stdio (Cursor / Claude Desktop / Docker)

```bash
uv run airbyte-mcp
```

#### Streamable HTTP (remote / MCP Inspector)

```bash
uv run airbyte-mcp-http
# Listening on http://127.0.0.1:8080/mcp
```

## Run with uvx (zero-install)

[uvx](https://docs.astral.sh/uv/) runs the published PyPI package on demand — no
clone, no virtualenv, no persistent install. The command matches the package
name, so no `--from` is needed:

```bash
# stdio
uvx airbyte-mcp

# streamable HTTP
uvx airbyte-mcp-http
```

> **Not the same as the official Airbyte replication MCP.** That one lives in the
> `airbyte` package and is invoked as `uvx --from=airbyte@latest airbyte-mcp`.
> Here the PyPI package *is* `airbyte-mcp`, so `uvx airbyte-mcp` unambiguously
> resolves to this server.

Credentials are passed via the client's `env` block (see below), or exported in
your shell for a manual run:

```bash
AIRBYTE_API_URL=http://localhost:8000/api/public/v1 \
AIRBYTE_CLIENT_ID=<your-client-id> \
AIRBYTE_CLIENT_SECRET=<your-client-secret> \
uvx airbyte-mcp
```

> **Python version:** the package targets **Python 3.13+**. uv auto-provisions a
> matching interpreter, so this normally just works. If your environment pins an
> older default, force it with `uvx --python=3.13 airbyte-mcp`.

Client config (e.g. Cursor `.cursor/mcp.json`) using uvx:

```json
{
  "mcpServers": {
    "airbyte": {
      "command": "uvx",
      "args": ["airbyte-mcp"],
      "env": {
        "AIRBYTE_API_URL": "http://localhost:8000/api/public/v1",
        "AIRBYTE_CLIENT_ID": "<your-client-id>",
        "AIRBYTE_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

## Client Configuration

Every MCP client (Cursor, Claude Desktop, etc.) can run the server in one of three ways:

- **uvx** — zero-install; runs the published package on demand (see [Run with uvx](#run-with-uvx-zero-install)).
- **uv** — from a local clone; best for development.
- **Docker** — no Python / uv required on the host; everything runs in a container. Build the image once and every client config reuses it.

> **Host networking note**: if Airbyte is running on your host machine (e.g. via `abctl`), inside the Docker container `localhost` does **not** point to your host. Use `http://host.docker.internal:8000/api/public/v1` on macOS/Windows, or add `--network=host` to the `docker run` args on Linux.

### Build the Docker image (one-time)

```bash
docker build -t airbyte-mcp:latest .
```

### Cursor

Add to `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

**Option A — uv**

```json
{
  "mcpServers": {
    "airbyte": {
      "command": "uv",
      "args": ["--directory", "/path/to/airbyte-mcp", "run", "airbyte-mcp"],
      "env": {
        "AIRBYTE_API_URL": "http://localhost:8000/api/public/v1",
        "AIRBYTE_CLIENT_ID": "<your-client-id>",
        "AIRBYTE_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

**Option B — Docker**

```json
{
  "mcpServers": {
    "airbyte": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--name", "airbyte-mcp",
        "-e", "AIRBYTE_API_URL",
        "-e", "AIRBYTE_CLIENT_ID",
        "-e", "AIRBYTE_CLIENT_SECRET",
        "airbyte-mcp:latest"
      ],
      "env": {
        "AIRBYTE_API_URL": "http://host.docker.internal:8000/api/public/v1",
        "AIRBYTE_CLIENT_ID": "<your-client-id>",
        "AIRBYTE_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

**Option A — uv**

```json
{
  "mcpServers": {
    "airbyte": {
      "command": "uv",
      "args": ["--directory", "/path/to/airbyte-mcp", "run", "airbyte-mcp"],
      "env": {
        "AIRBYTE_API_URL": "http://localhost:8000/api/public/v1",
        "AIRBYTE_CLIENT_ID": "<your-client-id>",
        "AIRBYTE_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

**Option B — Docker**

```json
{
  "mcpServers": {
    "airbyte": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--name", "airbyte-mcp",
        "-e", "AIRBYTE_API_URL",
        "-e", "AIRBYTE_CLIENT_ID",
        "-e", "AIRBYTE_CLIENT_SECRET",
        "airbyte-mcp:latest"
      ],
      "env": {
        "AIRBYTE_API_URL": "http://host.docker.internal:8000/api/public/v1",
        "AIRBYTE_CLIENT_ID": "<your-client-id>",
        "AIRBYTE_CLIENT_SECRET": "<your-client-secret>"
      }
    }
  }
}
```

### Claude Code (HTTP)

**Option A — uv**

```bash
uv run airbyte-mcp-http &
claude mcp add --transport http airbyte http://127.0.0.1:8080/mcp
```

**Option B — Docker**

```bash
docker build -f Dockerfile.http -t airbyte-mcp-http:latest .
docker run -d --rm --name airbyte-mcp-http \
  -p 8080:8080 \
  -e AIRBYTE_API_URL=http://host.docker.internal:8000/api/public/v1 \
  -e AIRBYTE_CLIENT_ID=<your-client-id> \
  -e AIRBYTE_CLIENT_SECRET=<your-client-secret> \
  airbyte-mcp-http:latest
claude mcp add --transport http airbyte http://127.0.0.1:8080/mcp
```

> The HTTP image binds `0.0.0.0:8080` inside the container (so `-p 8080:8080`
> works) and ships a `HEALTHCHECK` on that port; check it with `docker ps` or
> `docker inspect --format '{{.State.Health.Status}}' airbyte-mcp-http`.

### MCP Inspector

```bash
# Start the server in HTTP mode (uv or docker — either works)
uv run airbyte-mcp-http
#   or: docker run --rm -p 8080:8080 --env-file .env airbyte-mcp-http:latest

# In another terminal
npx @modelcontextprotocol/inspector
# Then connect to http://127.0.0.1:8080/mcp in the inspector UI
```

## Running Manually (without a client)

If you just want to exercise the server from the CLI:

```bash
# stdio (uvx — no clone)
uvx airbyte-mcp

# stdio (uv)
uv run airbyte-mcp

# stdio (Docker)
docker run --rm -i --env-file .env airbyte-mcp:latest

# HTTP (uvx — no clone)
uvx airbyte-mcp-http

# HTTP (uv)
uv run airbyte-mcp-http

# HTTP (Docker)
docker run --rm -p 8080:8080 --env-file .env airbyte-mcp-http:latest
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AIRBYTE_API_URL` | No | `http://localhost:8000/api/public/v1` | Airbyte API base URL |
| `AIRBYTE_CLIENT_ID` | Yes* | — | Application client ID |
| `AIRBYTE_CLIENT_SECRET` | Yes* | — | Application client secret |
| `AIRBYTE_ACCESS_TOKEN` | No | — | Pre-fetched token (skips exchange) |
| `AIRBYTE_INTERNAL_API_URL` | No | *(derived)* | Override Config API base (Cloud: `https://cloud.airbyte.com/api/v1`) |
| `AIRBYTE_REQUEST_TIMEOUT_SECONDS` | No | `30` | Default HTTP timeout for public API calls |
| `AIRBYTE_INTERNAL_LOG_TIMEOUT_SECONDS` | No | `120` | Timeout for internal/Cloud Config API log endpoints |
| `HTTP_HOST` | No | `127.0.0.1` | HTTP transport bind address |
| `HTTP_PORT` | No | `8080` | HTTP transport port |

*Not required if `AIRBYTE_ACCESS_TOKEN` is provided.

## Documentation

- [Authentication](docs/authentication.md) — token exchange, credentials setup
- [Architecture](docs/architecture.md) — system design, package layout, token lifecycle
- [Remote / HTTP Security](docs/remote.md) — no-auth risk and secure deployment options (design only)
- [Comparison vs Official MCPs](docs/comparison.md) — open-source-first positioning vs official MCPs
- [Endpoints Checklist](docs/endpoints.md) — full Airbyte API coverage status
- [Local Setup](docs/local-setup.md) — abctl installation walkthrough
- [Contributing](docs/CONTRIBUTING.md) — development workflow, PR guidelines
- [Security](docs/SECURITY.md) — vulnerability reporting
- [Changelog](CHANGELOG.md) — release history

## Contributing

Contributions are welcome! See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) to get started.

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
