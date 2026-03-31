"""Runtime resource path helpers for source, release, and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path


def _candidate_roots() -> list[Path]:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(str(meipass)).expanduser().resolve())

    executable = getattr(sys, "executable", None)
    if executable:
        candidates.append(Path(str(executable)).expanduser().resolve().parent)

    here = Path(__file__).resolve()
    candidates.extend([here.parents[1], here.parent, Path.cwd().resolve()])

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def resource_root(*required_children: str) -> Path:
    for root in _candidate_roots():
        if all((root / child).exists() for child in required_children):
            return root
    details = ", ".join(required_children) or "<none>"
    tried = ", ".join(str(path) for path in _candidate_roots())
    raise FileNotFoundError(f"Could not locate runtime resource root for [{details}] from: {tried}")


def examples_root() -> Path:
    packaged_examples = Path(__file__).resolve().parent / "_assets"
    if (packaged_examples / "input_demo.png").exists():
        return packaged_examples
    return resource_root("examples") / "examples"


def catalog_root() -> Path:
    return resource_root("flut") / "flut"
