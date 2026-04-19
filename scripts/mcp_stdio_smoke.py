#!/usr/bin/env python3
"""Spawn the airbyte_mcp server over stdio and exercise every tool.

Usage:
    uv run python scripts/mcp_stdio_smoke.py

Requires a running Airbyte instance and valid .env credentials.
"""

from __future__ import annotations

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run() -> None:
    env = {**os.environ}

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "airbyte-mcp"],
        env=env,
    )

    print("Connecting to airbyte-mcp via stdio …")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools_resp = await session.list_tools()
            tool_names = [t.name for t in tools_resp.tools]
            print(f"\nRegistered tools ({len(tool_names)}):")
            for name in sorted(tool_names):
                print(f"  - {name}")

            # Health check
            print("\n--- airbyte_health_check ---")
            result = await session.call_tool("airbyte_health_check", {})
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            # List workspaces
            print("\n--- airbyte_list_workspaces ---")
            result = await session.call_tool(
                "airbyte_list_workspaces",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            # List sources
            print("\n--- airbyte_list_sources ---")
            result = await session.call_tool(
                "airbyte_list_sources",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            # List destinations
            print("\n--- airbyte_list_destinations ---")
            result = await session.call_tool(
                "airbyte_list_destinations",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            # List connections
            print("\n--- airbyte_list_connections ---")
            result = await session.call_tool(
                "airbyte_list_connections",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            # List jobs
            print("\n--- airbyte_list_jobs ---")
            result = await session.call_tool(
                "airbyte_list_jobs",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

    print("\nSmoke test complete.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
