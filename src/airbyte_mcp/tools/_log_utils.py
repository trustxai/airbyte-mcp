"""Shared helpers for log-related tools."""

from __future__ import annotations

from typing import Any


def attempt_matches(attempt_info: dict[str, Any], attempt_number: int, list_index: int) -> bool:
    """Return True when *attempt_info* corresponds to *attempt_number*.

    Matches ``attemptNumber`` rather than list position. Falls back to
    *list_index* when metadata is absent (legacy payloads).
    """
    attempt = attempt_info.get("attempt", attempt_info)
    if not isinstance(attempt, dict):
        return list_index == attempt_number

    if "attemptNumber" in attempt:
        try:
            return int(attempt["attemptNumber"]) == attempt_number
        except (TypeError, ValueError):
            return False

    return list_index == attempt_number


def truncate_structured_logs(
    data: dict[str, Any],
    tail_entries: int,
    attempt_number: int | None = None,
) -> dict[str, Any]:
    """Truncate structured log entries in-place to keep only the last *tail_entries*.

    Works with ``get_debug_info`` (multiple attempts), ``get_for_job`` (single
    attempt), bare-list ``logLines``, and mixed ``events`` / ``structuredLogs``
    shapes.
    """
    attempts = data.get("attempts")
    if attempts is not None:
        for i, attempt_info in enumerate(attempts):
            if attempt_number is not None and not attempt_matches(attempt_info, attempt_number, i):
                continue
            _truncate_logs_value(_resolve_logs_payload(attempt_info), tail_entries)
    else:
        _truncate_logs_value(_resolve_logs_payload(data), tail_entries)

    return data


def _resolve_logs_payload(container: dict[str, Any]) -> Any:
    """Find the logs payload on debug-info, get_for_job, or jobs/get shapes."""
    logs = container.get("logs")
    if logs is not None:
        return logs

    attempt = container.get("attempt")
    if isinstance(attempt, dict):
        return attempt.get("logs")

    return None


def _truncate_logs_value(logs: Any, tail_entries: int) -> None:
    """Truncate log entries in-place for dict, list, or nested shapes."""
    if logs is None:
        return

    if isinstance(logs, list):
        if len(logs) > tail_entries:
            logs[:] = logs[-tail_entries:]
        return

    if not isinstance(logs, dict):
        return

    for key in ("logLines", "structuredLogs", "events"):
        entries = logs.get(key)
        if isinstance(entries, list) and len(entries) > tail_entries:
            logs[key] = entries[-tail_entries:]


def extract_full_log_text(logs_data: Any) -> str:
    """Extract plain-text log lines from Config API log payloads."""
    if not logs_data:
        return ""

    if isinstance(logs_data, list):
        return "\n".join(str(line) for line in logs_data)

    if not isinstance(logs_data, dict):
        return str(logs_data)

    events = logs_data.get("events")
    if isinstance(events, list) and events:
        lines: list[str] = []
        for event in events:
            if isinstance(event, dict):
                timestamp = event.get("timestamp", "")
                level = event.get("level", "INFO")
                message = event.get("message", "")
                lines.append(f"[{timestamp}] {level}: {message}")
            else:
                lines.append(str(event))
        return "\n".join(lines)

    for key in ("logLines", "structuredLogs"):
        entries = logs_data.get(key)
        if isinstance(entries, list) and entries:
            return "\n".join(str(line) for line in entries)

    return ""


def paginate_log_text(
    log_text: str,
    *,
    max_lines: int,
    from_tail: bool,
    line_offset: int | None,
) -> tuple[str, int, int, int]:
    """Slice *log_text* by line and return text plus pagination metadata.

    Returns ``(text, start_line_1based, returned_line_count, total_lines)``.
    """
    log_lines = log_text.splitlines()
    total_lines = len(log_lines)

    if total_lines == 0:
        return log_text, 1, 0, 0

    effective_max = total_lines if max_lines == 0 else max_lines

    if from_tail:
        start_index = max(0, total_lines - effective_max)
        selected_lines = log_lines[start_index:][:effective_max]
    else:
        start_index = line_offset or 0
        selected_lines = log_lines[start_index : start_index + effective_max]

    return "\n".join(selected_lines), start_index + 1, len(selected_lines), total_lines
