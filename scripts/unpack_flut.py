#!/usr/bin/env python3
"""Unpack FLUT v1 to CUBE LUT."""

from __future__ import annotations

import argparse
import json

try:
    from .flut_codec import resolve_key, unpack_flut_file
except ImportError:  # pragma: no cover - script execution fallback
    from flut_codec import resolve_key, unpack_flut_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unpack encrypted .flut to .cube")
    parser.add_argument("input_flut", help="Path to input .flut file")
    parser.add_argument("output_cube", help="Path to output .cube file")
    parser.add_argument("--print-metadata", action="store_true", help="Print decoded metadata JSON")
    parser.add_argument("--key-base64", help="Base64 AES key (32-byte decoded)")
    parser.add_argument("--key-file", help="Path to file containing base64 AES key")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key = resolve_key(key_base64=args.key_base64, key_file=args.key_file)
    metadata = unpack_flut_file(
        input_flut=args.input_flut,
        output_cube=args.output_cube,
        key=key,
    )

    print(f"Unpacked: {args.input_flut} -> {args.output_cube}")
    if args.print_metadata:
        print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
