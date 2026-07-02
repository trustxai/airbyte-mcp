"""Shared helpers for internal Configuration API job tools."""

from __future__ import annotations

from typing import Any

from airbyte_mcp.formatters import epoch_to_human

INTERNAL_API_HINT = (
    "This tool requires the Airbyte Configuration API (self-managed only). "
    "If you are using Airbyte Cloud, this endpoint is not available."
)

TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled", "incomplete"})

CONFIG_TYPE_LABELS: dict[str, str] = {
    "sync": "Sync",
    "reset_connection": "Reset",
    "refresh": "Refresh",
    "clear": "Clear",
    "check_connection_source": "Check Source",
    "check_connection_destination": "Check Destination",
    "discover_schema": "Discover Schema",
}


def build_stream_descriptors(streams: list[Any]) -> list[dict[str, str]]:
    """Build internal-API stream descriptors from pydantic stream models."""
    descriptors: list[dict[str, str]] = []
    for stream in streams:
        descriptor: dict[str, str] = {"streamName": stream.name}
        if stream.namespace is not None:
            descriptor["streamNamespace"] = stream.namespace
        descriptors.append(descriptor)
    return descriptors


def extract_internal_job_id_status(data: dict[str, Any]) -> tuple[int | str, str]:
    """Extract job id and status from internal API trigger responses."""
    job = data.get("job", {})
    job_id = data.get("jobId", job.get("id", "?"))
    status = data.get("status", job.get("status", "?"))
    return job_id, status


def format_duration_seconds(created_at: int | float | None, updated_at: int | float | None) -> str:
    """Human-readable duration between two epoch timestamps (seconds or ms)."""
    if created_at is None or updated_at is None:
        return "N/A"
    start = created_at / 1000 if created_at > 1e11 else created_at
    end = updated_at / 1000 if updated_at > 1e11 else updated_at
    seconds = max(0, int(end - start))
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def format_enabled_streams(enabled_streams: list[dict[str, Any]] | None) -> str:
    if not enabled_streams:
        return "N/A"
    labels: list[str] = []
    for stream in enabled_streams[:10]:
        name = stream.get("name", "?")
        namespace = stream.get("namespace", "")
        labels.append(f"{namespace}.{name}" if namespace else name)
    if len(enabled_streams) > 10:
        labels.append(f"+{len(enabled_streams) - 10} more")
    return ", ".join(labels)


def append_stream_stats_lines(
    lines: list[str],
    *,
    stream_stats: list[dict[str, Any]] | None,
    stream_aggregated_stats: list[dict[str, Any]] | None,
    prefix: str = "- **Per-stream stats**:",
) -> None:
    """Append per-stream stats from attempt-level or job-level aggregates."""
    if stream_stats:
        lines.append(prefix)
        for ss in stream_stats[:20]:
            name = ss.get("streamName", "?")
            ns = ss.get("streamNamespace", "")
            stats = ss.get("stats", {})
            emitted = stats.get("recordsEmitted", 0)
            committed = stats.get("recordsCommitted", 0)
            stream_label = f"{ns}.{name}" if ns else name
            lines.append(f"  - `{stream_label}`: {emitted:,} emitted, {committed:,} committed")
        if len(stream_stats) > 20:
            lines.append(f"  - ... +{len(stream_stats) - 20} more streams")
        return

    if stream_aggregated_stats:
        lines.append(prefix)
        for ss in stream_aggregated_stats[:20]:
            name = ss.get("streamName", "?")
            emitted = ss.get("recordsEmitted", 0)
            committed = ss.get("recordsCommitted", 0)
            lines.append(f"  - `{name}`: {emitted:,} emitted, {committed:,} committed")
        if len(stream_aggregated_stats) > 20:
            lines.append(f"  - ... +{len(stream_aggregated_stats) - 20} more streams")


def fmt_internal_job(job_info: dict[str, Any]) -> str:
    """Format a job from internal /jobs/list or /jobs/get responses."""
    job = job_info.get("job", job_info)
    config_type = job.get("configType", "?")
    label = CONFIG_TYPE_LABELS.get(config_type, config_type)
    status = job.get("status", "?")
    created_at = job.get("createdAt")
    updated_at = job.get("updatedAt")
    created = epoch_to_human(created_at)
    updated = epoch_to_human(updated_at)
    duration = format_duration_seconds(created_at, updated_at)

    lines = [
        f"## Job {job.get('id', '?')} — **{status}** ({label})",
        f"- **Config type**: {config_type}",
        f"- **Created**: {created}",
        f"- **Updated**: {updated}",
        f"- **Duration**: {duration}",
        f"- **Streams**: {format_enabled_streams(job.get('enabledStreams'))}",
    ]

    attempts = job_info.get("attempts", [])
    bytes_synced: int | None = None
    records_synced: int | None = None
    stream_stats: list[dict[str, Any]] | None = None

    if attempts:
        last = attempts[-1].get("attempt", attempts[-1])
        bytes_synced = last.get("bytesSynced")
        records_synced = last.get("recordsSynced")
        stream_stats = last.get("streamStats")

    if bytes_synced is None:
        aggregated = job.get("aggregatedStats") or {}
        bytes_synced = aggregated.get("bytesCommitted") or aggregated.get("bytesEmitted")
        if records_synced is None:
            records_synced = aggregated.get("recordsCommitted") or aggregated.get("recordsEmitted")

    if bytes_synced is not None:
        lines.append(f"- **Bytes synced**: {bytes_synced:,}")
    if records_synced is not None:
        lines.append(f"- **Records synced**: {records_synced:,}")

    append_stream_stats_lines(
        lines,
        stream_stats=stream_stats,
        stream_aggregated_stats=job.get("streamAggregatedStats"),
    )

    if status in ("failed", "incomplete"):
        lines.append(
            "- **Tip**: Use `airbyte_get_job_details` for failure reasons and `airbyte_get_job_logs` for full logs."
        )

    return "\n".join(lines) + "\n"
