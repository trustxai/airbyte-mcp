"""Tool registration for airbyte_mcp."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_all(mcp: FastMCP) -> None:
    """Import every tool module so their @mcp.tool decorators execute."""
    from airbyte_mcp.tools import (  # noqa: F401
        connections,
        definitions,
        destinations,
        health,
        job_logs,
        jobs,
        sources,
        streams,
        tags,
        workspaces,
    )
