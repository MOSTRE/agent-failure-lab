"""Optional LLM-assisted diagnosis enhancement.

The deterministic engine always works offline. This module is a deliberate
extension point: implement DiagnosisEnhancer with any provider (OpenAI-,
Anthropic-compatible, Ollama) to rewrite the explanation — never to change
the measured signals (category scores, critical step).
"""
from __future__ import annotations

from typing import Protocol

from .diagnosis.analyzer import Diagnosis
from .ingestion.schema import Trajectory


class DiagnosisExplanation(Protocol):
    text: str


class DiagnosisEnhancer(Protocol):
    def explain(self, trajectory: Trajectory, diagnosis: Diagnosis) -> str:
        ...


class NoOpEnhancer:
    """Default: return the deterministic explanation unchanged."""

    def explain(self, trajectory: Trajectory, diagnosis: Diagnosis) -> str:
        return diagnosis.explanation
