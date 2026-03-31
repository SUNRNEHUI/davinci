"""CLI favorites command tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers_cli import run_cli
from tests.helpers_runtime_bundle import make_runtime_bundle


class TestCliFavorites(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.cli_home = self.tmpdir / "cli_home"
        _, self.index_path = make_runtime_bundle(
            self.tmpdir,
            filter_id="demo_classic",
            display_name="Demo Classic",
            catalog="demo",
        )

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()

    def test_add_list_remove_and_clear_favorites(self) -> None:
        rc, stdout, stderr = run_cli(
            [
                "favorites",
                "add",
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--filter",
                "Demo Classic",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["filter"]["filter_id"], "demo_classic")
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(
            ["favorites", "list", "--index", str(self.index_path), "--catalog", "demo", "--json"],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(len(payload["favorites"]), 1)
        self.assertFalse(payload["favorites"][0]["stale"])
        self.assertEqual("", stderr)

        rc, stdout, stderr = run_cli(
            [
                "favorites",
                "remove",
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
            ["favorites", "clear", "--catalog", "demo", "--json"],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["scope"], "demo")
        self.assertEqual("", stderr)

    def test_add_unknown_filter_fails(self) -> None:
        rc, stdout, stderr = run_cli(
            [
                "favorites",
                "add",
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--filter",
                "unknown",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 2)
        self.assertEqual("", stdout)
        self.assertIn("[ERROR]", stderr)
