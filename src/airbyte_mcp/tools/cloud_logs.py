"""Cloud full-text sync log reads (Airbyte Cloud only).

Uses the Config API (``POST /jobs/get``) to fetch embedded attempt logs,
matching the PyAirbyte ``get_full_log_text`` path used by the official
Replication MCP.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

from airbyte_mcp.client import get_client
from airbyte_mcp.config import get_settings
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import to_json
from airbyte_mcp.server import mcp
from airbyte_mcp.tools._internal_jobs import CLOUD_LOGS_HINT
from airbyte_mcp.tools._log_utils import (
    _resolve_logs_payload,
    attempt_matches,
    extract_full_log_text,
    paginate_log_text,
)


class GetCloudSyncLogsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(
        ...,
        min_length=1,
        description="UUID of the Airbyte Cloud connection.",
    )
    job_id: int | None = Field(
        default=None,
        description="Optional job ID. When omitted, the latest job for the connection is used.",
    )
    attempt_number: int | None = Field(
        default=None,
        description="Optional attempt number (0-indexed). When omitted, the latest attempt is used.",
    )
    max_lines: int = Field(
        default=4000,
        ge=0,
        le=50000,
        description="Maximum number of log lines to return. Use 0 for no limit.",
    )
    from_tail: bool | None = Field(
        default=None,
        description=(
            "When true, return the last max_lines from the log. Defaults to true "
            "unless line_offset is set. Cannot combine with line_offset."
        ),
    )
    line_offset: int | None = Field(
        default=None,
        ge=0,
        description="Number of lines to skip from the start. Cannot combine with from_tail=true.",
    )

    @model_validator(mode="after")
    def validate_pagination(self) -> GetCloudSyncLogsInput:
        if self.line_offset is not None and self.from_tail is True:
            msg = "Cannot specify both line_offset and from_tail=true."
            raise ValueError(msg)
        return self


async def _resolve_latest_job_id(connection_id: str) -> int:
    client = get_client()
    resp = await client.request(
        "GET",
        "/jobs",
        params={
            "connectionId": connection_id,
            "limit": 1,
            "orderBy": "createdAt|DESC",
        },
    )
    jobs = resp.json().get("data", [])
    if not jobs:
        raise ValueError(f"No jobs found for connection {connection_id}")

    raw_id = jobs[0].get("jobId")
    if raw_id is None:
        raise ValueError(f"Latest job for connection {connection_id} has no jobId")
    return int(raw_id)


def _select_attempt(
    attempts_data: list[dict[str, Any]],
    attempt_number: int | None,
) -> tuple[int, dict[str, Any]]:
    if not attempts_data:
        raise ValueError("No attempts found for this job")

    if attempt_number is not None:
        for index, attempt_info in enumerate(attempts_data):
            if attempt_matches(attempt_info, attempt_number, index):
                return attempt_number, attempt_info
        raise ValueError(f"Attempt {attempt_number} not found for this job")

    latest_index = 0
    latest_number = 0
    for index, attempt_info in enumerate(attempts_data):
        attempt = attempt_info.get("attempt", attempt_info)
        number = attempt.get("attemptNumber", index) if isinstance(attempt, dict) else index
        if number >= latest_number:
            latest_number = number
            latest_index = index

    return latest_number, attempts_data[latest_index]


@mcp.tool(
    name="airbyte_get_cloud_sync_logs",
    annotations=ToolAnnotations(
        title="Get Airbyte Cloud Sync Logs (Full Text)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_cloud_sync_logs(params: GetCloudSyncLogsInput) -> str:
    """Get full-text sync logs for an Airbyte Cloud connection job attempt.

    Uses the Airbyte Cloud Config API (``POST /jobs/get``) to fetch embedded
    attempt logs and returns plain text with pagination metadata. This is the
    Cloud parity path — self-managed deployments should use
    ``airbyte_get_job_logs`` or ``airbyte_get_attempt_logs`` for richer
    structured diagnostics instead.

    When to Use:
        - You are on Airbyte Cloud and need the raw log text for a sync.
        - You want paginated tail/head reads of a large Cloud log file.
        - You already know the connection and optionally the job/attempt.

    When NOT to Use:
        - On self-managed Airbyte (abctl / OSS) — use the internal-API log tools.
        - When you need structured failure metadata — use
          ``airbyte_get_job_details`` on self-managed.

    Returns:
        JSON with job_id, attempt_number, log_text, log_text_start_line,
        log_text_line_count, and total_log_lines_available.

    Examples:
        Latest job, last 4000 lines:
            params = { "connection_id": "a1b2c3d4-..." }
        Specific job and attempt:
            params = {
                "connection_id": "a1b2c3d4-...",
                "job_id": 12345,
                "attempt_number": 0,
                "max_lines": 1000,
            }
    """
    settings = get_settings()
    if not settings.is_cloud_deployment:
        return CLOUD_LOGS_HINT

    from_tail = params.from_tail
    if from_tail is None and params.line_offset is None:
        from_tail = True
    if from_tail is None:
        from_tail = False

    try:
        client = get_client()
        job_id = params.job_id if params.job_id is not None else await _resolve_latest_job_id(params.connection_id)

        resp = await client.request(
            "POST",
            "/jobs/get",
            json_body={"id": job_id},
            use_internal=True,
            timeout=settings.airbyte_internal_log_timeout_seconds,
        )
        data = resp.json()
        attempts_data = data.get("attempts", [])
        attempt_number, attempt_info = _select_attempt(attempts_data, params.attempt_number)

        log_text = extract_full_log_text(_resolve_logs_payload(attempt_info))
        if not log_text:
            payload = {
                "job_id": job_id,
                "attempt_number": attempt_number,
                "log_text": (f"[No logs available for job '{job_id}', attempt {attempt_number}.]"),
                "log_text_start_line": 1,
                "log_text_line_count": 0,
                "total_log_lines_available": 0,
            }
            return to_json(payload)

        text, start_line, line_count, total_lines = paginate_log_text(
            log_text,
            max_lines=params.max_lines,
            from_tail=from_tail,
            line_offset=params.line_offset,
        )
        return to_json(
            {
                "job_id": job_id,
                "attempt_number": attempt_number,
                "log_text": text,
                "log_text_start_line": start_line,
                "log_text_line_count": line_count,
                "total_log_lines_available": total_lines,
            }
        )
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        msg = handle_api_error(exc)
        if "connect" in msg.lower() or "404" in msg:
            return f"{msg}\n\n{CLOUD_LOGS_HINT}"
        return msg
