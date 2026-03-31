"""apply_flut_image helper tests."""
import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


class TestApplyFlutImage(unittest.TestCase):
    def test_apply_uses_bundled_runtime_key(self):
        """A sibling runtime.key.b64 should remove the need for explicit key input."""
        from apply_flut_image import apply_flut_to_image
        from flut_codec import build_metadata, pack_flut_bytes

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.png"
            output_path = tmp_path / "output.png"
            flut_path = tmp_path / "demo.flut"
            key_path = tmp_path / "runtime.key.b64"

            Image.fromarray(
                np.full((20, 20, 3), [80, 120, 180], dtype=np.uint8),
                mode="RGB",
            ).save(input_path)

            cube = (
                b'TITLE "Invert2"\n'
                b"LUT_3D_SIZE 2\n"
                b"1.0 1.0 1.0\n"
                b"0.0 1.0 1.0\n"
                b"1.0 0.0 1.0\n"
                b"0.0 0.0 1.0\n"
                b"1.0 1.0 0.0\n"
                b"0.0 1.0 0.0\n"
                b"1.0 0.0 0.0\n"
                b"0.0 0.0 0.0\n"
            )
            key = os.urandom(32)
            metadata = build_metadata(
                payload=cube,
                skill_id="leica.skill.test",
                skill_version="1.0.0",
                filter_id="invert2",
                display_name="Invert2",
                lut_domain="rec709",
                created_at="2026-03-28T00:00:00Z",
            )
            flut_path.write_bytes(pack_flut_bytes(cube_payload=cube, key=key, metadata=metadata))
            key_path.write_text(base64.b64encode(key).decode("ascii"), encoding="utf-8")

            result = apply_flut_to_image(
                flut_path=flut_path,
                input_path=input_path,
                output_path=output_path,
                intensity=1.0,
            )

            self.assertEqual(str(output_path.resolve()), result["output_path"])
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
