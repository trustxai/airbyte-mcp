"""Source and destination definition tools for the Airbyte API.

Definitions represent the available connector types (custom or
marketplace) scoped to a workspace.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, to_json
from airbyte_mcp.server import mcp

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListSourceDefinitionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetSourceDefinitionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace.")
    definition_id: str = Field(..., min_length=1, description="UUID of the source definition.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class ListDestinationDefinitionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetDestinationDefinitionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace.")
    definition_id: str = Field(..., min_length=1, description="UUID of the destination definition.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_definition(defn: dict[str, Any], kind: str = "source") -> str:
    name = defn.get("name", "Unnamed")
    def_id = defn.get("sourceDefinitionId", defn.get("destinationDefinitionId", defn.get("definitionId", "?")))
    docker_repo = defn.get("dockerRepository", "?")
    docker_tag = defn.get("dockerImageTag", "?")
    return f"### {name} (`{def_id}`)\n- Image: `{docker_repo}:{docker_tag}`\n"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_source_definitions",
    annotations=ToolAnnotations(
        title="List Airbyte Source Definitions",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_source_definitions(params: ListSourceDefinitionsInput) -> str:
    """List available source connector definitions in a workspace.

    Source definitions describe which connector types are available
    (e.g. Postgres, Stripe, Google Sheets). Each definition has a
    UUID that can be used when creating a new source.

    When to Use:
        - Find the definition ID for a specific connector type before
          creating a source with airbyte_create_source.
        - Audit which custom connectors are installed in a workspace.

    Returns:
        List of source definitions with name, definition ID, and
        Docker image information.

    Examples:
        params = { "workspace_id": "a1b2c3d4-..." }
    """
    try:
        client = get_client()
        resp = await client.request(
            "GET",
            f"/workspaces/{params.workspace_id}/definitions/sources",
        )
        body = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(body)

        items = body if isinstance(body, list) else body.get("data", [])
        if not items:
            return "No source definitions found for this workspace."

        lines = [f"# Source Definitions ({len(items)})", ""]
        for defn in items:
            lines.append(_fmt_definition(defn, "source"))
        return "\n".join(lines)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_source_definition",
    annotations=ToolAnnotations(
        title="Get Airbyte Source Definition",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_source_definition(params: GetSourceDefinitionInput) -> str:
    """Get details of a specific source connector definition.

    Returns the full definition including name, Docker image, and
    connector specification.

    When to Use:
        - Inspect what a specific source connector provides.
        - Check the Docker image version for a connector.

    Examples:
        params = { "workspace_id": "...", "definition_id": "..." }
    """
    try:
        client = get_client()
        resp = await client.request(
            "GET",
            f"/workspaces/{params.workspace_id}/definitions/sources/{params.definition_id}",
        )
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_definition(data, "source")
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_list_destination_definitions",
    annotations=ToolAnnotations(
        title="List Airbyte Destination Definitions",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_destination_definitions(params: ListDestinationDefinitionsInput) -> str:
    """List available destination connector definitions in a workspace.

    Destination definitions describe which connector types are
    available (e.g. BigQuery, Snowflake, S3). Each definition has a
    UUID that can be used when creating a new destination.

    When to Use:
        - Find the definition ID for a specific connector type before
          creating a destination with airbyte_create_destination.
        - Audit which custom connectors are installed in a workspace.

    Returns:
        List of destination definitions with name, definition ID,
        and Docker image information.

    Examples:
        params = { "workspace_id": "a1b2c3d4-..." }
    """
    try:
        client = get_client()
        resp = await client.request(
            "GET",
            f"/workspaces/{params.workspace_id}/definitions/destinations",
        )
        body = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(body)

        items = body if isinstance(body, list) else body.get("data", [])
        if not items:
            return "No destination definitions found for this workspace."

        lines = [f"# Destination Definitions ({len(items)})", ""]
        for defn in items:
            lines.append(_fmt_definition(defn, "destination"))
        return "\n".join(lines)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_destination_definition",
    annotations=ToolAnnotations(
        title="Get Airbyte Destination Definition",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_destination_definition(params: GetDestinationDefinitionInput) -> str:
    """Get details of a specific destination connector definition.

    Returns the full definition including name, Docker image, and
    connector specification.

    When to Use:
        - Inspect what a specific destination connector provides.
        - Check the Docker image version for a connector.

    Examples:
        params = { "workspace_id": "...", "definition_id": "..." }
    """
    try:
        client = get_client()
        resp = await client.request(
            "GET",
            f"/workspaces/{params.workspace_id}/definitions/destinations/{params.definition_id}",
        )
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_definition(data, "destination")
    except Exception as exc:
        return handle_api_error(exc)
