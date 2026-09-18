"""Each detector must fire on its fixture and stay quiet elsewhere."""
from pathlib import Path

import pytest

from agentlab.adapters.base import load_trajectory
from agentlab.diagnosis.analyzer import analyze

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

EXPECTED = {
    "hallucinated_api": "hallucinated_api",
    "wrong_file": "wrong_file",
    "ignored_test_failure": "ignored_test_failure",
    "scope_creep": "scope_creep",
    "infinite_repair_loop": "infinite_repair_loop",
    "premature_completion": "premature_completion",
    "destructive_change": "destructive_change",
    "partial_success": "partial_success",
    "missing_test_execution": "missing_test_execution",
    "stale_context": "stale_context",
}


@pytest.mark.parametrize("fixture,want", sorted(EXPECTED.items()))
def test_detector_fires(fixture, want):
    traj = load_trajectory(FIXTURES / f"{fixture}.jsonl")
    diag = analyze(traj)
    assert diag.category == want, f"{fixture}: scores={diag.scores}"
    assert 0.0 <= diag.confidence <= 1.0
    assert diag.evidence, "diagnosis without evidence is not useful"


def test_demo_diagnosis_matches_product_story():
    traj = load_trajectory(
        FIXTURES.parent.parent / "examples" / "sessions" / "demo.jsonl"
    )
    diag = analyze(traj)
    assert diag.category == "hallucinated_api"
    assert diag.critical_step == 12
    assert diag.recovery_opportunity == 13
    assert diag.downstream_impact == 9
    assert diag.success is False


def test_confidence_is_honest_without_repo_context():
    # No known_symbols: hallucination can only be a guess.
    traj = load_trajectory(FIXTURES / "hallucinated_api.jsonl")
    traj.metadata.pop("known_symbols", None)
    diag = analyze(traj)
    assert diag.confidence < 0.9
