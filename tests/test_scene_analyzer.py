"""Scene analyzer tests."""
import unittest
import json
import sys
from pathlib import Path
import tempfile
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


class TestSceneAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()

    def _make_image(self, mode: str = "warm", size: tuple = (200, 150)) -> Path:
        """Generate test image. warm=warm tones, cool=cool tones, bw=black&white"""
        p = Path(self.tmpdir) / f"test_{mode}.jpg"
        if mode == "warm":
            arr = np.zeros((*size, 3), dtype=np.uint8)
            arr[..., 0] = np.random.randint(150, 255, size)
            arr[..., 1] = np.random.randint(80, 160, size)
            arr[..., 2] = np.random.randint(20, 80, size)
        elif mode == "cool":
            arr = np.zeros((*size, 3), dtype=np.uint8)
            arr[..., 0] = np.random.randint(20, 80, size)
            arr[..., 1] = np.random.randint(80, 160, size)
            arr[..., 2] = np.random.randint(150, 255, size)
        elif mode == "bw":
            v = np.random.randint(0, 255, size)
            arr = np.stack([v, v, v], axis=-1).astype(np.uint8)
        else:
            arr = np.random.randint(0, 255, (*size, 3), dtype=np.uint8)

        Image.fromarray(arr, mode="RGB").save(p)
        return p

    def _make_synthetic_scene(self, scene: str) -> Path:
        """Generate deterministic synthetic scene for heuristic checks."""
        p = Path(self.tmpdir) / f"synthetic_{scene}.png"

        if scene == "portrait":
            height, width = 360, 240
            arr = np.zeros((height, width, 3), dtype=np.uint8)

            # Cool neutral background
            for y in range(height):
                t = y / max(height - 1, 1)
                arr[y, :, 0] = int(58 + 18 * t)
                arr[y, :, 1] = int(74 + 20 * t)
                arr[y, :, 2] = int(96 + 24 * t)

            yy, xx = np.ogrid[:height, :width]
            cx, cy = width // 2, height // 2

            # Face ellipse in center
            face = ((xx - cx) / (width * 0.21)) ** 2 + ((yy - cy) / (height * 0.30)) ** 2 <= 1.0
            arr[face] = np.array([214, 168, 138], dtype=np.uint8)

            # Hair and shoulder regions to create portrait-like structure
            hair = ((xx - cx) / (width * 0.16)) ** 2 + ((yy - int(cy - height * 0.19)) / (height * 0.10)) ** 2 <= 1.0
            arr[hair] = np.array([68, 50, 40], dtype=np.uint8)
            arr[int(height * 0.64): int(height * 0.88), int(width * 0.28): int(width * 0.72)] = np.array(
                [98, 75, 66],
                dtype=np.uint8,
            )
        elif scene == "landscape":
            height, width = 200, 360
            arr = np.zeros((height, width, 3), dtype=np.uint8)
            horizon = int(height * 0.55)

            # Sky gradient
            for y in range(horizon):
                t = y / max(horizon - 1, 1)
                arr[y, :, 0] = int(70 + 35 * t)
                arr[y, :, 1] = int(130 + 45 * t)
                arr[y, :, 2] = int(210 + 35 * t)

            # Ground gradient
            for y in range(horizon, height):
                t = (y - horizon) / max(height - horizon - 1, 1)
                arr[y, :, 0] = int(42 + 70 * t)
                arr[y, :, 1] = int(118 + 42 * t)
                arr[y, :, 2] = int(60 + 24 * t)

            # Dark ridge introduces edge texture near horizon
            x = np.arange(width)
            ridge = (horizon - 16 - (12 * np.sin(x / 23.0))).astype(int)
            for xi, y0 in enumerate(ridge):
                y_start = max(0, y0)
                arr[y_start:horizon, xi] = np.array([48, 72, 58], dtype=np.uint8)
        else:
            raise ValueError(f"Unknown synthetic scene: {scene}")

        Image.fromarray(arr, mode="RGB").save(p)
        return p


    def test_analyze_returns_scene(self):
        """Analysis result should include 'scene' field."""
        from scene_analyzer import analyze_scene

        img_path = self._make_image("warm")
        result = analyze_scene(img_path)
        self.assertIn("scene", result)
        self.assertIn(result["scene"], {"portrait", "landscape", "street", "general"})

    def test_analyze_returns_recommendations(self):
        """Analysis result should include recommended filter_ids."""
        from scene_analyzer import analyze_scene

        img_path = self._make_image("cool")
        result = analyze_scene(img_path)
        self.assertIn("recommended_filters", result)
        self.assertIsInstance(result["recommended_filters"], list)
        self.assertGreaterEqual(len(result["recommended_filters"]), 3)

    def test_analyze_returns_confidence(self):
        """Analysis result should include confidence."""
        from scene_analyzer import analyze_scene

        img_path = self._make_image("bw")
        result = analyze_scene(img_path)
        self.assertIn("confidence", result)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_analyze_returns_color_stats(self):
        """Analysis result should include color statistics."""
        from scene_analyzer import analyze_scene

        img_path = self._make_image("warm")
        result = analyze_scene(img_path)
        self.assertIn("color_stats", result)
        stats = result["color_stats"]
        self.assertIn("warm_ratio", stats)
        self.assertIn("cool_ratio", stats)
        self.assertIn("saturation_avg", stats)

    def test_portrait_leaning_synthetic_case(self):
        """Center skin-heavy synthetic image should lean portrait."""
        from scene_analyzer import analyze_scene

        img_path = self._make_synthetic_scene("portrait")
        result = analyze_scene(img_path)
        stats = result["color_stats"]

        self.assertEqual(result["scene"], "portrait")
        self.assertGreaterEqual(stats.get("center_subject_weight", 0.0), 0.3)
        self.assertGreaterEqual(stats.get("center_skin_ratio", 0.0), 0.12)

    def test_landscape_leaning_synthetic_case(self):
        """Wide blue/green synthetic image should lean landscape."""
        from scene_analyzer import analyze_scene

        img_path = self._make_synthetic_scene("landscape")
        result = analyze_scene(img_path)
        stats = result["color_stats"]

        self.assertEqual(result["scene"], "landscape")
        self.assertGreaterEqual(stats.get("nature_ratio", 0.0), 0.5)
        self.assertLessEqual(stats.get("skin_tone_ratio", 1.0), 0.05)

    def test_extreme_aspect_ratio_image_does_not_crash(self):
        from scene_analyzer import analyze_scene

        img_path = self._make_image("warm", size=(1000, 1))
        result = analyze_scene(img_path)

        self.assertIn(result["scene"], {"portrait", "landscape", "street", "general"})

    def test_recommended_filter_ids_exist_in_index(self):
        """All scene recommendation IDs must exist in the shipped index."""
        from leica_catalog import scene_filters_for_catalog

        index_path = Path(__file__).resolve().parents[1] / "flut" / "leica" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        available_ids = {item["filter_id"] for item in index["filters"]}
        scene_filters = scene_filters_for_catalog("leica")

        for scene, filter_ids in scene_filters.items():
            for filter_id in filter_ids:
                self.assertIn(filter_id, available_ids, f"{scene} references missing filter {filter_id}")

    def test_fuji_recommended_filter_ids_exist_in_index(self):
        """Fuji scene recommendations must resolve to the shipped Fuji catalog."""
        from leica_catalog import scene_filters_for_catalog

        index_path = Path(__file__).resolve().parents[1] / "flut" / "fuji" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        available_ids = {item["filter_id"] for item in index["filters"]}
        scene_filters = scene_filters_for_catalog("fuji")

        for scene, filter_ids in scene_filters.items():
            for filter_id in filter_ids:
                self.assertIn(filter_id, available_ids, f"{scene} references missing Fuji filter {filter_id}")

if __name__ == "__main__":
    unittest.main()
