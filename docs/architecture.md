# Architecture

## Overview

`airbyte-mcp` is a Python MCP server built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk) (the official MCP Python SDK). It exposes read and write tools that wrap the [Airbyte Public API](https://reference.airbyte.com/reference/getting-started) and the internal Configuration API (self-managed only) for job diagnostics.

## High-Level Flow

```mermaid
flowchart LR
    subgraph Clients
        Cursor[Cursor IDE]
        Claude[Claude Desktop]
        Inspector[MCP Inspector]
    end

    Stdio["airbyte-mcp (stdio)"]

    subgraph AirbyteMCP["airbyte_mcp package"]
        FastMCP[FastMCP server]
        Tools[Tool modules]
        Client[AirbyteClient]
        TokenCache[Token cache]
    end

    AirbyteAPI[Airbyte Public API]

    Cursor -->|stdio| Stdio
    Claude -->|stdio| Stdio
    Inspector -->|stdio| Stdio

    Stdio --> FastMCP
    FastMCP --> Tools
    Tools --> Client
    Client --> TokenCache
    Client -->|"Bearer token"| AirbyteAPI
    TokenCache -.->|"POST /applications/token"| AirbyteAPI
```

## Package Layout

```
src/airbyte_mcp/
├── __init__.py          # Package metadata
├── __main__.py          # python -m airbyte_mcp
├── server.py            # FastMCP instance + entry points
├── config.py            # pydantic-settings (env / .env)
├── client.py            # AirbyteClient (httpx + token lifecycle)
├── errors.py            # Centralised error formatting
├── formatters.py        # Markdown / JSON response helpers
└── tools/
    ├── __init__.py      # register_all(mcp)
    ├── _log_utils.py    # Structured log truncation helpers
    ├── health.py        # airbyte_health_check
    ├── workspaces.py    # airbyte_list_workspaces, airbyte_get_workspace
    ├── sources.py       # airbyte_list_sources, airbyte_get_source, create, update
    ├── destinations.py  # airbyte_list_destinations, airbyte_get_destination, create, update
    ├── connections.py   # airbyte_list_connections, airbyte_get_connection, create, update
    ├── jobs.py          # airbyte_list_jobs, airbyte_get_job, trigger_sync, cancel_job
    ├── job_logs.py      # airbyte_get_job_details, airbyte_get_job_logs, airbyte_get_attempt_logs
    ├── streams.py       # airbyte_get_stream_properties
    ├── tags.py          # airbyte_list_tags, airbyte_create_tag, update, delete
    └── definitions.py   # source/destination definition listing and lookup
```

## Token Lifecycle

1. On the first tool call, `AirbyteClient` exchanges `client_id` + `client_secret` for an access token via `POST /applications/token`.
2. The token is cached in memory with a 30-second safety margin before the reported `expires_in`.
3. Subsequent requests reuse the cached token.
4. If the token is expired (or the API returns `401`), the client automatically fetches a new one and retries the request once.

## Transport

The server runs over **stdio** via the `airbyte-mcp` entry point (`main_stdio`),
which is the transport used by Cursor, Claude Desktop, Claude Code, the MCP
Inspector, and Docker. Remote HTTP transport is not supported.
