"""Response formatting helpers (Markdown / JSON)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ResponseFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"


def to_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def epoch_to_human(ts: int | float | None) -> str:
    if ts is None:
        return "N/A"
    if ts > 1e11:
        ts = ts / 1000
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def paginated_response(
    *,
    items: list[dict[str, Any]],
    total: int | None = None,
    limit: int,
    offset: int,
    fmt: ResponseFormat,
    item_formatter: Any | None = None,
    title: str = "Results",
) -> str:
    """Build a paginated response in the requested format."""
    count = len(items)
    has_more = (total is not None and total > offset + count) or count == limit

    if fmt == ResponseFormat.JSON:
        payload: dict[str, Any] = {
            "count": count,
            "offset": offset,
            "has_more": has_more,
            "data": items,
        }
        if total is not None:
            payload["total"] = total
        return to_json(payload)

    # Markdown
    lines = [f"# {title}", ""]
    meta_parts = [f"Showing **{count}** items (offset {offset})"]
    if total is not None:
        meta_parts.append(f"total **{total}**")
    if has_more:
        meta_parts.append(f"next offset → **{offset + count}**")
    lines.append(", ".join(meta_parts))
    lines.append("")

    for item in items:
        if item_formatter:
            lines.append(item_formatter(item))
        else:
            for k, v in item.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")

    return "\n".join(lines)
