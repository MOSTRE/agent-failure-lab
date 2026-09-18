"""Adapter tests against checked-in fixtures."""
from pathlib import Path

from agentlab.adapters.base import load_trajectory
from agentlab.adapters.claude import ClaudeAdapter
from agentlab.adapters.codex import CodexAdapter
from agentlab.adapters.gemini import GeminiAdapter
from agentlab.adapters.generic import GenericAdapter
from agentlab.adapters.opencode import OpenCodeAdapter

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_generic_parses_demo():
    traj = GenericAdapter().parse(FIXTURES.parent.parent / "examples" / "sessions" / "demo.jsonl")
    assert traj.task.startswith("Fix authentication timeout")
    assert len(traj.events) > 10


def test_claude_adapter_detects_and_parses():
    p = FIXTURES / "claude.json"
    assert ClaudeAdapter().detect(p)
    traj = ClaudeAdapter().parse(p)
    assert traj.task == "Fix auth timeout"
    assert any(e.kind == "tool_call" for e in traj.events)


def test_codex_adapter_parses():
    p = FIXTURES / "codex.json"
    assert CodexAdapter().detect(p)
    traj = CodexAdapter().parse(p)
    assert len(traj.events) == 3


def test_opencode_adapter_parses():
    p = FIXTURES / "opencode.json"
    assert OpenCodeAdapter().detect(p)
    traj = OpenCodeAdapter().parse(p)
    assert traj.task == "Fix auth timeout"


def test_gemini_adapter_maps_function_call(tmp_path):
    import json

    p = tmp_path / "gemini.jsonl"
    p.write_text(
        json.dumps({"content": {"parts": [{"functionCall": {"name": "readFile", "args": {"path": "a"}}}]}}) + "\n",
        encoding="utf-8",
    )
    assert GeminiAdapter().detect(p)
    traj = GeminiAdapter().parse(p)
    assert traj.events[0].kind == "tool_call"


def test_load_trajectory_auto_detects():
    traj = load_trajectory(FIXTURES / "claude.json")
    assert traj.source_format == "claude"
    traj = load_trajectory(FIXTURES / "codex.json")
    assert traj.source_format == "codex"
