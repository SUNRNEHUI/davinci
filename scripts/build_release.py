#!/usr/bin/env python3
"""Build the standalone DAVINCI release package."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_DIR = PROJECT_ROOT / "dist" / "davinci-v1"
MANIFEST_NAME = "release-manifest.json"

ROOT_FILES = (
    "SKILL.md",
    "requirements.txt",
    "pyproject.toml",
    "examples/input_demo.png",
)

TREE_RULES: dict[str, set[str]] = {
    "agents": {".yaml", ".yml"},
    "scripts": {".py"},
    "flut": {".py", ".flut", ".json", ".b64"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the standalone DAVINCI release package.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_RELEASE_DIR),
        help="Directory where the release package will be written.",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Also create a .zip archive next to the output directory.",
    )
    return parser.parse_args()


def _reset_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _copy_root_files(output_dir: Path) -> list[str]:
    copied: list[str] = []
    for relative in ROOT_FILES:
        src = PROJECT_ROOT / relative
        dest = output_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(relative)
    return copied


def _copy_tree(output_dir: Path, relative_dir: str, allowed_suffixes: set[str]) -> list[str]:
    src_root = PROJECT_ROOT / relative_dir
    copied: list[str] = []
    for src in sorted(src_root.rglob("*")):
        if src.is_dir():
            continue
        if src.name.startswith("."):
            continue
        if src.suffix not in allowed_suffixes:
            continue
        rel = src.relative_to(PROJECT_ROOT)
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(rel.as_posix())
    return copied


def _write_release_readme(output_dir: Path) -> str:
    content = """# DAVINCI CLI Release Package

This directory is the source release payload for DAVINCI.

It supports two usage modes:
- local CLI
- local Codex skill install

## Contents
- `SKILL.md`
- `agents/openai.yaml`
- `requirements.txt`
- `pyproject.toml`
- `examples/input_demo.png`
- `scripts/*.py`
- bundled style assets

## Quick Start

Remember these 3 commands first:

```bash
davinci
davinci activate
davinci demo
davinci start
```

If `davinci` is not installed yet, use the module form:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
python3 -m scripts.leica_cli
python3 -m scripts.leica_cli demo
python3 -m scripts.leica_cli start
```

Optional editable install:

```bash
python3 -m pip install -e .
davinci
davinci demo
davinci start
```

What `davinci start` does:
- lets you drag a photo into the terminal
- lets you paste the path
- opens the macOS file picker when you press Enter
- opens the official DAVINCI page once for first-time activation
- lets you type `demo` if you want to preview the product first
- shows 3 clearly different looks first
- saves outputs under `~/Pictures/DAVINCI/`
- saves demo outputs under `~/Pictures/DAVINCI/_demo/`

## Platform Scope

- Official downloadable build: macOS Apple Silicon only
- Windows/Linux: no official installer or standalone package yet
- Source mode on other platforms is not part of the current public support promise

## Install As A Local Codex Skill

Copy this extracted folder into `~/.codex/skills/davinci` and restart Codex:

```bash
mkdir -p ~/.codex/skills
cp -R /path/to/davinci-v1 ~/.codex/skills/davinci
```

After restart, prompts like these should trigger the skill:
- `帮我调个莱卡滤镜`
- `帮我给这张图来个富士味`
- `给这张照片来点胶片感`
- `先推荐几个滤镜`
"""
    readme_path = output_dir / "README.md"
    readme_path.write_text(content, encoding="utf-8")
    return "README.md"


def _write_manifest(output_dir: Path, copied_files: list[str]) -> str:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_name": output_dir.name,
        "file_count": len(copied_files),
        "files": sorted(copied_files),
    }
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return MANIFEST_NAME


def build_release(output_dir: Path, *, make_zip: bool = False) -> dict[str, str | int]:
    output_dir = output_dir.expanduser().resolve()
    _reset_output_dir(output_dir)

    copied_files = _copy_root_files(output_dir)
    copied_files.append(_write_release_readme(output_dir))

    for relative_dir, suffixes in TREE_RULES.items():
        copied_files.extend(_copy_tree(output_dir, relative_dir, suffixes))

    copied_files.append(_write_manifest(output_dir, copied_files))

    result: dict[str, str | int] = {
        "output_dir": str(output_dir),
        "file_count": len(copied_files),
    }
    if make_zip:
        archive_path = shutil.make_archive(
            str(output_dir),
            "zip",
            root_dir=output_dir.parent,
            base_dir=output_dir.name,
        )
        result["zip_path"] = archive_path
    return result


def main() -> int:
    args = parse_args()
    result = build_release(Path(args.output_dir), make_zip=args.zip)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
