"""Live read-only integration tests (credential-gated)."""

from __future__ import annotations

import pytest

from airbyte_mcp.tools.job_logs import (
    GetAttemptLogsInput,
    GetJobLogsInput,
    ListJobsInternalInput,
    airbyte_get_attempt_logs,
    airbyte_get_job_logs,
    airbyte_list_jobs_internal,
)
from airbyte_mcp.tools.jobs import WaitForJobInput, airbyte_wait_for_job


@pytest.mark.live
@pytest.mark.asyncio
async def test_list_jobs_internal_returns_jobs(live_connection_id: str) -> None:
    result = await airbyte_list_jobs_internal(ListJobsInternalInput(connection_id=live_connection_id, limit=3))
    assert "Airbyte Jobs (Internal API)" in result
    assert "Job " in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_wait_for_job_terminal_immediately(live_succeeded_job_id: int) -> None:
    result = await airbyte_wait_for_job(
        WaitForJobInput(
            job_id=live_succeeded_job_id,
            max_wait_seconds=1,
            poll_interval_seconds=1,
        )
    )
    assert "succeeded" in result.lower()


@pytest.mark.live
@pytest.mark.asyncio
async def test_get_job_logs_returns_structured_json(live_succeeded_job_id: int) -> None:
    result = await airbyte_get_job_logs(GetJobLogsInput(job_id=live_succeeded_job_id, tail_lines=10))
    assert not result.startswith("Error")
    assert "attempts" in result or "logs" in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_get_attempt_logs_returns_structured_json(live_succeeded_job_id: int) -> None:
    result = await airbyte_get_attempt_logs(
        GetAttemptLogsInput(job_id=live_succeeded_job_id, attempt_number=0, tail_lines=10)
    )
    assert not result.startswith("Error")
    assert "logs" in result or "attempt" in result
