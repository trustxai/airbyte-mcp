"""Job tools for the Airbyte API."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, paginated_response, to_json
from airbyte_mcp.server import mcp

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
        description="Filter by job type: 'sync' or 'reset'.",
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
        description="Job type: 'sync' to replicate data, or 'reset' to clear and re-sync.",
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
    """List sync and reset jobs with rich filtering options.

    Jobs represent individual sync or reset executions. Every time a
    connection runs (manually or on schedule), Airbyte creates a job
    that tracks status, duration, bytes synced, and rows synced.

    When to Use:
        - Check recent sync activity for a specific connection.
        - Find failed or running jobs across workspaces.
        - Audit sync volume (bytes/rows) over a date range.
        - Monitor whether scheduled syncs are executing on time.

    When NOT to Use:
        - If you already have a job ID, use airbyte_get_job for full
          details.
        - To see pipeline definitions (schedule, streams), use
          airbyte_get_connection instead.

    Filters:
        All filters are optional and combinable:
        - connection_id: restrict to one pipeline.
        - workspace_ids: restrict to specific workspaces.
        - job_type: "sync" or "reset".
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
