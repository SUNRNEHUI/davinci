"""Installer script smoke tests."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestInstallScripts(unittest.TestCase):
    def test_install_sh_is_macos_only_with_source_and_binary_modes(self) -> None:
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("python3 or python is required for macOS source installation", text)
        self.assertIn("pipx install --force", text)
        self.assertIn("DAVINCI_RELEASE_URL", text)
        self.assertIn("Binary installer currently supports macOS Apple Silicon only", text)
        self.assertIn("install.sh currently supports macOS only", text)


if __name__ == "__main__":
    unittest.main()
