"""ASCII Camera atmosphere engine tests."""
import unittest
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


class TestAsciiCamera(unittest.TestCase):

    def test_camera_top_view_is_multiline(self):
        """Camera top view should return multi-line ASCII string."""
        from ascii_camera import camera_top_view

        result = camera_top_view()
        self.assertIn("\n", result)
        self.assertGreater(len(result), 100)

    def test_metering_animation_frames(self):
        """Metering animation should return at least 2 frames."""
        from ascii_camera import metering_frames

        frames = metering_frames()
        self.assertGreaterEqual(len(frames), 2)
        for frame in frames:
            self.assertIsInstance(frame, str)

    def test_shutter_animation_frames(self):
        """Shutter animation should return at least 2 frames."""
        from ascii_camera import shutter_frames

        frames = shutter_frames()
        self.assertGreaterEqual(len(frames), 2)

    def test_developing_animation_frames(self):
        """Developing animation should return at least 2 frames."""
        from ascii_camera import developing_frames

        frames = developing_frames()
        self.assertGreaterEqual(len(frames), 2)

    def test_filter_dial_returns_filter_name(self):
        """Dial display should contain the filter name."""
        from ascii_camera import filter_dial

        result = filter_dial("Leica Classic", 3, 15)
        self.assertIn("Classic", result)

    def test_progress_bar_contains_percent_and_stage(self):
        """Progress bar should expose both percent and stage label."""
        from ascii_camera import progress_bar

        result = progress_bar("ANALYZE", 55)
        self.assertIn("55%", result)
        self.assertIn("ANALYZE", result)

    def test_all_ascii_is_printable(self):
        """All output should contain only printable chars + newlines."""
        from ascii_camera import camera_top_view, filter_dial, progress_bar

        for func, args in [
            (camera_top_view, ()),
            (filter_dial, ("Leica Classic", 3, 15)),
            (progress_bar, ("LOAD", 15)),
        ]:
            text = func(*args)
            for ch in text:
                self.assertTrue(
                    ch.isprintable() or ch == "\n",
                    f"Non-printable char in {func.__name__}: {repr(ch)}",
                )


if __name__ == "__main__":
    unittest.main()
