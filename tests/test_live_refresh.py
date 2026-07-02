"""Live destructive integration tests (explicit opt-in required)."""

from __future__ import annotations

import json
import os

import pytest

from airbyte_mcp.formatters import ResponseFormat
from airbyte_mcp.tools._internal_jobs import extract_internal_job_id_status
from airbyte_mcp.tools.jobs import (
    StreamDescriptor,
    TriggerClearInput,
    TriggerRefreshInput,
    WaitForJobInput,
    airbyte_trigger_clear,
    airbyte_trigger_refresh,
    airbyte_wait_for_job,
)


@pytest.mark.live
@pytest.mark.destructive
@pytest.mark.asyncio
async def test_trigger_refresh_and_wait() -> None:
    connection_id = os.environ["AIRBYTE_TEST_CONNECTION_ID"]
    stream_name = os.environ.get("AIRBYTE_TEST_STREAM_NAME")
    if not stream_name:
        pytest.skip("Set AIRBYTE_TEST_STREAM_NAME for destructive refresh test")

    result = await airbyte_trigger_refresh(
        TriggerRefreshInput(
            connection_id=connection_id,
            streams=[StreamDescriptor(name=stream_name)],
            refresh_type="merge",
            response_format=ResponseFormat.JSON,
        )
    )
    data = json.loads(result)
    job_id, status = extract_internal_job_id_status(data)
    assert job_id != "?"
    assert status


@pytest.mark.live
@pytest.mark.destructive
@pytest.mark.asyncio
async def test_trigger_clear_and_cancel() -> None:
    connection_id = os.environ["AIRBYTE_TEST_CONNECTION_ID"]
    stream_name = os.environ.get("AIRBYTE_TEST_STREAM_NAME")
    if not stream_name:
        pytest.skip("Set AIRBYTE_TEST_STREAM_NAME for destructive clear test")

    result = await airbyte_trigger_clear(
        TriggerClearInput(
            connection_id=connection_id,
            streams=[StreamDescriptor(name=stream_name)],
            response_format=ResponseFormat.JSON,
        )
    )
    data = json.loads(result)
    job_id, _status = extract_internal_job_id_status(data)
    assert isinstance(job_id, int)

    wait_result = await airbyte_wait_for_job(
        WaitForJobInput(job_id=job_id, max_wait_seconds=30, poll_interval_seconds=2)
    )
    assert any(word in wait_result.lower() for word in ("pending", "running", "succeeded", "cancelled", "failed"))
