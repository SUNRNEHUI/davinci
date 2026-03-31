#!/usr/bin/env python3
"""Generic batch packer for CUBE->FLUT catalogs."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .flut_codec import build_metadata, pack_flut_file, resolve_key
except ImportError:  # pragma: no cover - script execution fallback
    from flut_codec import build_metadata, pack_flut_file, resolve_key


MANIFEST_FILENAME = "manifest.json"


def slugify(name: str) -> str:
    lowered = name.strip().lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or "unknown"


def _ensure_unique(base: str, used: set[str]) -> str:
    if base not in used:
        used.add(base)
        return base

    index = 2
    while True:
        candidate = f"{base}_{index}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def _collect_cube_files(catalog_dir: Path, *, pattern: str, recursive: bool) -> list[Path]:
    iterator = catalog_dir.rglob(pattern) if recursive else catalog_dir.glob(pattern)
    return sorted(path for path in iterator if path.is_file())


def load_catalog_manifest(manifest_path: Path | str) -> dict[str, Any]:
    path = Path(manifest_path).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    filters = data.get("filters")
    if not isinstance(filters, list) or not filters:
        raise ValueError(f"Manifest must include a non-empty 'filters' list: {path}")

    validated_filters: list[dict[str, Any]] = []
    seen_filter_ids: set[str] = set()
    for idx, item in enumerate(filters):
        if not isinstance(item, dict):
            raise ValueError(f"Manifest filter #{idx} must be an object: {path}")
        missing = [key for key in ("source_cube", "filter_id", "display_name") if not item.get(key)]
        if missing:
            raise ValueError(
                f"Manifest filter #{idx} missing required fields {', '.join(missing)}: {path}"
            )
        entry = dict(item)
        entry["source_cube"] = str(entry["source_cube"]).strip()
        entry["filter_id"] = str(entry["filter_id"]).strip()
        entry["display_name"] = str(entry["display_name"]).strip()
        if not entry["source_cube"] or not entry["filter_id"] or not entry["display_name"]:
            raise ValueError(f"Manifest filter #{idx} contains empty required string fields: {path}")
        if entry["filter_id"] in seen_filter_ids:
            raise ValueError(f"Manifest has duplicate filter_id '{entry['filter_id']}': {path}")
        seen_filter_ids.add(entry["filter_id"])
        aliases = entry.get("aliases")
        if aliases is not None and not (
            isinstance(aliases, list) and all(isinstance(alias, str) and alias.strip() for alias in aliases)
        ):
            raise ValueError(f"Manifest filter #{idx} has invalid aliases list: {path}")
        validated_filters.append(entry)

    scene_filters = data.get("scene_filters")
    if scene_filters is not None:
        if not isinstance(scene_filters, dict):
            raise ValueError(f"Manifest 'scene_filters' must be an object: {path}")
        for scene, filter_ids in scene_filters.items():
            if not isinstance(scene, str) or not isinstance(filter_ids, list):
                raise ValueError(f"Manifest scene_filters has invalid entry for {scene!r}: {path}")
            if not all(isinstance(filter_id, str) and filter_id.strip() for filter_id in filter_ids):
                raise ValueError(f"Manifest scene_filters[{scene!r}] must contain filter id strings: {path}")
            missing_ids = [filter_id for filter_id in filter_ids if filter_id not in seen_filter_ids]
            if missing_ids:
                missing_str = ", ".join(sorted(set(missing_ids)))
                raise ValueError(
                    f"Manifest scene_filters[{scene!r}] references unknown filter ids: {missing_str}: {path}"
                )

    return {
        **data,
        "filters": validated_filters,
    }


def pack_catalog(
    *,
    catalog_dir: Path,
    output_dir: Path,
    index_file: Path,
    key: bytes,
    skill_id: str,
    skill_version: str,
    lut_domain: str,
    filter_prefix: str,
    pattern: str = "*.cube",
    recursive: bool = True,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not catalog_dir.exists():
        raise ValueError(f"Catalog dir not found: {catalog_dir}")
    if not catalog_dir.is_dir():
        raise ValueError(f"Catalog path is not a directory: {catalog_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    index_file.parent.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(timezone.utc).isoformat()
    used_filter_ids: set[str] = set()
    entries: list[dict[str, Any]] = []
    prefix_slug = slugify(filter_prefix) if filter_prefix else ""

    if manifest is not None:
        filters_from_manifest = manifest["filters"]
        for item in filters_from_manifest:
            source_cube = catalog_dir / item["source_cube"]
            if not source_cube.exists():
                raise ValueError(f"Manifest source cube not found: {source_cube}")

            requested_filter_id = str(item["filter_id"]).strip()
            filter_id = _ensure_unique(requested_filter_id, used_filter_ids)
            out_name = f"{filter_id}.flut"
            out_path = output_dir / out_name
            payload = source_cube.read_bytes()
            metadata = build_metadata(
                payload=payload,
                skill_id=skill_id,
                skill_version=skill_version,
                filter_id=filter_id,
                display_name=item["display_name"],
                lut_domain=lut_domain,
                created_at=created_at,
            )
            pack_flut_file(
                input_cube=str(source_cube),
                output_flut=str(out_path),
                key=key,
                metadata=metadata,
            )
            entry = dict(item)
            entry["filter_id"] = filter_id
            entry["flut_file"] = out_name
            entries.append(entry)
    else:
        cube_files = _collect_cube_files(catalog_dir, pattern=pattern, recursive=recursive)
        if not cube_files:
            mode = "recursive" if recursive else "top-level"
            raise ValueError(f"No CUBE files found ({mode}, pattern={pattern!r}): {catalog_dir}")

        for cube_path in cube_files:
            rel_path = cube_path.relative_to(catalog_dir)
            rel_no_suffix = rel_path.with_suffix("")
            rel_slug = slugify(rel_no_suffix.as_posix().replace("/", "_"))
            filter_base = f"{prefix_slug}_{rel_slug}" if prefix_slug else rel_slug
            filter_id = _ensure_unique(filter_base, used_filter_ids)
            out_name = f"{filter_id}.flut"
            out_path = output_dir / out_name

            payload = cube_path.read_bytes()
            metadata = build_metadata(
                payload=payload,
                skill_id=skill_id,
                skill_version=skill_version,
                filter_id=filter_id,
                display_name=rel_path.stem,
                lut_domain=lut_domain,
                created_at=created_at,
            )
            pack_flut_file(
                input_cube=str(cube_path),
                output_flut=str(out_path),
                key=key,
                metadata=metadata,
            )
            entries.append(
                {
                    "filter_id": filter_id,
                    "display_name": rel_path.stem,
                    "source_cube": rel_path.as_posix(),
                    "flut_file": out_name,
                }
            )

    index = {
        "skill_id": skill_id,
        "skill_version": skill_version,
        "lut_domain": lut_domain,
        "generated_at": created_at,
        "filter_count": len(entries),
        "filters": [
            {
                "filter_id": entry["filter_id"],
                "display_name": entry["display_name"],
                "flut_file": entry["flut_file"],
            }
            for entry in entries
        ],
    }

    index_file.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    output_manifest = build_output_manifest(
        base_manifest=manifest,
        entries=entries,
        skill_id=skill_id,
        skill_version=skill_version,
        lut_domain=lut_domain,
        generated_at=created_at,
        catalog_dir=output_dir,
        filter_prefix=filter_prefix,
    )
    (output_dir / MANIFEST_FILENAME).write_text(
        json.dumps(output_manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return index


def build_output_manifest(
    *,
    base_manifest: dict[str, Any] | None,
    entries: list[dict[str, Any]],
    skill_id: str,
    skill_version: str,
    lut_domain: str,
    generated_at: str,
    catalog_dir: Path,
    filter_prefix: str,
) -> dict[str, Any]:
    if base_manifest is not None:
        manifest = deepcopy(base_manifest)
    else:
        manifest = {
            "catalog": slugify(catalog_dir.name),
            "display_name": catalog_dir.name,
            "scene_filters": {},
            "filters": [],
        }

    manifest["catalog"] = str(manifest.get("catalog") or slugify(filter_prefix or catalog_dir.name))
    manifest["display_name"] = str(manifest.get("display_name") or manifest["catalog"])
    manifest["skill_id"] = skill_id
    manifest["skill_version"] = skill_version
    manifest["lut_domain"] = lut_domain
    manifest["generated_at"] = generated_at
    manifest["filter_count"] = len(entries)

    by_key = {(entry["source_cube"], entry["filter_id"]): entry for entry in entries}
    output_filters: list[dict[str, Any]] = []
    if base_manifest is not None:
        for item in base_manifest["filters"]:
            matched = next(
                (
                    entry
                    for entry in entries
                    if entry["source_cube"] == item["source_cube"] or entry["filter_id"] == item["filter_id"]
                ),
                None,
            )
            if matched is None:
                continue
            merged = dict(item)
            merged["filter_id"] = matched["filter_id"]
            merged["display_name"] = matched["display_name"]
            merged["source_cube"] = matched["source_cube"]
            merged["flut_file"] = matched["flut_file"]
            output_filters.append(merged)
    else:
        for entry in entries:
            output_filters.append(dict(entry))

    manifest["filters"] = output_filters
    manifest.setdefault("scene_filters", {})
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pack a generic CUBE catalog into FLUT + index")
    parser.add_argument("--catalog-dir", required=True, help="Directory containing source .cube files")
    parser.add_argument("--output-dir", required=True, help="Directory for output .flut files")
    parser.add_argument("--index-file", required=True, help="Path to output index JSON")
    parser.add_argument("--manifest", help="Optional manifest.json defining ids, display names, and scene rules")
    parser.add_argument("--skill-id", help="Skill identifier")
    parser.add_argument("--skill-version", help="Skill version")
    parser.add_argument("--lut-domain", choices=["rec709", "rawDecoded"], help="LUT domain")
    parser.add_argument("--filter-prefix", default="", help="Optional prefix for generated filter_id")
    parser.add_argument("--pattern", default="*.cube", help="Glob pattern for source files")
    parser.add_argument("--non-recursive", action="store_true", help="Only scan top-level catalog dir")
    parser.add_argument("--key-base64", help="Base64 AES key")
    parser.add_argument("--key-file", help="Path to base64 AES key file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key = resolve_key(key_base64=args.key_base64, key_file=args.key_file)
    manifest = load_catalog_manifest(args.manifest) if args.manifest else None
    skill_id = args.skill_id or (manifest or {}).get("skill_id") or "catalog.skill.core"
    skill_version = args.skill_version or (manifest or {}).get("skill_version") or "1.0.0"
    lut_domain = args.lut_domain or (manifest or {}).get("lut_domain") or "rec709"
    filter_prefix = args.filter_prefix or (manifest or {}).get("catalog") or ""

    try:
        index = pack_catalog(
            catalog_dir=Path(args.catalog_dir),
            output_dir=Path(args.output_dir),
            index_file=Path(args.index_file),
            key=key,
            skill_id=skill_id,
            skill_version=skill_version,
            lut_domain=lut_domain,
            filter_prefix=filter_prefix,
            pattern=args.pattern,
            recursive=not args.non_recursive,
            manifest=manifest,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Packed {index['filter_count']} filters into: {args.output_dir}")
    print(f"Index file: {args.index_file}")
    print(f"Manifest: {Path(args.output_dir) / MANIFEST_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
