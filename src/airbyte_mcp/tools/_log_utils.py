"""Shared helpers for log-related tools."""

from __future__ import annotations

from typing import Any


def truncate_structured_logs(
    data: dict[str, Any],
    tail_entries: int,
    attempt_number: int | None = None,
) -> dict[str, Any]:
    """Truncate structured log entries in-place to keep only the last *tail_entries*.

    Works with both ``get_debug_info`` (multiple attempts) and
    ``get_for_job`` (single attempt) response shapes.
    """
    attempts = data.get("attempts")
    if attempts is not None:
        for i, attempt_info in enumerate(attempts):
            if attempt_number is not None and i != attempt_number:
                continue
            _truncate_logs_dict(attempt_info.get("logs"), tail_entries)
    else:
        _truncate_logs_dict(data.get("logs"), tail_entries)

    return data


def _truncate_logs_dict(logs: Any, tail_entries: int) -> None:
    if not isinstance(logs, dict):
        return
    for key in ("logLines", "structuredLogs"):
        entries = logs.get(key)
        if isinstance(entries, list) and len(entries) > tail_entries:
            logs[key] = entries[-tail_entries:]
