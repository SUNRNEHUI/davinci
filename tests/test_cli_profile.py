"""CLI profile command tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers_cli import run_cli


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_IMAGE = ROOT / "examples" / "input_demo.png"


class TestCliProfile(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.cli_home = self.tmpdir / "cli_home"

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()

    def test_profile_set_show_and_reset(self) -> None:
        rc, stdout, stderr = run_cli(
            [
                "profile",
                "set",
                "--default-catalog",
                "fuji",
                "--intensity",
                "0.77",
                "--algorithm",
                "trilinear",
                "--theme",
                "minimal",
                "--top-k",
                "2",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["profile"]["default_catalog"], "fuji")
        self.assertEqual(payload["profile"]["algorithm"], "trilinear")
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(["profile", "show", "--json"], cli_home=self.cli_home)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["profile"]["theme"], "minimal")
        self.assertEqual(payload["profile"]["top_k"], 2)
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(["profile", "reset", "--json"], cli_home=self.cli_home)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["profile"]["default_catalog"], "leica")
        self.assertEqual(payload["profile"]["algorithm"], "tetrahedral")
        self.assertEqual("", stderr)

    def test_profile_defaults_apply_to_recommend_command(self) -> None:
        rc, stdout, stderr = run_cli(
            [
                "profile",
                "set",
                "--default-catalog",
                "fuji",
                "--top-k",
                "2",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(
            [
                "recommend",
                "--input",
                str(EXAMPLE_IMAGE),
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "fuji")
        self.assertEqual(len(payload["recommendations"]), 2)
        self.assertEqual("", stderr)

    def test_invalid_persisted_numeric_values_do_not_crash_cli(self) -> None:
        self.cli_home.mkdir(parents=True, exist_ok=True)
        (self.cli_home / "profile.json").write_text(
            json.dumps({"intensity": "bad", "top_k": "oops"}),
            encoding="utf-8",
        )

        rc, stdout, stderr = run_cli(["profile", "show", "--json"], cli_home=self.cli_home)

        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["profile"]["intensity"], 0.85)
        self.assertEqual(payload["profile"]["top_k"], 3)
        self.assertEqual("", stderr)
