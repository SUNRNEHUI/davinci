#!/usr/bin/env python3
"""Batch pack all Leica CUBE files into FLUT files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from .flut_codec import build_metadata, pack_flut_file, resolve_key
except ImportError:  # pragma: no cover - script execution fallback
    from flut_codec import build_metadata, pack_flut_file, resolve_key


def slugify(name: str) -> str:
    lowered = name.strip().lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch pack Leica .cube files into .flut")
    parser.add_argument("--input-dir", required=True, help="Directory containing Leica .cube files")
    parser.add_argument("--output-dir", required=True, help="Directory for generated .flut files")
    parser.add_argument("--index-file", required=True, help="Output JSON index file path")
    parser.add_argument("--skill-id", default="leica.skill.core", help="Skill identifier")
    parser.add_argument("--skill-version", default="1.0.0", help="Skill version")
    parser.add_argument("--lut-domain", default="rec709", choices=["rec709", "rawDecoded"])
    parser.add_argument("--key-base64", help="Base64 AES key")
    parser.add_argument("--key-file", help="Path to base64 AES key file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key = resolve_key(key_base64=args.key_base64, key_file=args.key_file)

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    index_file = Path(args.index_file)

    if not input_dir.exists():
        raise SystemExit(f"Input dir not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    index_file.parent.mkdir(parents=True, exist_ok=True)

    cube_files = sorted(input_dir.glob("*.cube"))
    if not cube_files:
        raise SystemExit(f"No .cube files found in: {input_dir}")

    created_at = datetime.now(timezone.utc).isoformat()
    entries: list[dict[str, str]] = []

    for cube_path in cube_files:
        display_name = cube_path.stem
        filter_slug = slugify(display_name)
        filter_id = f"leica_{filter_slug}"
        out_name = f"{filter_id}.flut"
        out_path = output_dir / out_name

        payload = cube_path.read_bytes()
        metadata = build_metadata(
            payload=payload,
            skill_id=args.skill_id,
            skill_version=args.skill_version,
            filter_id=filter_id,
            display_name=display_name,
            lut_domain=args.lut_domain,
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
                "display_name": display_name,
                "flut_file": out_name,
            }
        )

    index = {
        "skill_id": args.skill_id,
        "skill_version": args.skill_version,
        "lut_domain": args.lut_domain,
        "generated_at": created_at,
        "filter_count": len(entries),
        "filters": entries,
    }

    index_file.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Packed {len(entries)} filters into: {output_dir}")
    print(f"Index file: {index_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
