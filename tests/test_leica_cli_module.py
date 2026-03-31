"""Module-mode CLI smoke tests."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_IMAGE = ROOT / "examples" / "input_demo.png"


class TestLeicaCliModule(unittest.TestCase):
    def test_module_entrypoint_lists_filters(self):
        """`python -m scripts.leica_cli` should work in package mode."""
        env = dict(os.environ)
        cli_home = tempfile.mkdtemp()
        env["DAVINCI_CLI_HOME"] = cli_home
        env["DAVINCI_HOME"] = cli_home
        env["LEICA_CLI_HOME"] = cli_home
        env["DAVINCI_OUTPUT_ROOT"] = tempfile.mkdtemp()
        result = subprocess.run(
            [sys.executable, "-m", "scripts.leica_cli", "list-filters", "--json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "list-filters")
        self.assertGreaterEqual(payload["count"], 1)

    def test_module_entrypoint_can_render_with_shipped_assets(self):
        """Package mode should still find the shipped FLUT index and runtime key."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "rendered.png"
            env = dict(os.environ)
            env["DAVINCI_CLI_HOME"] = str(Path(tmp) / "cli_home")
            env["DAVINCI_HOME"] = str(Path(tmp) / "cli_home")
            env["LEICA_CLI_HOME"] = str(Path(tmp) / "cli_home")
            env["DAVINCI_OUTPUT_ROOT"] = str(Path(tmp) / "davinci_output")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.leica_cli",
                    "render",
                    "--input",
                    str(EXAMPLE_IMAGE),
                    "--filter",
                    "Leica Classic",
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(output_path.exists())
