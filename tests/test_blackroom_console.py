"""Focused tests for blackroom console theme rendering."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path


class TestBlackroomConsoleThemes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.input_path = self.tmpdir / "input.jpg"
        self.index_path = self.tmpdir / "index.json"
        self.output_dir = self.tmpdir / "out"
        self.input_path.write_text("not an image", encoding="utf-8")
        self.index_path.write_text("{}", encoding="utf-8")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_experience(self, *, theme: str | None = None, use_color: bool = False):
        from blackroom_console import StudioConsoleExperience

        stream = io.StringIO()
        kwargs = {}
        if theme is not None:
            kwargs["theme"] = theme
        experience = StudioConsoleExperience(
            prompt="帮我调色",
            input_path=self.input_path,
            index_path=self.index_path,
            output_dir=self.output_dir,
            catalog="leica",
            stream=stream,
            pace_ms=0,
            use_color=use_color,
            **kwargs,
        )
        return experience, stream

    def test_default_theme_keeps_blackroom_output(self) -> None:
        experience, stream = self._make_experience()
        experience.start()
        text = stream.getvalue()
        self.assertEqual(experience.theme, "blackroom")
        self.assertIn("DAVINCI / BLACKROOM CONSOLE", text)
        self.assertIn("DAVINCI", text)
        self.assertIn("BLACKROOM SEQUENCE", text)

    def test_minimal_theme_uses_minimal_header_without_logo(self) -> None:
        experience, stream = self._make_experience(theme="minimal")
        experience.start()
        text = stream.getvalue()
        self.assertEqual(experience.theme, "minimal")
        self.assertIn("DAVINCI / MINIMAL CONSOLE", text)
        self.assertNotIn("______ _", text)
        self.assertIn("Trace", text)

    def test_cipher_theme_changes_frame_and_color_palette(self) -> None:
        from blackroom_console import _box

        rendered = _box("LOAD", ["cipher payload"], theme="cipher")
        self.assertTrue(rendered.startswith("#"))
        self.assertIn(": cipher payload", rendered)

        experience, stream = self._make_experience(theme="cipher", use_color=True)
        experience.start()
        experience.on_stage("LOAD", 10, {})
        text = stream.getvalue()
        self.assertIn("CIPHER STREAM", text)
        self.assertIn("DAVINCI", text)
        self.assertIn("\033[38;5;46m", text)

    def test_unknown_theme_falls_back_to_blackroom(self) -> None:
        experience, stream = self._make_experience(theme="neon")
        experience.start()
        text = stream.getvalue()
        self.assertEqual(experience.theme, "blackroom")
        self.assertIn("DAVINCI / BLACKROOM CONSOLE", text)

    def test_available_themes_contains_required_set(self) -> None:
        from blackroom_console import available_themes

        themes = set(available_themes())
        self.assertTrue({"blackroom", "minimal", "cipher"}.issubset(themes))

    def test_logo_lines_keep_uniform_width_and_clear_in_spacing(self) -> None:
        from blackroom_console import _LOGO_GLYPHS, _logo_lines

        lines = _logo_lines()
        widths = {len(line) for line in lines}
        self.assertEqual(1, len(widths))
        self.assertIn("______", lines[0])
        self.assertIn("|__", "\n".join(lines))
        self.assertEqual("         ", _LOGO_GLYPHS["V"][0])
        self.assertEqual("    V    ", _LOGO_GLYPHS["V"][-1])

    def test_finish_includes_next_moves_guidance(self) -> None:
        experience, stream = self._make_experience()
        experience.finish(
            {
                "recommended_filters": [
                    {"display_name": "Leica Classic"},
                    {"display_name": "Leica Chrome"},
                ],
                "contact_sheet_path": str(self.output_dir / "contact.png"),
                "final_output_path": str(self.output_dir / "final.jpg"),
            }
        )
        text = stream.getvalue()
        self.assertIn("NEXT MOVES", text)
        self.assertIn("Lead Look", text)
        self.assertIn("favorites add", text)


if __name__ == "__main__":
    unittest.main()
