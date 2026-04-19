# Airbyte MCP Server (airbyte-mcp)

MCP server for the [Airbyte Public API](https://reference.airbyte.com/reference/getting-started). Built with the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP).

Lets any MCP-compatible client (Cursor, Claude Desktop, Claude Code, MCP Inspector, etc.) interact with your Airbyte instance through natural language.

## Features

- 30 tools covering workspaces, sources, destinations, connections, jobs, job logs, tags, streams, and connector definitions
- Read and write operations for core resources (create, update, delete)
- Job diagnostics via the internal Configuration API (self-managed): detailed failure reasons, per-stream stats, and structured logs
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
| **Job Logs (Internal API)** | |
| `airbyte_get_job_details` | Per-attempt stats, failure reasons, and stacktraces |
| `airbyte_get_job_logs` | Structured log entries for all attempts |
| `airbyte_get_attempt_logs` | Structured log entries for a specific attempt |
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
  - **[uv](https://docs.astral.sh/uv/)** + **Python 3.13+** (local install), or
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

## Client Configuration

Every MCP client (Cursor, Claude Desktop, etc.) can run the server in one of two ways:

- **uv** — quickest to set up, but requires [uv](https://docs.astral.sh/uv/) installed locally.
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
# stdio (uv)
uv run airbyte-mcp

# stdio (Docker)
docker run --rm -i --env-file .env airbyte-mcp:latest

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
| `HTTP_HOST` | No | `127.0.0.1` | HTTP transport bind address |
| `HTTP_PORT` | No | `8080` | HTTP transport port |

*Not required if `AIRBYTE_ACCESS_TOKEN` is provided.

## Documentation

- [Authentication](docs/authentication.md) — token exchange, credentials setup
- [Architecture](docs/architecture.md) — system design, package layout, token lifecycle
- [Endpoints Checklist](docs/endpoints.md) — full Airbyte API coverage status
- [Local Setup](docs/local-setup.md) — abctl installation walkthrough
- [Contributing](docs/CONTRIBUTING.md) — development workflow, PR guidelines
- [Security](docs/SECURITY.md) — vulnerability reporting
- [Changelog](CHANGELOG.md) — release history

## Contributing

Contributions are welcome! See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) to get started.

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
