#!/usr/bin/env python3

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from flut_codec import (  # type: ignore
    HEADER_STRUCT,
    build_metadata,
    pack_flut_bytes,
    pack_flut_file,
    parse_header,
    unpack_flut_bytes,
    unpack_flut_file,
)


SAMPLE_CUBE = b"""TITLE \"Leica Test\"\nLUT_3D_SIZE 33\n0.0 0.0 0.0\n1.0 1.0 1.0\n"""


class FLUTCodecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = os.urandom(32)
        self.metadata = build_metadata(
            payload=SAMPLE_CUBE,
            skill_id="leica.skill.core",
            skill_version="1.0.0",
            filter_id="leica_classic",
            display_name="Leica Classic",
            lut_domain="rec709",
            created_at="2026-03-27T00:00:00Z",
        )

    def test_roundtrip_in_memory(self) -> None:
        blob = pack_flut_bytes(cube_payload=SAMPLE_CUBE, key=self.key, metadata=self.metadata)
        decoded_metadata, payload = unpack_flut_bytes(flut_blob=blob, key=self.key)

        self.assertEqual(payload, SAMPLE_CUBE)
        self.assertEqual(decoded_metadata["filter_id"], "leica_classic")

    def test_roundtrip_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_cube = tmp_path / "input.cube"
            out_flut = tmp_path / "output.flut"
            out_cube = tmp_path / "output.cube"
            in_cube.write_bytes(SAMPLE_CUBE)

            pack_flut_file(
                input_cube=str(in_cube),
                output_flut=str(out_flut),
                key=self.key,
                metadata=self.metadata,
            )
            returned_metadata = unpack_flut_file(
                input_flut=str(out_flut),
                output_cube=str(out_cube),
                key=self.key,
            )

            self.assertEqual(out_cube.read_bytes(), SAMPLE_CUBE)
            self.assertEqual(returned_metadata["skill_id"], "leica.skill.core")

    def test_plaintext_not_directly_visible(self) -> None:
        blob = pack_flut_bytes(cube_payload=SAMPLE_CUBE, key=self.key, metadata=self.metadata)
        self.assertNotIn(b"LUT_3D_SIZE", blob)
        self.assertNotIn(b"Leica Test", blob)

    def test_tampered_ciphertext_should_fail(self) -> None:
        blob = bytearray(pack_flut_bytes(cube_payload=SAMPLE_CUBE, key=self.key, metadata=self.metadata))
        blob[-1] ^= 0x01
        with self.assertRaises(ValueError):
            unpack_flut_bytes(flut_blob=bytes(blob), key=self.key)

    def test_tampered_metadata_should_fail(self) -> None:
        blob = bytearray(pack_flut_bytes(cube_payload=SAMPLE_CUBE, key=self.key, metadata=self.metadata))
        header = parse_header(bytes(blob))
        metadata_start = HEADER_STRUCT.size
        metadata_end = metadata_start + header.metadata_len
        mutate_index = metadata_start + min(5, header.metadata_len - 1)
        blob[mutate_index] ^= 0x01

        # Ensure mutation happened within metadata region
        self.assertLess(mutate_index, metadata_end)

        with self.assertRaises(ValueError):
            unpack_flut_bytes(flut_blob=bytes(blob), key=self.key)

    def test_wrong_key_should_fail(self) -> None:
        blob = pack_flut_bytes(cube_payload=SAMPLE_CUBE, key=self.key, metadata=self.metadata)
        wrong_key = os.urandom(32)
        with self.assertRaises(ValueError):
            unpack_flut_bytes(flut_blob=blob, key=wrong_key)

    def test_key_example_is_32_bytes(self) -> None:
        key_b64 = base64.b64encode(self.key).decode("ascii")
        self.assertEqual(len(base64.b64decode(key_b64)), 32)


if __name__ == "__main__":
    unittest.main()

