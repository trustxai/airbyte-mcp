"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: integration tests requiring Airbyte credentials")
    config.addinivalue_line("markers", "destructive: mutating integration tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    load_dotenv()
    has_creds = bool(os.getenv("AIRBYTE_CLIENT_ID") and os.getenv("AIRBYTE_CLIENT_SECRET"))
    allow_destructive = os.getenv("AIRBYTE_TEST_ALLOW_DESTRUCTIVE") == "1"

    skip_live = pytest.mark.skip(reason="AIRBYTE_CLIENT_ID and AIRBYTE_CLIENT_SECRET required for live tests")
    skip_destructive = pytest.mark.skip(reason="Set AIRBYTE_TEST_ALLOW_DESTRUCTIVE=1 to run mutating live tests")

    for item in items:
        if "live" in item.keywords and not has_creds:
            item.add_marker(skip_live)
        if "destructive" in item.keywords and not allow_destructive:
            item.add_marker(skip_destructive)


@pytest.fixture
def internal_jobs_list_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "internal_jobs_list.json").read_text())


@pytest.fixture
def sample_internal_job(internal_jobs_list_fixture: dict) -> dict:
    return internal_jobs_list_fixture["jobs"][0]


def _get_access_token() -> str:
    load_dotenv()
    api_url = os.getenv("AIRBYTE_API_URL", "http://localhost:8000/api/public/v1")
    token = os.getenv("AIRBYTE_ACCESS_TOKEN", "")
    if token:
        return token
    client_id = os.getenv("AIRBYTE_CLIENT_ID", "")
    client_secret = os.getenv("AIRBYTE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("Missing Airbyte credentials")
    resp = httpx.post(
        f"{api_url}/applications/token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant-type": "client_credentials",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def live_connection_id() -> str:
    configured = os.getenv("AIRBYTE_TEST_CONNECTION_ID")
    if configured:
        return configured

    load_dotenv()
    api_url = os.getenv("AIRBYTE_API_URL", "http://localhost:8000/api/public/v1")
    token = _get_access_token()
    resp = httpx.get(
        f"{api_url}/connections",
        headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        params={"limit": 1},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        pytest.skip("No connections available for live tests")
    return data[0]["connectionId"]


@pytest.fixture(scope="session")
def live_succeeded_job_id(live_connection_id: str) -> int:
    load_dotenv()
    api_url = os.getenv("AIRBYTE_API_URL", "http://localhost:8000/api/public/v1")
    internal_url = api_url.replace("/api/public/v1", "/api/v1")
    token = _get_access_token()
    resp = httpx.post(
        f"{internal_url}/jobs/list",
        headers={
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        },
        json={
            "configTypes": ["sync", "reset_connection", "refresh", "clear"],
            "configId": live_connection_id,
            "statuses": ["succeeded"],
            "pagination": {"pageSize": 1, "rowOffset": 0},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    if not jobs:
        pytest.skip("No succeeded jobs available for live wait test")
    return jobs[0]["job"]["id"]
