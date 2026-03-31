"""Release package builder tests."""

import tempfile
import unittest
from pathlib import Path

from scripts.build_release import MANIFEST_NAME, build_release


class TestBuildRelease(unittest.TestCase):
    def test_build_release_contains_skill_runtime_and_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "release"
            result = build_release(output_dir)
            self.assertEqual(str(output_dir.resolve()), result["output_dir"])
            self.assertTrue((output_dir / "README.md").exists())
            readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("davinci demo", readme_text)
            self.assertIn("~/Pictures/DAVINCI/_demo/", readme_text)
            self.assertIn("macOS Apple Silicon only", readme_text)
            self.assertNotIn("FLUT", readme_text)
            self.assertTrue((output_dir / "SKILL.md").exists())
            self.assertTrue((output_dir / "agents" / "openai.yaml").exists())
            self.assertTrue((output_dir / "scripts" / "leica_cli.py").exists())
            self.assertTrue((output_dir / "examples" / "input_demo.png").exists())
            self.assertTrue((output_dir / "flut" / "leica" / "index.json").exists())
            self.assertTrue((output_dir / "flut" / "leica" / "runtime.key.b64").exists())
            self.assertTrue((output_dir / "flut" / "fuji" / "index.json").exists())
            self.assertTrue((output_dir / "flut" / "fuji" / "runtime.key.b64").exists())
            self.assertTrue((output_dir / MANIFEST_NAME).exists())

    def test_build_release_can_zip_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "release"
            result = build_release(output_dir, make_zip=True)
            self.assertIn("zip_path", result)
            self.assertTrue(Path(str(result["zip_path"])).exists())
