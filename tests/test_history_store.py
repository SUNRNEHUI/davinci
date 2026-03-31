"""Persistent product store tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.leica_product_store import MAX_HISTORY_ENTRIES, ProductStore, default_cli_home


class TestHistoryStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.home = Path(self.tmpdir_obj.name) / "cli_home"
        self.store = ProductStore(self.home)

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()

    def test_profile_load_falls_back_on_corrupt_json(self) -> None:
        self.store.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.store.profile_path.write_text("{broken", encoding="utf-8")

        profile = self.store.load_profile()

        self.assertEqual(profile["default_catalog"], "leica")
        self.assertTrue(self.store.consume_warnings())

    def test_append_history_caps_and_keeps_newest_first(self) -> None:
        for index in range(MAX_HISTORY_ENTRIES + 5):
            self.store.append_history(
                {
                    "command": "render",
                    "catalog": "leica",
                    "output_path": f"/tmp/out_{index}.png",
                    "display_name": f"Look {index}",
                }
            )

        history = self.store.load_history()

        self.assertEqual(len(history), MAX_HISTORY_ENTRIES)
        self.assertEqual(history[0]["display_name"], f"Look {MAX_HISTORY_ENTRIES + 4}")
        self.assertEqual(history[-1]["display_name"], "Look 5")

    def test_workspace_switch_and_status_tracking(self) -> None:
        self.assertEqual(self.store.current_workspace(), "default")
        self.store.set_current_workspace("project-a")
        self.assertEqual(self.store.current_workspace(), "project-a")
        workspaces = self.store.list_workspaces()
        self.assertIn("project-a", workspaces)
        vs = self.store.workspace_status("project-a")
        self.assertEqual(vs["workspace"], "project-a")
        self.assertEqual(vs["active_sessions"], 0)

    def test_session_workspace_filter_and_close_marker(self) -> None:
        self.store.set_current_workspace("alpha")
        session_a = self.store.create_session(
            input_path="/tmp/in_a.jpg",
            catalog="leica",
            index_path="/tmp/index_a.json",
            output_dir="/tmp/out_a",
            theme="blackroom",
        )
        self.store.set_current_workspace("beta")
        session_b = self.store.create_session(
            input_path="/tmp/in_b.jpg",
            catalog="leica",
            index_path="/tmp/index_b.json",
            output_dir="/tmp/out_b",
            theme="minimal",
        )
        alpha_sessions = self.store.sessions_by_workspace("alpha")
        beta_sessions = self.store.sessions_by_workspace("beta")
        self.assertEqual(len(alpha_sessions), 1)
        self.assertEqual(len(beta_sessions), 1)
        closed = self.store.mark_session_closed(session_a["session_id"], reason="done")
        self.assertIsNotNone(closed)
        self.assertIn("closed_at", closed)
        self.assertEqual(closed["close_reason"], "done")

    def test_workspace_meta_recovers_from_invalid_type(self) -> None:
        self.store.workspace_meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.store.workspace_meta_path.write_text("[]", encoding="utf-8")

        self.assertEqual(self.store.current_workspace(), "default")
        self.assertEqual([], self.store.list_workspaces())
        self.assertTrue(self.store.consume_warnings())

    def test_profile_invalid_numeric_values_fall_back_to_defaults(self) -> None:
        self.store.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.store.profile_path.write_text(
            json.dumps({"intensity": "bad", "top_k": "oops"}),
            encoding="utf-8",
        )

        profile = self.store.load_profile()

        self.assertEqual(profile["intensity"], 0.85)
        self.assertEqual(profile["top_k"], 3)
        self.assertTrue(self.store.consume_warnings())

    def test_default_cli_home_prefers_davinci_env_and_falls_back_to_legacy(self) -> None:
        explicit = self.home / "explicit"
        legacy = self.home / ".leica-skill"
        legacy.mkdir(parents=True, exist_ok=True)

        with patch.dict(os.environ, {"DAVINCI_CLI_HOME": str(explicit)}, clear=False):
            self.assertEqual(default_cli_home(), explicit.resolve())

        with patch.dict(
            os.environ,
            {"DAVINCI_CLI_HOME": "", "DAVINCI_HOME": "", "LEICA_CLI_HOME": ""},
            clear=False,
        ), patch("pathlib.Path.home", return_value=self.home):
            self.assertEqual(default_cli_home(), legacy.resolve())

    def test_activation_roundtrip(self) -> None:
        self.assertFalse(self.store.is_activated())

        activation = self.store.mark_activated(activation_url="https://example.com")

        self.assertTrue(self.store.is_activated())
        self.assertTrue(bool(activation["activated_at"]))
        self.assertEqual("https://example.com", activation["activation_url"])

        reset = self.store.reset_activation()

        self.assertFalse(reset["activated"])
