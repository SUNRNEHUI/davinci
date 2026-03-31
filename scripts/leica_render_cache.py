"""Simple deterministic cache for renders/contact sheets."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .leica_product_store import default_cli_home
except ImportError:  # pragma: no cover - script execution fallback
    from leica_product_store import default_cli_home


@dataclass(frozen=True)
class RenderCacheKey:
    input_path: Path
    input_mtime: float
    catalog: str
    filter_ids: tuple[str, ...]
    intensity: float
    algorithm: str
    output_type: str

    def fingerprint(self) -> str:
        canonical = "|".join(
            (
                str(self.input_path.resolve()),
                f"{self.input_mtime:.6f}",
                self.catalog,
                ",".join(self.filter_ids),
                f"{self.intensity:.4f}",
                self.algorithm,
                self.output_type,
            )
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_cache_dir() -> Path:
    return (default_cli_home() / "render_cache").resolve()


def cache_entry_path(key: str) -> Path:
    return default_cache_dir() / "entries" / f"{key}.json"


def cache_file_path(key: str, output_suffix: str) -> Path:
    safe_suffix = output_suffix.lstrip(".")
    return default_cache_dir() / "files" / f"{key}.{safe_suffix}"


def ensure_cache_dirs() -> None:
    base = default_cache_dir()
    (base / "entries").mkdir(parents=True, exist_ok=True)
    (base / "files").mkdir(parents=True, exist_ok=True)


def make_render_cache_key(
    *,
    input_path: Path | str,
    catalog: str,
    filter_ids: list[str] | tuple[str, ...],
    intensity: float,
    algorithm: str,
    output_type: str,
) -> RenderCacheKey:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {path}")
    filter_tuple = tuple(str(item) for item in filter_ids)
    return RenderCacheKey(
        input_path=path,
        input_mtime=path.stat().st_mtime,
        catalog=catalog,
        filter_ids=filter_tuple,
        intensity=float(intensity),
        algorithm=str(algorithm),
        output_type=str(output_type),
    )


def store_render_cache(
    src: Path | str,
    *,
    key: RenderCacheKey,
    output_suffix: str = "png",
    metadata: dict[str, Any] | None = None,
) -> Path:
    src_path = Path(src).expanduser().resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")
    ensure_cache_dirs()
    entry = {
        "key": key.fingerprint(),
        "output_type": key.output_type,
        "catalog": key.catalog,
        "filter_ids": list(key.filter_ids),
        "intensity": key.intensity,
        "algorithm": key.algorithm,
        "input_path": str(key.input_path),
        "input_mtime": key.input_mtime,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        entry["metadata"] = metadata
    dest = cache_file_path(key.fingerprint(), output_suffix)
    shutil.copy2(src_path, dest)
    cache_entry_path(key.fingerprint()).write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    return dest


def lookup_render_cache(key: RenderCacheKey, *, output_suffix: str = "png") -> Path | None:
    path = cache_file_path(key.fingerprint(), output_suffix)
    if path.exists():
        return path
    return None


def inspect_render_cache() -> list[dict[str, Any]]:
    ensure_cache_dirs()
    entries: list[dict[str, Any]] = []
    for path in sorted((default_cache_dir() / "entries").glob("*.json")):
        try:
            entries.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return entries


def clear_render_cache() -> None:
    base = default_cache_dir()
    if base.exists():
        shutil.rmtree(base)
