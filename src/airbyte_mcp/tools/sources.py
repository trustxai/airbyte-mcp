"""Source tools for the Airbyte API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import (
    ResponseFormat,
    epoch_to_human,
    paginated_response,
    to_json,
)
from airbyte_mcp.server import mcp

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListSourcesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_ids: Optional[list[str]] = Field(
        default=None,
        description="Filter by workspace UUIDs. Omit to list across all allowed workspaces.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    include_deleted: bool = Field(
        default=False, description="Include soft-deleted sources."
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetSourceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., min_length=1, description="UUID of the source.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_source(src: dict) -> str:
    created = epoch_to_human(src.get("createdAt"))
    return (
        f"## {src.get('name', 'Unnamed')} (`{src.get('sourceId', '?')}`)\n"
        f"- **Type**: {src.get('sourceType', '?')}\n"
        f"- **Workspace**: {src.get('workspaceId', '?')}\n"
        f"- **Created**: {created}\n"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_sources",
    annotations={
        "title": "List Airbyte Sources",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def airbyte_list_sources(params: ListSourcesInput) -> str:
    """List source connectors configured in Airbyte.

    Sources represent the data origins (databases, APIs, SaaS apps, etc.)
    that Airbyte reads from. Each source is linked to a workspace and can
    be paired with one or more destinations via connections.

    When to Use:
        - Discover which source connectors are set up.
        - Find a source's UUID to inspect its configuration or look up
          related connections.
        - Audit sources across one or more workspaces.

    When NOT to Use:
        - If you already have a source ID, use airbyte_get_source for
          full details.
        - To see what data a source actually moves, look at connections
          (airbyte_list_connections) or jobs (airbyte_list_jobs).

    Returns:
        Paginated list of sources. Each entry includes:
        - name, sourceId (UUID), sourceType, workspaceId, createdAt.

        Markdown format shows a heading per source with bullet fields.
        JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).

    Examples:
        List all sources in a workspace:
            params = { "workspace_ids": ["a1b2c3d4-..."] }
        List first 5 sources across all workspaces:
            params = { "limit": 5 }
        Include soft-deleted sources:
            params = { "include_deleted": true }
    """
    try:
        client = get_client()
        query: dict = {
            "limit": params.limit,
            "offset": params.offset,
            "includeDeleted": params.include_deleted,
        }
        if params.workspace_ids:
            query["workspaceIds"] = params.workspace_ids
        resp = await client.request("GET", "/sources", params=query)
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_source,
            title="Airbyte Sources",
        )
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_source",
    annotations={
        "title": "Get Airbyte Source",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def airbyte_get_source(params: GetSourceInput) -> str:
    """Get full details of a single source connector by its UUID.

    Returns the source name, type (e.g. postgres, stripe, google-sheets),
    workspace, creation date, and connector configuration. Secrets in the
    configuration object are masked by the Airbyte API.

    When to Use:
        - Inspect a specific source's configuration or connector type.
        - Verify a source ID is valid.
        - Check when a source was created or which workspace owns it.

    When NOT to Use:
        - If you need to browse sources, use airbyte_list_sources.
        - To see sync activity, use airbyte_list_jobs filtered by the
          connection that uses this source.

    Returns:
        Source details including: name, sourceId, sourceType,
        workspaceId, createdAt, and configuration (secrets masked).

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get source by ID:
            params = { "source_id": "a1b2c3d4-..." }
        Get raw JSON:
            params = { "source_id": "a1b2c3d4-...", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the source ID does not exist.
    """
    try:
        client = get_client()
        resp = await client.request("GET", f"/sources/{params.source_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_source(data)
    except Exception as exc:
        return handle_api_error(exc)
