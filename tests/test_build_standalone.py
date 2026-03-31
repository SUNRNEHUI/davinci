"""Standalone builder tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_standalone import MANIFEST_NAME, build_standalone


class TestBuildStandalone(unittest.TestCase):
    def test_build_standalone_assembles_bundle_and_supporting_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_app = tmp_path / "fake-app"
            fake_app.mkdir(parents=True, exist_ok=True)
            (fake_app / "davinci").write_text("binary", encoding="utf-8")
            (fake_app / "_internal").mkdir()
            (fake_app / "_internal" / "placeholder.txt").write_text("ok", encoding="utf-8")

            output_dir = tmp_path / "standalone"
            build_root = tmp_path / "build-root"

            with (
                patch("scripts.build_standalone._ensure_pyinstaller"),
                patch("scripts.build_standalone._run_pyinstaller", return_value=fake_app),
                patch("scripts.build_standalone._best_effort_codesign", return_value=(True, None)),
            ):
                result = build_standalone(
                    output_dir,
                    build_root=build_root,
                    python_executable="python3",
                    make_zip=False,
                )

            self.assertEqual(str(output_dir.resolve()), result["output_dir"])
            self.assertTrue((output_dir / "davinci").exists())
            self.assertTrue((output_dir / "DAVINCI.command").exists())
            self.assertTrue((output_dir / "README.md").exists())
            self.assertTrue((output_dir / "TESTER_GUIDE_CN.md").exists())
            self.assertTrue((output_dir / "install.sh").exists())
            self.assertTrue((output_dir / MANIFEST_NAME).exists())

            launcher_text = (output_dir / "DAVINCI.command").read_text(encoding="utf-8")
            self.assertIn('exec "$SCRIPT_DIR/davinci" "$@"', launcher_text)
            install_text = (output_dir / "install.sh").read_text(encoding="utf-8")
            self.assertIn("DAVINCI_RELEASE_URL", install_text)

            manifest = json.loads((output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["executable"], "davinci")
            self.assertTrue(manifest["signed"])
