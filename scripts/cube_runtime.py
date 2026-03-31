#!/usr/bin/env python3
"""Independent CUBE LUT runtime.

Provides:
- CUBE parsing
- trilinear interpolation
- tetrahedral interpolation (default)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

InterpolationAlgorithm = Literal["tetrahedral", "trilinear"]


@dataclass(frozen=True)
class CubeLUT:
    size: int
    # Axis order: [blue, green, red, channel], where channel is RGB output.
    table: np.ndarray
    domain_min: np.ndarray
    domain_max: np.ndarray
    title: str | None = None


def _parse_title(raw_line: str) -> str | None:
    rest = raw_line.strip()[5:].strip()
    if not rest:
        return None
    if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
        return rest[1:-1]
    return rest


def parse_cube_bytes(payload: bytes) -> CubeLUT:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"CUBE text must be UTF-8 decodable: {exc}") from exc

    title: str | None = None
    size: int | None = None
    domain_min = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    domain_max = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    values: list[list[float]] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue

        upper = line.upper()
        if upper.startswith("TITLE"):
            title = _parse_title(line)
            continue

        if upper.startswith("LUT_3D_SIZE"):
            tokens = line.split()
            if len(tokens) != 2:
                raise ValueError(f"Invalid LUT_3D_SIZE line: {raw}")
            try:
                size = int(tokens[1])
            except ValueError as exc:
                raise ValueError(f"Invalid LUT_3D_SIZE value: {tokens[1]}") from exc
            if size <= 1:
                raise ValueError(f"LUT_3D_SIZE must be > 1, got {size}")
            continue

        if upper.startswith("DOMAIN_MIN"):
            tokens = line.split()
            if len(tokens) != 4:
                raise ValueError(f"Invalid DOMAIN_MIN line: {raw}")
            domain_min = np.array([float(tokens[1]), float(tokens[2]), float(tokens[3])], dtype=np.float32)
            continue

        if upper.startswith("DOMAIN_MAX"):
            tokens = line.split()
            if len(tokens) != 4:
                raise ValueError(f"Invalid DOMAIN_MAX line: {raw}")
            domain_max = np.array([float(tokens[1]), float(tokens[2]), float(tokens[3])], dtype=np.float32)
            continue

        tokens = line.split()
        if len(tokens) != 3:
            raise ValueError(f"Invalid LUT data line: {raw}")
        try:
            values.append([float(tokens[0]), float(tokens[1]), float(tokens[2])])
        except ValueError as exc:
            raise ValueError(f"Invalid LUT data numeric values: {raw}") from exc

    if size is None:
        raise ValueError("Missing LUT_3D_SIZE")

    expected = size * size * size
    if len(values) != expected:
        raise ValueError(
            f"LUT data count mismatch: expected {expected}, got {len(values)}"
        )

    if np.any(domain_max <= domain_min):
        raise ValueError("Invalid DOMAIN range: DOMAIN_MAX must be > DOMAIN_MIN for all channels")

    table = np.asarray(values, dtype=np.float32).reshape((size, size, size, 3))
    return CubeLUT(
        size=size,
        table=table,
        domain_min=domain_min,
        domain_max=domain_max,
        title=title,
    )


def _prepare_sampling(rgb_flat: np.ndarray, lut: CubeLUT) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Map RGB from source domain into LUT domain and scale to [0, size-1]
    span = np.maximum(lut.domain_max - lut.domain_min, 1e-12)
    normalized = np.clip((rgb_flat - lut.domain_min) / span, 0.0, 1.0)
    scaled = normalized * float(lut.size - 1)

    idx0 = np.floor(scaled).astype(np.int32)
    idx0 = np.clip(idx0, 0, lut.size - 1)
    idx1 = np.clip(idx0 + 1, 0, lut.size - 1)
    frac = scaled - idx0.astype(np.float32)

    r0 = idx0[:, 0]
    g0 = idx0[:, 1]
    b0 = idx0[:, 2]
    r1 = idx1[:, 0]
    g1 = idx1[:, 1]
    b1 = idx1[:, 2]

    return r0, g0, b0, r1, g1, b1, frac


def _sample_corners(lut: CubeLUT, r0: np.ndarray, g0: np.ndarray, b0: np.ndarray, r1: np.ndarray, g1: np.ndarray, b1: np.ndarray) -> tuple[np.ndarray, ...]:
    t = lut.table
    c000 = t[b0, g0, r0]
    c100 = t[b0, g0, r1]
    c010 = t[b0, g1, r0]
    c110 = t[b0, g1, r1]
    c001 = t[b1, g0, r0]
    c101 = t[b1, g0, r1]
    c011 = t[b1, g1, r0]
    c111 = t[b1, g1, r1]
    return c000, c100, c010, c110, c001, c101, c011, c111


def _apply_trilinear(
    frac: np.ndarray,
    c000: np.ndarray,
    c100: np.ndarray,
    c010: np.ndarray,
    c110: np.ndarray,
    c001: np.ndarray,
    c101: np.ndarray,
    c011: np.ndarray,
    c111: np.ndarray,
) -> np.ndarray:
    fr = frac[:, 0:1]
    fg = frac[:, 1:2]
    fb = frac[:, 2:3]

    c00 = c000 * (1.0 - fr) + c100 * fr
    c10 = c010 * (1.0 - fr) + c110 * fr
    c01 = c001 * (1.0 - fr) + c101 * fr
    c11 = c011 * (1.0 - fr) + c111 * fr

    c0 = c00 * (1.0 - fg) + c10 * fg
    c1 = c01 * (1.0 - fg) + c11 * fg

    return c0 * (1.0 - fb) + c1 * fb


def _apply_tetrahedral(
    frac: np.ndarray,
    c000: np.ndarray,
    c100: np.ndarray,
    c010: np.ndarray,
    c110: np.ndarray,
    c001: np.ndarray,
    c101: np.ndarray,
    c011: np.ndarray,
    c111: np.ndarray,
) -> np.ndarray:
    fr = frac[:, 0]
    fg = frac[:, 1]
    fb = frac[:, 2]

    out = np.empty_like(c000)

    m1 = (fr >= fg) & (fg >= fb)
    m2 = (fr >= fg) & (fg < fb) & (fr >= fb)
    m3 = (fr >= fg) & (fg < fb) & (fr < fb)
    m4 = (fr < fg) & (fb >= fg)
    m5 = (fr < fg) & (fb < fg) & (fb >= fr)
    m6 = (fr < fg) & (fb < fg) & (fb < fr)

    out[m1] = (
        c000[m1]
        + fr[m1, None] * (c100[m1] - c000[m1])
        + fg[m1, None] * (c110[m1] - c100[m1])
        + fb[m1, None] * (c111[m1] - c110[m1])
    )

    out[m2] = (
        c000[m2]
        + fr[m2, None] * (c100[m2] - c000[m2])
        + fb[m2, None] * (c101[m2] - c100[m2])
        + fg[m2, None] * (c111[m2] - c101[m2])
    )

    out[m3] = (
        c000[m3]
        + fb[m3, None] * (c001[m3] - c000[m3])
        + fr[m3, None] * (c101[m3] - c001[m3])
        + fg[m3, None] * (c111[m3] - c101[m3])
    )

    out[m4] = (
        c000[m4]
        + fb[m4, None] * (c001[m4] - c000[m4])
        + fg[m4, None] * (c011[m4] - c001[m4])
        + fr[m4, None] * (c111[m4] - c011[m4])
    )

    out[m5] = (
        c000[m5]
        + fg[m5, None] * (c010[m5] - c000[m5])
        + fb[m5, None] * (c011[m5] - c010[m5])
        + fr[m5, None] * (c111[m5] - c011[m5])
    )

    out[m6] = (
        c000[m6]
        + fg[m6, None] * (c010[m6] - c000[m6])
        + fr[m6, None] * (c110[m6] - c010[m6])
        + fb[m6, None] * (c111[m6] - c110[m6])
    )

    return out


def apply_lut_rgb(
    rgb: np.ndarray,
    lut: CubeLUT,
    *,
    intensity: float = 1.0,
    algorithm: InterpolationAlgorithm = "tetrahedral",
) -> np.ndarray:
    if rgb.ndim < 2 or rgb.shape[-1] != 3:
        raise ValueError(f"Expected RGB array with last dimension=3, got shape={rgb.shape}")

    clamped_intensity = float(np.clip(intensity, 0.0, 1.0))
    rgb_float = np.clip(rgb.astype(np.float32, copy=False), 0.0, 1.0)

    flat = rgb_float.reshape(-1, 3)
    r0, g0, b0, r1, g1, b1, frac = _prepare_sampling(flat, lut)
    c000, c100, c010, c110, c001, c101, c011, c111 = _sample_corners(lut, r0, g0, b0, r1, g1, b1)

    if algorithm == "trilinear":
        mapped = _apply_trilinear(frac, c000, c100, c010, c110, c001, c101, c011, c111)
    elif algorithm == "tetrahedral":
        mapped = _apply_tetrahedral(frac, c000, c100, c010, c110, c001, c101, c011, c111)
    else:
        raise ValueError(f"Unsupported interpolation algorithm: {algorithm}")

    blended = flat + clamped_intensity * (mapped - flat)
    return np.clip(blended, 0.0, 1.0).reshape(rgb_float.shape)


def apply_lut_uint8(
    rgb_u8: np.ndarray,
    lut: CubeLUT,
    *,
    intensity: float = 1.0,
    algorithm: InterpolationAlgorithm = "tetrahedral",
) -> np.ndarray:
    if rgb_u8.dtype != np.uint8:
        raise ValueError("Expected uint8 image array")
    rgb = rgb_u8.astype(np.float32) / 255.0
    out = apply_lut_rgb(rgb, lut, intensity=intensity, algorithm=algorithm)
    return np.clip(np.round(out * 255.0), 0, 255).astype(np.uint8)

