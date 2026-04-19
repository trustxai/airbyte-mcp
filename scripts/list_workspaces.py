#!/usr/bin/env python3
"""Smoke-test: list Airbyte workspaces via direct HTTP (no MCP).

Usage:
    uv run python scripts/list_workspaces.py

Reads credentials from .env (or environment). Demonstrates the raw
API call that the MCP server wraps.
"""

import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("AIRBYTE_API_URL", "http://localhost:8000/api/public/v1")
CLIENT_ID = os.getenv("AIRBYTE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AIRBYTE_CLIENT_SECRET", "")
ACCESS_TOKEN = os.getenv("AIRBYTE_ACCESS_TOKEN", "")


def _get_token() -> str:
    if ACCESS_TOKEN:
        return ACCESS_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        print(
            "ERROR: set AIRBYTE_CLIENT_ID + AIRBYTE_CLIENT_SECRET (or AIRBYTE_ACCESS_TOKEN).",
            file=sys.stderr,
        )
        sys.exit(1)
    resp = httpx.post(
        f"{API_URL}/applications/token",
        json={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant-type": "client_credentials",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main() -> None:
    token = _get_token()
    resp = httpx.get(
        f"{API_URL}/workspaces",
        headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        params={"limit": 10},
        timeout=15.0,
    )
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
