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
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, epoch_to_human, to_json
from airbyte_mcp.server import mcp

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


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
        description="Max log lines to return per attempt (from the end).",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetAttemptLogsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: int = Field(..., description="Numeric ID of the job.")
    attempt_number: int = Field(..., description="Attempt number (0-indexed).")
    tail_lines: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Max log lines to return (from the end).",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


_INTERNAL_API_HINT = (
    "This tool requires the Airbyte Configuration API (self-managed only). "
    "If you are using Airbyte Cloud, this endpoint is not available."
)

# ---------------------------------------------------------------------------
# Formatters
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


def _extract_log_lines(
    attempt_info: dict[str, Any],
    tail_lines: int,
) -> list[str]:
    """Extract log lines from an AttemptInfoRead object."""
    logs = attempt_info.get("logs")
    if not logs:
        return []
    if isinstance(logs, dict):
        lines: list[str] = logs.get("logLines", [])
    elif isinstance(logs, list):
        lines = list(logs)
    else:
        return []
    if tail_lines and len(lines) > tail_lines:
        return list(lines[-tail_lines:])
    return lines


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


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
    per-stream statistics, and structured failure summaries.

    When to Use:
        - A job failed and you need to understand WHY (failure origin,
          type, message, stacktrace).
        - You want per-stream record/byte counts for a specific sync.
        - You need to see how many attempts a job took and what
          happened in each one.

    When NOT to Use:
        - For a quick status check, use airbyte_get_job (public API).
        - For actual log lines, use airbyte_get_job_logs or
          airbyte_get_attempt_logs.
        - On Airbyte Cloud (internal API not available).

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
    to fetch raw log lines for each attempt. Logs can be very large,
    so use tail_lines to limit output and attempt_number to focus on
    a specific attempt.

    When to Use:
        - You need the raw log output to debug a sync failure.
        - You want to search for specific error messages or stack
          traces in the logs.
        - airbyte_get_job_details showed a failure but you need more
          context from the full logs.

    When NOT to Use:
        - For structured failure info, use airbyte_get_job_details.
        - On Airbyte Cloud (internal API not available).

    Returns:
        Log lines per attempt, limited to tail_lines from the end
        of each attempt's log output.

    Examples:
        Last 200 lines for all attempts:
            params = { "job_id": 12345 }
        Last 500 lines for attempt 0 only:
            params = { "job_id": 12345, "attempt_number": 0, "tail_lines": 500 }
    """
    try:
        client = get_client()
        resp = await client.request(
            "POST",
            "/jobs/get_debug_info",
            json_body={"id": params.job_id},
            use_internal=True,
        )
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        attempts = data.get("attempts", [])
        lines = [f"# Logs for Job {params.job_id}", ""]

        for i, attempt_info in enumerate(attempts):
            if params.attempt_number is not None and i != params.attempt_number:
                continue

            attempt = attempt_info.get("attempt", {})
            status = attempt.get("status", "?")
            log_lines = _extract_log_lines(attempt_info, params.tail_lines)

            lines.append(f"## Attempt {i} — **{status}**")
            if log_lines:
                logs = attempt_info.get("logs")
                total = len(logs.get("logLines", [])) if isinstance(logs, dict) else len(logs or [])
                if total > params.tail_lines:
                    lines.append(f"*Showing last {params.tail_lines} of {total} lines*\n")
                lines.append("```")
                lines.extend(log_lines)
                lines.append("```")
            else:
                lines.append("*No log lines available.*")
            lines.append("")

        if not attempts:
            lines.append("*No attempts found for this job.*")

        return "\n".join(lines)
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
    to fetch log lines for exactly one attempt. More efficient than
    airbyte_get_job_logs when you know which attempt failed.

    When to Use:
        - A job had multiple attempts and you want logs for a specific
          one (e.g. the failing attempt).
        - You already identified the failing attempt number from
          airbyte_get_job_details.

    When NOT to Use:
        - If you want logs for all attempts, use airbyte_get_job_logs.
        - On Airbyte Cloud (internal API not available).

    Returns:
        Log lines for the specified attempt.

    Examples:
        params = { "job_id": 12345, "attempt_number": 0 }
        params = { "job_id": 12345, "attempt_number": 2, "tail_lines": 500 }
    """
    try:
        client = get_client()
        resp = await client.request(
            "POST",
            "/attempt/get_for_job",
            json_body={
                "jobId": params.job_id,
                "attemptNumber": params.attempt_number,
            },
            use_internal=True,
        )
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return to_json(data)

        attempt = data.get("attempt", {})
        status = attempt.get("status", "?")
        log_lines = _extract_log_lines(data, params.tail_lines)

        lines = [
            f"# Attempt {params.attempt_number} of Job {params.job_id} — **{status}**",
            "",
        ]

        lines.append(_fmt_attempt_stats(attempt))
        lines.append("")

        if log_lines:
            all_logs = data.get("logs")
            total = len(all_logs.get("logLines", [])) if isinstance(all_logs, dict) else len(all_logs or [])
            if total > params.tail_lines:
                lines.append(f"*Showing last {params.tail_lines} of {total} lines*\n")
            lines.append("```")
            lines.extend(log_lines)
            lines.append("```")
        else:
            lines.append("*No log lines available for this attempt.*")

        return "\n".join(lines)
    except Exception as exc:
        msg = handle_api_error(exc)
        if "connect" in msg.lower() or "404" in msg:
            return f"{msg}\n\n{_INTERNAL_API_HINT}"
        return msg
