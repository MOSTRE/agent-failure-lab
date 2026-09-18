"""Normalization and reader tests."""
import json

import pytest

from agentlab.ingestion.normalize import normalize_record, normalize_records
from agentlab.ingestion.reader import SessionReadError, read_jsonl


def test_normalize_tool_call_extracts_path():
    e = normalize_record(
        {"type": "tool_call", "tool": "write_file", "input": {"path": "src/a.py"}}, 1
    )
    assert e.kind == "tool_call"
    assert e.files_changed == ["src/a.py"]


def test_kind_aliases():
    assert normalize_record({"type": "edit", "input": {"path": "x"}}, 1).kind == "file_write"
    assert normalize_record({"type": "bash", "input": {"command": "ls"}}, 1).kind == "shell_command"
    assert normalize_record({"type": "test", "input": {"command": "pytest"}}, 1).kind == "test_run"


def test_task_inferred_from_first_user_message():
    traj = normalize_records([
        {"type": "message", "role": "user", "content": "Fix the thing"},
        {"type": "tool_call", "tool": "shell", "input": {"command": "ls"}},
    ])
    assert traj.task == "Fix the thing"


def test_test_outcome_from_exit_code():
    traj = normalize_records([
        {"type": "test_run", "input": {"command": "pytest"}, "exit_code": 1},
    ])
    assert traj.events[0].test_passed is False


def test_reader_recovers_events_before_bad_line(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        json.dumps({"type": "message", "role": "user", "content": "hi"}) + "\n"
        "{ not json\n"
        + json.dumps({"type": "tool_call", "tool": "x", "input": {}}) + "\n",
        encoding="utf-8",
    )
    records, warnings = read_jsonl(p)
    assert len(records) == 2
    assert any("Line 2" in w for w in warnings)


def test_reader_rejects_empty_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("\n\n", encoding="utf-8")
    with pytest.raises(SessionReadError):
        read_jsonl(p)
