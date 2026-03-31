"""Session workbench tests."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.leica_product_store import ProductStore
from scripts.leica_session import FilterSession
from tests.helpers_cli import run_cli
from tests.helpers_runtime_bundle import make_runtime_bundle


class TestCliSession(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.cli_home = self.tmpdir / "cli_home"
        self.input_path = self.tmpdir / "input.png"
        Image.fromarray(np.full((32, 32, 3), [90, 120, 170], dtype=np.uint8), mode="RGB").save(self.input_path)
        _, self.index_path = make_runtime_bundle(
            self.tmpdir,
            filter_id="demo_classic",
            display_name="Demo Classic",
            catalog="demo",
            include_manifest=True,
        )

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()

    def test_session_script_runs_preview_apply_undo_redo(self) -> None:
        rc, stdout, stderr = run_cli(
            [
                "session",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--catalog",
                "demo",
                "--output-dir",
                str(self.tmpdir / "out"),
                "--command",
                "preview",
                "--command",
                "apply 1",
                "--command",
                "undo",
                "--command",
                "redo",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "demo")
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertIsNotNone(payload["selected_filter"])
        self.assertEqual(payload["cursor"], 0)
        self.assertEqual(payload["selected_filter"]["filter_id"], "demo_classic")
        self.assertTrue(any(item["event"] == "undo" for item in payload["events"]))
        self.assertTrue(any(item["event"] == "redo" for item in payload["events"]))
        self.assertEqual("", stderr)

    def test_session_invalid_command_keeps_running(self) -> None:
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
                "not-real",
                "--command",
                "status",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(any(item["event"] == "error" and not item["ok"] for item in payload["events"]))
        self.assertTrue(any(item["event"] == "status" for item in payload["events"]))
        self.assertEqual("", stderr)

    def test_session_compare_and_close(self) -> None:
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
                "compare 1 1",
                "--command",
                "close",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(any(event["event"] == "compare" for event in payload["events"]))
        self.assertTrue(any(event["event"] == "close" for event in payload["events"]))
        self.assertIsNotNone(payload["closed_at"])
        self.assertEqual("", stderr)

    def test_session_exit_stops_follow_up_commands(self) -> None:
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
                "exit",
                "--command",
                "apply 1",
                "--json",
            ],
            cli_home=self.cli_home,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(["exit"], [event["event"] for event in payload["events"]])
        self.assertIsNone(payload["selected_filter"])
        self.assertEqual("", stderr)

    def test_session_prompt_uses_active_theme(self) -> None:
        prompts: list[str] = []

        def scripted_input(prompt: str) -> str:
            prompts.append(prompt)
            return "exit"

        session = FilterSession(
            store=ProductStore(self.cli_home),
            input_path=self.input_path,
            output_dir=self.tmpdir / "prompt_out",
            index_path=self.index_path,
            catalog="demo",
            intensity=0.85,
            algorithm="tetrahedral",
            top_k=1,
            theme="minimal",
            stream=io.StringIO(),
            input_fn=scripted_input,
        )

        summary = session.run_interactive()

        self.assertEqual(["minimal> "], prompts)
        self.assertIsNotNone(summary["closed_at"])
