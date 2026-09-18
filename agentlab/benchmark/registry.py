"""Discover and inspect benchmarks on disk."""
from __future__ import annotations

from pathlib import Path

from .models import Benchmark


def discover(root: Path) -> list[tuple[str, Path]]:
    """Return [(name, dir)] sorted by name for every dir holding benchmark.yaml."""
    found: list[tuple[str, Path]] = []
    if not root.exists():
        return found
    for child in sorted(root.iterdir()):
        if child.is_dir() and ((child / "benchmark.yaml").exists() or (child / "benchmark.yml").exists()):
            found.append((child.name, child))
    # Also support nested groups: benchmarks/<category>/<name>
    for child in sorted(root.iterdir()):
        if child.is_dir() and not ((child / "benchmark.yaml").exists()):
            for grand in sorted(child.iterdir()):
                if grand.is_dir() and ((grand / "benchmark.yaml").exists() or (grand / "benchmark.yml").exists()):
                    found.append((f"{child.name}/{grand.name}", grand))
    return found


def load_by_name(root: Path, name: str) -> tuple[Benchmark, Path]:
    direct = root / name
    if direct.is_dir():
        return Benchmark.load(direct), direct
    for found_name, path in discover(root):
        if found_name == name or found_name.endswith("/" + name) or path.name == name:
            return Benchmark.load(path), path
    raise FileNotFoundError(
        f"Benchmark '{name}' not found under {root}. Try `agentlab benchmark list`."
    )
