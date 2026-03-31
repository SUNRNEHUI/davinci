"""Single-image keyboard browser for DAVINCI filter previews."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import tkinter as tk
    from PIL import ImageTk
except Exception:  # pragma: no cover - optional GUI dependency
    tk = None
    ImageTk = None

try:
    from .contact_sheet import _apply_filter_to_thumbnail, _resolve_contact_sheet_key
except ImportError:  # pragma: no cover - script execution fallback
    from contact_sheet import _apply_filter_to_thumbnail, _resolve_contact_sheet_key


BG = "#111111"
FG = "#f4f4f4"
MUTED = "#9a9a9a"
ACCENT = "#d61e1e"


def browse_filter_previews(
    *,
    input_path: Path | str,
    options: list[dict[str, Any]],
    intensity: float,
    title: str,
    start_index: int = 0,
) -> tuple[int | None, str | None]:
    """Open a local browser window and return the selected option index."""
    if tk is None or ImageTk is None:
        return None, "tkinter unavailable"
    if not options:
        return None, "no options available"

    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        browser = _FilterBrowserWindow(
            root=root,
            input_path=Path(input_path).expanduser().resolve(),
            options=options,
            intensity=float(intensity),
            title=title,
            start_index=start_index,
        )
        root.mainloop()
        try:
            root.update_idletasks()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
        return browser.selected_index, None
    except Exception as exc:  # pragma: no cover - GUI runtime branch
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        return None, str(exc)


class _FilterBrowserWindow:
    def __init__(
        self,
        *,
        root: tk.Tk,
        input_path: Path,
        options: list[dict[str, Any]],
        intensity: float,
        title: str,
        start_index: int,
    ) -> None:
        self.root = root
        self.input_path = input_path
        self.options = options
        self.intensity = intensity
        self.title = title
        self.index = min(max(start_index, 0), len(options) - 1)
        self.selected_index: int | None = None
        self._photo_cache: dict[int, tuple[ImageTk.PhotoImage, str | None]] = {}
        self._rendering_indices: set[int] = set()
        self._closed = False

        self.root.configure(bg=BG)
        self.root.title(title)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        screen_w = max(int(self.root.winfo_screenwidth()), 1024)
        screen_h = max(int(self.root.winfo_screenheight()), 768)
        self.max_preview_size = (
            max(min(screen_w - 140, 1480), 720),
            max(min(screen_h - 260, 980), 480),
        )

        source = Image.open(self.input_path).convert("RGB")
        preview = source.copy()
        preview.thumbnail(self.max_preview_size, Image.LANCZOS)
        self.base_preview = preview
        self.base_rgb = np.asarray(preview, dtype=np.uint8)
        self.base_photo = ImageTk.PhotoImage(image=self.base_preview)

        self.meta_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.help_var = tk.StringVar(value="← → / ↑ ↓ 切换   Enter 保存   Esc 关闭")

        frame = tk.Frame(self.root, bg=BG, padx=20, pady=18)
        frame.pack(fill="both", expand=True)

        self.image_label = tk.Label(
            frame,
            bg=BG,
            bd=1,
            highlightthickness=1,
            highlightbackground="#2e2e2e",
        )
        self.image_label.pack(fill="both", expand=True)

        meta_label = tk.Label(
            frame,
            textvariable=self.meta_var,
            bg=BG,
            fg=FG,
            anchor="w",
            justify="left",
            font=("Helvetica", 17, "bold"),
            pady=10,
        )
        meta_label.pack(fill="x")

        detail_label = tk.Label(
            frame,
            textvariable=self.detail_var,
            bg=BG,
            fg=MUTED,
            anchor="w",
            justify="left",
            font=("Helvetica", 12),
        )
        detail_label.pack(fill="x")

        help_label = tk.Label(
            frame,
            textvariable=self.help_var,
            bg=BG,
            fg=ACCENT,
            anchor="w",
            justify="left",
            font=("Helvetica", 12),
            pady=6,
        )
        help_label.pack(fill="x")

        self.root.bind("<Left>", lambda _: self._step(-1))
        self.root.bind("<Up>", lambda _: self._step(-1))
        self.root.bind("<Right>", lambda _: self._step(1))
        self.root.bind("<Down>", lambda _: self._step(1))
        self.root.bind("<Home>", lambda _: self._jump(0))
        self.root.bind("<End>", lambda _: self._jump(len(self.options) - 1))
        self.root.bind("<Return>", lambda _: self._select())
        self.root.bind("<Escape>", lambda _: self._close())
        self.root.bind("q", lambda _: self._close())
        self.root.bind("Q", lambda _: self._close())

        window_w = max(self.base_preview.width + 40, 860)
        window_h = max(self.base_preview.height + 150, 680)
        self.root.geometry(f"{window_w}x{window_h}")
        self.root.minsize(720, 560)
        self.image_label.focus_set()
        self.root.after(0, self._refresh)

    def _step(self, delta: int) -> None:
        if not self.options:
            return
        self.index = (self.index + delta) % len(self.options)
        self._refresh()

    def _jump(self, idx: int) -> None:
        self.index = min(max(idx, 0), len(self.options) - 1)
        self._refresh()

    def _select(self) -> None:
        self.selected_index = self.index
        self.help_var.set("正在生成成片，请稍候...")
        try:
            self.root.withdraw()
            self.root.update()
        except Exception:
            pass
        try:
            self.root.after_idle(self._close)
        except Exception:
            self._close()

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.root.quit()
        except Exception:
            pass

    def _refresh(self) -> None:
        option = self.options[self.index]
        technical_name = str(option.get("technical_name") or option.get("display_name") or option.get("plain_name"))
        family_name = str(option.get("family_name") or option.get("catalog") or "DAVINCI")
        photo, error = self._photo_cache.get(self.index, (self.base_photo, None))
        self.image_label.configure(image=photo)
        self.image_label.image = photo
        self.meta_var.set(f"{self.index + 1:02d}/{len(self.options):02d}  {option['plain_name']}")
        if self.index not in self._photo_cache:
            self.detail_var.set(f"{family_name}  |  {technical_name}  |  正在生成预览...")
            self._request_render(self.index)
        elif error:
            self.detail_var.set(f"{family_name}  |  {technical_name}  |  预览失败：{error}")
        else:
            self.detail_var.set(f"{family_name}  |  {technical_name}")
        self.root.title(f"{self.title}  {self.index + 1:02d}/{len(self.options):02d}  {option['plain_name']}")

    def _request_render(self, idx: int) -> None:
        if idx in self._photo_cache or idx in self._rendering_indices or self._closed:
            return
        self._rendering_indices.add(idx)
        worker = threading.Thread(target=self._render_in_background, args=(idx,), daemon=True)
        worker.start()

    def _render_in_background(self, idx: int) -> None:
        option = self.options[idx]
        try:
            image = self._render_option_preview(option)
            error = None
        except Exception as exc:  # pragma: no cover - depends on local GUI/runtime
            image = self.base_preview
            error = str(exc)
        try:
            self.root.after(0, lambda: self._finish_render(idx, image, error))
        except Exception:
            self._rendering_indices.discard(idx)

    def _finish_render(self, idx: int, image: Image.Image, error: str | None) -> None:
        self._rendering_indices.discard(idx)
        if self._closed:
            return
        photo = ImageTk.PhotoImage(image=image)
        payload = (photo, error)
        self._photo_cache[idx] = payload
        if idx == self.index:
            self._refresh()

    def _render_option_preview(self, option: dict[str, Any]) -> Image.Image:
        flut_path = Path(str(option["flut_file"])).expanduser().resolve()
        key_file = str(Path(str(option["_index_path"])).parent / "runtime.key.b64")
        preview_arr = _apply_filter_to_thumbnail(
            self.base_rgb,
            flut_path,
            _resolve_contact_sheet_key(
                filter_entry={"key_file": key_file},
                flut_path=flut_path,
                shared_key=None,
                shared_key_file=key_file,
            ),
            intensity=self.intensity,
        )
        return Image.fromarray(preview_arr, mode="RGB")
