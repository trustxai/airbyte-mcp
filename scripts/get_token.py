#!/usr/bin/env python3
"""Exchange Airbyte client credentials for an access token.

Usage:
    uv run python scripts/get_token.py

Reads AIRBYTE_API_URL, AIRBYTE_CLIENT_ID, and AIRBYTE_CLIENT_SECRET
from a .env file (or environment variables).
"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("AIRBYTE_API_URL", "http://localhost:8000/api/public/v1")
CLIENT_ID = os.getenv("AIRBYTE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AIRBYTE_CLIENT_SECRET", "")


def main() -> None:
    if not CLIENT_ID or not CLIENT_SECRET:
        print(
            "ERROR: AIRBYTE_CLIENT_ID and AIRBYTE_CLIENT_SECRET must be set.",
            file=sys.stderr,
        )
        print("Run `abctl local credentials` to retrieve them.", file=sys.stderr)
        sys.exit(1)

    url = f"{API_URL}/applications/token"
    print(f"POST {url}")

    resp = httpx.post(
        url,
        json={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant-type": "client_credentials",
        },
        timeout=15.0,
    )

    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    body = resp.json()
    print(f"\nAccess token (expires in {body.get('expires_in', '?')}s):\n")
    print(body["access_token"])


if __name__ == "__main__":
    main()
