#!/usr/bin/env python3
"""Apply encrypted FLUT skill to an image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    from .cube_runtime import apply_lut_uint8, parse_cube_bytes
    from .flut_codec import default_key_candidates, resolve_key, unpack_flut_bytes
except ImportError:  # pragma: no cover - script execution fallback
    from cube_runtime import apply_lut_uint8, parse_cube_bytes
    from flut_codec import default_key_candidates, resolve_key, unpack_flut_bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply .flut LUT to image")
    parser.add_argument("--flut", required=True, help="Path to .flut file")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--intensity", type=float, default=1.0, help="Blend intensity [0,1]")
    parser.add_argument("--algorithm", choices=["tetrahedral", "trilinear"], default="tetrahedral")
    parser.add_argument("--print-metadata", action="store_true", help="Print decoded metadata")
    parser.add_argument("--key-base64", help="Base64 AES key (32-byte decoded)")
    parser.add_argument("--key-file", help="Path to file containing base64 AES key")
    return parser.parse_args()


def _load_image_rgb_with_alpha(path: Path) -> tuple[np.ndarray, np.ndarray | None, str]:
    image = Image.open(path)
    src_mode = image.mode

    if "A" in image.getbands():
        rgba = image.convert("RGBA")
        arr = np.asarray(rgba, dtype=np.uint8)
        rgb = arr[..., :3]
        alpha = arr[..., 3:4]
        return rgb, alpha, src_mode

    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return rgb, None, src_mode


def _save_image(path: Path, rgb: np.ndarray, alpha: np.ndarray | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if alpha is not None and path.suffix.lower() in {".png", ".webp", ".tif", ".tiff"}:
        out = np.concatenate([rgb, alpha], axis=-1)
        Image.fromarray(out, mode="RGBA").save(path)
        return

    Image.fromarray(rgb, mode="RGB").save(path)


def apply_flut_to_image(
    *,
    flut_path: Path | str,
    input_path: Path | str,
    output_path: Path | str,
    intensity: float = 1.0,
    algorithm: str = "tetrahedral",
    key: bytes | None = None,
    key_base64: str | None = None,
    key_file: str | None = None,
) -> dict[str, Any]:
    """Apply one FLUT file to one image and return run metadata."""
    flut_path = Path(flut_path).expanduser().resolve()
    input_path = Path(input_path).expanduser().resolve()
    output_path = Path(output_path).expanduser().resolve()

    if key is None:
        key = resolve_key(
            key_base64=key_base64,
            key_file=key_file,
            default_key_files=default_key_candidates(flut_path),
        )

    flut_blob = flut_path.read_bytes()
    metadata, cube_payload = unpack_flut_bytes(flut_blob=flut_blob, key=key)
    lut = parse_cube_bytes(cube_payload)

    rgb, alpha, src_mode = _load_image_rgb_with_alpha(input_path)
    out_rgb = apply_lut_uint8(
        rgb,
        lut,
        intensity=intensity,
        algorithm=algorithm,
    )
    _save_image(output_path, out_rgb, alpha)

    return {
        "metadata": metadata,
        "lut": lut,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "source_mode": src_mode,
        "algorithm": algorithm,
        "intensity": float(np.clip(intensity, 0.0, 1.0)),
    }


def main() -> int:
    args = parse_args()
    result = apply_flut_to_image(
        flut_path=args.flut,
        input_path=args.input,
        output_path=args.output,
        intensity=args.intensity,
        algorithm=args.algorithm,
        key_base64=args.key_base64,
        key_file=args.key_file,
    )
    lut = result["lut"]
    metadata = result["metadata"]
    in_path = Path(result["input_path"])
    out_path = Path(result["output_path"])

    print(
        f"Applied FLUT: input={in_path} output={out_path} "
        f"algorithm={args.algorithm} intensity={float(np.clip(args.intensity, 0.0, 1.0)):.3f}"
    )
    print(
        f"LUT: title={lut.title or '-'} size={lut.size} "
        f"domain_min={lut.domain_min.tolist()} domain_max={lut.domain_max.tolist()}"
    )
    print(f"Source image mode={result['source_mode']}")

    if args.print_metadata:
        print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
