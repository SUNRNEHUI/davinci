"""Pipeline integration tests."""
import unittest
import sys
from pathlib import Path
import tempfile
import json
import os
import io
import base64
from contextlib import redirect_stdout, redirect_stderr
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


class TestLeicaPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.test_img = Path(cls.tmpdir) / "input.jpg"
        img = Image.fromarray(
            np.random.randint(50, 200, (300, 400, 3), dtype=np.uint8), mode="RGB"
        )
        img.save(cls.test_img)

        # Mock filter index (no real .flut decryption needed)
        cls.index_path = Path(cls.tmpdir) / "index.json"
        filters = [
            {
                "filter_id": "leica_leica_classic",
                "display_name": "Leica Classic",
                "flut_file": "mock.flut",
            },
            {
                "filter_id": "leica_leica_bw_hc",
                "display_name": "Leica BW HC",
                "flut_file": "mock.flut",
            },
            {
                "filter_id": "leica_leica_vivid",
                "display_name": "Leica VIVID",
                "flut_file": "mock.flut",
            },
        ]
        cls.index_path.write_text(json.dumps({"filters": filters}))

    def _make_invert_flut_and_index(self) -> tuple[bytes, Path, Path]:
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
        flut_blob = pack_flut_bytes(cube_payload=cube, key=key, metadata=metadata)

        flut_dir = Path(self.tmpdir) / "flut_case"
        flut_dir.mkdir(parents=True, exist_ok=True)
        flut_file = flut_dir / "invert2.flut"
        flut_file.write_bytes(flut_blob)

        index_path = flut_dir / "index.json"
        index_path.write_text(
            json.dumps(
                {
                    "filters": [
                        {
                            "filter_id": "leica_leica_classic",
                            "display_name": "Leica Classic",
                            "flut_file": "invert2.flut",
                        }
                    ]
                }
            )
        )
        return key, flut_file, index_path

    def _write_runtime_key(self, directory: Path, key: bytes) -> Path:
        key_path = directory / "runtime.key.b64"
        key_path.write_text(
            base64.b64encode(key).decode("ascii"),
            encoding="utf-8",
        )
        return key_path

    def test_pipeline_returns_ascii_output(self):
        """Pipeline should return ASCII string (atmosphere layer)."""
        from leica_pipeline import run_pipeline

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=self.index_path,
            skip_flut_apply=True,
        )
        self.assertIn("ascii", result)
        self.assertIn("LEICA", result["ascii"])

    def test_pipeline_generates_contact_sheet(self):
        """Pipeline should generate Contact Sheet image."""
        from leica_pipeline import run_pipeline

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=self.index_path,
            skip_flut_apply=True,
        )
        self.assertIn("contact_sheet_path", result)
        self.assertTrue(Path(result["contact_sheet_path"]).exists())

    def test_pipeline_returns_scene_info(self):
        """Pipeline should return scene analysis result."""
        from leica_pipeline import run_pipeline

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=self.index_path,
            skip_flut_apply=True,
        )
        self.assertIn("scene", result)
        self.assertIn(result["scene"]["scene"], {"portrait", "landscape", "street", "general"})

    def test_pipeline_returns_recommended_filters(self):
        """Pipeline should return recommended filter details."""
        from leica_pipeline import run_pipeline

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=self.index_path,
            skip_flut_apply=True,
        )
        self.assertIn("recommended_filters", result)
        self.assertIsInstance(result["recommended_filters"], list)

    def test_pipeline_requires_key_when_not_skipping(self):
        """生产流程下缺少 key 必须失败，避免静默退化到原图。"""
        from leica_pipeline import run_pipeline

        with self.assertRaises(ValueError):
            run_pipeline(
                input_path=self.test_img,
                output_dir=Path(self.tmpdir),
                filter_index_path=self.index_path,
                skip_flut_apply=False,
            )

    def test_pipeline_resolves_relative_flut_paths_and_applies_filter(self):
        """index 里的相对 flut_file 应按 index 目录解析，并真实应用滤镜。"""
        from leica_pipeline import run_pipeline
        from contact_sheet import SHEET_WIDTH, PADDING, CELL_GAP, FRAME_BORDER, COLS

        key, _, real_index_path = self._make_invert_flut_and_index()

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            intensity=1.0,
        )
        sheet_path = Path(result["contact_sheet_path"])
        self.assertTrue(sheet_path.exists())

        with Image.open(sheet_path) as sheet_img:
            sheet = np.asarray(sheet_img.convert("RGB"), dtype=np.int16)
        with Image.open(self.test_img) as src:
            thumb_w = (SHEET_WIDTH - 2 * PADDING - (COLS - 1) * CELL_GAP) // COLS
            thumb_h = int(thumb_w * src.height / max(src.width, 1))
        header_h = 56

        x0 = PADDING + FRAME_BORDER
        y0 = PADDING + header_h + FRAME_BORDER
        x1 = PADDING + (thumb_w + 2 * FRAME_BORDER + CELL_GAP) + FRAME_BORDER
        y1 = y0

        original_cell = sheet[y0:y0 + thumb_h, x0:x0 + thumb_w]
        filtered_cell = sheet[y1:y1 + thumb_h, x1:x1 + thumb_w]
        diff = np.abs(original_cell - filtered_cell)
        self.assertGreater(float(diff.mean()), 1.0)

    def test_pipeline_uses_bundled_runtime_key_when_present(self):
        """index 同目录存在 runtime.key.b64 时，不应再要求手工传 key。"""
        from leica_pipeline import run_pipeline

        key, _, real_index_path = self._make_invert_flut_and_index()
        self._write_runtime_key(real_index_path.parent, key)

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=real_index_path,
            skip_flut_apply=False,
            intensity=1.0,
            auto_apply="top1",
        )
        self.assertTrue(Path(result["contact_sheet_path"]).exists())
        self.assertTrue(Path(result["final_output_path"]).exists())

    def test_pipeline_reuses_render_cache_for_contact_sheet_and_final_output(self):
        """相同输入重复执行时，应复用缓存而不是再次渲染。"""
        from leica_pipeline import run_pipeline
        from leica_render_cache import clear_render_cache

        clear_render_cache()
        key, _, real_index_path = self._make_invert_flut_and_index()
        first_output = Path(self.tmpdir) / "cache_first"
        second_output = Path(self.tmpdir) / "cache_second"

        first = run_pipeline(
            input_path=self.test_img,
            output_dir=first_output,
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            intensity=1.0,
            auto_apply="top1",
        )
        self.assertFalse(first["cache"]["contact_sheet_hit"])
        self.assertFalse(first["cache"]["final_render_hit"])

        with patch("leica_pipeline.generate_contact_sheet", side_effect=AssertionError("contact sheet should be cached")):
            with patch("leica_pipeline.apply_flut_to_image", side_effect=AssertionError("final render should be cached")):
                second = run_pipeline(
                    input_path=self.test_img,
                    output_dir=second_output,
                    filter_index_path=real_index_path,
                    key=key,
                    skip_flut_apply=False,
                    intensity=1.0,
                    auto_apply="top1",
                )

        self.assertTrue(second["cache"]["contact_sheet_hit"])
        self.assertTrue(second["cache"]["final_render_hit"])
        self.assertTrue(Path(second["contact_sheet_path"]).exists())
        self.assertTrue(Path(second["final_output_path"]).exists())

    def test_pipeline_cache_invalidates_when_display_name_changes(self):
        """Contact sheet 标签变化后不应误命中旧缓存。"""
        from leica_pipeline import run_pipeline
        from leica_render_cache import clear_render_cache

        clear_render_cache()
        key, _, real_index_path = self._make_invert_flut_and_index()

        first = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir) / "name_cache_a",
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            intensity=1.0,
        )
        self.assertFalse(first["cache"]["contact_sheet_hit"])

        payload = json.loads(real_index_path.read_text(encoding="utf-8"))
        payload["filters"][0]["display_name"] = "Renamed Classic"
        real_index_path.write_text(json.dumps(payload), encoding="utf-8")

        second = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir) / "name_cache_b",
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            intensity=1.0,
        )
        self.assertFalse(second["cache"]["contact_sheet_hit"])

    def test_pipeline_cache_invalidates_when_manifest_display_name_changes_in_process(self):
        """同一进程内修改 manifest 标签后也不应继续命中旧 contact sheet 缓存。"""
        from leica_pipeline import run_pipeline
        from leica_render_cache import clear_render_cache

        clear_render_cache()
        _, index_path = make_runtime_bundle(
            Path(self.tmpdir) / "manifest_cache_case",
            filter_id="demo_classic",
            display_name="Demo Classic",
            catalog="demo",
            include_manifest=True,
        )

        first = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir) / "manifest_cache_a",
            filter_index_path=index_path,
            catalog="demo",
            skip_flut_apply=False,
            auto_apply="none",
        )
        self.assertFalse(first["cache"]["contact_sheet_hit"])

        manifest_path = index_path.parent / "manifest.json"
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_payload["filters"][0]["display_name"] = "Manifest Rename"
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

        second = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir) / "manifest_cache_b",
            filter_index_path=index_path,
            catalog="demo",
            skip_flut_apply=False,
            auto_apply="none",
        )
        self.assertFalse(second["cache"]["contact_sheet_hit"])

    def test_pipeline_final_output_without_suffix_uses_input_suffix(self):
        """无后缀 final_output 应自动补齐图片后缀。"""
        from leica_pipeline import run_pipeline

        key, _, real_index_path = self._make_invert_flut_and_index()
        target = Path(self.tmpdir) / "suffix_case" / "rendered"

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir) / "suffix_case",
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            intensity=1.0,
            auto_apply="top1",
            final_output=str(target),
        )

        self.assertTrue(result["final_output_path"].endswith(".jpg"))
        self.assertTrue(Path(result["final_output_path"]).exists())

    def test_pipeline_accepts_relative_index_path_in_real_apply_mode(self):
        """真实 apply 模式下，相对 index 路径也应可用。"""
        from leica_pipeline import run_pipeline

        key, _, real_index_path = self._make_invert_flut_and_index()
        relative_index_path = os.path.relpath(real_index_path, Path.cwd())

        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=relative_index_path,
            key=key,
            skip_flut_apply=False,
            intensity=1.0,
        )
        self.assertTrue(Path(result["contact_sheet_path"]).exists())

    def test_pipeline_stage_callback_is_monotonic(self):
        """阶段进度应单调递增，且包含核心阶段。"""
        from leica_pipeline import run_pipeline

        key, _, real_index_path = self._make_invert_flut_and_index()
        events: list[tuple[str, int]] = []

        def capture(stage: str, percent: int, payload: dict | None) -> None:
            del payload
            events.append((stage, percent))

        run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            auto_apply="top1",
            stage_callback=capture,
        )

        percents = [percent for _, percent in events]
        self.assertEqual(percents, sorted(percents))
        stages = [stage for stage, _ in events]
        for stage in ("LOAD", "ANALYZE_SCENE", "RECOMMEND", "DONE"):
            self.assertIn(stage, stages)

    def test_pipeline_auto_apply_top1_creates_final_output(self):
        """启用 top1 自动应用时，应输出最终图片。"""
        from leica_pipeline import run_pipeline

        key, _, real_index_path = self._make_invert_flut_and_index()
        result = run_pipeline(
            input_path=self.test_img,
            output_dir=Path(self.tmpdir),
            filter_index_path=real_index_path,
            key=key,
            skip_flut_apply=False,
            auto_apply="top1",
            intensity=1.0,
        )
        self.assertIsNotNone(result["final_output_path"])
        self.assertTrue(Path(result["final_output_path"]).exists())

    def test_main_reports_auto_open_failure_without_crashing(self):
        """auto-open 失败时应打印 fallback 路径并返回成功。"""
        import leica_pipeline

        output_dir = Path(self.tmpdir) / "main_auto_open"
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = [
            "leica_pipeline.py",
            "--input",
            str(self.test_img),
            "--output-dir",
            str(output_dir),
            "--index",
            str(self.index_path),
            "--skip-flut-apply",
            "--auto-open",
        ]

        with patch.object(leica_pipeline, "open_result", return_value=(False, "no gui")):
            with patch("sys.argv", argv):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    rc = leica_pipeline.main()

        self.assertEqual(rc, 0)
        self.assertIn("[OPEN-FAILED]", stdout.getvalue())
        self.assertIn("contact_sheet_", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
