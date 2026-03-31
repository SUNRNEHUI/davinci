"""ASCII Art Leica Camera atmosphere engine.

Provides terminal-friendly ASCII art for an immersive Leica camera experience.
All output uses printable ASCII characters for maximum terminal compatibility.
"""
from __future__ import annotations


def camera_top_view() -> str:
    """Leica M series camera top view ASCII art."""
    return (
        "        ___________________________________________\n"
        "       /                                           \\\n"
        "      /    +-+                               +-+    \\\n"
        "     |     |O|         LEICA M               |O|     |\n"
        "     |     +-+        ___ ___                +-+     |\n"
        "     |               /   X   \\                       |\n"
        "     |      [===]    |  O   O |    [===]             |\n"
        "     |               |________|                      |\n"
        "     |    SHUTTER     VIEWFINDER      DIAL           |\n"
        "     |                                               |\n"
        "      \\               _  _  _  _  _                 /\n"
        "       \\_____________|_||_||_||_||_|_______________/\n"
        "                     BASE PLATE\n"
    )


def metering_frames() -> list[str]:
    """Metering animation frame sequence."""
    return [
        "  [METERING]  . . . . . . . . . ",
        "  [METERING]  . . . . . . . . . . ",
        "  [METERING]  Measuring light... ",
        "  [METERING]  >>>  |  <<<  ",
        "  [METERING]  >>>  ||| <<<  ",
        "  [ OK ]  Exposure: Normal  1/125s  f/2.8",
    ]


def shutter_frames() -> list[str]:
    """Shutter release animation frame sequence."""
    return [
        "        +---+\n"
        "        |   |  <-- shutter closed\n"
        "        +---+",

        "        +   +\n"
        "          |  \n"
        "        +   +",

        "        +   +\n"
        "             <-- CLICK!\n"
        "        +   +",

        "        +---+\n"
        "        |   |  <-- shutter closed\n"
        "        +---+",
    ]


def developing_frames() -> list[str]:
    """Darkroom developing animation frame sequence."""
    return [
        "  [DARKROOM]  Soaking paper...",
        "  [DARKROOM]  Image appearing... .  ",
        "  [DARKROOM]  Image appearing... .. ",
        "  [DARKROOM]  Image appearing... ...",
        "  [DARKROOM]  Fixing... ",
        "  [DARKROOM]  Wash & dry... ",
        "  [ DONE ]  Print ready.",
    ]


def filter_dial(
    current_filter: str,
    index: int,
    total: int,
) -> str:
    """Display filter dial current state."""
    dial_markers = "<" + "-" * 20 + ">"
    position = int((index / max(total, 1)) * 20)
    indicator = " " * (position + 1) + "v"

    return (
        f"    +-- FILTER DIAL --[ {index}/{total} ]--+\n"
        f"    |  {dial_markers}  |\n"
        f"    |  {indicator}  |\n"
        f"    |  SELECTED: {current_filter:<20s}  |\n"
        f"    +-----------------------------------+\n"
    )


def scene_result(scene: str, confidence: float) -> str:
    """Scene analysis result display."""
    bar_len = 20
    filled = int(confidence * bar_len)
    bar = "#" * filled + "-" * (bar_len - filled)

    return (
        f"    +-- LIGHT METER --+\n"
        f"    |  Scene:  {scene:<8s}  |\n"
        f"    |  Match:  [{bar}] {confidence:.0%}  |\n"
        f"    |  Status: READY    |\n"
        f"    +------------------+\n"
    )


def progress_bar(stage: str, percent: int, *, width: int = 20) -> str:
    """Render a deterministic CLI progress bar."""
    clamped = max(0, min(100, int(percent)))
    filled = int((clamped / 100.0) * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"  [{bar}] {clamped:3d}%  {stage}"


def analysis_stats(color_stats: dict[str, float]) -> str:
    """Render scene-analysis metrics in a compact ASCII panel."""
    warm = color_stats.get("warm_ratio", 0.0)
    sat = color_stats.get("saturation_avg", 0.0)
    contrast = color_stats.get("contrast", 0.0)
    return (
        "    +-- ANALYSIS ------+\n"
        f"    |  Warmth:   {warm:>5.2f}      |\n"
        f"    |  Saturation:{sat:>5.2f}      |\n"
        f"    |  Contrast: {contrast:>5.2f}      |\n"
        "    +------------------+\n"
    )


def recommendation_block(items: list[tuple[str, str]]) -> str:
    """Render filter recommendations and short reasons."""
    lines = ["    +-- RECOMMENDED LOOKS --------------------------------------------+"]
    for index, (name, reason) in enumerate(items, start=1):
        lines.append(f"    |  {index:>2d}. {name:<18.18s} | {reason:<31.31s} |")
    lines.append("    +-----------------------------------------------------------------+")
    return "\n".join(lines)
