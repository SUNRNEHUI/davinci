"""Generate DAVINCI contact sheet and comparison previews.

Creates a film contact sheet image showing the original photo
with multiple filter effects applied, styled like a darkroom proof sheet.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# --- Layout constants ---
SHEET_WIDTH = 2400
PADDING = 40
CELL_GAP = 16
FRAME_BORDER = 4
BG_COLOR = (20, 20, 20)
FRAME_COLOR = (240, 240, 240)
LABEL_COLOR = (180, 180, 180)
TITLE_COLOR = (255, 255, 255)
LEICA_RED = (220, 30, 30)
COLS = 4
COMPARE_WIDTH = 2200
COMPARE_GAP = 22
COMPARE_PADDING = 40
COMPARE_HEADER_H = 72
COMPARE_LABEL_H = 38


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try loading a system font, fallback to default."""
    for path in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _apply_filter_to_thumbnail(
    thumb_rgb: np.ndarray,
    flut_path: Path,
    key: bytes,
    intensity: float = 0.85,
) -> np.ndarray:
    """Apply a single filter to thumbnail."""
    try:
        from .cube_runtime import apply_lut_uint8, parse_cube_bytes
        from .flut_codec import unpack_flut_bytes
    except ImportError:  # pragma: no cover - script execution fallback
        from cube_runtime import apply_lut_uint8, parse_cube_bytes
        from flut_codec import unpack_flut_bytes

    flut_blob = flut_path.read_bytes()
    _, cube_payload = unpack_flut_bytes(flut_blob=flut_blob, key=key)
    lut = parse_cube_bytes(cube_payload)
    return apply_lut_uint8(thumb_rgb, lut, intensity=intensity)


def _resolve_contact_sheet_key(
    *,
    filter_entry: dict,
    flut_path: Path,
    shared_key: bytes | None,
    shared_key_file: str | None,
) -> bytes:
    if shared_key is not None:
        return shared_key

    explicit_key = filter_entry.get("key")
    if isinstance(explicit_key, bytes):
        return explicit_key

    explicit_key_file = filter_entry.get("key_file")
    if explicit_key_file:
        try:
            from .flut_codec import resolve_key
        except ImportError:  # pragma: no cover - script execution fallback
            from flut_codec import resolve_key

        return resolve_key(
            key_base64=None,
            key_file=str(explicit_key_file),
        )

    try:
        from .flut_codec import default_key_candidates, resolve_key
    except ImportError:  # pragma: no cover - script execution fallback
        from flut_codec import default_key_candidates, resolve_key

    return resolve_key(
        key_base64=None,
        key_file=shared_key_file,
        default_key_files=default_key_candidates(flut_path),
    )


