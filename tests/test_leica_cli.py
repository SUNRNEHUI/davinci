"""CLI entrypoint integration tests."""

import base64
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from tests.helpers_runtime_bundle import make_runtime_bundle


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


class TestLeicaCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.default_output_root = self.tmpdir / "davinci_output"
        self.env_patch = patch.dict(
            os.environ,
            {
                "LEICA_CLI_HOME": str(self.tmpdir / "cli_home"),
                "DAVINCI_OUTPUT_ROOT": str(self.default_output_root),
            },
        )
        self.env_patch.start()
        self.input_path = self.tmpdir / "input.png"
        self.output_dir = self.tmpdir / "output"
        Image.fromarray(
            np.full((48, 64, 3), [70, 120, 180], dtype=np.uint8),
            mode="RGB",
        ).save(self.input_path)

        self.key, self.index_path = self._make_runtime_bundle()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.tmpdir_obj.cleanup()

    def _make_runtime_bundle(self) -> tuple[bytes, Path]:
        from flut_codec import build_metadata, pack_flut_bytes

        cube = (
            b'TITLE "Invert2"\n'
            b"LUT_3D_SIZE 2\n"
            b"1.0 1.0 1.0\n"
            b"0.0 1.0 1.0\n"
            b"1.0 0.0 1.0\n"
            b"0.0 0.0 1.0\n"
            b"1.0 1.0 0.0\n"
            b"0.0 1.0 0.0\n"
            b"1.0 0.0 0.0\n"
            b"0.0 0.0 0.0\n"
        )
        key = os.urandom(32)
        metadata = build_metadata(
            payload=cube,
            skill_id="leica.skill.test",
            skill_version="1.0.0",
            filter_id="leica_leica_classic",
            display_name="Leica Classic",
            lut_domain="rec709",
            created_at="2026-03-28T00:00:00Z",
        )

        bundle_dir = self.tmpdir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        flut_path = bundle_dir / "classic.flut"
        flut_path.write_bytes(pack_flut_bytes(cube_payload=cube, key=key, metadata=metadata))
        (bundle_dir / "runtime.key.b64").write_text(
            base64.b64encode(key).decode("ascii"),
            encoding="utf-8",
        )

        index_path = bundle_dir / "index.json"
        index_path.write_text(
            json.dumps(
                {
                    "filters": [
                        {
                            "filter_id": "leica_leica_classic",
                            "display_name": "Leica Classic",
                            "flut_file": "classic.flut",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return key, index_path

    def _make_multi_filter_bundle(self, *, catalog: str) -> Path:
        _, index_path = make_runtime_bundle(
            self.tmpdir / f"{catalog}_bundle",
            filter_id=f"{catalog}_classic",
            display_name="Classic",
            catalog=catalog,
            include_manifest=True,
        )
        bundle_dir = index_path.parent
        second_flut = bundle_dir / f"{catalog}_favorite.flut"
        second_flut.write_bytes((bundle_dir / f"{catalog}_classic.flut").read_bytes())
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        index_payload["filters"].append(
            {
                "filter_id": f"{catalog}_favorite",
                "display_name": "Favorite",
                "flut_file": second_flut.name,
            }
        )
        index_path.write_text(json.dumps(index_payload), encoding="utf-8")
        manifest_path = bundle_dir / "manifest.json"
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_payload["filters"].append(
            {
                "filter_id": f"{catalog}_favorite",
                "display_name": "Favorite",
                "source_cube": "Favorite.cube",
                "flut_file": second_flut.name,
                "reason": "Favorite look.",
            }
        )
        manifest_payload["scene_filters"] = {
            "general": [f"{catalog}_classic", f"{catalog}_favorite"],
        }
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
        return index_path

    def _make_three_filter_bundle(self, *, catalog: str) -> Path:
        index_path = self._make_multi_filter_bundle(catalog=catalog)
        bundle_dir = index_path.parent
        third_flut = bundle_dir / f"{catalog}_mono.flut"
        third_flut.write_bytes((bundle_dir / f"{catalog}_classic.flut").read_bytes())

        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        index_payload["filters"].append(
            {
                "filter_id": f"{catalog}_mono",
                "display_name": "Mono",
                "flut_file": third_flut.name,
            }
        )
        index_path.write_text(json.dumps(index_payload), encoding="utf-8")

        manifest_path = bundle_dir / "manifest.json"
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_payload["filters"].append(
            {
                "filter_id": f"{catalog}_mono",
                "display_name": "Mono",
                "source_cube": "Mono.cube",
                "flut_file": third_flut.name,
                "reason": "Mono demo look.",
            }
        )
        manifest_payload["scene_filters"] = {
            "general": [f"{catalog}_classic", f"{catalog}_favorite", f"{catalog}_mono"],
            "portrait": [f"{catalog}_classic", f"{catalog}_favorite"],
            "street": [f"{catalog}_mono", f"{catalog}_favorite"],
            "landscape": [f"{catalog}_classic", f"{catalog}_favorite"],
        }
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
        return index_path

    def _make_index_only_bundle(self, *, catalog: str) -> Path:
        bundle_dir = self.tmpdir / f"{catalog}_index_only"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        index_path = bundle_dir / "index.json"
        index_path.write_text(
            json.dumps(
                {
                    "filters": [
                        {
                            "filter_id": f"{catalog}_classic",
                            "display_name": "Classic",
                            "flut_file": "classic.flut",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return index_path

    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                rc = leica_cli.main(argv)
            except SystemExit as exc:
                rc = int(exc.code) if isinstance(exc.code, int) else 0
        return rc, stdout.getvalue(), stderr.getvalue()

    def test_list_filters_json(self) -> None:
        rc, stdout, stderr = self._run_cli(
            ["list-filters", "--index", str(self.index_path), "--json"]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["filters"][0]["display_name"], "Leica Classic")
        self.assertEqual("", stderr)

    def test_list_filters_custom_manifest_catalog_is_inferred(self) -> None:
        index_path = self._make_multi_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(["list-filters", "--index", str(index_path), "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "demo")
        self.assertTrue(all(item["catalog"] == "demo" for item in payload["filters"]))
        self.assertEqual("", stderr)

    def test_list_filters_index_only_catalog_is_inferred_from_filter_prefix(self) -> None:
        index_path = self._make_index_only_bundle(catalog="kodak")

        rc, stdout, stderr = self._run_cli(["list-filters", "--index", str(index_path), "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "kodak")
        self.assertEqual("", stderr)

    def test_list_catalogs_json(self) -> None:
        rc, stdout, stderr = self._run_cli(["list-catalogs", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["command"], "list-catalogs")
        self.assertTrue(any(item["catalog"] == "leica" for item in payload["catalogs"]))
        self.assertTrue(any(item["catalog"] == "fuji" for item in payload["catalogs"]))
        self.assertEqual("", stderr)

    def test_help_command_outputs_beginner_copy(self) -> None:
        rc, stdout, stderr = self._run_cli(["help"])
        self.assertEqual(rc, 0)
        self.assertIn("DAVINCI 快速上手", stdout)
        self.assertIn("帮我调色", stdout)
        self.assertIn(str(self.default_output_root), stdout)
        self.assertIn("内置风格系列", stdout)
        self.assertIn("Leica", stdout)
        self.assertEqual("", stderr)

    def test_home_command_shows_demo_first_entry(self) -> None:
        rc, stdout, stderr = self._run_cli(["home"])
        self.assertEqual(rc, 0)
        self.assertIn("DAVINCI", stdout)
        self.assertIn("欢迎使用达芬奇调色台", stdout)
        self.assertIn("1. 先看 Leica 风格", stdout)
        self.assertIn("2. 先看 Fuji 风格", stdout)
        self.assertIn("3. 我不确定，直接帮我推荐", stdout)
        self.assertIn("拖入照片或输入文件路径开始", stdout)
        self.assertIn("直接回车：先看演示", stdout)
        self.assertIn("原图不会被覆盖", stdout)
        self.assertEqual("", stderr)

    def test_no_args_defaults_to_home(self) -> None:
        rc, stdout, stderr = self._run_cli([])
        self.assertEqual(rc, 0)
        self.assertIn("DAVINCI", stdout)
        self.assertIn("1. 先看 Leica 风格", stdout)
        self.assertEqual("", stderr)

    def test_home_interactive_enter_defaults_to_demo(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", return_value=""),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["home"])
        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("欢迎使用达芬奇调色台", text)
        self.assertIn("[ACTIVATE]", text)
        self.assertLess(text.index("欢迎使用达芬奇调色台"), text.index("[ACTIVATE]"))
        self.assertIn("USE YOUR OWN PHOTO NEXT", text)
        self.assertEqual("", stderr.getvalue())

    def test_home_without_history_hides_continue_action(self) -> None:
        rc, stdout, stderr = self._run_cli(["home"])
        self.assertEqual(rc, 0)
        self.assertNotIn("其他：continue 继续上一次", stdout)
        self.assertEqual("", stderr)

    def test_home_with_history_shows_continue_action(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--catalog",
                "fuji",
                "--theme",
                "minimal",
                "--command",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        rc, stdout, stderr = self._run_cli(["home"])
        self.assertEqual(rc, 0)
        self.assertIn("其他：continue 继续上一次", stdout)
        self.assertEqual("", stderr)

    def test_home_accepts_photo_path_then_feel_prompt(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", side_effect=[str(self.input_path), "", "2", "", "1", "exit"]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["home"])
        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("LEICA FILTERS", text)
        self.assertIn("已为你选中", text)
        self.assertEqual("", stderr.getvalue())

    def test_home_brand_choice_leica_opens_full_family_overview(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", side_effect=["1", "", str(self.input_path), "", "4", "exit"]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["home"])
        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("LEICA FILTERS", text)
        self.assertIn("已为你选中", text)
        self.assertEqual("", stderr.getvalue())

    def test_home_accepts_watch_leica_and_opens_full_family_overview(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", side_effect=["看莱卡", "", str(self.input_path), "", "1", "exit"]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["home"])
        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("LEICA FILTERS", text)
        self.assertIn("输入编号直接保存当前滤镜", text)
        self.assertIn("已为你选中", text)
        self.assertEqual("", stderr.getvalue())

    def test_home_leica_flow_can_switch_to_fuji_overview(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", side_effect=["1", "", str(self.input_path), "", "看富士", "1", "exit"]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["home"])
        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("LEICA FILTERS", text)
        self.assertIn("FUJI FILTERS", text)
        self.assertIn("已为你选中", text)
        self.assertEqual("", stderr.getvalue())

    def test_home_leica_flow_plain_fuji_command_switches_to_fuji_overview(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", side_effect=["1", "", str(self.input_path), "", "富士", "1", "exit"]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["home"])
        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("LEICA FILTERS", text)
        self.assertIn("FUJI FILTERS", text)
        self.assertNotIn("REFINED DIRECTIONS", text)
        self.assertIn("已为你选中", text)
        self.assertEqual("", stderr.getvalue())

    def test_activate_command_marks_cli_as_activated(self) -> None:
        import leica_cli

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("leica_cli._can_prompt", return_value=True),
            patch("leica_cli._open_activation_url", return_value=(True, None)),
            patch("builtins.input", return_value=""),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = leica_cli.main(["activate"])
        self.assertEqual(rc, 0)
        self.assertIn("激活完成", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_top_level_help_mentions_home_and_demo(self) -> None:
        rc, stdout, stderr = self._run_cli(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("First run:", stdout)
        self.assertIn("davinci demo", stdout)
        self.assertIn("davinci start", stdout)
        self.assertEqual("", stderr)

    def test_start_without_input_prompts_for_path(self) -> None:
        with patch("builtins.input", return_value=str(self.input_path)):
            rc, stdout, stderr = self._run_cli(
                [
                    "start",
                    "--theme",
                    "minimal",
                    "--command",
                    "exit",
                    "--no-open",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("THREE DIRECTIONS", stdout)
        self.assertEqual("", stderr)

    def test_start_without_input_can_redirect_to_demo(self) -> None:
        with patch("builtins.input", return_value="demo"):
            rc, stdout, stderr = self._run_cli(
                [
                    "start",
                    "--theme",
                    "minimal",
                    "--command",
                    "exit",
                    "--no-open",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("input_demo", stdout)
        self.assertEqual("", stderr)

    def test_brands_json_lists_beginner_family_summaries(self) -> None:
        rc, stdout, stderr = self._run_cli(["brands", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["command"], "brands")
        self.assertTrue(any(item["catalog"] == "leica" for item in payload["families"]))
        self.assertTrue(any(item["catalog"] == "fuji" for item in payload["families"]))
        self.assertTrue(all("best_for" in item for item in payload["families"]))
        self.assertIn("davinci start", payload["next_steps"])
        self.assertEqual("", stderr)

    def test_brands_text_explains_how_to_choose(self) -> None:
        rc, stdout, stderr = self._run_cli(["brands"])
        self.assertEqual(rc, 0)
        self.assertIn("适合你在这种时候选", stdout)
        self.assertIn("你可以直接说", stdout)
        self.assertIn("davinci start", stdout)
        self.assertEqual("", stderr)

    def test_home_json_does_not_expose_legacy_state_path(self) -> None:
        rc, stdout, stderr = self._run_cli(["home", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["command"], "home")
        self.assertNotIn("state_home", payload)
        self.assertTrue(all("best_for" in item for item in payload["families"]))
        self.assertEqual("", stderr)

    def test_list_filters_fuji_catalog_json(self) -> None:
        rc, stdout, stderr = self._run_cli(["list-filters", "--catalog", "fuji", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "fuji")
        self.assertGreaterEqual(payload["count"], 10)
        self.assertTrue(any(item["filter_id"] == "fuji_provia" for item in payload["filters"]))
        self.assertEqual("", stderr)

    def test_recommend_json_returns_ranked_entries(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "recommend",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--top-k",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["command"], "recommend")
        self.assertEqual(len(payload["recommendations"]), 1)
        self.assertEqual(payload["recommendations"][0]["rank"], 1)
        self.assertEqual("", stderr)

    def test_recommend_fuji_catalog_returns_fuji_ids(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "recommend",
                "--input",
                str(self.input_path),
                "--catalog",
                "fuji",
                "--top-k",
                "2",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "fuji")
        self.assertTrue(all(item["filter_id"].startswith("fuji_") for item in payload["recommendations"]))
        self.assertEqual("", stderr)

    def test_recommend_applies_favorite_boost_before_top_k_cut(self) -> None:
        index_path = self._make_multi_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "favorites",
                "add",
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--filter",
                "Favorite",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(
            [
                "recommend",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--full-preview",
                "--top-k",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual("demo_favorite", payload["recommendations"][0]["filter_id"])
        self.assertTrue(payload["recommendations"][0]["favorite_boost"])
        self.assertEqual("", stderr)

    def test_analyze_custom_catalog_prefers_general_scene_filters_over_leica_defaults(self) -> None:
        index_path = self._make_multi_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "analyze",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(all(filter_id.startswith("demo_") for filter_id in payload["recommended_filters"]))
        self.assertEqual("", stderr)

    def test_render_accepts_numeric_filter_selection(self) -> None:
        target = self.output_dir / "classic.png"
        rc, stdout, stderr = self._run_cli(
            [
                "render",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--filter",
                "1",
                "--output",
                str(target),
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(target.exists())
        self.assertEqual(payload["filter"]["position"], 1)
        self.assertEqual(payload["filter"]["display_name"], "Leica Classic")
        self.assertEqual("", stderr)

    def test_auto_json_creates_contact_sheet_and_final_output(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "auto",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--output-dir",
                str(self.output_dir),
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertTrue(Path(payload["final_output_path"]).exists())
        self.assertEqual(payload["mode"], "top1")
        self.assertEqual("", stderr)

    def test_auto_select_filter_json_applies_requested_filter(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "auto",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--output-dir",
                str(self.output_dir),
                "--mode",
                "preview",
                "--select-filter",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["selected_filter"]["position"], 1)
        self.assertTrue(Path(payload["final_output_path"]).exists())
        self.assertEqual("", stderr)

    def test_studio_json_creates_outputs(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "studio",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--output-dir",
                str(self.output_dir),
                "--pace-ms",
                "0",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["experience"], "studio")
        self.assertEqual(payload["command"], "studio")
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertTrue(Path(payload["final_output_path"]).exists())
        self.assertEqual("", stderr)

    def test_start_json_returns_beginner_options_and_outputs(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--theme",
                "minimal",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["command"], "start")
        self.assertGreaterEqual(len(payload["options"]), 3)
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertTrue(Path(payload["hero_output_path"]).exists())
        self.assertTrue(Path(payload["compare_output_path"]).exists())
        self.assertEqual("", stderr)

    def test_demo_json_runs_with_bundled_image(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "demo",
                "--theme",
                "minimal",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["command"], "demo")
        self.assertTrue(Path(payload["demo_image"]).exists())
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertTrue(Path(payload["hero_output_path"]).exists())
        self.assertEqual(
            Path(payload["output_dir"]).resolve().relative_to(self.default_output_root.resolve()).parts[0],
            "_demo",
        )
        self.assertIn("davinci start", payload["next_steps"])
        self.assertIn("davinci brands", payload["next_steps"])
        self.assertEqual("", stderr)

    def test_start_pick_uses_picker_result(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")
        with patch("leica_cli._pick_image_path", return_value=str(self.input_path)):
            rc, stdout, stderr = self._run_cli(
                [
                    "start",
                    "--pick",
                    "--index",
                    str(index_path),
                    "--catalog",
                    "demo",
                    "--theme",
                    "minimal",
                    "--json",
                ]
            )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["input_path"], str(self.input_path.resolve()))
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertEqual("", stderr)

    def test_start_without_output_dir_uses_davinci_output_root(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--theme",
                "minimal",
                "--json",
            ]
        )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(str(payload["output_dir"]).startswith(str(self.default_output_root.resolve())))
        self.assertEqual(self.input_path.stem, Path(payload["output_dir"]).name)
        self.assertEqual("", stderr)

    def test_start_scripted_selection_writes_final_output(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--theme",
                "minimal",
                "--command",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertIsNotNone(payload["selected_option"])
        self.assertTrue(Path(payload["final_output_path"]).exists())
        self.assertEqual("", stderr)

    def test_start_refine_warm_updates_options_and_outputs(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--catalog",
                "fuji",
                "--output-dir",
                str(self.output_dir / "warm"),
                "--theme",
                "minimal",
                "--command",
                "更暖",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["events"][-1]["event"], "refine")
        self.assertEqual(payload["events"][-1]["payload"]["prompt"], "更暖")
        self.assertIn("start_sheet_02", Path(payload["contact_sheet_path"]).name)
        self.assertIn("_hero_02_", Path(payload["hero_output_path"]).name)
        self.assertIn("_compare_02_", Path(payload["compare_output_path"]).name)
        self.assertTrue(Path(payload["contact_sheet_path"]).exists())
        self.assertTrue(Path(payload["hero_output_path"]).exists())
        self.assertTrue(Path(payload["compare_output_path"]).exists())
        self.assertTrue(any("warm" in (option.get("intent_tags") or []) for option in payload["options"]))
        self.assertEqual("", stderr)

    def test_start_refresh_avoids_repeating_same_three_filters(self) -> None:
        base_args = [
            "start",
            "--input",
            str(self.input_path),
            "--catalog",
            "fuji",
            "--theme",
            "minimal",
            "--json",
        ]
        rc, stdout, stderr = self._run_cli(base_args + ["--output-dir", str(self.output_dir / "refresh_initial")])
        self.assertEqual(rc, 0)
        initial_payload = json.loads(stdout)
        initial_ids = {item["filter_id"] for item in initial_payload["options"]}

        rc, stdout, stderr = self._run_cli(
            base_args
            + [
                "--output-dir",
                str(self.output_dir / "refresh_next"),
                "--command",
                "换一个",
            ]
        )
        self.assertEqual(rc, 0)
        refreshed_payload = json.loads(stdout)
        refreshed_ids = {item["filter_id"] for item in refreshed_payload["options"]}
        self.assertEqual(refreshed_payload["events"][-1]["event"], "refresh")
        self.assertNotEqual(initial_ids, refreshed_ids)
        self.assertLess(len(initial_ids & refreshed_ids), len(initial_ids))
        self.assertTrue(Path(refreshed_payload["contact_sheet_path"]).exists())
        self.assertEqual("", stderr)

    def test_start_switches_to_other_family_when_requested(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--output-dir",
                str(self.output_dir / "family_initial"),
                "--theme",
                "minimal",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        initial_payload = json.loads(stdout)
        initial_family = initial_payload["options"][0]["catalog"]

        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--output-dir",
                str(self.output_dir / "family_other"),
                "--theme",
                "minimal",
                "--command",
                "看其他系列",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        switched_payload = json.loads(stdout)
        self.assertEqual(switched_payload["events"][-1]["event"], "refresh")
        requested_family = switched_payload["events"][-1]["payload"]["requested_family"]
        self.assertIsNotNone(requested_family)
        self.assertEqual(switched_payload["options"][0]["catalog"], requested_family)
        self.assertNotEqual(initial_family, switched_payload["options"][0]["catalog"])
        self.assertEqual("", stderr)

    def test_start_selecting_nonhero_option_renders_distinct_final_output(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--output-dir",
                str(self.output_dir / "select_second"),
                "--theme",
                "minimal",
                "--command",
                "2",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["selected_option"]["position"], 2)
        self.assertTrue(Path(payload["final_output_path"]).exists())
        self.assertTrue(Path(payload["final_compare_path"]).exists())
        self.assertNotEqual(payload["final_output_path"], payload["hero_output_path"])
        self.assertEqual("", stderr)

    def test_start_selection_appends_history_entry(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")

        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--output-dir",
                str(self.output_dir / "history"),
                "--theme",
                "minimal",
                "--command",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(["history", "list", "--json"])
        self.assertEqual(rc, 0)
        history = json.loads(stdout)
        latest = history["events"][0]
        self.assertEqual(latest["command"], "start")
        self.assertEqual(latest["filter_id"], payload["selected_option"]["filter_id"])
        self.assertEqual(latest["output_path"], payload["final_output_path"])
        self.assertEqual("", stderr)

    def test_continue_returns_current_session_summary(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "session",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--catalog",
                "leica",
                "--command",
                "status",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        session_payload = json.loads(stdout)
        session_id = session_payload["session_id"]

        rc, stdout, stderr = self._run_cli(["continue", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["resume_type"], "session")
        self.assertEqual(payload["session"]["session_id"], session_id)
        self.assertEqual("", stderr)

    def test_continue_falls_back_to_history_when_no_session_exists(self) -> None:
        index_path = self._make_three_filter_bundle(catalog="demo")
        rc, stdout, stderr = self._run_cli(
            [
                "start",
                "--input",
                str(self.input_path),
                "--index",
                str(index_path),
                "--catalog",
                "demo",
                "--output-dir",
                str(self.output_dir / "continue_history"),
                "--theme",
                "minimal",
                "--command",
                "1",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        start_payload = json.loads(stdout)

        cli_home = Path(os.environ["LEICA_CLI_HOME"])
        current_session = cli_home / "current_session"
        if current_session.exists():
            current_session.unlink()

        rc, stdout, stderr = self._run_cli(["continue", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["resume_type"], "history")
        self.assertEqual(payload["history"]["output_path"], start_payload["final_output_path"])
        self.assertIn("davinci continue --open", payload["next_steps"])
        self.assertEqual("", stderr)

    def test_continue_without_session_or_existing_result_fails_with_product_hint(self) -> None:
        rc, stdout, stderr = self._run_cli(["continue"])
        self.assertEqual(rc, 0)
        self.assertIn("现在还没有可继续的内容", stdout)
        self.assertIn("davinci", stdout)
        self.assertIn("davinci demo", stdout)
        self.assertIn("davinci start", stdout)
        self.assertEqual("", stderr)

    def test_studio_choose_prompts_and_renders(self) -> None:
        with patch("builtins.input", return_value="1"):
            rc, stdout, stderr = self._run_cli(
                [
                    "studio",
                    "--input",
                    str(self.input_path),
                    "--index",
                    str(self.index_path),
                    "--output-dir",
                    str(self.output_dir),
                    "--choose",
                    "--pace-ms",
                    "0",
                    "--no-color",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("CHOOSER", stdout)
        self.assertIn("SELECTION LOCK", stdout)
        self.assertEqual("", stderr)

    def test_studio_text_contains_blackroom_panels(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "studio",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--output-dir",
                str(self.output_dir),
                "--pace-ms",
                "0",
                "--no-color",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertIn("Catalog:", stdout)
        self.assertIn("DAVINCI", stdout)
        self.assertIn("FILTER RANK", stdout)
        self.assertIn("OUTPUT", stdout)
        self.assertEqual("", stderr)

    def test_studio_cipher_theme_changes_console_title(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "studio",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--output-dir",
                str(self.output_dir),
                "--theme",
                "cipher",
                "--pace-ms",
                "0",
                "--no-color",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertIn("CIPHER CONSOLE", stdout)
        self.assertEqual("", stderr)

    def test_catalog_doctor_json_reports_findings(self) -> None:
        bundle_dir = self.index_path.parent
        manifest_path = bundle_dir / "manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()

        rc, stdout, stderr = self._run_cli(
            [
                "catalog",
                "doctor",
                "--index",
                str(self.index_path),
                "--catalog",
                "leica",
                "--strict",
                "--json",
            ]
        )
        self.assertEqual(rc, 2)
        payload = json.loads(stdout)
        self.assertEqual(payload["catalog"], "leica")
        self.assertGreater(payload["summary"]["issue_count"], 0)
        self.assertEqual("", stderr)

    def test_catalog_doctor_returns_failure_when_validation_fails(self) -> None:
        bundle_dir = self.index_path.parent
        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "catalog": "leica",
                    "display_name": "Leica",
                    "skill_id": "leica.skill.test",
                    "skill_version": "1.0.0",
                    "filters": [
                        {
                            "filter_id": "leica_leica_classic",
                            "display_name": "Leica Classic",
                            "source_cube": "Classic.cube",
                            "flut_file": "classic.flut",
                            "reason": "Test reason.",
                        }
                    ],
                    "scene_filters": {"general": ["leica_leica_classic"]},
                }
            ),
            encoding="utf-8",
        )
        (bundle_dir / "classic.flut").unlink()

        rc, stdout, stderr = self._run_cli(
            [
                "catalog",
                "doctor",
                "--index",
                str(self.index_path),
                "--catalog",
                "leica",
                "--json",
            ]
        )

        self.assertEqual(rc, 2)
        payload = json.loads(stdout)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["validation"]["ok"])
        self.assertEqual("", stderr)

    def test_workspace_and_sessions_commands_follow_current_workspace(self) -> None:
        rc, stdout, stderr = self._run_cli(["workspace", "switch", "campaign-a", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["current_workspace"], "campaign-a")
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(
            [
                "session",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--catalog",
                "leica",
                "--command",
                "status",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        session_payload = json.loads(stdout)
        session_id = session_payload["session_id"]
        self.assertEqual(session_payload["workspace"], "campaign-a")
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(["sessions", "list", "--json"])
        self.assertEqual(rc, 0)
        listing = json.loads(stdout)
        self.assertEqual(listing["workspace"], "campaign-a")
        self.assertEqual(listing["sessions"][0]["session_id"], session_id)
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(["sessions", "close", "--session-id", session_id, "--json"])
        self.assertEqual(rc, 0)
        closed = json.loads(stdout)
        self.assertEqual(closed["session"]["session_id"], session_id)
        self.assertIsNotNone(closed["session"]["closed_at"])
        self.assertEqual("", stderr)

    def test_cache_list_and_clear_json(self) -> None:
        rc, stdout, stderr = self._run_cli(
            [
                "auto",
                "--input",
                str(self.input_path),
                "--index",
                str(self.index_path),
                "--output-dir",
                str(self.output_dir),
                "--json",
            ]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertIn("cache", payload)
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(["cache", "list", "--json"])
        self.assertEqual(rc, 0)
        cache_payload = json.loads(stdout)
        self.assertGreaterEqual(cache_payload["count"], 1)
        self.assertEqual("", stderr)

        rc, stdout, stderr = self._run_cli(["cache", "clear", "--json"])
        self.assertEqual(rc, 0)
        cleared = json.loads(stdout)
        self.assertTrue(cleared["cleared"])
        self.assertEqual("", stderr)
