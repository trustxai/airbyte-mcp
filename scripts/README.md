# Scripts

Utility scripts for testing and debugging the Airbyte MCP server.

## Prerequisites

1. A running Airbyte instance (e.g. via `abctl local install`)
2. A `.env` file in the project root (copy from `.env.example` and fill in credentials)

## Available Scripts

### `get_token.py`

Exchange your `client_id` / `client_secret` for a short-lived access token. Useful to confirm your Airbyte credentials work before running the MCP server.

```bash
uv run python scripts/get_token.py
```

### `list_workspaces.py`

Direct HTTP call to `GET /workspaces` — bypasses MCP entirely. Good for verifying API connectivity.

```bash
uv run python scripts/list_workspaces.py
```

### `mcp_stdio_smoke.py`

Spawns the full MCP server via stdio and calls every registered tool. This is the closest thing to an end-to-end test.

```bash
uv run python scripts/mcp_stdio_smoke.py
```
