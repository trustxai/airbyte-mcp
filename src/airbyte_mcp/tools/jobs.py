"""Job tools for the Airbyte API."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, paginated_response, to_json
from airbyte_mcp.server import mcp
from airbyte_mcp.tools._internal_jobs import (
    INTERNAL_API_HINT,
    TERMINAL_JOB_STATUSES,
    build_stream_descriptors,
    extract_internal_job_id_status,
    fmt_internal_job,
)

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListJobsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str | None = Field(
        default=None,
        description="Filter by connection UUID.",
    )
    workspace_ids: list[str] | None = Field(
        default=None,
        description="Filter by workspace UUIDs.",
    )
    job_type: str | None = Field(
        default=None,
        description=(
            "Filter by job type: 'sync', 'reset', 'refresh', or 'clear'. "
            "Note: 'refresh' and 'clear' require Airbyte >= 0.63 and may not "
            "appear on older deployments. When omitted, defaults to sync+reset "
            "on most Airbyte versions."
        ),
    )
    status: str | None = Field(
        default=None,
        description="Filter by status: pending, running, incomplete, failed, succeeded, cancelled.",
    )
    created_at_start: str | None = Field(
        default=None,
        description="ISO-8601 start date filter (e.g. '2024-01-01T00:00:00Z').",
    )
    created_at_end: str | None = Field(
        default=None,
        description="ISO-8601 end date filter.",
    )
    order_by: str | None = Field(
        default=None,
        description="Order results, e.g. 'createdAt|DESC'.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetJobInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: str = Field(..., min_length=1, description="Numeric ID of the job (as string).")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class TriggerSyncInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(..., min_length=1, description="UUID of the connection to sync.")
    job_type: str = Field(
        default="sync",
        description=(
            "Job type: 'sync' to replicate data, or 'reset' to clear and "
            "re-sync. To trigger a refresh (non-destructive re-read), use "
            "airbyte_trigger_refresh instead."
        ),
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class StreamDescriptor(BaseModel):
    """Identifies a single connection stream."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Stream name (e.g. 'oe-trailer').")
    namespace: str | None = Field(
        default=None,
        description="Stream namespace. Omit if the stream has no namespace.",
    )


class TriggerRefreshInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(
        ...,
        min_length=1,
        description="UUID of the connection containing the streams to refresh.",
    )
    streams: list[StreamDescriptor] = Field(
        ...,
        min_length=1,
        description="One or more streams to refresh. Each needs at least a 'name'.",
    )
    refresh_type: str = Field(
        default="merge",
        description=(
            "Refresh strategy: 'merge' retains previous records and merges "
            "new data (Refresh and Retain Records); 'truncate' replaces "
            "destination data with the fresh read (Refresh and Remove Records)."
        ),
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class TriggerClearInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(
        ...,
        min_length=1,
        description="UUID of the connection containing the streams to clear.",
    )
    streams: list[StreamDescriptor] = Field(
        ...,
        min_length=1,
        description="One or more streams to clear. Each needs at least a 'name'.",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class WaitForJobInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: int = Field(..., description="Numeric ID of the job to monitor.")
    max_wait_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Maximum seconds to wait before returning a timeout message.",
    )
    poll_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Seconds between status polls.",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class CancelJobInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: str = Field(..., min_length=1, description="Numeric ID of the job to cancel.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_job(job: dict[str, Any]) -> str:
    duration = job.get("duration", "N/A")
    bytes_synced = job.get("bytesSynced")
    rows_synced = job.get("rowsSynced")
    bytes_str = f"{bytes_synced:,}" if bytes_synced is not None else "N/A"
    rows_str = f"{rows_synced:,}" if rows_synced is not None else "N/A"
    status = job.get("status", "?")
    lines = [
        f"## Job {job.get('jobId', '?')} — **{status}**",
        f"- **Type**: {job.get('jobType', '?')}",
        f"- **Connection**: {job.get('connectionId', '?')}",
        f"- **Started**: {job.get('startTime', 'N/A')}",
        f"- **Last updated**: {job.get('lastUpdatedAt', 'N/A')}",
        f"- **Duration**: {duration}",
        f"- **Bytes synced**: {bytes_str}",
        f"- **Rows synced**: {rows_str}",
    ]
    if status in ("failed", "incomplete"):
        lines.append(
            "- **Tip**: Use `airbyte_get_job_details` for failure reasons and `airbyte_get_job_logs` for full logs."
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_jobs",
    annotations=ToolAnnotations(
        title="List Airbyte Jobs",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_jobs(params: ListJobsInput) -> str:
    """List sync, reset, refresh, and clear jobs with rich filtering.

    Jobs represent individual executions. Every time a connection runs
    (manually or on schedule), Airbyte creates a job that tracks
    status, duration, bytes synced, and rows synced.

    When to Use:
        - Check recent sync activity for a specific connection.
        - Find failed or running jobs across workspaces.
        - Audit sync volume (bytes/rows) over a date range.
        - Monitor whether scheduled syncs are executing on time.
        - Check the status of a refresh or clear job.

    When NOT to Use:
        - If you already have a job ID, use airbyte_get_job for full
          details.
        - To see pipeline definitions (schedule, streams), use
          airbyte_get_connection instead.
        - If refresh/clear jobs are not returned (older Airbyte
          versions), use airbyte_list_jobs_internal instead.

    Filters:
        All filters are optional and combinable:
        - connection_id: restrict to one pipeline.
        - workspace_ids: restrict to specific workspaces.
        - job_type: "sync", "reset", "refresh", or "clear".
          Note: "refresh" and "clear" require Airbyte >= 0.63.
          When omitted, most versions default to sync+reset only.
        - status: pending, running, incomplete, failed, succeeded,
          or cancelled.
        - created_at_start / created_at_end: ISO-8601 date range
          (e.g. "2024-01-01T00:00:00Z").
        - order_by: sort field, e.g. "createdAt|DESC" (default).

    Returns:
        Paginated list of jobs. Each entry includes:
        - jobId, jobType, status, connectionId, startTime, duration,
          bytesSynced, rowsSynced.

        Markdown format shows a heading per job with bullet fields.
        JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).

    Examples:
        Recent failed jobs for a connection:
            params = { "connection_id": "a1b2c3d4-...", "status": "failed", "limit": 5 }
        All sync jobs in the last 7 days:
            params = { "job_type": "sync", "created_at_start": "2024-06-01T00:00:00Z" }
        Refresh jobs for a connection:
            params = { "connection_id": "a1b2c3d4-...", "job_type": "refresh" }
        Latest 3 jobs, newest first:
            params = { "limit": 3, "order_by": "createdAt|DESC" }
    """
    try:
        client = get_client()
        query: dict[str, Any] = {"limit": params.limit, "offset": params.offset}
        if params.connection_id:
            query["connectionId"] = params.connection_id
        if params.workspace_ids:
            query["workspaceIds"] = params.workspace_ids
        if params.job_type:
            query["jobType"] = params.job_type
        if params.status:
            query["status"] = params.status
        if params.created_at_start:
            query["createdAtStart"] = params.created_at_start
        if params.created_at_end:
            query["createdAtEnd"] = params.created_at_end
        if params.order_by:
            query["orderBy"] = params.order_by

        resp = await client.request("GET", "/jobs", params=query)
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_job,
            title="Airbyte Jobs",
        )
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_job",
    annotations=ToolAnnotations(
        title="Get Airbyte Job",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_job(params: GetJobInput) -> str:
    """Get full details of a single sync or reset job by its numeric ID.

    Returns the job status, type, associated connection, start time,
    duration, and volume metrics (bytes and rows synced). Use this to
    inspect a specific job's outcome.

    When to Use:
        - Check whether a specific job succeeded or failed.
        - Get precise bytes/rows synced for a particular run.
        - Inspect job duration for performance analysis.
        - Follow up on a job ID returned by airbyte_list_jobs.

    When NOT to Use:
        - If you need to browse multiple jobs, use airbyte_list_jobs
          with filters.
        - To see the pipeline definition (schedule, streams), use
          airbyte_get_connection instead.

    Returns:
        Job details including: jobId, jobType, status, connectionId,
        startTime, duration, bytesSynced, rowsSynced.

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get job by ID:
            params = { "job_id": "12345" }
        Get raw JSON:
            params = { "job_id": "12345", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the job ID does not exist.
    """
    try:
        client = get_client()
        resp = await client.request("GET", f"/jobs/{params.job_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_job(data)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_trigger_sync",
    annotations=ToolAnnotations(
        title="Trigger Airbyte Sync",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_trigger_sync(params: TriggerSyncInput) -> str:
    """Trigger a sync or reset job for a connection.

    Starts a new job that replicates data from source to destination
    (sync) or clears destination data and re-syncs (reset).

    When to Use:
        - Manually kick off a sync outside the regular schedule.
        - Trigger a reset after schema changes or data issues.
        - Automate syncs in response to upstream events.

    When NOT to Use:
        - The connection is already running a sync (check with
          airbyte_list_jobs first).
        - If you need a non-destructive refresh (re-read without
          clearing the destination), use airbyte_trigger_refresh
          instead. Resets drop destination data first, which causes
          downtime; refreshes swap data only on success.

    Returns:
        The newly created job with its jobId and initial status.

    Examples:
        Trigger a sync:
            params = { "connection_id": "a1b2c3d4-..." }
        Trigger a reset:
            params = { "connection_id": "a1b2c3d4-...", "job_type": "reset" }
    """
    try:
        client = get_client()
        body = {
            "connectionId": params.connection_id,
            "jobType": params.job_type,
        }
        resp = await client.request("POST", "/jobs", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_job(data)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_cancel_job",
    annotations=ToolAnnotations(
        title="Cancel Airbyte Job",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_cancel_job(params: CancelJobInput) -> str:
    """Cancel a running sync or reset job.

    Sends a cancellation request to the Airbyte API. The job will
    transition to 'cancelled' status. Already-committed data is
    retained; only in-flight data is discarded.

    When to Use:
        - Stop a long-running or stuck sync.
        - Cancel an accidental reset.

    Returns:
        The cancelled job's details.

    Examples:
        params = { "job_id": "12345" }
    """
    try:
        client = get_client()
        resp = await client.request("DELETE", f"/jobs/{params.job_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_job(data)
    except Exception as exc:
        return handle_api_error(exc)


_INTERNAL_API_HINT = INTERNAL_API_HINT


def _internal_api_error_message(exc: Exception) -> str:
    msg = handle_api_error(exc)
    if "connect" in msg.lower() or "404" in msg or "405" in msg:
        return f"{msg}\n\n{_INTERNAL_API_HINT}"
    return msg


def _fmt_triggered_job(
    *,
    action: str,
    data: dict[str, Any],
    connection_id: str,
    stream_names: str,
    extra_lines: list[str] | None = None,
) -> str:
    job_id, status = extract_internal_job_id_status(data)
    lines = [
        f"## {action}",
        f"- **Job ID**: {job_id}",
        f"- **Status**: {status}",
        f"- **Streams**: {stream_names}",
        f"- **Connection**: {connection_id}",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    lines.append("")
    lines.append("Use `airbyte_wait_for_job` or `airbyte_get_job_details` to monitor progress.")
    return "\n".join(lines)


async def _fetch_internal_job(job_id: int) -> dict[str, Any]:
    client = get_client()
    resp = await client.request(
        "POST",
        "/jobs/get",
        json_body={"id": job_id},
        use_internal=True,
    )
    data: dict[str, Any] = resp.json()
    return data


@mcp.tool(
    name="airbyte_trigger_refresh",
    annotations=ToolAnnotations(
        title="Trigger Airbyte Stream Refresh (Internal API)",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_trigger_refresh(params: TriggerRefreshInput) -> str:
    """Trigger a refresh for one or more streams in a connection.

    Uses the internal Configuration API to start a refresh job. Unlike
    a reset (which drops destination data first), a refresh re-reads
    from source and swaps/merges data only on success — no downtime.

    Requires a self-managed Airbyte deployment where the Configuration
    API (/api/v1) is accessible. NOT available on Airbyte Cloud.

    When to Use:
        - A stream has data gaps from a connector bug and you want to
          re-read without clearing the destination table first.
        - You need to reconcile stale rows in an incremental-append
          stream without risking downtime from a full reset.
        - Source data was corrected and you want to pull a fresh copy
          while the old data remains queryable.

    When NOT to Use:
        - On Airbyte Cloud (internal API not available).
        - If a full reset is acceptable, use airbyte_trigger_sync with
          job_type='reset' instead (simpler, public API).
        - If the connection is already running a job, wait for it to
          finish first.

    Refresh Types:
        - 'merge' (default): Retain previous records and merge new
          data. Old and new generations coexist, distinguished by
          _airbyte_generation_id. Safest option.
        - 'truncate': Replace destination data with the fresh read.
          Only newly synced rows appear after completion.

    Returns:
        The created job with its jobId and initial status.

    Examples:
        Refresh a single stream (merge):
            params = {
                "connection_id": "a1b2c3d4-...",
                "streams": [{"name": "oe-trailer"}]
            }
        Refresh multiple streams (truncate):
            params = {
                "connection_id": "a1b2c3d4-...",
                "streams": [
                    {"name": "oe-trailer"},
                    {"name": "arinvitm", "namespace": "public"}
                ],
                "refresh_type": "truncate"
            }
    """
    try:
        client = get_client()

        refresh_mode = "Merge" if params.refresh_type.lower() == "merge" else "Truncate"

        body: dict[str, Any] = {
            "connectionId": params.connection_id,
            "refreshMode": refresh_mode,
            "streams": build_stream_descriptors(params.streams),
        }
        resp = await client.request(
            "POST",
            "/connections/refresh",
            json_body=body,
            use_internal=True,
        )
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        stream_names = ", ".join(s.name for s in params.streams)
        return _fmt_triggered_job(
            action="Refresh triggered",
            data=data,
            connection_id=params.connection_id,
            stream_names=stream_names,
            extra_lines=[f"- **Refresh type**: {params.refresh_type}"],
        )
    except Exception as exc:
        return _internal_api_error_message(exc)


@mcp.tool(
    name="airbyte_trigger_clear",
    annotations=ToolAnnotations(
        title="Trigger Airbyte Stream Clear (Internal API)",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_trigger_clear(params: TriggerClearInput) -> str:
    """Clear destination data for one or more streams in a connection.

    Uses the internal Configuration API (POST /connections/clear) to
    remove synced data for the selected streams and reset their cursors.
    Unlike a refresh, a clear does not re-read from source — run a sync
    afterward to backfill data.

    Requires a self-managed Airbyte deployment where the Configuration
    API (/api/v1) is accessible. NOT available on Airbyte Cloud.

    When to Use:
        - Remove stale or incorrect destination data for specific streams.
        - Prepare streams for a clean re-sync after schema or config changes.
        - Clear affected streams after approving non-breaking schema changes.

    When NOT to Use:
        - On Airbyte Cloud (internal API not available).
        - If you want to re-read source data without deleting first, use
          airbyte_trigger_refresh instead.
        - If the connection is already running a job, wait for it to finish.

    Returns:
        The created clear/reset job with its job ID and initial status.

    Examples:
        Clear a single stream:
            params = {
                "connection_id": "a1b2c3d4-...",
                "streams": [{"name": "oe-trailer"}]
            }
        Clear multiple streams:
            params = {
                "connection_id": "a1b2c3d4-...",
                "streams": [
                    {"name": "oe-trailer"},
                    {"name": "arinvitm", "namespace": "public"}
                ]
            }
    """
    try:
        client = get_client()
        body: dict[str, Any] = {
            "connectionId": params.connection_id,
            "streams": build_stream_descriptors(params.streams),
        }
        resp = await client.request(
            "POST",
            "/connections/clear",
            json_body=body,
            use_internal=True,
        )
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        stream_names = ", ".join(s.name for s in params.streams)
        return _fmt_triggered_job(
            action="Clear triggered",
            data=data,
            connection_id=params.connection_id,
            stream_names=stream_names,
            extra_lines=["- **Note**: Run a sync after clear completes to backfill data."],
        )
    except Exception as exc:
        return _internal_api_error_message(exc)


@mcp.tool(
    name="airbyte_wait_for_job",
    annotations=ToolAnnotations(
        title="Wait for Airbyte Job Completion (Internal API)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_wait_for_job(params: WaitForJobInput) -> str:
    """Poll an internal job until it reaches a terminal status.

    Uses the internal Configuration API (POST /jobs/get) to poll job
    status until it becomes succeeded, failed, cancelled, or incomplete,
    or until max_wait_seconds is reached.

    When to Use:
        - After airbyte_trigger_refresh or airbyte_trigger_clear to
          block until the job finishes.
        - Automate workflows that need to know when a job completed.

    When NOT to Use:
        - For a one-shot status check, use airbyte_get_job_details.
        - On Airbyte Cloud (internal API not available).

    Returns:
        Final job summary when a terminal status is reached, or a
        timeout message if max_wait_seconds elapses first.

    Examples:
        Wait up to 10 minutes for job 12345:
            params = { "job_id": 12345, "max_wait_seconds": 600 }
        Poll every 10 seconds:
            params = { "job_id": 12345, "poll_interval_seconds": 10 }
    """
    try:
        elapsed = 0
        last_data: dict[str, Any] | None = None

        while elapsed <= params.max_wait_seconds:
            last_data = await _fetch_internal_job(params.job_id)
            status = last_data.get("job", {}).get("status", "?")

            if status in TERMINAL_JOB_STATUSES:
                if params.response_format == ResponseFormat.JSON:
                    return to_json(last_data)
                return fmt_internal_job(last_data)

            if elapsed >= params.max_wait_seconds:
                break

            await asyncio.sleep(params.poll_interval_seconds)
            elapsed += params.poll_interval_seconds

        status = last_data.get("job", {}).get("status", "?") if last_data else "unknown"
        if params.response_format == ResponseFormat.JSON and last_data is not None:
            payload = {
                "timed_out": True,
                "job_id": params.job_id,
                "last_status": status,
                "elapsed_seconds": elapsed,
                "job": last_data,
            }
            return to_json(payload)

        return (
            f"## Job {params.job_id} still **{status}** after {elapsed}s\n"
            f"- Poll again with `airbyte_wait_for_job` or check "
            f"`airbyte_get_job_details`.\n"
        )
    except Exception as exc:
        return _internal_api_error_message(exc)
