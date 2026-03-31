"""Tests for the deterministic render cache helper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.leica_render_cache import (
    clear_render_cache,
    inspect_render_cache,
    lookup_render_cache,
    make_render_cache_key,
    store_render_cache,
)


class TestRenderCache(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.input_path = self.tmpdir / "photo.png"
        self.input_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        self.key = make_render_cache_key(
            input_path=self.input_path,
            catalog="leica",
            filter_ids=["leica_leica_classic"],
            intensity=0.86,
            algorithm="tetrahedral",
            output_type="contact",
        )

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()
        clear_render_cache()

    def test_store_and_lookup(self) -> None:
        dummy = self.tmpdir / "sheet.png"
        dummy.write_bytes(b"PNG")
        cached = store_render_cache(
            dummy,
            key=self.key,
            output_suffix="png",
        )
        self.assertTrue(cached.exists())
        found = lookup_render_cache(self.key, output_suffix="png")
        self.assertEqual(cached, found)

        entries = inspect_render_cache()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["catalog"], "leica")
        self.assertEqual(entries[0]["filter_ids"], ["leica_leica_classic"])

    def test_clear_cache_removes_files(self) -> None:
        dummy = self.tmpdir / "sheet.png"
        dummy.write_bytes(b"PNG")
        store_render_cache(dummy, key=self.key, output_suffix="png")
        clear_render_cache()
        self.assertEqual(inspect_render_cache(), [])

    def test_make_key_requires_existing_file(self) -> None:
        missing = self.tmpdir / "missing.png"
        with self.assertRaises(FileNotFoundError):
            make_render_cache_key(
                input_path=missing,
                catalog="leica",
                filter_ids=["leica_leica_classic"],
                intensity=0.5,
                algorithm="tetrahedral",
                output_type="contact",
            )
