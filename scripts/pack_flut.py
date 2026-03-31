#!/usr/bin/env python3
"""Pack a CUBE LUT into FLUT v1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    from .flut_codec import build_metadata, pack_flut_file, resolve_key
except ImportError:  # pragma: no cover - script execution fallback
    from flut_codec import build_metadata, pack_flut_file, resolve_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pack .cube into encrypted .flut")
    parser.add_argument("input_cube", help="Path to source .cube file")
    parser.add_argument("output_flut", help="Path to output .flut file")

    parser.add_argument("--skill-id", required=True, help="Skill identifier")
    parser.add_argument("--skill-version", default="1.0.0", help="Skill version")
    parser.add_argument("--filter-id", required=True, help="Filter identifier")
    parser.add_argument("--display-name", required=True, help="Display name")
    parser.add_argument("--lut-domain", default="rec709", choices=["rec709", "rawDecoded"])

    parser.add_argument("--key-base64", help="Base64 AES key (32-byte decoded)")
    parser.add_argument("--key-file", help="Path to file containing base64 AES key")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key = resolve_key(key_base64=args.key_base64, key_file=args.key_file)

    cube_bytes = Path(args.input_cube).read_bytes()
    metadata = build_metadata(
        payload=cube_bytes,
        skill_id=args.skill_id,
        skill_version=args.skill_version,
        filter_id=args.filter_id,
        display_name=args.display_name,
        lut_domain=args.lut_domain,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    pack_flut_file(
        input_cube=args.input_cube,
        output_flut=args.output_flut,
        key=key,
        metadata=metadata,
    )

    print(f"Packed: {args.input_cube} -> {args.output_flut}")
    print(f"skill={args.skill_id} filter={args.filter_id} domain={args.lut_domain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
