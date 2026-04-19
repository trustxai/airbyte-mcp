"""FastMCP server definition and entry points for airbyte_mcp."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("airbyte_mcp")

# Register all tools (side-effect imports via decorators)
from airbyte_mcp.tools import register_all  # noqa: E402

register_all(mcp)


def main_stdio() -> None:
    """Entry point for local / Docker stdio transport."""
    mcp.run()


def main_http() -> None:
    """Entry point for streamable HTTP transport (remote / cloud)."""
    from airbyte_mcp.config import get_settings

    s = get_settings()
    mcp.settings.host = s.http_host
    mcp.settings.port = s.http_port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main_stdio()
