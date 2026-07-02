"""Unit tests for structured log truncation and Cloud log text helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from airbyte_mcp.tools._log_utils import (
    attempt_matches,
    extract_full_log_text,
    paginate_log_text,
    truncate_structured_logs,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def debug_info_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "get_debug_info_multi_attempt.json").read_text())


@pytest.fixture
def get_for_job_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "get_for_job_single_attempt.json").read_text())


@pytest.fixture
def cloud_jobs_get_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "jobs_get_cloud_attempt.json").read_text())


def test_attempt_matches_uses_attempt_number_not_list_index() -> None:
    attempt_info = {"attempt": {"id": 9002, "attemptNumber": 1}}
    assert attempt_matches(attempt_info, attempt_number=1, list_index=0) is True
    assert attempt_matches(attempt_info, attempt_number=0, list_index=1) is False


def test_truncate_debug_info_all_attempts(debug_info_fixture: dict) -> None:
    data = truncate_structured_logs(debug_info_fixture, tail_entries=2)
    first = data["attempts"][0]["logs"]["logLines"]
    second = data["attempts"][1]["logs"]["structuredLogs"]
    assert first == ["line-a3", "line-a4"]
    assert len(second) == 2
    assert second[-1]["message"] == "retry-end"


def test_truncate_debug_info_specific_attempt(debug_info_fixture: dict) -> None:
    data = truncate_structured_logs(debug_info_fixture, tail_entries=1, attempt_number=1)
    untouched = data["attempts"][0]["logs"]["logLines"]
    trimmed = data["attempts"][1]["logs"]["structuredLogs"]
    assert untouched == ["line-a0", "line-a1", "line-a2", "line-a3", "line-a4"]
    assert len(trimmed) == 1
    assert trimmed[0]["message"] == "retry-end"


def test_truncate_get_for_job_events(get_for_job_fixture: dict) -> None:
    data = truncate_structured_logs(get_for_job_fixture, tail_entries=2)
    events = data["logs"]["events"]
    assert len(events) == 2
    assert events[0]["message"] == "finished"


def test_truncate_bare_list_logs() -> None:
    payload = {"logs": ["l0", "l1", "l2", "l3"]}
    data = truncate_structured_logs(payload, tail_entries=2)
    assert data["logs"] == ["l2", "l3"]


def test_truncate_logs_nested_under_attempt() -> None:
    payload = {
        "attempt": {
            "attemptNumber": 0,
            "logs": {"logLines": ["a", "b", "c", "d"]},
        }
    }
    data = truncate_structured_logs(payload, tail_entries=2)
    assert data["attempt"]["logs"]["logLines"] == ["c", "d"]


def test_extract_full_log_text_from_events(get_for_job_fixture: dict) -> None:
    text = extract_full_log_text(get_for_job_fixture["logs"])
    assert "[2024-01-01T00:00:00Z] INFO: started" in text
    assert "WARN: cleanup" in text


def test_extract_full_log_text_from_log_lines(cloud_jobs_get_fixture: dict) -> None:
    attempt_info = cloud_jobs_get_fixture["attempts"][0]
    text = extract_full_log_text(attempt_info["logs"])
    assert text == "cloud-line-1\ncloud-line-2\ncloud-line-3"


def test_paginate_log_text_from_tail() -> None:
    text = "\n".join(f"line-{index}" for index in range(10))
    sliced, start, count, total = paginate_log_text(
        text,
        max_lines=3,
        from_tail=True,
        line_offset=None,
    )
    assert sliced == "line-7\nline-8\nline-9"
    assert start == 8
    assert count == 3
    assert total == 10


def test_paginate_log_text_with_offset() -> None:
    text = "\n".join(f"line-{index}" for index in range(5))
    sliced, start, count, total = paginate_log_text(
        text,
        max_lines=2,
        from_tail=False,
        line_offset=1,
    )
    assert sliced == "line-1\nline-2"
    assert start == 2
    assert count == 2
    assert total == 5
