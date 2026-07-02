"""Job log and diagnostics tools using the Airbyte internal Configuration API.

These tools require a self-managed Airbyte deployment where the
Configuration API (``/api/v1``) is accessible.  They gracefully
degrade with a clear error message on Airbyte Cloud.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.config import get_settings
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, epoch_to_human, paginated_response, to_json
from airbyte_mcp.server import mcp
from airbyte_mcp.tools._internal_jobs import (
    INTERNAL_API_HINT,
    fmt_internal_job,
)
from airbyte_mcp.tools._log_utils import truncate_structured_logs

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListJobsInternalInput(BaseModel):
    """Input for listing jobs via the internal Configuration API."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(
        ...,
        min_length=1,
        description="UUID of the connection to list jobs for.",
    )
    config_types: list[str] | None = Field(
        default=None,
        description=(
            "Filter by config/job types. Common values: 'sync', "
            "'reset_connection', 'refresh', 'clear'. When omitted, "
            "returns ALL job types including refresh and clear."
        ),
    )
    status: str | None = Field(
        default=None,
        description="Filter by status: pending, running, incomplete, failed, succeeded, cancelled.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetJobDetailsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: int = Field(..., description="Numeric ID of the job.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetJobLogsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: int = Field(..., description="Numeric ID of the job.")
    attempt_number: int | None = Field(
        default=None,
        description="If set, only return logs for this specific attempt (0-indexed).",
    )
    tail_lines: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Max structured log entries to return per attempt (from the end).",
    )


class GetAttemptLogsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: int = Field(..., description="Numeric ID of the job.")
    attempt_number: int = Field(..., description="Attempt number (0-indexed).")
    tail_lines: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Max structured log entries to return (from the end).",
    )


_INTERNAL_API_HINT = INTERNAL_API_HINT

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _fmt_failure(failure: dict[str, Any]) -> str:
    origin = failure.get("failureOrigin", "unknown")
    ftype = failure.get("failureType", "unknown")
    ext_msg = failure.get("externalMessage", "")
    int_msg = failure.get("internalMessage", "")
    ts = epoch_to_human(failure.get("timestamp"))
    stacktrace = failure.get("stacktrace", "")

    lines = [
        f"  - **{origin}** / **{ftype}** at {ts}",
    ]
    if ext_msg:
        lines.append(f"    - Message: {ext_msg}")
    if int_msg:
        lines.append(f"    - Internal: {int_msg}")
    if stacktrace:
        trimmed = stacktrace[:500]
        if len(stacktrace) > 500:
            trimmed += "... (truncated)"
        lines.append(f"    - Stacktrace: `{trimmed}`")
    return "\n".join(lines)


