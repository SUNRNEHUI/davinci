"""Contact Sheet generator tests."""
import unittest
import sys
from pathlib import Path
import tempfile
import os
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


class TestContactSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.test_img = Path(cls.tmpdir) / "test_input.jpg"
        img = Image.fromarray(
            np.random.randint(0, 255, (150, 200, 3), dtype=np.uint8), mode="RGB"
        )
        img.save(cls.test_img)

    def _make_invert_flut(self) -> tuple[bytes, Path]:
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
            filter_id="invert2",
            display_name="Invert2",
            lut_domain="rec709",
            created_at="2026-03-28T00:00:00Z",
        )
        flut_blob = pack_flut_bytes(cube_payload=cube, key=key, metadata=metadata)
        flut_path = Path(self.tmpdir) / "invert2.flut"
        flut_path.write_bytes(flut_blob)
        return key, flut_path

    def test_generate_full_sheet_creates_file(self):
        """全景模式：15 个滤镜 + 1 原图，应生成 16 格 Contact Sheet。"""
        from contact_sheet import generate_contact_sheet

        filters = [
            {"filter_id": f"filter_{i}", "display_name": f"Leica {i}"}
            for i in range(15)
        ]
        output = Path(self.tmpdir) / "sheet_full.png"
        result = generate_contact_sheet(
            input_path=self.test_img,
            filters=filters,
            output_path=output,
            include_original=True,
        )
        self.assertTrue(output.exists())
        self.assertIsInstance(result, Path)
        with Image.open(output) as img:
            self.assertEqual(img.mode, "RGB")

    def test_generate_curated_sheet(self):
        """精选模式：4 个滤镜，应生成 4 格 Contact Sheet。"""
        from contact_sheet import generate_contact_sheet

        filters = [
            {"filter_id": "classic", "display_name": "Leica Classic"},
            {"filter_id": "bw_hc", "display_name": "Leica BW HC"},
            {"filter_id": "vivid", "display_name": "Leica VIVID"},
            {"filter_id": "chrome", "display_name": "Leica Chrome"},
        ]
        output = Path(self.tmpdir) / "sheet_curated.png"
        generate_contact_sheet(
            input_path=self.test_img,
            filters=filters,
            output_path=output,
            include_original=False,
        )
        self.assertTrue(output.exists())
        with Image.open(output) as img:
            self.assertEqual(img.mode, "RGB")

    def test_sheet_dimensions_reasonable(self):
        """输出图片尺寸应该合理：宽度不超过 2400px。"""
        from contact_sheet import generate_contact_sheet

        filters = [
            {"filter_id": f"f{i}", "display_name": f"F{i}"} for i in range(15)
        ]
        output = Path(self.tmpdir) / "sheet_dims.png"
        generate_contact_sheet(
            input_path=self.test_img,
            filters=filters,
            output_path=output,
            include_original=True,
        )
        with Image.open(output) as img:
            self.assertLessEqual(img.width, 2400)
            self.assertGreater(img.height, 0)

    def test_empty_filters_with_original(self):
        """无滤镜但有原图时，应只生成原图预览。"""
        from contact_sheet import generate_contact_sheet

        output = Path(self.tmpdir) / "sheet_empty.png"
        generate_contact_sheet(
            input_path=self.test_img,
            filters=[],
            output_path=output,
            include_original=True,
        )
        self.assertTrue(output.exists())

    def test_requires_key_when_flut_filters_present(self):
        """当存在 flut_file 时，缺少 key 必须失败，而不是静默退回原图。"""
        from contact_sheet import generate_contact_sheet

        output = Path(self.tmpdir) / "sheet_requires_key.png"
        with self.assertRaises(ValueError):
            generate_contact_sheet(
                input_path=self.test_img,
                filters=[
                    {
                        "filter_id": "classic",
                        "display_name": "Leica Classic",
                        "flut_file": str(Path(self.tmpdir) / "missing.flut"),
                    }
                ],
                output_path=output,
                include_original=False,
            )

    def test_real_flut_changes_filtered_cell(self):
        """真实 flut 应用后，滤镜格像素应与原图格明显不同。"""
        from contact_sheet import (
            generate_contact_sheet,
            SHEET_WIDTH,
            PADDING,
            CELL_GAP,
            FRAME_BORDER,
            COLS,
        )

        key, flut_path = self._make_invert_flut()
        output = Path(self.tmpdir) / "sheet_real_flut.png"
        generate_contact_sheet(
            input_path=self.test_img,
            filters=[
                {
                    "filter_id": "invert2",
                    "display_name": "Invert2",
                    "flut_file": str(flut_path),
                }
            ],
            output_path=output,
            include_original=True,
            intensity=1.0,
            key=key,
        )

        with Image.open(output) as sheet_img:
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

    def test_generate_before_after_preview_creates_file(self):
        """前后对比图应正常生成，供新手快速决策。"""
        from contact_sheet import generate_before_after_preview

        key, flut_path = self._make_invert_flut()
        rendered = Path(self.tmpdir) / "rendered.png"

        from apply_flut_image import apply_flut_to_image

        apply_flut_to_image(
            flut_path=flut_path,
            input_path=self.test_img,
            output_path=rendered,
            intensity=1.0,
            key=key,
        )

        output = Path(self.tmpdir) / "before_after.png"
        result = generate_before_after_preview(
            input_path=self.test_img,
            rendered_path=rendered,
            output_path=output,
        )

        self.assertEqual(result, output)
        self.assertTrue(output.exists())
        with Image.open(output) as image:
            self.assertEqual(image.mode, "RGB")
            self.assertGreater(image.width, image.height)


if __name__ == "__main__":
    unittest.main()
