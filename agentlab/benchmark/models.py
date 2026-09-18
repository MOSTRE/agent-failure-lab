"""Benchmark data model: the stable on-disk format."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Verification(BaseModel):
    command: str = "pytest -q"
    timeout_seconds: int = 120
    expected_exit_code: int = 0


class BenchmarkMeta(BaseModel):
    difficulty: str = "medium"
    tags: list[str] = Field(default_factory=list)
    source_session: str | None = None
    agent: str | None = None


class Benchmark(BaseModel):
    version: int = 1
    name: str
    description: str = ""
    task: str = ""
    category: str = ""
    base_commit: str = ""
    verification: Verification = Field(default_factory=Verification)
    metadata: BenchmarkMeta = Field(default_factory=BenchmarkMeta)

    def to_yaml(self) -> str:
        data = self.model_dump(exclude_none=True)
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, text: str) -> "Benchmark":
        return cls.model_validate(yaml.safe_load(text))

    @classmethod
    def load(cls, directory: Path) -> "Benchmark":
        for candidate in (directory / "benchmark.yaml", directory / "benchmark.yml"):
            if candidate.exists():
                return cls.from_yaml(candidate.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"No benchmark.yaml in {directory}")


def benchmark_to_dict(b: Benchmark) -> dict[str, Any]:
    return b.model_dump(exclude_none=True)