def _fmt_attempt_stats(attempt: dict[str, Any]) -> str:
    status = attempt.get("status", "?")
    created = epoch_to_human(attempt.get("createdAt"))
    ended = epoch_to_human(attempt.get("endedAt"))
    bytes_synced = attempt.get("bytesSynced")
    records_synced = attempt.get("recordsSynced")

    lines = [
        f"### Attempt {attempt.get('id', '?')} — **{status}**",
        f"- Started: {created}",
        f"- Ended: {ended}",
        f"- Bytes synced: {bytes_synced:,}" if bytes_synced is not None else "- Bytes synced: N/A",
        f"- Records synced: {records_synced:,}" if records_synced is not None else "- Records synced: N/A",
    ]

    total_stats = attempt.get("totalStats")
    if total_stats:
        emitted = total_stats.get("recordsEmitted")
        committed = total_stats.get("recordsCommitted")
        if emitted is not None:
            lines.append(f"- Records emitted: {emitted:,}")
        if committed is not None:
            lines.append(f"- Records committed: {committed:,}")

    stream_stats = attempt.get("streamStats", [])
    if stream_stats:
        lines.append("- **Per-stream stats**:")
        for ss in stream_stats[:20]:
            name = ss.get("streamName", "?")
            ns = ss.get("streamNamespace", "")
            stats = ss.get("stats", {})
            emitted = stats.get("recordsEmitted", 0)
            committed = stats.get("recordsCommitted", 0)
            label = f"{ns}.{name}" if ns else name
            lines.append(f"  - `{label}`: {emitted:,} emitted, {committed:,} committed")
        if len(stream_stats) > 20:
            lines.append(f"  - ... +{len(stream_stats) - 20} more streams")

    failure_summary = attempt.get("failureSummary")
    if failure_summary:
        failures = failure_summary.get("failures", [])
        partial = failure_summary.get("partialSuccess")
        if partial is not None:
            lines.append(f"- Partial success: {partial}")
        if failures:
            lines.append("- **Failures**:")
            for f in failures:
                lines.append(_fmt_failure(f))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_jobs_internal",
    annotations=ToolAnnotations(
        title="List Airbyte Jobs — All Types (Internal API)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_jobs_internal(params: ListJobsInternalInput) -> str:
    """List ALL job types for a connection, including refresh and clear.

    Uses the internal Configuration API (POST /v1/jobs/list) which
    returns every job type: sync, reset_connection, refresh, clear,
    and more. The public API's airbyte_list_jobs only returns sync
    and reset on most Airbyte versions.

    When to Use:
        - Check the status of a refresh job triggered from the UI or
          via airbyte_trigger_refresh.
        - See clear jobs that aren't visible in the public API.
        - Get a complete job history for a connection including all
          job types.
        - Monitor a running refresh to see if it has completed.

    When NOT to Use:
        - On Airbyte Cloud — use airbyte_get_cloud_sync_logs for full-text logs.
        - If you only need sync/reset jobs, airbyte_list_jobs is
          simpler and works on Cloud too.

    Config Types (filter):
        Common values for config_types:
        - "sync" — regular incremental or full-refresh syncs
        - "reset_connection" — connection resets
        - "refresh" — stream refreshes (merge or truncate)
        - "clear" — stream clears
        When omitted, returns ALL types.

    Returns:
        Paginated list of jobs with per-attempt stats. Each entry
        shows config type, status, timestamps, and stream-level
        record counts when available.

    Examples:
        All jobs for a connection:
            params = { "connection_id": "a1b2c3d4-..." }
        Only refresh jobs:
            params = { "connection_id": "a1b2c3d4-...", "config_types": ["refresh"] }
        Failed jobs of any type:
            params = { "connection_id": "a1b2c3d4-...", "status": "failed" }
    """
    try:
        client = get_client()

        config_types = params.config_types or [
            "sync",
            "reset_connection",
            "refresh",
            "clear",
        ]

        body: dict[str, Any] = {
            "configTypes": config_types,
            "configId": params.connection_id,
            "pagination": {
                "pageSize": params.limit,
                "rowOffset": params.offset,
            },
        }
        if params.status:
            body["statuses"] = [params.status]

        resp = await client.request(
            "POST",
            "/jobs/list",
            json_body=body,
            use_internal=True,
        )
        data = resp.json()
        jobs = data.get("jobs", [])
        total = data.get("totalJobCount")

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        return paginated_response(
            items=jobs,
            total=total,
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=fmt_internal_job,
            title="Airbyte Jobs (Internal API)",
        )
    except Exception as exc:
        msg = handle_api_error(exc)
        if "connect" in msg.lower() or "404" in msg:
            return f"{msg}\n\n{_INTERNAL_API_HINT}"
        return msg


@mcp.tool(
    name="airbyte_get_job_details",
    annotations=ToolAnnotations(
        title="Get Airbyte Job Details (Internal API)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_job_details(params: GetJobDetailsInput) -> str:
    """Get detailed job information including per-attempt stats and failure reasons.

    Uses the internal Configuration API (POST /v1/jobs/get) which
    returns much richer data than the public API: full attempt history,
    per-stream statistics, and structured failure summaries. Works for
    ALL job types including refresh and clear jobs.

    When to Use:
        - A job failed and you need to understand WHY (failure origin,
          type, message, stacktrace).
        - You want per-stream record/byte counts for a specific sync.
        - You need to see how many attempts a job took and what
          happened in each one.
        - Monitor a refresh job's progress (get the job ID from
          airbyte_trigger_refresh or airbyte_list_jobs_internal).

    When NOT to Use:
        - For a quick status check, use airbyte_get_job (public API).
        - For actual log lines, use airbyte_get_job_logs or
          airbyte_get_attempt_logs.
        - On Airbyte Cloud — use airbyte_get_cloud_sync_logs for full-text logs.

    Returns:
        Job metadata plus a section per attempt with: status, timing,
        bytes/records synced, per-stream stats, and failure details.

    Examples:
        params = { "job_id": 12345 }
    """
    try:
        client = get_client()
        resp = await client.request(
            "POST",
            "/jobs/get",
            json_body={"id": params.job_id},
            use_internal=True,
        )
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        job = data.get("job", {})
        attempts = data.get("attempts", [])

        lines = [
            f"# Job {job.get('id', params.job_id)} — **{job.get('status', '?')}**",
            f"- **Config type**: {job.get('configType', '?')}",
            f"- **Created**: {epoch_to_human(job.get('createdAt'))}",
            f"- **Updated**: {epoch_to_human(job.get('updatedAt'))}",
            f"- **Attempts**: {len(attempts)}",
            "",
        ]

        for attempt_info in attempts:
            attempt = attempt_info.get("attempt", attempt_info)
            lines.append(_fmt_attempt_stats(attempt))
            lines.append("")

        return "\n".join(lines)
    except Exception as exc:
        msg = handle_api_error(exc)
        if "connect" in msg.lower() or "404" in msg:
            return f"{msg}\n\n{_INTERNAL_API_HINT}"
        return msg


@mcp.tool(
    name="airbyte_get_job_logs",
    annotations=ToolAnnotations(
        title="Get Airbyte Job Logs (Internal API)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_job_logs(params: GetJobLogsInput) -> str:
    """Get the actual log output for a job's sync attempts.

    Uses the internal Configuration API (POST /v1/jobs/get_debug_info)
    to fetch structured log entries for each attempt.  Logs can be very
    large, so use tail_lines to limit output and attempt_number to
    focus on a specific attempt.

    Always returns JSON — structured logs are best consumed as-is by
    LLMs and scripts.  Each log entry contains timestamp, message,
    level, logSource, and caller metadata.

    When to Use:
        - You need the raw log output to debug a sync failure.
        - You want to search for specific error messages or stack
          traces in the logs.
        - airbyte_get_job_details showed a failure but you need more
          context from the full logs.

    When NOT to Use:
        - For structured failure info, use airbyte_get_job_details.
        - On Airbyte Cloud — use airbyte_get_cloud_sync_logs for full-text logs.

    Returns:
        JSON with structured log entries per attempt, truncated to
        the last tail_lines entries.

    Examples:
        Last 200 entries for all attempts:
            params = { "job_id": 12345 }
        Last 500 entries for attempt 0 only:
            params = { "job_id": 12345, "attempt_number": 0, "tail_lines": 500 }
    """
    try:
        client = get_client()
        settings = get_settings()
        resp = await client.request(
            "POST",
            "/jobs/get_debug_info",
            json_body={"id": params.job_id},
            use_internal=True,
            timeout=settings.airbyte_internal_log_timeout_seconds,
        )
        data = resp.json()
        truncate_structured_logs(data, params.tail_lines, params.attempt_number)
        return to_json(data)
    except Exception as exc:
        msg = handle_api_error(exc)
        if "connect" in msg.lower() or "404" in msg:
            return f"{msg}\n\n{_INTERNAL_API_HINT}"
        return msg


@mcp.tool(
    name="airbyte_get_attempt_logs",
    annotations=ToolAnnotations(
        title="Get Airbyte Attempt Logs (Internal API)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_attempt_logs(params: GetAttemptLogsInput) -> str:
    """Get logs for a specific attempt of a job.

    Uses the internal Configuration API (POST /v1/attempt/get_for_job)
    to fetch structured log entries for exactly one attempt.  More
    efficient than airbyte_get_job_logs when you know which attempt
    failed.

    Always returns JSON — structured logs are best consumed as-is.

    When to Use:
        - A job had multiple attempts and you want logs for a specific
          one (e.g. the failing attempt).
        - You already identified the failing attempt number from
          airbyte_get_job_details.

    When NOT to Use:
        - If you want logs for all attempts, use airbyte_get_job_logs.
        - On Airbyte Cloud — use airbyte_get_cloud_sync_logs for full-text logs.

    Returns:
        JSON with attempt metadata and structured log entries,
        truncated to the last tail_lines entries.

    Examples:
        params = { "job_id": 12345, "attempt_number": 0 }
        params = { "job_id": 12345, "attempt_number": 2, "tail_lines": 500 }
    """
    try:
        client = get_client()
        settings = get_settings()
        resp = await client.request(
            "POST",
            "/attempt/get_for_job",
            json_body={
                "jobId": params.job_id,
                "attemptNumber": params.attempt_number,
            },
            use_internal=True,
            timeout=settings.airbyte_internal_log_timeout_seconds,
        )
        data = resp.json()
        truncate_structured_logs(data, params.tail_lines)
        return to_json(data)
    except Exception as exc:
        msg = handle_api_error(exc)
        if "connect" in msg.lower() or "404" in msg:
            return f"{msg}\n\n{_INTERNAL_API_HINT}"
        return msg
