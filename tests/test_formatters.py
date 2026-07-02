"""Unit tests for formatters and internal job helpers."""

from __future__ import annotations

from airbyte_mcp.formatters import ResponseFormat, epoch_to_human, paginated_response
from airbyte_mcp.tools._internal_jobs import (
    append_stream_stats_lines,
    build_stream_descriptors,
    extract_internal_job_id_status,
    fmt_internal_job,
    format_duration_seconds,
    format_enabled_streams,
)
from airbyte_mcp.tools.jobs import StreamDescriptor


def test_epoch_to_human_seconds() -> None:
    assert epoch_to_human(1782894600).endswith("UTC")


def test_format_duration_seconds() -> None:
    assert format_duration_seconds(100, 160) == "1m 0s"
    assert format_duration_seconds(None, 160) == "N/A"


def test_format_enabled_streams() -> None:
    streams = [{"name": "orders", "namespace": "public"}, {"name": "users"}]
    assert format_enabled_streams(streams) == "public.orders, users"


def test_build_stream_descriptors() -> None:
    streams = [
        StreamDescriptor(name="orders", namespace="public"),
        StreamDescriptor(name="users"),
    ]
    assert build_stream_descriptors(streams) == [
        {"streamName": "orders", "streamNamespace": "public"},
        {"streamName": "users"},
    ]


def test_extract_internal_job_id_status_nested_job() -> None:
    data = {"job": {"id": 51108, "status": "pending"}, "attempts": []}
    assert extract_internal_job_id_status(data) == (51108, "pending")


def test_append_stream_stats_lines_prefers_attempt_stats() -> None:
    lines: list[str] = []
    append_stream_stats_lines(
        lines,
        stream_stats=[
            {
                "streamName": "orders",
                "stats": {"recordsEmitted": 10, "recordsCommitted": 9},
            }
        ],
        stream_aggregated_stats=None,
    )
    assert any("orders" in line for line in lines)


def test_fmt_internal_job_from_fixture(sample_internal_job: dict) -> None:
    rendered = fmt_internal_job(sample_internal_job)
    assert "Job 50900" in rendered
    assert "succeeded" in rendered
    assert "PURCHASE_POSTED_TRANSACTIONS" in rendered
    assert "Duration" in rendered
    assert "2,300,292" in rendered


def test_paginated_response_markdown() -> None:
    output = paginated_response(
        items=[{"jobId": "1"}],
        total=10,
        limit=1,
        offset=0,
        fmt=ResponseFormat.MARKDOWN,
        title="Jobs",
    )
    assert "# Jobs" in output
    assert "total **10**" in output
