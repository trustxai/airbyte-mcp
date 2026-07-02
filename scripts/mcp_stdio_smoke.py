#!/usr/bin/env python3
"""Spawn the airbyte_mcp server over stdio and exercise every tool.

Usage:
    uv run python scripts/mcp_stdio_smoke.py

Requires a running Airbyte instance and valid .env credentials.
"""

from __future__ import annotations

import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _first_connection_id(session: ClientSession) -> str | None:
    result = await session.call_tool(
        "airbyte_list_connections",
        {"params": {"limit": 1, "response_format": "json"}},
    )
    for content in result.content:
        text = content.text if hasattr(content, "text") else str(content)
        payload = json.loads(text)
        data = payload.get("data", [])
        if data:
            return data[0].get("connectionId")
    return None


async def _latest_internal_job_id(session: ClientSession, connection_id: str) -> int | None:
    result = await session.call_tool(
        "airbyte_list_jobs_internal",
        {"params": {"connection_id": connection_id, "limit": 1, "response_format": "json"}},
    )
    for content in result.content:
        text = content.text if hasattr(content, "text") else str(content)
        if text.startswith("Error"):
            print(text)
            return None
        payload = json.loads(text)
        jobs = payload.get("jobs", [])
        if jobs:
            return jobs[0]["job"]["id"]
    return None


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

            tools_resp = await session.list_tools()
            tool_names = [t.name for t in tools_resp.tools]
            print(f"\nRegistered tools ({len(tool_names)}):")
            for name in sorted(tool_names):
                print(f"  - {name}")

            print("\n--- airbyte_health_check ---")
            result = await session.call_tool("airbyte_health_check", {})
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            print("\n--- airbyte_list_workspaces ---")
            result = await session.call_tool(
                "airbyte_list_workspaces",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            print("\n--- airbyte_list_sources ---")
            result = await session.call_tool(
                "airbyte_list_sources",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            print("\n--- airbyte_list_destinations ---")
            result = await session.call_tool(
                "airbyte_list_destinations",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            print("\n--- airbyte_list_connections ---")
            result = await session.call_tool(
                "airbyte_list_connections",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            print("\n--- airbyte_list_jobs ---")
            result = await session.call_tool(
                "airbyte_list_jobs",
                {"params": {"limit": 5, "response_format": "markdown"}},
            )
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            connection_id = await _first_connection_id(session)
            if connection_id:
                print("\n--- airbyte_list_jobs_internal ---")
                result = await session.call_tool(
                    "airbyte_list_jobs_internal",
                    {
                        "params": {
                            "connection_id": connection_id,
                            "limit": 3,
                            "response_format": "markdown",
                        }
                    },
                )
                for c in result.content:
                    print(c.text if hasattr(c, "text") else c)

                job_id = await _latest_internal_job_id(session, connection_id)
                if job_id is not None:
                    print(f"\n--- airbyte_get_job_logs (job_id={job_id}) ---")
                    result = await session.call_tool(
                        "airbyte_get_job_logs",
                        {"params": {"job_id": job_id, "tail_lines": 5}},
                    )
                    for c in result.content:
                        text = c.text if hasattr(c, "text") else str(c)
                        print(text[:500] + ("…" if len(text) > 500 else ""))

                    print(f"\n--- airbyte_get_attempt_logs (job_id={job_id}, attempt=0) ---")
                    result = await session.call_tool(
                        "airbyte_get_attempt_logs",
                        {"params": {"job_id": job_id, "attempt_number": 0, "tail_lines": 5}},
                    )
                    for c in result.content:
                        text = c.text if hasattr(c, "text") else str(c)
                        print(text[:500] + ("…" if len(text) > 500 else ""))

                print(f"\n--- airbyte_get_cloud_sync_logs (connection_id={connection_id}) ---")
                result = await session.call_tool(
                    "airbyte_get_cloud_sync_logs",
                    {"params": {"connection_id": connection_id, "max_lines": 20}},
                )
                for c in result.content:
                    text = c.text if hasattr(c, "text") else str(c)
                    print(text[:500] + ("…" if len(text) > 500 else ""))
            else:
                print("\nSkipping log tools — no connections found.")

    print("\nSmoke test complete.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
