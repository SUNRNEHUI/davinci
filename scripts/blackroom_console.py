"""High-drama terminal presentation for DAVINCI console flows."""

from __future__ import annotations

import hashlib
import textwrap
import time
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from .ascii_camera import progress_bar
except ImportError:  # pragma: no cover - script execution fallback
    from ascii_camera import progress_bar


BOX_WIDTH = 78
DEFAULT_THEME = "blackroom"

_THEME_PRESETS: dict[str, dict[str, Any]] = {
    "blackroom": {
        "title": "DAVINCI / BLACKROOM CONSOLE",
        "signal_label": "Signal",
        "show_logo": True,
        "mood": "Analog noir / tungsten hush / gallery relay",
        "hero_lines": [
            "BLACKROOM SEQUENCE :: analyze the photo -> show 3 looks -> open the proof sheet",
            "Stay in the terminal. Decide by eye, not by memorizing filter names.",
        ],
        "boot_note": "Chemistry online. Compare first, lock later.",
        "progress": {"fill": "=", "empty": ".", "head": ">", "label": "Gate"},
        "colors": {
            "green": "\033[38;5;114m",
            "cyan": "\033[38;5;81m",
            "red": "\033[38;5;203m",
        },
    },
    "minimal": {
        "title": "DAVINCI / MINIMAL CONSOLE",
        "signal_label": "Trace",
        "show_logo": False,
        "mood": "Plain console / quiet handoff / zero drama",
        "hero_lines": [],
        "boot_note": "Keep it readable. No extra theater.",
        "progress": {"fill": "#", "empty": "-", "head": ">", "label": "Trace"},
        "colors": {
            "green": "\033[38;5;250m",
            "cyan": "\033[38;5;250m",
            "red": "\033[38;5;250m",
        },
    },
    "cipher": {
        "title": "DAVINCI / CIPHER CONSOLE",
        "signal_label": "Cipher",
        "show_logo": True,
        "mood": "Telemetry grid / covert lab / signal lock",
        "hero_lines": [
            "CIPHER STREAM :: analyze the frame -> branch into 3 visual directions",
            "A darker terminal skin over the same trusted render pipeline.",
        ],
        "boot_note": "Signal discipline enabled. Visual noise suppressed.",
        "progress": {"fill": "1", "empty": "0", "head": ">", "label": "Stream"},
        "colors": {
            "green": "\033[38;5;46m",
            "cyan": "\033[38;5;51m",
            "red": "\033[38;5;82m",
        },
    },
}

_THEME_BOX_STYLES: dict[str, dict[str, str]] = {
    "blackroom": {"top": "=", "bottom": "-", "corner": "+", "side": "|"},
    "minimal": {"top": "-", "bottom": "-", "corner": "+", "side": "|"},
    "cipher": {"top": "~", "bottom": "~", "corner": "#", "side": ":"},
}

_THEME_STAGE_COPY: dict[str, dict[str, str]] = {
    "blackroom": {
        "LOAD": "Preparing runtime, catalog, and proof-sheet targets.",
        "ANALYZE_WARMTH": "Estimating whether the frame wants warmer or cooler color.",
        "ANALYZE_STATS": "Reading contrast, saturation, and exposure balance.",
        "ANALYZE_SCENE": "Deciding whether this behaves like portrait, landscape, or documentary.",
        "RECOMMEND": "Picking directions that look clearly different at first glance.",
        "RENDER_CONTACT_SHEET": "Building contact sheet for fast comparison.",
        "APPLY_TOP1": "Rendering the strongest recommendation automatically.",
        "DONE": "Pipeline settled. Assets are ready.",
        "*": "Processing.",
    },
    "minimal": {
        "LOAD": "Loading runtime assets.",
        "ANALYZE_WARMTH": "Estimating scene warmth.",
        "ANALYZE_STATS": "Sampling core image stats.",
        "ANALYZE_SCENE": "Identifying scene type.",
        "RECOMMEND": "Ranking filters for handoff.",
        "RENDER_CONTACT_SHEET": "Rendering contact sheet.",
        "APPLY_TOP1": "Applying top recommendation.",
        "DONE": "Done.",
        "*": "Running.",
    },
    "cipher": {
        "LOAD": "Initializing matrix channels and index stream.",
        "ANALYZE_WARMTH": "Parsing whether the frame wants a warmer or cooler grade.",
        "ANALYZE_STATS": "Computing contrast, saturation, and tonal signatures.",
        "ANALYZE_SCENE": "Resolving whether the frame reads as portrait, landscape, or documentary.",
        "RECOMMEND": "Selecting 3 directions worth comparing side by side.",
        "RENDER_CONTACT_SHEET": "Materializing proof grid.",
        "APPLY_TOP1": "Committing prime look to output.",
        "DONE": "Signal locked. Render complete.",
        "*": "Streaming.",
    },
}


