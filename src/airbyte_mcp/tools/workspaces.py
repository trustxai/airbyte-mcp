"""Workspace tools for the Airbyte API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, paginated_response, to_json
from airbyte_mcp.server import mcp

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListWorkspacesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    include_deleted: bool = Field(
        default=False, description="Include soft-deleted workspaces."
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class GetWorkspaceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_workspace(ws: dict) -> str:
    return (
        f"## {ws.get('name', 'Unnamed')} (`{ws.get('workspaceId', '?')}`)\n"
        f"- **Data residency**: {ws.get('dataResidency', 'auto')}\n"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_workspaces",
    annotations={
        "title": "List Airbyte Workspaces",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def airbyte_list_workspaces(params: ListWorkspacesInput) -> str:
    """List all Airbyte workspaces the current credentials have access to.

    Workspaces are the top-level organizational unit in Airbyte. Every
    source, destination, and connection belongs to exactly one workspace.
    Use this tool to discover workspace IDs before filtering other
    resources.

    When to Use:
        - Discover which workspaces exist and get their UUIDs.
        - Find a workspace by name to use its ID in other calls.
        - Audit workspace configuration (data residency, etc.).

    When NOT to Use:
        - If you already have a workspace ID, use airbyte_get_workspace
          for full details instead.

    Returns:
        Paginated list of workspaces. Each entry includes:
        - name, workspaceId (UUID), dataResidency.

        Markdown format shows a heading per workspace.
        JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).
        The response header indicates whether more pages exist.

    Examples:
        List first 5 workspaces:
            params = { "limit": 5 }
        List including deleted workspaces:
            params = { "include_deleted": true }
        Get raw JSON for scripting:
            params = { "response_format": "json" }
    """
    try:
        client = get_client()
        resp = await client.request(
            "GET",
            "/workspaces",
            params={
                "limit": params.limit,
                "offset": params.offset,
                "includeDeleted": params.include_deleted,
            },
        )
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_workspace,
            title="Airbyte Workspaces",
        )
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_workspace",
    annotations={
        "title": "Get Airbyte Workspace",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def airbyte_get_workspace(params: GetWorkspaceInput) -> str:
    """Get full details of a single Airbyte workspace by its UUID.

    Returns the workspace name, data residency region, and other
    metadata. Use when you already know the workspace ID and need its
    properties.

    When to Use:
        - Look up a specific workspace's name or data residency.
        - Confirm a workspace ID is valid before passing it to other
          tools.

    When NOT to Use:
        - If you need to browse or search workspaces, use
          airbyte_list_workspaces instead.

    Returns:
        Workspace details including: name, workspaceId, dataResidency.

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get workspace by ID:
            params = { "workspace_id": "a1b2c3d4-..." }
        Get raw JSON:
            params = { "workspace_id": "a1b2c3d4-...", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the workspace ID does not exist.
        Returns a 403 message if credentials lack access to that workspace.
    """
    try:
        client = get_client()
        resp = await client.request("GET", f"/workspaces/{params.workspace_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_workspace(data)
    except Exception as exc:
        return handle_api_error(exc)