def generate_contact_sheet(
    input_path: Path | str,
    filters: list[dict],
    output_path: Path | str,
    *,
    include_original: bool = True,
    intensity: float = 0.85,
    key: bytes | None = None,
    key_file: str | None = None,
    flut_base_dir: Path | str | None = None,
) -> Path:
    """Generate a Contact Sheet image.

    Args:
        input_path: Source image path.
        filters: List of {"filter_id", "display_name", optional "flut_file"}.
        output_path: Where to save the result.
        include_original: Include the unfiltered original.
        intensity: Filter strength (0-1).
        key: AES decryption key.
        key_file: Path to key file.
        flut_base_dir: Base directory for relative flut_file paths.

    Returns:
        Path to the generated image.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Load source image
    src_img = Image.open(input_path).convert("RGB")

    if flut_base_dir is not None:
        flut_base_dir = Path(flut_base_dir)

    # Build entries: (id, flut_path_or_None, display_name)
    entries: list[tuple[str, Path | None, str]] = []
    if include_original:
        entries.append(("original", None, "ORIGINAL"))

    for f in filters:
        flut: Path | None = None
        flut_file = f.get("flut_file")
        if flut_file:
            flut = Path(flut_file)
            if not flut.is_absolute() and flut_base_dir is not None:
                flut = flut_base_dir / flut
        entries.append((f["filter_id"], flut, f["display_name"]))

    total = len(entries)
    if total == 0:
        total = 1
    rows = math.ceil(total / COLS)

    # Compute thumbnail dimensions
    avail_width = SHEET_WIDTH - 2 * PADDING - (COLS - 1) * CELL_GAP
    thumb_w = avail_width // COLS
    thumb_h = int(thumb_w * src_img.height / max(src_img.width, 1))

    cell_w = thumb_w + 2 * FRAME_BORDER
    cell_h = thumb_h + 2 * FRAME_BORDER + 32  # 32px for label

    header_h = 56
    sheet_h = PADDING + header_h + rows * cell_h + (rows - 1) * CELL_GAP + PADDING

    # Create canvas
    sheet = Image.new("RGB", (SHEET_WIDTH, sheet_h), BG_COLOR)
    draw = ImageDraw.Draw(sheet)

    # Draw header
    font_title = _get_font(28)
    font_label = _get_font(20)

    draw.text((PADDING, 16), "DAVINCI CONTACT SHEET", fill=TITLE_COLOR, font=font_title)
    # Leica red dot
    draw.ellipse(
        [SHEET_WIDTH - PADDING - 20, 18, SHEET_WIDTH - PADDING, 38], fill=LEICA_RED
    )

    # Resolve a shared key if one was explicitly supplied.
    if key is None and key_file is not None:
        try:
            from .flut_codec import resolve_key
        except ImportError:  # pragma: no cover - script execution fallback
            from flut_codec import resolve_key

        key = resolve_key(key_base64=None, key_file=str(key_file) if key_file else None)

    # Resize source to thumbnail
    src_thumb = src_img.resize((thumb_w, thumb_h), Image.LANCZOS)
    src_thumb_arr = np.asarray(src_thumb, dtype=np.uint8)

    # Place each cell
    for idx, (fid, flut_path, name) in enumerate(entries):
        row = idx // COLS
        col = idx % COLS

        x = PADDING + col * (cell_w + CELL_GAP)
        y = PADDING + header_h + row * (cell_h + CELL_GAP)

        # White frame border
        draw.rectangle(
            [x, y, x + cell_w - 1, y + thumb_h + 2 * FRAME_BORDER - 1],
            fill=FRAME_COLOR,
        )

        # Apply filter or use original
        if fid == "original" or flut_path is None:
            thumb_arr = src_thumb_arr
        else:
            filter_entry = filters[idx - 1] if include_original else filters[idx]
            thumb_arr = _apply_filter_to_thumbnail(
                src_thumb_arr,
                flut_path,
                _resolve_contact_sheet_key(
                    filter_entry=filter_entry,
                    flut_path=flut_path,
                    shared_key=key,
                    shared_key_file=key_file,
                ),
                intensity,
            )

        thumb_img = Image.fromarray(thumb_arr, mode="RGB")
        sheet.paste(thumb_img, (x + FRAME_BORDER, y + FRAME_BORDER))

        # Label: number + name
        label = f"#{idx + 1}  {name}"
        draw.text(
            (x + FRAME_BORDER, y + thumb_h + 2 * FRAME_BORDER + 6),
            label,
            fill=LABEL_COLOR,
            font=font_label,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)
    return output_path


def generate_before_after_preview(
    input_path: Path | str,
    rendered_path: Path | str,
    output_path: Path | str,
    *,
    left_label: str = "BEFORE",
    right_label: str = "AFTER",
) -> Path:
    """Generate a simple before/after side-by-side preview."""
    input_path = Path(input_path)
    rendered_path = Path(rendered_path)
    output_path = Path(output_path)

    before = Image.open(input_path).convert("RGB")
    after = Image.open(rendered_path).convert("RGB")
    target_w = (SHEET_WIDTH - (PADDING * 2) - CELL_GAP) // 2
    aspect = before.height / max(before.width, 1)
    target_h = max(int(target_w * aspect), 1)
    before = before.resize((target_w, target_h), Image.LANCZOS)
    after = after.resize((target_w, target_h), Image.LANCZOS)

    canvas_h = PADDING * 2 + 72 + target_h
    canvas = Image.new("RGB", (SHEET_WIDTH, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)
    font_title = _get_font(28)
    font_label = _get_font(20)

    draw.text((PADDING, 16), "BEFORE / AFTER", fill=TITLE_COLOR, font=font_title)
    draw.ellipse(
        [SHEET_WIDTH - PADDING - 20, 18, SHEET_WIDTH - PADDING, 38], fill=LEICA_RED
    )

    left_x = PADDING
    right_x = PADDING + target_w + CELL_GAP
    top_y = PADDING + 56

    for x in (left_x, right_x):
        draw.rectangle(
            [x, top_y, x + target_w + 2 * FRAME_BORDER - 1, top_y + target_h + 2 * FRAME_BORDER - 1],
            fill=FRAME_COLOR,
        )

    canvas.paste(before, (left_x + FRAME_BORDER, top_y + FRAME_BORDER))
    canvas.paste(after, (right_x + FRAME_BORDER, top_y + FRAME_BORDER))
    draw.text((left_x + FRAME_BORDER, top_y + target_h + 14), left_label, fill=LABEL_COLOR, font=font_label)
    draw.text((right_x + FRAME_BORDER, top_y + target_h + 14), right_label, fill=LABEL_COLOR, font=font_label)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=92)
    return output_path


def generate_before_after_preview(
    input_path: Path | str,
    rendered_path: Path | str,
    output_path: Path | str,
    *,
    left_label: str = "BEFORE",
    right_label: str = "AFTER",
) -> Path:
    """Render a side-by-side before/after preview for quick beginner review."""
    input_path = Path(input_path)
    rendered_path = Path(rendered_path)
    output_path = Path(output_path)

    before = Image.open(input_path).convert("RGB")
    after = Image.open(rendered_path).convert("RGB")

    avail_width = COMPARE_WIDTH - 2 * COMPARE_PADDING - COMPARE_GAP
    pane_w = avail_width // 2
    pane_h = int(pane_w * before.height / max(before.width, 1))

    before_thumb = before.resize((pane_w, pane_h), Image.LANCZOS)
    after_thumb = after.resize((pane_w, pane_h), Image.LANCZOS)

    canvas_h = COMPARE_PADDING * 2 + COMPARE_HEADER_H + pane_h + COMPARE_LABEL_H
    canvas = Image.new("RGB", (COMPARE_WIDTH, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)
    font_title = _get_font(28)
    font_label = _get_font(22)

    draw.text((COMPARE_PADDING, 18), "DAVINCI BEFORE / AFTER", fill=TITLE_COLOR, font=font_title)
    draw.ellipse(
        [COMPARE_WIDTH - COMPARE_PADDING - 20, 18, COMPARE_WIDTH - COMPARE_PADDING, 38],
        fill=LEICA_RED,
    )

    left_x = COMPARE_PADDING
    top_y = COMPARE_PADDING + COMPARE_HEADER_H
    right_x = left_x + pane_w + COMPARE_GAP

    for pane_x in (left_x, right_x):
        draw.rectangle(
            [pane_x - FRAME_BORDER, top_y - FRAME_BORDER, pane_x + pane_w + FRAME_BORDER - 1, top_y + pane_h + FRAME_BORDER - 1],
            fill=FRAME_COLOR,
        )

    canvas.paste(before_thumb, (left_x, top_y))
    canvas.paste(after_thumb, (right_x, top_y))

    label_y = top_y + pane_h + 10
    draw.text((left_x, label_y), left_label, fill=LABEL_COLOR, font=font_label)
    draw.text((right_x, label_y), right_label, fill=LABEL_COLOR, font=font_label)

    divider_x = left_x + pane_w + (COMPARE_GAP // 2)
    draw.line(
        [(divider_x, top_y), (divider_x, top_y + pane_h)],
        fill=(90, 90, 90),
        width=2,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=92)
    return output_path
