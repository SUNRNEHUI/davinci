from __future__ import annotations

import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import filter_browser


class _FakeRoot:
    def __init__(self) -> None:
        self.mainloop_called = False
        self.destroy_called = False
        self.quit_called = False
        self.withdraw_called = False
        self.update_called = False
        self.after_idle_called = False
        self.after_called = False

    def mainloop(self) -> None:
        self.mainloop_called = True

    def destroy(self) -> None:
        self.destroy_called = True

    def quit(self) -> None:
        self.quit_called = True

    def withdraw(self) -> None:
        self.withdraw_called = True

    def update_idletasks(self) -> None:
        self.update_called = True

    def update(self) -> None:
        self.update_called = True

    def after_idle(self, callback) -> None:
        self.after_idle_called = True
        callback()

    def after(self, _delay: int, callback) -> None:
        self.after_called = True
        callback()


class _FakeVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class TestFilterBrowser(unittest.TestCase):
    def test_browse_filter_previews_returns_error_when_tk_is_unavailable(self) -> None:
        with patch.object(filter_browser, "tk", None), patch.object(filter_browser, "ImageTk", None):
            selected_index, error = filter_browser.browse_filter_previews(
                input_path="/tmp/input.jpg",
                options=[{"plain_name": "Demo"}],
                intensity=0.85,
                title="DAVINCI",
            )

        self.assertIsNone(selected_index)
        self.assertEqual(error, "tkinter unavailable")

    def test_browse_filter_previews_destroys_root_after_mainloop(self) -> None:
        root = _FakeRoot()

        class FakeBrowser:
            def __init__(self, **_: object) -> None:
                self.selected_index = 2

        fake_tk = types.SimpleNamespace(Tk=lambda: root)
        with (
            patch.object(filter_browser, "tk", fake_tk),
            patch.object(filter_browser, "ImageTk", object()),
            patch.object(filter_browser, "_FilterBrowserWindow", FakeBrowser),
        ):
            selected_index, error = filter_browser.browse_filter_previews(
                input_path=Path("/tmp/input.jpg"),
                options=[{"plain_name": "A"}],
                intensity=0.85,
                title="DAVINCI",
            )

        self.assertIsNone(error)
        self.assertEqual(selected_index, 2)
        self.assertTrue(root.mainloop_called)
        self.assertTrue(root.update_called)
        self.assertTrue(root.destroy_called)

    def test_select_hides_window_before_closing(self) -> None:
        root = _FakeRoot()
        help_var = _FakeVar()
        closed = {"value": False}

        stub = types.SimpleNamespace(
            root=root,
            help_var=help_var,
            index=3,
            selected_index=None,
            _close=lambda: closed.__setitem__("value", True),
        )

        filter_browser._FilterBrowserWindow._select(stub)

        self.assertEqual(stub.selected_index, 3)
        self.assertEqual(help_var.value, "正在生成成片，请稍候...")
        self.assertTrue(root.withdraw_called)
        self.assertTrue(root.update_called)
        self.assertTrue(root.after_idle_called)
        self.assertTrue(closed["value"])

    def test_refresh_shows_placeholder_and_requests_background_render(self) -> None:
        image_label = types.SimpleNamespace(configure=lambda **_: None, image=None)
        meta_var = _FakeVar()
        detail_var = _FakeVar()
        photo = object()
        requested = {"value": None}

        stub = types.SimpleNamespace(
            index=0,
            options=[{"plain_name": "自然经典", "technical_name": "Leica Classic", "family_name": "Leica"}],
            _photo_cache={},
            _rendering_indices=set(),
            _closed=False,
            base_photo=photo,
            image_label=image_label,
            meta_var=meta_var,
            detail_var=detail_var,
            title="DAVINCI Leica",
            root=types.SimpleNamespace(title=lambda _: None),
            _request_render=lambda idx: requested.__setitem__("value", idx),
        )

        filter_browser._FilterBrowserWindow._refresh(stub)

        self.assertEqual(meta_var.value, "01/01  自然经典")
        self.assertIn("正在生成预览", detail_var.value)
        self.assertEqual(requested["value"], 0)
