"""Beginner product flow tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from scripts.leica_beginner import BeginnerStartFlow
from scripts.leica_product_store import ProductStore
from tests.helpers_runtime_bundle import make_runtime_bundle


class TestLeicaBeginner(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.input_path = self.tmpdir / "input.png"
        Image.fromarray(
            np.full((48, 64, 3), [70, 120, 180], dtype=np.uint8),
            mode="RGB",
        ).save(self.input_path)
        self.store = ProductStore(self.tmpdir / "cli_home")

    def tearDown(self) -> None:
        self.tmpdir_obj.cleanup()

    def _make_three_filter_bundle(self, *, catalog: str, filter_ids: list[str]) -> Path:
        _, index_path = make_runtime_bundle(
            self.tmpdir / f"{catalog}_bundle",
            filter_id=filter_ids[0],
            display_name=filter_ids[0].replace("_", " ").title(),
            catalog=catalog,
            include_manifest=True,
        )
        bundle_dir = index_path.parent
        base_flut = bundle_dir / f"{filter_ids[0]}.flut"

        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        manifest_path = bundle_dir / "manifest.json"
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        for filter_id in filter_ids[1:]:
            flut_path = bundle_dir / f"{filter_id}.flut"
            flut_path.write_bytes(base_flut.read_bytes())
            index_payload["filters"].append(
                {
                    "filter_id": filter_id,
                    "display_name": filter_id.replace("_", " ").title(),
                    "flut_file": flut_path.name,
                }
            )
            manifest_payload["filters"].append(
                {
                    "filter_id": filter_id,
                    "display_name": filter_id.replace("_", " ").title(),
                    "source_cube": f"{filter_id}.cube",
                    "flut_file": flut_path.name,
                    "reason": f"{filter_id} demo look.",
                }
            )

        manifest_payload["scene_filters"] = {
            "general": filter_ids,
            "portrait": filter_ids,
            "street": filter_ids,
            "landscape": filter_ids,
        }
        index_path.write_text(json.dumps(index_payload), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
        return index_path

    def _make_flow(
        self,
        *,
        sources: list[tuple[str, Path]],
        prompt: str = "帮我调色",
        auto_open: bool = False,
    ) -> tuple[BeginnerStartFlow, io.StringIO]:
        stream = io.StringIO()
        flow = BeginnerStartFlow(
            store=self.store,
            input_path=self.input_path,
            output_dir=self.tmpdir / "output",
            sources=sources,
            prompt=prompt,
            intensity=0.85,
            algorithm="tetrahedral",
            theme="minimal",
            stream=stream,
            input_fn=lambda _: "exit",
            auto_open=auto_open,
            use_color=False,
            pace_ms=0,
        )
        return flow, stream

    def test_start_creates_contact_sheet_and_before_after_preview(self) -> None:
        index_path = self._make_three_filter_bundle(
            catalog="demo",
            filter_ids=["demo_classic", "demo_film", "demo_mono"],
        )
        flow, _ = self._make_flow(sources=[("demo", index_path)])

        summary = flow.start()

        self.assertTrue(Path(summary["contact_sheet_path"]).exists())
        self.assertTrue(Path(summary["hero_output_path"]).exists())
        self.assertTrue(Path(summary["compare_output_path"]).exists())

    def test_family_switch_scopes_next_round_to_other_catalog(self) -> None:
        demo_index = self._make_three_filter_bundle(
            catalog="demo",
            filter_ids=["demo_classic", "demo_film", "demo_mono"],
        )
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, _ = self._make_flow(sources=[("demo", demo_index), ("fuji", fuji_index)])

        summary = flow.run_commands(["看其他系列"])

        self.assertEqual(summary["events"][-1]["event"], "refresh")
        requested_family = summary["events"][-1]["payload"]["requested_family"]
        self.assertIsNotNone(requested_family)
        self.assertTrue(all(option["catalog"] == requested_family for option in summary["options"]))

    def test_beginner_surface_hides_technical_name_and_writes_final_compare(self) -> None:
        index_path = self._make_three_filter_bundle(
            catalog="demo",
            filter_ids=["demo_classic", "demo_warm", "demo_mono"],
        )
        flow, stream = self._make_flow(sources=[("demo", index_path)], prompt="更暖")

        summary = flow.run_commands(["1"])

        self.assertNotIn("技术名", stream.getvalue())
        self.assertIn("https://sensear.softsugar.com/", stream.getvalue())
        self.assertTrue(Path(summary["final_output_path"]).exists())
        self.assertTrue(Path(summary["final_compare_path"]).exists())

    def test_family_overview_lists_all_filters_and_accepts_number_selection(self) -> None:
        demo_index = self._make_three_filter_bundle(
            catalog="demo",
            filter_ids=["demo_classic", "demo_film", "demo_mono"],
        )
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, stream = self._make_flow(sources=[("demo", demo_index), ("fuji", fuji_index)])

        summary = flow.run_commands(["看富士", "2"])

        text = stream.getvalue()
        self.assertIn("FUJI FILTERS", text)
        self.assertIn("Fuji Velvia", text)
        self.assertTrue(all(option["catalog"] == "fuji" for option in summary["options"]))
        self.assertEqual(summary["selected_option"]["catalog"], "fuji")
        self.assertTrue(Path(summary["final_output_path"]).exists())

    def test_family_overview_zero_returns_to_three_directions(self) -> None:
        demo_index = self._make_three_filter_bundle(
            catalog="demo",
            filter_ids=["demo_classic", "demo_film", "demo_mono"],
        )
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, stream = self._make_flow(sources=[("demo", demo_index), ("fuji", fuji_index)])

        summary = flow.run_commands(["看富士", "0"])

        text = stream.getvalue()
        self.assertIn("FUJI FILTERS", text)
        self.assertIn("THREE DIRECTIONS", text)
        self.assertEqual(summary["events"][-1]["event"], "browse_exit")

    def test_family_overview_can_switch_to_other_family_with_natural_phrase(self) -> None:
        leica_index = self._make_three_filter_bundle(
            catalog="leica",
            filter_ids=["leica_classic", "leica_film", "leica_mono"],
        )
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, stream = self._make_flow(sources=[("leica", leica_index), ("fuji", fuji_index)], prompt="看莱卡")

        summary = flow.run_commands(["我想看看富士滤镜"])

        text = stream.getvalue()
        self.assertIn("LEICA FILTERS", text)
        self.assertIn("FUJI FILTERS", text)
        self.assertTrue(all(option["catalog"] == "fuji" for option in summary["options"]))

    def test_plain_family_name_enters_catalog_overview(self) -> None:
        leica_index = self._make_three_filter_bundle(
            catalog="leica",
            filter_ids=["leica_classic", "leica_film", "leica_mono"],
        )
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, stream = self._make_flow(sources=[("leica", leica_index), ("fuji", fuji_index)])

        summary = flow.run_commands(["富士"])

        text = stream.getvalue()
        self.assertIn("FUJI FILTERS", text)
        self.assertNotIn("REFINED DIRECTIONS", text)
        self.assertTrue(all(option["catalog"] == "fuji" for option in summary["options"]))

    def test_family_overview_auto_open_browser_can_select_and_save(self) -> None:
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, stream = self._make_flow(sources=[("fuji", fuji_index)], prompt="看富士", auto_open=True)

        with (
            patch.object(BeginnerStartFlow, "_can_use_catalog_browser", return_value=True),
            patch("scripts.leica_beginner.browse_filter_previews", return_value=(1, None)) as browser_mock,
            patch("scripts.leica_beginner.open_result", return_value=(True, None)) as open_mock,
        ):
            summary = flow.start()

        browser_mock.assert_called_once()
        open_mock.assert_called_once_with(Path(summary["final_output_path"]))
        self.assertIn("SAVING LOOK", stream.getvalue())
        self.assertIn("正在生成：", stream.getvalue())
        self.assertEqual(summary["selected_option"]["catalog"], "fuji")
        self.assertEqual(summary["selected_option"]["position"], 2)
        self.assertTrue(Path(summary["final_output_path"]).exists())

    def test_family_overview_browser_failure_falls_back_to_contact_sheet(self) -> None:
        fuji_index = self._make_three_filter_bundle(
            catalog="fuji",
            filter_ids=["fuji_provia", "fuji_velvia", "fuji_eterna"],
        )
        flow, _ = self._make_flow(sources=[("fuji", fuji_index)], prompt="看富士", auto_open=True)

        with (
            patch.object(BeginnerStartFlow, "_can_use_catalog_browser", return_value=True),
            patch("scripts.leica_beginner.browse_filter_previews", return_value=(None, "tk unavailable")),
            patch("scripts.leica_beginner.open_result", return_value=(True, None)) as open_mock,
        ):
            summary = flow.start()

        self.assertIsNone(summary["selected_option"])
        open_mock.assert_called_once()
        self.assertEqual(summary["open_events"][0]["path"], "interactive-filter-browser")
        self.assertEqual(summary["open_events"][1]["path"], summary["contact_sheet_path"])