def available_themes() -> tuple[str, ...]:
    return tuple(_THEME_PRESETS.keys())


def _normalize_theme(theme: str | None) -> str:
    candidate = (theme or DEFAULT_THEME).strip().lower()
    if candidate not in _THEME_PRESETS:
        return DEFAULT_THEME
    return candidate


class StudioConsoleExperience:
    """Render a darker, more cinematic CLI presentation layer."""

    def __init__(
        self,
        *,
        prompt: str,
        input_path: Path | str,
        index_path: Path | str,
        output_dir: Path | str,
        catalog: str,
        stream: Any = None,
        pace_ms: int | None = None,
        use_color: bool | None = None,
        theme: str = DEFAULT_THEME,
        boot_hint: str | None = None,
    ) -> None:
        import sys

        self.prompt = prompt
        self.input_path = Path(input_path).expanduser().resolve()
        self.index_path = Path(index_path).expanduser().resolve()
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.catalog = catalog
        self.stream = stream or sys.stdout
        self.theme = _normalize_theme(theme)
        self._theme_config = _THEME_PRESETS[self.theme]
        self.use_color = self._detect_color_support() if use_color is None else use_color
        self.pace_s = self._resolve_pace_seconds(pace_ms)
        self.boot_hint = boot_hint

    def start(self) -> None:
        # Gradient logo is emitted directly to preserve TrueColor escape codes.
        if self._theme_config["show_logo"] and self.theme == "blackroom" and self.use_color:
            for line in _gradient_logo_lines():
                self._emit(line)
            self._emit()
        header_lines: list[str] = []
        if self._theme_config["show_logo"] and (self.theme != "blackroom" or not self.use_color):
            self._emit()
            header_lines.extend(_logo_lines())
            header_lines.append("GRADE FAST. CHOOSE BY EYE.")
        header_lines.extend(self._theme_config.get("hero_lines", []))
        header_lines.extend(
            [
                self._theme_config["title"],
                f"Mood   : {self._theme_config.get('mood', '-')}",
                "Flow   : analyze -> show options -> open proof -> choose or refine",
                f"Catalog: {self.catalog.upper()}",
                self._binary_signature(),
                f"Prompt : {self.prompt}",
                f"Source : {self.input_path}",
            ]
        )
        meta = _image_meta(self.input_path)
        if meta:
            header_lines.append(f"Image  : {meta}")
        header_lines.append(f"Output : {self.output_dir}")
        header_lines.append(f"Note   : {self._theme_config.get('boot_note', 'Ready.')}")
        header_lines.append(f"Next   : {self.boot_hint or 'Wait for the proof sheet, then choose a look.'}")
        self._emit_box("BOOTSTRAP", header_lines, accent="cyan")
        self._sleep()

    def on_stage(self, stage: str, percent: int, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        self._emit_box(
            stage,
            [
                self._stage_meter(stage, percent),
                self._stage_status(stage, payload),
                _stage_copy(stage, theme=self.theme),
            ],
            accent="green",
        )

        if stage == "LOAD":
            self._emit_box(
                "INGEST",
                [
                    f"Input : {payload.get('input_path', self.input_path)}",
                    f"Index : {payload.get('index_path', self.index_path)}",
                    f"Out   : {payload.get('output_dir', self.output_dir)}",
                ],
            )
        elif stage == "ANALYZE_SCENE":
            stats = payload.get("color_stats", {})
            self._emit_box(
                "SCENE TELEMETRY",
                [
                    f"Scene      : {payload.get('scene', '-')}",
                    f"Confidence : {payload.get('confidence', 0.0):.0%}",
                    (
                        "Warm / Sat / Ctr : "
                        f"{stats.get('warm_ratio', 0.0):.3f} / "
                        f"{stats.get('saturation_avg', 0.0):.3f} / "
                        f"{stats.get('contrast', 0.0):.3f}"
                    ),
                    (
                        "Brightness / Cool : "
                        f"{stats.get('brightness_avg', 0.0):.3f} / "
                        f"{stats.get('cool_ratio', 0.0):.3f}"
                    ),
                ],
                accent="cyan",
            )
        elif stage == "RECOMMEND":
            rows = []
            for idx, item in enumerate(payload.get("recommendations", []), start=1):
                rows.append(f"{idx:02d}. {item['display_name']} :: {item['reason']}")
            self._emit_box("FILTER RANK", rows or ["No recommendation payload"], accent="red")
        elif stage == "RENDER_CONTACT_SHEET":
            self._emit_box(
                "DARKROOM",
                [
                    "Generating proof sheet from curated catalog looks.",
                    f"Cache  : {'hit' if payload.get('cache_hit') else 'miss'}",
                    f"Target : {payload.get('path', '-')}",
                    "Signal : theatrical terminal output, no GUI dependency.",
                ],
            )
        elif stage == "APPLY_TOP1":
            self._emit_box(
                "PRIME LOOK",
                [
                    f"Selection : {payload.get('display_name', '-')}",
                    f"Queue     : 1 / {payload.get('total', 1)}",
                    f"Cache     : {'hit' if payload.get('cache_hit') else 'miss'}",
                    "Render    : locked to top1 recommendation.",
                ],
                accent="red",
            )
        elif stage == "DONE":
            self._emit_box(
                "PIPELINE LOCK",
                [
                    f"Scene      : {payload.get('scene', '-')}",
                    f"Confidence : {payload.get('confidence', 0.0):.0%}",
                    "Status     : render complete",
                ],
                accent="green",
            )

        self._sleep()

    def finish(self, result: dict[str, Any]) -> None:
        names = ", ".join(item["display_name"] for item in result["recommended_filters"])
        lead = result["recommended_filters"][0]["display_name"] if result["recommended_filters"] else "none"
        lines = [
            f"Lead Look     : {lead}",
            f"Contact Sheet : {result['contact_sheet_path']}",
            f"Final Image   : {result.get('final_output_path') or 'preview-only'}",
            f"Recommended   : {names}",
        ]
        self._emit_box("OUTPUT", lines, accent="cyan")
        self._emit_box(
            "NEXT MOVES",
            [
                "Use `session` to compare alternates without rerunning the first analysis.",
                "Use `--choose` when you want manual control after the proof sheet appears.",
                "Use `favorites add` once a look becomes part of your default taste.",
            ],
            accent="green",
        )

    def report_open(self, path: Path, success: bool, error: str | None = None) -> None:
        lines = [f"Path    : {path}", f"Status  : {'opened' if success else 'failed'}"]
        if error:
            lines.append(f"Reason  : {error}")
        self._emit_box("LAUNCH", lines, accent="green" if success else "red")

    def show_selection_prompt(self, filters: list[dict[str, Any]]) -> None:
        rows = ["Select a look by number. Enter defaults to #1. q skips final render."]
        for idx, item in enumerate(filters, start=1):
            rows.append(f"{idx:02d}. {item['display_name']} :: {item['reason']}")
        self._emit_box("CHOOSER", rows, accent="red")

    def report_selection(self, selection: dict[str, Any]) -> None:
        rows = [
            f"Selection : #{selection['position']} {selection['display_name']}",
            f"Filter ID : {selection['filter_id']}",
            f"Output    : {selection['output_path']}",
        ]
        reason = selection.get("reason")
        if reason:
            rows.append(f"Reason    : {reason}")
        self._emit_box("SELECTION LOCK", rows, accent="green")

    def show_panel(self, title: str, lines: list[str], *, accent: str = "green") -> None:
        self._emit_box(title, lines, accent=accent)

    def _emit_box(self, title: str, lines: list[str], accent: str = "green") -> None:
        text = _box(title, lines, theme=self.theme)
        self._emit(self._colorize(text, accent))

    def _emit(self, text: str = "") -> None:
        print(text, file=self.stream, flush=True)

    def _colorize(self, text: str, accent: str) -> str:
        if not self.use_color:
            return text
        colors = self._theme_config["colors"]
        reset = "\033[0m"
        return f"{colors.get(accent, colors['green'])}{text}{reset}"

    def _binary_signature(self) -> str:
        seed = f"{self.prompt}|{self.input_path.name}|{self.index_path.name}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
        bits = "".join(f"{int(ch, 16):04b}" for ch in digest)
        label = self._theme_config["signal_label"]
        return f"{label:<6}: " + " ".join(bits[idx:idx + 8] for idx in range(0, len(bits), 8))

    def _stage_meter(self, stage: str, percent: int) -> str:
        clamped = max(0, min(100, int(percent)))
        config = self._theme_config.get("progress", {})
        width = 30
        fill = str(config.get("fill", "#"))[:1]
        empty = str(config.get("empty", "-"))[:1]
        head = str(config.get("head", ">"))[:1]
        label = str(config.get("label", "Stage"))
        filled = int((clamped / 100.0) * width)
        if clamped <= 0:
            bar = empty * width
        elif clamped >= 100:
            bar = fill * width
        else:
            body = fill * max(filled - 1, 0)
            remainder = width - len(body) - 1
            bar = body + head + (empty * max(remainder, 0))
        return f"  [{bar}] {clamped:3d}%  {stage:<20s} {label}"

    def _stage_status(self, stage: str, payload: dict[str, Any]) -> str:
        scene = str(payload.get("scene", "-"))
        confidence = float(payload.get("confidence", 0.0))
        if stage == "LOAD":
            return "Status : input, style library, and output path are ready"
        if stage == "ANALYZE_WARMTH":
            return "Status : checking whether warmer or cooler grading fits this frame"
        if stage == "ANALYZE_STATS":
            return "Status : measuring contrast, saturation, and brightness balance"
        if stage == "ANALYZE_SCENE":
            return f"Status : reading this frame as {scene} with {confidence:.0%} confidence"
        if stage == "RECOMMEND":
            count = len(payload.get("recommendations", []))
            return f"Status : picked {count} look{'s' if count != 1 else ''} worth comparing"
        if stage == "RENDER_CONTACT_SHEET":
            return f"Status : proof sheet {'loaded from cache' if payload.get('cache_hit') else 'rendering now'}"
        if stage == "APPLY_TOP1":
            return f"Status : rendering the strongest first-pass look {'from cache' if payload.get('cache_hit') else 'now'}"
        if stage == "DONE":
            return "Status : outputs are ready to review"
        return f"Status : {progress_bar(stage, payload.get('percent', 0), width=16).strip()}"

    def _detect_color_support(self) -> bool:
        is_tty = getattr(self.stream, "isatty", lambda: False)()
        return bool(is_tty)

    def _resolve_pace_seconds(self, pace_ms: int | None) -> float:
        if pace_ms is not None:
            return max(float(pace_ms), 0.0) / 1000.0
        if self._detect_color_support():
            return 0.08
        return 0.0

    def _sleep(self) -> None:
        if self.pace_s > 0:
            time.sleep(self.pace_s)


def _box(title: str, lines: list[str], *, theme: str = DEFAULT_THEME) -> str:
    inner = BOX_WIDTH - 4
    title_text = f" {title} "
    left = max((BOX_WIDTH - 2 - len(title_text)) // 2, 0)
    right = max(BOX_WIDTH - 2 - len(title_text) - left, 0)
    frame = _THEME_BOX_STYLES.get(theme, _THEME_BOX_STYLES[DEFAULT_THEME])
    rendered = [
        frame["corner"] + frame["top"] * left + title_text + frame["top"] * right + frame["corner"]
    ]
    for line in lines:
        wrapped = textwrap.wrap(
            line,
            width=inner,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        for chunk in wrapped:
            rendered.append(f"{frame['side']} {chunk:<{inner}} {frame['side']}")
    rendered.append(frame["corner"] + frame["bottom"] * (BOX_WIDTH - 2) + frame["corner"])
    return "\n".join(rendered)


def _stage_copy(stage: str, *, theme: str = DEFAULT_THEME) -> str:
    copybook = _THEME_STAGE_COPY.get(theme, _THEME_STAGE_COPY[DEFAULT_THEME])
    return copybook.get(stage, copybook["*"])


_LOGO_GLYPHS: dict[str, tuple[str, ...]] = {
    "D": (
        " ______  ",
        "|  __  \\ ",
        "| |  | | ",
        "| |  | | ",
        "| |__| | ",
        "|_____/  ",
    ),
    "A": (
        "    _    ",
        "   / \\   ",
        "  / _ \\  ",
        " / ___ \\ ",
        "/_/   \\_\\",
        "|_|   |_|",
    ),
    "V": (
        "         ",
        "\\ \\   / /",
        " \\ \\ / / ",
        "  \\ V /  ",
        "   \\ /   ",
        "    V    ",
    ),
    "I": (
        "  _____  ",
        " |_   _| ",
        "   | |   ",
        "   | |   ",
        "  _| |_  ",
        " |_____| ",
    ),
    "N": (
        " _   _   ",
        "| \\ | |  ",
        "|  \\| |  ",
        "| . ` |  ",
        "| |\\  |  ",
        "|_| \\_|  ",
    ),
    "C": (
        "  _____  ",
        " / ____| ",
        "| |      ",
        "| |      ",
        "| |____  ",
        " \\_____| ",
    ),
}


def _build_logo_lines(word: str = "DAVINCI") -> list[str]:
    rows: list[str] = []
    glyph_height = len(next(iter(_LOGO_GLYPHS.values())))
    for row_idx in range(glyph_height):
        row = " ".join(_LOGO_GLYPHS[ch][row_idx] for ch in word)
        rows.append(row.rstrip())
    width = max(len(row) for row in rows)
    rows = [row.ljust(width) for row in rows]
    rows.append("S T U D I O".center(width))
    return rows


def _logo_lines() -> list[str]:
    return list(_LOGO_RAW)


# ---------------------------------------------------------------------------
# Gradient logo — 256-color / TrueColor ANSI (magenta → red → orange → gold)
# ---------------------------------------------------------------------------

_GRADIENT_STOPS: list[tuple[int, int, int]] = [
    (220, 50, 220),   # magenta
    (230, 40, 50),    # red
    (255, 140, 30),   # orange
    (255, 210, 60),   # gold
]

# 256-color ramp: magenta(163) → red(197) → orange(214) → gold(223) → warm yellow(229)
_GRADIENT_256_RAMP: list[int] = [
    163, 164, 165, 166, 167, 168, 169, 170, 171, 172,  # magenta tones
    173, 174, 175, 176, 177, 178, 179, 180, 181, 182,  # purple → red tones
    183, 184, 185, 186, 187, 188, 189, 190, 191, 192,  # warm reds
    193, 194, 195, 196, 197, 198, 199, 200, 201, 202,  # red → orange-red
    203, 204, 205, 206, 207, 208, 209, 210, 211, 212,  # orange tones
    213, 214, 215, 216, 217, 218, 219, 220, 221, 222,  # amber tones
    223, 224, 225, 226, 227, 228, 229,                  # gold → warm yellow
]

_LOGO_RAW: list[str] = _build_logo_lines()


def _lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _gradient_color(t: float) -> tuple[int, int, int]:
    """Interpolate across _GRADIENT_STOPS at position *t* in [0, 1]."""
    n = len(_GRADIENT_STOPS) - 1
    segment = min(int(t * n), n - 1)
    local_t = (t * n) - segment
    return _lerp_color(_GRADIENT_STOPS[segment], _GRADIENT_STOPS[segment + 1], local_t)


def _detect_truecolor() -> bool:
    """Check whether the terminal supports 24-bit TrueColor."""
    import os
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return True
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program in ("iTerm.app", "WezTerm", "Hyper", "Alacritty", "kitty", "contour"):
        return True
    return False


def _colorize_line_gradient(line: str) -> str:
    """Apply a left-to-right gradient to *line*, using TrueColor or 256-color."""
    reset = "\033[0m"
    max_col = max(len(line) - 1, 1)
    parts: list[str] = []
    truecolor = _detect_truecolor()
    for idx, ch in enumerate(line):
        t = idx / max_col
        if truecolor:
            r, g, b = _gradient_color(t)
            parts.append(f"\033[38;2;{r};{g};{b}m{ch}")
        else:
            color_idx = min(int(t * len(_GRADIENT_256_RAMP)), len(_GRADIENT_256_RAMP) - 1)
            code = _GRADIENT_256_RAMP[color_idx]
            parts.append(f"\033[38;5;{code}m{ch}")
    parts.append(reset)
    return "".join(parts)


def _gradient_logo_lines() -> list[str]:
    return [_colorize_line_gradient(line) for line in _LOGO_RAW]


def _image_meta(path: Path) -> str | None:
    try:
        with Image.open(path) as image:
            stat = path.stat()
            return f"{image.width}x{image.height} {image.mode} {_human_size(stat.st_size)}"
    except Exception:
        return None


def _human_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size_bytes} B"
