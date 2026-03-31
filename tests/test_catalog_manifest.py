"""Manifest-aware catalog behavior tests."""

from __future__ import annotations

import json
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


class CatalogManifestTests(unittest.TestCase):
    def test_fuji_scene_filters_and_reasons_come_from_manifest(self) -> None:
        from leica_catalog import build_recommendation_details, scene_filters_for_catalog

        scene_filters = scene_filters_for_catalog("fuji")
        self.assertEqual(scene_filters["landscape"][0], "fuji_velvia")

        details = build_recommendation_details(
            "landscape",
            [{"filter_id": "fuji_velvia", "display_name": "Fuji Velvia / VIVID", "catalog": "fuji"}],
            catalog="fuji",
        )
        self.assertEqual(details[0]["reason"], "High saturation for landscapes, sky, and foliage.")

    def test_load_filter_index_merges_manifest_aliases(self) -> None:
        from leica_catalog import find_filter, load_filter_index

        filters = load_filter_index(catalog="fuji")
        _, selected = find_filter(filters, "classic negative")
        self.assertEqual(selected["filter_id"], "fuji_classic_neg")
        self.assertIn("aliases", selected)

    def test_custom_bundle_manifest_is_used_near_index(self) -> None:
        from leica_catalog import build_recommendation_details, load_filter_index, scene_filters_for_catalog

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = {
                "catalog": "kodak",
                "scene_filters": {"general": ["kodak_portra_400"]},
                "filters": [
                    {
                        "filter_id": "kodak_portra_400",
                        "display_name": "Kodak Portra 400",
                        "source_cube": "Portra400.cube",
                        "flut_file": "kodak_portra_400.flut",
                        "reason": "Soft pastel color for daylight portraits.",
                        "aliases": ["portra 400"],
                    }
                ],
            }
            index = {
                "skill_id": "kodak.skill.rec709",
                "skill_version": "1.0.0",
                "lut_domain": "rec709",
                "filter_count": 1,
                "filters": [
                    {
                        "filter_id": "kodak_portra_400",
                        "display_name": "Placeholder",
                        "flut_file": "kodak_portra_400.flut",
                    }
                ],
            }
            (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")

            filters = load_filter_index(tmp_path / "index.json", catalog="kodak")
            self.assertEqual(filters[0]["display_name"], "Kodak Portra 400")
            self.assertEqual(
                scene_filters_for_catalog("kodak", index_path=tmp_path / "index.json"),
                {"general": ["kodak_portra_400"]},
            )

            details = build_recommendation_details(
                "general",
                filters,
                catalog="kodak",
                index_path=tmp_path / "index.json",
            )
            self.assertEqual(details[0]["reason"], "Soft pastel color for daylight portraits.")
