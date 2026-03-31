#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cube_runtime import apply_lut_rgb, parse_cube_bytes  # type: ignore
from flut_codec import build_metadata, pack_flut_bytes, unpack_flut_bytes  # type: ignore


def make_cube_text(size: int, fn) -> bytes:
    lines = [
        'TITLE "Generated Test LUT"',
        f"LUT_3D_SIZE {size}",
    ]
    denom = float(size - 1)
    for b in range(size):
        bv = b / denom
        for g in range(size):
            gv = g / denom
            for r in range(size):
                rv = r / denom
                out = fn(rv, gv, bv)
                lines.append(f"{out[0]:.8f} {out[1]:.8f} {out[2]:.8f}")
    return ("\n".join(lines) + "\n").encode("utf-8")


class CubeRuntimeTests(unittest.TestCase):
    def test_identity_lut_tetrahedral(self) -> None:
        cube = make_cube_text(2, lambda r, g, b: (r, g, b))
        lut = parse_cube_bytes(cube)

        rgb = np.array(
            [
                [0.12, 0.34, 0.56],
                [0.91, 0.02, 0.77],
                [0.00, 1.00, 0.50],
            ],
            dtype=np.float32,
        )

        out = apply_lut_rgb(rgb, lut, algorithm="tetrahedral", intensity=1.0)
        np.testing.assert_allclose(out, rgb, atol=1e-6)

    def test_identity_lut_trilinear(self) -> None:
        cube = make_cube_text(2, lambda r, g, b: (r, g, b))
        lut = parse_cube_bytes(cube)
        rgb = np.random.RandomState(0).rand(10, 3).astype(np.float32)
        out = apply_lut_rgb(rgb, lut, algorithm="trilinear", intensity=1.0)
        np.testing.assert_allclose(out, rgb, atol=1e-6)

    def test_invert_lut(self) -> None:
        cube = make_cube_text(2, lambda r, g, b: (1.0 - r, 1.0 - g, 1.0 - b))
        lut = parse_cube_bytes(cube)
        rgb = np.array([[0.2, 0.4, 0.9], [0.0, 0.1, 1.0]], dtype=np.float32)
        out = apply_lut_rgb(rgb, lut, algorithm="tetrahedral", intensity=1.0)
        np.testing.assert_allclose(out, 1.0 - rgb, atol=1e-6)

    def test_intensity_blend(self) -> None:
        cube = make_cube_text(2, lambda r, g, b: (1.0 - r, 1.0 - g, 1.0 - b))
        lut = parse_cube_bytes(cube)
        rgb = np.array([[0.2, 0.4, 0.6]], dtype=np.float32)

        out0 = apply_lut_rgb(rgb, lut, intensity=0.0)
        out1 = apply_lut_rgb(rgb, lut, intensity=1.0)
        out05 = apply_lut_rgb(rgb, lut, intensity=0.5)

        np.testing.assert_allclose(out0, rgb, atol=1e-6)
        np.testing.assert_allclose(out1, 1.0 - rgb, atol=1e-6)
        np.testing.assert_allclose(out05, (rgb + (1.0 - rgb)) * 0.5, atol=1e-6)

    def test_flut_roundtrip_then_apply(self) -> None:
        cube = make_cube_text(2, lambda r, g, b: (r, g, b))
        key = os.urandom(32)

        metadata = build_metadata(
            payload=cube,
            skill_id="leica.skill.core",
            skill_version="1.0.0",
            filter_id="identity",
            display_name="Identity",
            lut_domain="rec709",
            created_at="2026-03-27T00:00:00Z",
        )
        blob = pack_flut_bytes(cube_payload=cube, key=key, metadata=metadata)
        _, decoded_cube = unpack_flut_bytes(flut_blob=blob, key=key)

        lut = parse_cube_bytes(decoded_cube)
        rgb = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        out = apply_lut_rgb(rgb, lut, algorithm="tetrahedral", intensity=1.0)
        np.testing.assert_allclose(out, rgb, atol=1e-6)


if __name__ == "__main__":
    unittest.main()

