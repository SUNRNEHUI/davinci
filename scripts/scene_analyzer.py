"""Scene-aware recommendation engine.

Analyzes image color distribution and maps the result to catalog-specific filters.
Uses only numpy + Pillow — no OpenCV dependency.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    from .leica_catalog import DEFAULT_CATALOG, scene_filters_for_catalog
except ImportError:  # pragma: no cover - script execution fallback
    from leica_catalog import DEFAULT_CATALOG, scene_filters_for_catalog


DEFAULT_SCENE_FILTERS = scene_filters_for_catalog(DEFAULT_CATALOG)


def _clip01(value: float) -> float:
    """Clamp numeric value to [0, 1]."""
    return float(max(0.0, min(1.0, value)))


def _band_score(value: float, target: float, spread: float) -> float:
    """Return high score when value is near target."""
    if spread <= 1e-6:
        return 0.0
    return _clip01(1.0 - abs(value - target) / spread)


def _region_mean(values: np.ndarray, mask: np.ndarray) -> float:
    """Compute masked mean with safe fallback."""
    count = int(mask.sum())
    if count <= 0:
        return 0.0
    return float(values[mask].mean())


def _build_center_mask(height: int, width: int) -> np.ndarray:
    """Elliptical center mask used for central-subject weighting."""
    yy, xx = np.ogrid[:height, :width]
    cx = (width - 1) * 0.5
    cy = (height - 1) * 0.5
    rx = max(width * 0.32, 1.0)
    ry = max(height * 0.32, 1.0)
    norm = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    return norm <= 1.0


def _compute_color_stats(rgb: np.ndarray) -> dict[str, float]:
    """Compute color and structure statistics from RGB array."""
    r = rgb[..., 0].astype(np.float32)
    g = rgb[..., 1].astype(np.float32)
    b = rgb[..., 2].astype(np.float32)

    warm_mask = r > b
    warm_ratio = float(warm_mask.mean())
    cool_ratio = 1.0 - warm_ratio

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    sat = np.zeros_like(max_c, dtype=float)
    np.divide((max_c - min_c), max_c, out=sat, where=max_c > 1e-6)
    saturation_avg = float(sat.mean())

    brightness = (r + g + b) / (3.0 * 255.0)
    brightness_avg = float(brightness.mean())
    brightness_std = float(brightness.std())
    contrast = _clip01(brightness_std / 0.32)

    # Gradient-based edge density, normalized for simple texture complexity.
    dx = np.diff(brightness, axis=1, append=brightness[:, -1:])
    dy = np.diff(brightness, axis=0, append=brightness[-1:, :])
    grad = np.hypot(dx, dy)
    edge_threshold = max(float(np.percentile(grad, 75)) * 0.9, 0.06)
    edge_mask = grad >= edge_threshold
    edge_density = float(edge_mask.mean())

    # HSV histogram diversity measures overall color distribution complexity.
    hsv = np.asarray(Image.fromarray(rgb, mode="RGB").convert("HSV"), dtype=np.uint8)
    h = hsv[..., 0].astype(np.int32)
    s_hsv = hsv[..., 1].astype(np.float32) / 255.0
    v_hsv = hsv[..., 2].astype(np.float32) / 255.0
    colorful = (s_hsv > 0.15) & (v_hsv > 0.12)
    if np.any(colorful):
        bins = (h[colorful] // 16).astype(np.int32)
        hist = np.bincount(bins, minlength=16).astype(np.float64)
        p = hist / (hist.sum() + 1e-12)
        valid = p[p > 0]
        hue_entropy = float(-(valid * np.log2(valid)).sum() / np.log2(16.0))
        dominant_hue_ratio = float(p.max())
    else:
        hue_entropy = 0.0
        dominant_hue_ratio = 1.0
    color_diversity = _clip01(hue_entropy)

    # Approximate skin-tone coverage with RGB + YCbCr rule intersection.
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    rgb_skin = (
        (r > 95.0)
        & (g > 40.0)
        & (b > 20.0)
        & ((max_c - min_c) > 15.0)
        & (np.abs(r - g) > 15.0)
        & (r > g)
        & (r > b)
    )
    ycbcr_skin = (cb > 85.0) & (cb < 135.0) & (cr > 135.0) & (cr < 180.0)
    skin_mask = rgb_skin & ycbcr_skin
    skin_tone_ratio = float(skin_mask.mean())

    center_mask = _build_center_mask(rgb.shape[0], rgb.shape[1])
    outer_mask = ~center_mask
    center_skin_ratio = _region_mean(skin_mask, center_mask)
    outer_skin_ratio = _region_mean(skin_mask, outer_mask)
    center_edge_density = _region_mean(edge_mask, center_mask)
    outer_edge_density = _region_mean(edge_mask, outer_mask)
    center_sat = _region_mean(sat, center_mask)
    outer_sat = _region_mean(sat, outer_mask)

    # Weighted center-subject heuristic: skin focus + texture focus + color focus.
    skin_focus = _clip01((center_skin_ratio - outer_skin_ratio) * 3.0 + center_skin_ratio * 1.4)
    texture_focus = _clip01((center_edge_density - outer_edge_density) * 2.2 + 0.5)
    color_focus = _clip01((center_sat - outer_sat) * 1.8 + 0.5)
    center_subject_weight = _clip01(0.55 * skin_focus + 0.30 * texture_focus + 0.15 * color_focus)

    # Nature-like coverage (green/blue dominant colorful pixels) for landscape cues.
    colorful_mask = s_hsv > 0.2
    green_dominant = (g > r * 1.03) & (g > b * 0.97) & colorful_mask
    blue_dominant = (b > r * 1.05) & (b >= g * 0.95) & colorful_mask
    nature_ratio = float((green_dominant | blue_dominant).mean())

    aspect = float(rgb.shape[1]) / max(float(rgb.shape[0]), 1.0)
    portrait_shape = _clip01((1.0 / max(aspect, 1e-6) - 0.95) / 0.75)
    landscape_shape = _clip01((aspect - 1.05) / 1.0)

    return {
        "warm_ratio": round(warm_ratio, 3),
        "cool_ratio": round(cool_ratio, 3),
        "saturation_avg": round(saturation_avg, 3),
        "brightness_avg": round(brightness_avg, 3),
        "contrast": round(contrast, 3),
        "edge_density": round(edge_density, 3),
        "color_diversity": round(color_diversity, 3),
        "dominant_hue_ratio": round(dominant_hue_ratio, 3),
        "skin_tone_ratio": round(skin_tone_ratio, 3),
        "center_skin_ratio": round(center_skin_ratio, 3),
        "center_subject_weight": round(center_subject_weight, 3),
        "nature_ratio": round(nature_ratio, 3),
        "portrait_shape": round(portrait_shape, 3),
        "landscape_shape": round(landscape_shape, 3),
    }


def _classify_scene(stats: dict[str, float]) -> tuple[str, float]:
    """Classify scene from handcrafted multi-signal heuristics."""
    scores: dict[str, float] = {}

    w = stats["warm_ratio"]
    s = stats["saturation_avg"]
    c = stats["contrast"]
    edge = stats.get("edge_density", 0.0)
    diversity = stats.get("color_diversity", 0.0)
    dominant_hue = stats.get("dominant_hue_ratio", 1.0)
    skin = stats.get("skin_tone_ratio", 0.0)
    center_skin = stats.get("center_skin_ratio", 0.0)
    center_subject = stats.get("center_subject_weight", 0.0)
    nature = stats.get("nature_ratio", 0.0)
    portrait_shape = stats.get("portrait_shape", 0.0)
    landscape_shape = stats.get("landscape_shape", 0.0)

    skin_score = _clip01(center_skin * 1.3 + skin * 0.7)
    sat_mid = _band_score(s, 0.42, 0.32)
    edge_mid = _band_score(edge, 0.25, 0.25)
    contrast_mid = _band_score(c, 0.45, 0.35)

    scores["portrait"] = _clip01(
        0.33 * skin_score
        + 0.27 * center_subject
        + 0.15 * sat_mid
        + 0.10 * edge_mid
        + 0.10 * portrait_shape
        + 0.05 * contrast_mid
    )

    scores["landscape"] = _clip01(
        0.31 * nature
        + 0.19 * diversity
        + 0.15 * _clip01(s / 0.75)
        + 0.11 * _clip01(c / 0.65)
        + 0.11 * landscape_shape
        + 0.08 * (1.0 - _clip01(skin * 6.0))
        + 0.05 * (1.0 - center_subject)
    )

    scores["street"] = _clip01(
        0.32 * _clip01(edge / 0.45)
        + 0.24 * _clip01(c / 0.70)
        + 0.14 * _clip01((0.62 - s) / 0.62)
        + 0.10 * (1.0 - center_subject * 0.8)
        + 0.10 * (1.0 - _clip01(skin * 5.0))
        + 0.10 * (1.0 - _clip01((dominant_hue - 0.35) / 0.65))
    )

    primary_scores = sorted(
        [scores["portrait"], scores["landscape"], scores["street"]],
        reverse=True,
    )
    gap = primary_scores[0] - primary_scores[1]
    ambiguity = _clip01(1.0 - gap / 0.35)
    scores["general"] = _clip01(
        0.45 * ambiguity
        + 0.20 * _band_score(w, 0.5, 0.35)
        + 0.20 * _band_score(s, 0.4, 0.35)
        + 0.15 * _band_score(c, 0.45, 0.35)
    )

    ranked = sorted(scores.values(), reverse=True)
    best_scene = max(scores, key=lambda key: scores[key])
    confidence = _clip01(ranked[0] * 0.65 + (ranked[0] - ranked[1]) * 0.70)
    return best_scene, confidence


def analyze_scene(
    image_path: Path | str,
    *,
    scene_filters: dict[str, list[str]] | None = None,
    catalog: str | None = None,
    index_path: Path | str | None = None,
) -> dict[str, Any]:
    """Analyze image and return scene recommendation."""
    img = Image.open(image_path).convert("RGB")

    max_dim = 300
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (
            max(1, int(round(img.width * ratio))),
            max(1, int(round(img.height * ratio))),
        )
        img = img.resize(new_size, Image.LANCZOS)

    rgb = np.asarray(img, dtype=np.uint8)
    color_stats = _compute_color_stats(rgb)
    scene, confidence = _classify_scene(color_stats)

    filters = scene_filters or scene_filters_for_catalog(
        catalog or DEFAULT_CATALOG,
        index_path=index_path,
    )
    recommended_filters = filters.get(scene) or filters.get("general") or DEFAULT_SCENE_FILTERS[scene]

    return {
        "scene": scene,
        "confidence": round(confidence, 3),
        "recommended_filters": recommended_filters,
        "color_stats": color_stats,
    }
