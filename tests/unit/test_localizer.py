"""Critical-step localization: earliest cause, not final error."""
from pathlib import Path

from agentlab.adapters.base import load_trajectory
from agentlab.diagnosis import localizer

DEMO = Path(__file__).resolve().parent.parent.parent / "examples" / "sessions" / "demo.jsonl"


def test_critical_step_is_earliest_cause():
    traj = load_trajectory(DEMO)
    critical, scores, reasons = localizer.score_events(traj, hint_indices=[12])
    assert critical == 12
    # The confirming error right after scores lower than the cause itself.
    assert scores[12] >= scores[13]


def test_downstream_and_recovery():
    traj = load_trajectory(DEMO)
    assert localizer.downstream_impact(traj, 12) == 9
    assert localizer.recovery_opportunity(traj, 12) == 13


def test_no_signal_means_no_critical_step():
    from agentlab.ingestion.normalize import normalize_records

    traj = normalize_records([
        {"type": "message", "role": "user", "content": "hello"},
        {"type": "message", "role": "assistant", "content": "hi there"},
    ])
    critical, _, _ = localizer.score_events(traj)
    assert critical == 0
