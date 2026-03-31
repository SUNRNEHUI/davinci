"""End-to-end product flow tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tests.helpers_cli import run_cli
from tests.helpers_runtime_bundle import make_runtime_bundle


class TestE2EProductFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.cli_home = self.tmpdir / "cli_home"
        self.input_path = self.tmpdir / "input.png"
        Image.fromarray(np.full((40, 52, 3), [120, 100, 160], dtype=np.uint8), mode="RGB").save(self.input_path)
        _, self.index_path = make_runtime_bundle(
            self.tmpdir,
            filter_id="demo_classic",
            display_name="Demo Classic",
            catalog="demo",
            include_manifest=True,
        )

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()

    def test_profile_favorites_render_history_and_session_flow(self) -> None:
        rc, stdout, stderr = run_cli(
            [
                "profile",
                "set",
                "--default-catalog",
                "demo",
                "--intensity",
                "0.42",
                "--algorithm",
                "trilinear",
                "--top-k",
                "1",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(
            [
                "favorites",
                "add",
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--filter",
                "demo_classic",
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
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(payload["recommendations"][0]["favorite_boost"])
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(
            [
                "render",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--filter",
                "1",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["intensity"], 0.42)
        self.assertEqual(payload["algorithm"], "trilinear")
        self.assertTrue(Path(payload["output_path"]).exists())
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(["history", "list", "--json"], cli_home=self.cli_home)
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(any(item["command"] == "render" for item in payload["events"]))
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(
            [
                "session",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--command",
                "apply 1",
                "--command",
                "favorite",
                "--command",
                "history",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["selected_filter"]["filter_id"], "demo_classic")
        self.assertTrue(any(item["event"] == "favorite" for item in payload["events"]))
        self.assertEqual("", stderr)
