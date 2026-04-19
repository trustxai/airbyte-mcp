"""Stream property tools for the Airbyte API."""

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


class GetStreamPropertiesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., min_length=1, description="UUID of the source.")
    destination_id: str | None = Field(
        default=None,
        description="Optional UUID of the destination (refines sync mode availability).",
    )
    ignore_cache: bool = Field(
        default=False,
        description="If true, pull the latest schema from the source instead of using the cache.",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_stream(stream: dict[str, Any]) -> str:
    name = stream.get("streamName", stream.get("name", "?"))
    ns = stream.get("streamNamespace", "")
    sync_modes = stream.get("syncModes", [])
    cursor = stream.get("defaultCursorField", [])
    pkey = stream.get("sourceDefinedPrimaryKey", [])

    label = f"{ns}.{name}" if ns else name
    modes_str = ", ".join(sync_modes) if sync_modes else "N/A"
    cursor_str = ".".join(cursor) if cursor else "none"
    pkey_str = ", ".join(".".join(k) if isinstance(k, list) else str(k) for k in pkey) if pkey else "none"

    return f"### `{label}`\n- Sync modes: {modes_str}\n- Default cursor: {cursor_str}\n- Primary key: {pkey_str}\n"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_get_stream_properties",
    annotations=ToolAnnotations(
        title="Get Airbyte Stream Properties",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_stream_properties(params: GetStreamPropertiesInput) -> str:
    """Get the available streams and their properties for a source.

    Returns the list of streams that the source connector can produce,
    along with each stream's supported sync modes, default cursor
    field, and source-defined primary key.

    When to Use:
        - Before creating a connection, to discover which streams are
          available and which sync modes they support.
        - To verify that a source has the expected streams after
          configuration changes.
        - To find the right cursor field or primary key for
          incremental syncs.

    When NOT to Use:
        - To see which streams are currently configured on a
          connection, use airbyte_get_connection instead.

    Returns:
        List of streams with: name, namespace, sync modes,
        default cursor field, and primary key.

    Examples:
        Basic usage:
            params = { "source_id": "a1b2c3d4-..." }
        With destination context and cache bypass:
            params = {
                "source_id": "a1b2c3d4-...",
                "destination_id": "e5f6g7h8-...",
                "ignore_cache": true
            }
    """
    try:
        client = get_client()
        query: dict[str, Any] = {"sourceId": params.source_id}
        if params.destination_id:
            query["destinationId"] = params.destination_id
        if params.ignore_cache:
            query["ignoreCache"] = True

        resp = await client.request("GET", "/streams", params=query)
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        streams = data if isinstance(data, list) else data.get("data", data.get("streams", []))
        if not streams:
            return "No streams found for this source."

        lines = [f"# Stream Properties ({len(streams)} streams)", ""]
        for s in streams:
            lines.append(_fmt_stream(s))

        return "\n".join(lines)
    except Exception as exc:
        return handle_api_error(exc)
