"""Tag tools for the Airbyte API."""

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


class ListTagsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class CreateTagInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Name of the tag to create.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class UpdateTagInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    tag_id: str = Field(..., min_length=1, description="UUID of the tag to update.")
    name: str = Field(..., min_length=1, description="New name for the tag.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class DeleteTagInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    tag_id: str = Field(..., min_length=1, description="UUID of the tag to delete.")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_tag(tag: dict[str, Any]) -> str:
    return f"- **{tag.get('name', '?')}** (`{tag.get('tagId', tag.get('id', '?'))}`)\n"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_tags",
    annotations=ToolAnnotations(
        title="List Airbyte Tags",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_tags(params: ListTagsInput) -> str:
    """List all tags in Airbyte.

    Tags are labels that can be attached to resources (connections,
    sources, destinations) for organization and filtering.

    When to Use:
        - Discover existing tags before creating a new one.
        - Get tag IDs for use in filtering or management.

    Returns:
        List of tags with name and tagId.
    """
    try:
        client = get_client()
        resp = await client.request("GET", "/tags")
        body = resp.json()

        items = body if isinstance(body, list) else body.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return to_json(body)

        if not items:
            return "No tags found."

        lines = ["# Airbyte Tags", ""]
        for tag in items:
            lines.append(_fmt_tag(tag))
        return "\n".join(lines)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_create_tag",
    annotations=ToolAnnotations(
        title="Create Airbyte Tag",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_create_tag(params: CreateTagInput) -> str:
    """Create a new tag in Airbyte.

    When to Use:
        - Add a new organizational label for resources.

    Returns:
        The created tag with its tagId.

    Examples:
        params = { "name": "production" }
    """
    try:
        client = get_client()
        resp = await client.request("POST", "/tags", json_body={"name": params.name})
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return f"Tag created: {_fmt_tag(data)}"
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_update_tag",
    annotations=ToolAnnotations(
        title="Update Airbyte Tag",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_update_tag(params: UpdateTagInput) -> str:
    """Update an existing tag's name.

    When to Use:
        - Rename a tag for better organization.

    Returns:
        The updated tag.

    Examples:
        params = { "tag_id": "a1b2c3d4-...", "name": "staging" }
    """
    try:
        client = get_client()
        resp = await client.request(
            "PATCH",
            f"/tags/{params.tag_id}",
            json_body={"name": params.name},
        )
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return f"Tag updated: {_fmt_tag(data)}"
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_delete_tag",
    annotations=ToolAnnotations(
        title="Delete Airbyte Tag",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_delete_tag(params: DeleteTagInput) -> str:
    """Delete a tag by its UUID.

    This is a permanent operation. The tag will be removed from all
    resources it was attached to.

    When to Use:
        - Remove an obsolete or duplicate tag.

    Examples:
        params = { "tag_id": "a1b2c3d4-..." }
    """
    try:
        client = get_client()
        await client.request("DELETE", f"/tags/{params.tag_id}")
        return f"Tag `{params.tag_id}` deleted successfully."
    except Exception as exc:
        return handle_api_error(exc)
