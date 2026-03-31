"""Catalog validation tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.leica_catalog_validate import doctor_catalog_bundle, format_doctor_report, validate_catalog_bundle
from tests.helpers_runtime_bundle import make_runtime_bundle


class TestCatalogValidate(unittest.TestCase):
    def test_validate_clean_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="kodak_portra_400",
                display_name="Kodak Portra 400",
                catalog="kodak",
                include_manifest=True,
            )

            report = validate_catalog_bundle(index_path=index_path, catalog="kodak")

            self.assertTrue(report["ok"])
            self.assertEqual([], report["errors"])

    def test_validate_reports_missing_flut_and_scene_filter_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="broken_demo",
                display_name="Broken Demo",
                catalog="broken",
                include_manifest=True,
            )
            bundle_dir = index_path.parent
            (bundle_dir / "broken_demo.flut").unlink()
            (bundle_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "catalog": "broken",
                        "filters": [
                            {
                                "filter_id": "broken_demo",
                                "display_name": "Broken Demo",
                                "source_cube": "Demo.cube",
                                "flut_file": "broken_demo.flut",
                            }
                        ],
                        "scene_filters": {"general": ["missing_id"]},
                    }
                ),
                encoding="utf-8",
            )

            report = validate_catalog_bundle(index_path=index_path, catalog="broken", strict=True)

            self.assertFalse(report["ok"])
            self.assertTrue(any("Missing FLUT file" in item for item in report["errors"]))
            self.assertTrue(any("unknown filter_id" in item for item in report["errors"]))

    def test_doctor_suggests_manifest_fields_and_missing_runtime_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="demo_filter",
                display_name="Demo Filter",
                catalog="demo",
                include_manifest=True,
            )
            (index_path.parent / "runtime.key.b64").unlink()

            report = doctor_catalog_bundle(index_path=index_path, catalog="demo")
            codes = {item["code"] for item in report["issues"]}

            self.assertIn("manifest_missing_field", codes)
            self.assertIn("runtime_key_missing", codes)
            self.assertGreater(report["summary"]["missing_manifest_field_count"], 0)
            self.assertTrue(report["summary"]["missing_key_file"])
            self.assertTrue(report["suggested_fixes"])

    def test_doctor_detects_stale_favorite_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="demo_filter",
                display_name="Demo Filter",
                catalog="demo",
                include_manifest=True,
            )

            report = doctor_catalog_bundle(
                index_path=index_path,
                catalog="demo",
                favorite_filter_ids=["demo_filter", "missing_filter"],
            )
            stale = [item for item in report["issues"] if item["code"] == "stale_favorite_candidate"]

            self.assertEqual(1, len(stale))
            self.assertEqual("missing_filter", stale[0]["context"]["filter_id"])
            self.assertEqual(1, report["summary"]["stale_favorites_count"])

    def test_doctor_detects_manifest_index_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="demo_filter",
                display_name="Demo Filter",
                catalog="demo",
                include_manifest=True,
            )
            bundle_dir = index_path.parent

            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
            index_payload["filters"].append(
                {
                    "filter_id": "index_only",
                    "display_name": "Index Only",
                    "flut_file": "index_only.flut",
                }
            )
            index_path.write_text(json.dumps(index_payload), encoding="utf-8")
            (bundle_dir / "index_only.flut").write_bytes(b"ok")

            manifest_path = bundle_dir / "manifest.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["filters"][0]["display_name"] = "Manifest Name"
            manifest_payload["filters"][0]["flut_file"] = "manifest_name.flut"
            manifest_payload["filters"].append(
                {
                    "filter_id": "manifest_only",
                    "display_name": "Manifest Only",
                    "source_cube": "ManifestOnly.cube",
                    "flut_file": "manifest_only.flut",
                    "reason": "Only in manifest.",
                }
            )
            manifest_payload["scene_filters"] = {"general": ["demo_filter", "ghost_filter"]}
            manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

            report = doctor_catalog_bundle(index_path=index_path, catalog="demo")
            codes = {item["code"] for item in report["issues"]}

            self.assertIn("manifest_missing_filter", codes)
            self.assertIn("index_missing_filter", codes)
            self.assertIn("manifest_index_display_name_mismatch", codes)
            self.assertIn("manifest_index_flut_file_mismatch", codes)
            self.assertIn("scene_filter_unknown_filter_id", codes)
            self.assertGreaterEqual(report["summary"]["manifest_index_mismatch_count"], 4)

    def test_doctor_detects_invalid_runtime_key_base64(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="demo_filter",
                display_name="Demo Filter",
                catalog="demo",
                include_manifest=True,
            )
            (index_path.parent / "runtime.key.b64").write_text("not base64 !!", encoding="utf-8")

            report = doctor_catalog_bundle(index_path=index_path, catalog="demo")
            invalid_key_issues = [item for item in report["issues"] if item["code"] == "runtime_key_invalid_base64"]

            self.assertEqual(1, len(invalid_key_issues))
            self.assertEqual("error", invalid_key_issues[0]["severity"])
            self.assertFalse(report["ok"])

    def test_doctor_fails_when_base_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, index_path = make_runtime_bundle(
                tmp_path,
                filter_id="demo_filter",
                display_name="Demo Filter",
                catalog="demo",
                include_manifest=True,
            )
            (index_path.parent / "demo_filter.flut").unlink()

            report = doctor_catalog_bundle(index_path=index_path, catalog="demo")

            self.assertFalse(report["ok"])
            self.assertFalse(report["validation"]["ok"])
            rendered = format_doctor_report(report)
            self.assertIn("validation_errors=", rendered)
            self.assertIn("Missing FLUT file", rendered)
