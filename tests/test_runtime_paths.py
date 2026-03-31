"""Runtime resource path tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_resource_root_prefers_candidate_with_required_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad_root = tmp_path / "bad"
            good_root = tmp_path / "good"
            bad_root.mkdir()
            (good_root / "flut").mkdir(parents=True)
            (good_root / "examples").mkdir(parents=True)

            with patch.object(runtime_paths, "_candidate_roots", return_value=[bad_root, good_root]):
                self.assertEqual(runtime_paths.resource_root("flut", "examples"), good_root)
                self.assertEqual(runtime_paths.catalog_root(), good_root / "flut")
                self.assertEqual(runtime_paths.examples_root(), good_root / "examples")

    def test_resource_root_raises_clear_error_when_missing(self) -> None:
        with patch.object(runtime_paths, "_candidate_roots", return_value=[Path("/tmp/missing-a"), Path("/tmp/missing-b")]):
            with self.assertRaises(FileNotFoundError) as ctx:
                runtime_paths.resource_root("flut")
        self.assertIn("Could not locate runtime resource root", str(ctx.exception))
