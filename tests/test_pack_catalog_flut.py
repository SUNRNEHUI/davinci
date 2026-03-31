"""Tests for generic CUBE catalog batch packer."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


SAMPLE_CUBE = (
    b'TITLE "TestLUT"\n'
    b"LUT_3D_SIZE 2\n"
    b"0.0 0.0 0.0\n"
    b"1.0 0.0 0.0\n"
    b"0.0 1.0 0.0\n"
    b"1.0 1.0 0.0\n"
    b"0.0 0.0 1.0\n"
    b"1.0 0.0 1.0\n"
    b"0.0 1.0 1.0\n"
    b"1.0 1.0 1.0\n"
)


class PackCatalogFlutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = os.urandom(32)

    def test_pack_catalog_recursive_builds_index_and_flut_files(self) -> None:
        from flut_codec import unpack_flut_bytes
        from pack_catalog_flut import pack_catalog

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            catalog_dir = tmp_path / "catalog"
            output_dir = tmp_path / "out_flut"
            index_file = tmp_path / "index" / "catalog_index.json"

            (catalog_dir / "portraits").mkdir(parents=True, exist_ok=True)
            (catalog_dir / "landscape").mkdir(parents=True, exist_ok=True)
            cube_a = catalog_dir / "portraits" / "Classic.cube"
            cube_b = catalog_dir / "landscape" / "Vivid.cube"
            cube_a.write_bytes(SAMPLE_CUBE)
            cube_b.write_bytes(SAMPLE_CUBE.replace(b"TestLUT", b"TestLUT2"))

            index = pack_catalog(
                catalog_dir=catalog_dir,
                output_dir=output_dir,
                index_file=index_file,
                key=self.key,
                skill_id="demo.skill.core",
                skill_version="2.3.4",
                lut_domain="rec709",
                filter_prefix="demo",
            )

            self.assertEqual(index["skill_id"], "demo.skill.core")
            self.assertEqual(index["skill_version"], "2.3.4")
            self.assertEqual(index["filter_count"], 2)
            self.assertTrue(index_file.exists())

            flut_names = {entry["flut_file"] for entry in index["filters"]}
            self.assertEqual(len(flut_names), 2)
            for entry in index["filters"]:
                self.assertNotIn("source_cube", entry)
                out_flut = output_dir / entry["flut_file"]
                self.assertTrue(out_flut.exists())
                metadata, payload = unpack_flut_bytes(
                    flut_blob=out_flut.read_bytes(),
                    key=self.key,
                )
                self.assertEqual(metadata["filter_id"], entry["filter_id"])
                self.assertIn(payload, {cube_a.read_bytes(), cube_b.read_bytes()})

    def test_pack_catalog_deduplicates_filter_ids(self) -> None:
        from pack_catalog_flut import pack_catalog

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            catalog_dir = tmp_path / "catalog"
            output_dir = tmp_path / "out_flut"
            index_file = tmp_path / "catalog_index.json"

            (catalog_dir / "set_a").mkdir(parents=True, exist_ok=True)
            (catalog_dir / "set_b").mkdir(parents=True, exist_ok=True)
            # Same stem in different folders.
            (catalog_dir / "set_a" / "Classic.cube").write_bytes(SAMPLE_CUBE)
            (catalog_dir / "set_b" / "Classic.cube").write_bytes(SAMPLE_CUBE)

            index = pack_catalog(
                catalog_dir=catalog_dir,
                output_dir=output_dir,
                index_file=index_file,
                key=self.key,
                skill_id="demo.skill.core",
                skill_version="1.0.0",
                lut_domain="rec709",
                filter_prefix="demo",
            )

            filter_ids = [entry["filter_id"] for entry in index["filters"]]
            self.assertEqual(len(filter_ids), len(set(filter_ids)))
            self.assertEqual(index["filter_count"], 2)

    def test_pack_catalog_raises_when_no_cube_files(self) -> None:
        from pack_catalog_flut import pack_catalog

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            catalog_dir = tmp_path / "empty_catalog"
            output_dir = tmp_path / "out_flut"
            index_file = tmp_path / "catalog_index.json"
            catalog_dir.mkdir(parents=True, exist_ok=True)
            (catalog_dir / "readme.txt").write_text("not a cube", encoding="utf-8")

            with self.assertRaises(ValueError):
                pack_catalog(
                    catalog_dir=catalog_dir,
                    output_dir=output_dir,
                    index_file=index_file,
                    key=self.key,
                    skill_id="demo.skill.core",
                    skill_version="1.0.0",
                    lut_domain="rec709",
                    filter_prefix="demo",
                )

    def test_pack_catalog_manifest_controls_ids_and_writes_manifest(self) -> None:
        from pack_catalog_flut import load_catalog_manifest, pack_catalog

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            catalog_dir = tmp_path / "catalog"
            output_dir = tmp_path / "out_flut"
            index_file = tmp_path / "catalog_index.json"
            manifest_path = tmp_path / "manifest.json"

            catalog_dir.mkdir(parents=True, exist_ok=True)
            (catalog_dir / "A.cube").write_bytes(SAMPLE_CUBE)
            (catalog_dir / "B.cube").write_bytes(SAMPLE_CUBE.replace(b"TestLUT", b"TestLUT2"))
            manifest_path.write_text(
                """{
  "catalog": "demo",
  "display_name": "Demo Catalog",
  "skill_id": "demo.skill.rec709",
  "skill_version": "9.9.9",
  "lut_domain": "rec709",
  "scene_filters": {
    "general": ["demo_a", "demo_b"]
  },
  "filters": [
    {
      "source_cube": "A.cube",
      "filter_id": "demo_a",
      "display_name": "Demo A",
      "reason": "Reason A",
      "aliases": ["alpha"]
    },
    {
      "source_cube": "B.cube",
      "filter_id": "demo_b",
      "display_name": "Demo B",
      "reason": "Reason B"
    }
  ]
}""",
                encoding="utf-8",
            )

            index = pack_catalog(
                catalog_dir=catalog_dir,
                output_dir=output_dir,
                index_file=index_file,
                key=self.key,
                skill_id="demo.skill.rec709",
                skill_version="9.9.9",
                lut_domain="rec709",
                filter_prefix="demo",
                manifest=load_catalog_manifest(manifest_path),
            )

            self.assertEqual(
                [item["filter_id"] for item in index["filters"]],
                ["demo_a", "demo_b"],
            )
            output_manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(output_manifest["catalog"], "demo")
            self.assertEqual(output_manifest["scene_filters"]["general"], ["demo_a", "demo_b"])
            self.assertEqual(output_manifest["filters"][0]["aliases"], ["alpha"])
            self.assertEqual(output_manifest["filters"][0]["flut_file"], "demo_a.flut")

    def test_load_catalog_manifest_rejects_duplicate_filter_ids(self) -> None:
        from pack_catalog_flut import load_catalog_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                """{
  "filters": [
    {"source_cube": "A.cube", "filter_id": "demo_a", "display_name": "Demo A"},
    {"source_cube": "B.cube", "filter_id": "demo_a", "display_name": "Demo B"}
  ]
}""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate filter_id"):
                load_catalog_manifest(manifest_path)

    def test_load_catalog_manifest_rejects_unknown_scene_filter_ids(self) -> None:
        from pack_catalog_flut import load_catalog_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                """{
  "scene_filters": {
    "general": ["demo_missing"]
  },
  "filters": [
    {"source_cube": "A.cube", "filter_id": "demo_a", "display_name": "Demo A"}
  ]
}""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown filter ids"):
                load_catalog_manifest(manifest_path)


if __name__ == "__main__":
    unittest.main()
