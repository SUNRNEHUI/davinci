"""DAVINCI pipeline — orchestrates the full experience.

Flow: ASCII metering -> scene analysis -> Contact Sheet -> optional final render.

Usage:
    python leica_pipeline.py --input photo.jpg --output-dir ./output --index flut/leica/index.json --key-file key.b64
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from .apply_flut_image import apply_flut_to_image
    from .ascii_camera import (
        analysis_stats,
        camera_top_view,
        developing_frames,
        filter_dial,
        metering_frames,
        progress_bar,
        recommendation_block,
        scene_result,
        shutter_frames,
    )
    from .contact_sheet import generate_contact_sheet
    from .flut_codec import default_key_candidates, resolve_key
    from .leica_catalog import (
        DEFAULT_CATALOG,
        build_recommendation_details,
        infer_catalog_name,
        load_filter_index,
        scene_filters_for_catalog,
        select_recommended_filters,
    )
    from .leica_render_cache import lookup_render_cache, make_render_cache_key, store_render_cache
    from .leica_recommend_rank import apply_favorite_boost
    from .scene_analyzer import analyze_scene
except ImportError:  # pragma: no cover - script execution fallback
    from apply_flut_image import apply_flut_to_image
    from ascii_camera import (
        analysis_stats,
        camera_top_view,
        developing_frames,
        filter_dial,
        metering_frames,
        progress_bar,
        recommendation_block,
        scene_result,
        shutter_frames,
    )
    from contact_sheet import generate_contact_sheet
    from flut_codec import default_key_candidates, resolve_key
    from leica_catalog import (
        DEFAULT_CATALOG,
        build_recommendation_details,
        infer_catalog_name,
        load_filter_index,
        scene_filters_for_catalog,
        select_recommended_filters,
    )
    from leica_render_cache import lookup_render_cache, make_render_cache_key, store_render_cache
    from leica_recommend_rank import apply_favorite_boost
    from scene_analyzer import analyze_scene

StageCallback = Callable[[str, int, dict[str, Any] | None], None]

STAGE_MESSAGES: dict[str, str] = {
    "LOAD": "[LOADING] Checking input, index, and key...",
    "ANALYZE_WARMTH": "[ANALYZE] Estimating light and color temperature...",
    "ANALYZE_STATS": "[ANALYZE] Measuring saturation and contrast...",
    "ANALYZE_SCENE": "[ANALYZE] Classifying scene...",
    "RECOMMEND": "[RECOMMEND] Matching catalog looks to this frame...",
    "RENDER_CONTACT_SHEET": "[DARKROOM] Building contact sheet...",
    "APPLY_TOP1": "[DARKROOM] Rendering top recommendation...",
    "DONE": "[DONE] Render complete.",
}


class ConsoleExperience:
    """Print a staged Leica-style CLI experience."""

    def __init__(self, *, prompt: str, catalog: str = DEFAULT_CATALOG, stream: Any = None) -> None:
        self.prompt = prompt
        self.catalog = catalog
        self.stream = stream or sys.stdout

    def _emit(self, text: str = "") -> None:
        print(text, file=self.stream)

    def start(self) -> None:
        self._emit(f"[FLUT SKILL] Catalog={self.catalog.upper()} Request: {self.prompt}")
        self._emit(camera_top_view())

    def on_stage(self, stage: str, percent: int, payload: dict[str, Any] | None = None) -> None:
        self._emit(progress_bar(stage, percent))
        self._emit(STAGE_MESSAGES.get(stage, f"[{stage}]"))

        if stage == "LOAD" and payload:
            self._emit(f"  input={payload['input_path']}")
        elif stage == "ANALYZE_WARMTH":
            for frame in metering_frames()[:3]:
                self._emit(frame)
        elif stage == "ANALYZE_SCENE" and payload:
            self._emit(scene_result(payload["scene"], payload["confidence"]))
            self._emit(analysis_stats(payload["color_stats"]))
        elif stage == "RECOMMEND" and payload:
            items = [
                (item["display_name"], item["reason"])
                for item in payload["recommendations"]
            ]
            self._emit(recommendation_block(items))
        elif stage == "RENDER_CONTACT_SHEET":
            for frame in shutter_frames():
                self._emit(frame)
            for frame in developing_frames()[:4]:
                self._emit(frame)
        elif stage == "APPLY_TOP1" and payload:
            total = max(int(payload.get("total", 1)), 1)
            self._emit(filter_dial(payload["display_name"], 1, total))
        elif stage == "DONE" and payload:
            self._emit(f"  scene={payload['scene']}  confidence={payload['confidence']:.0%}")

    def finish(self, result: dict[str, Any]) -> None:
        self._emit(f"  Contact Sheet: {result['contact_sheet_path']}")
        if result.get("final_output_path"):
            self._emit(f"  Final Image:   {result['final_output_path']}")
        self._emit(
            f"  Recommended: {[item['display_name'] for item in result['recommended_filters']]}"
        )

    def report_open(self, path: Path, success: bool, error: str | None = None) -> None:
        if success:
            self._emit(f"[OPEN] {path}")
        else:
            self._emit(f"[OPEN-FAILED] {path}")
            if error:
                self._emit(f"  reason={error}")


def _build_ascii_output(scene: str, confidence: float) -> str:
    """Assemble terminal ASCII output."""
    lines = [camera_top_view()]
    lines.extend(metering_frames())
    lines.append(scene_result(scene, confidence))
    return "\n".join(lines)


def _resolve_final_output_path(
    *,
    output_dir: Path,
    input_path: Path,
    filter_id: str,
    final_output: str | None,
) -> Path:
    if final_output:
        resolved = Path(final_output).expanduser().resolve()
        if resolved.suffix:
            return resolved
        suffix = input_path.suffix or ".png"
        return resolved.with_name(resolved.name + suffix)

    suffix = input_path.suffix or ".png"
    return output_dir / f"{input_path.stem}_{filter_id}{suffix}"


def _cache_filter_tokens(filters: list[dict[str, Any]]) -> list[str]:
    tokens: list[str] = []
    for item in filters:
        filter_id = str(item.get("filter_id") or "unknown")
        display_name = str(item.get("display_name") or filter_id)
        flut_file = item.get("flut_file")
        if not flut_file:
            tokens.append(f"{filter_id}@virtual@{display_name}")
            continue
        flut_path = Path(str(flut_file)).expanduser().resolve()
        if flut_path.exists():
            stat = flut_path.stat()
            tokens.append(f"{filter_id}@{display_name}@{flut_path}:{stat.st_mtime:.6f}:{stat.st_size}")
        else:
            tokens.append(f"{filter_id}@{display_name}@missing:{flut_path}")
    return tokens


def open_result(path: Path | str) -> tuple[bool, str | None]:
    """Best-effort open for generated results."""
    path = Path(path).expanduser().resolve()
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["open", str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(
                ["xdg-open", str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as exc:  # pragma: no cover - platform-specific branch
        return False, str(exc)
    return True, None


def run_pipeline(
    input_path: Path | str,
    output_dir: Path | str,
    filter_index_path: Path | str,
    *,
    catalog: str = DEFAULT_CATALOG,
    skip_flut_apply: bool = False,
    intensity: float = 0.85,
    algorithm: str = "tetrahedral",
    auto_apply: str = "none",
    full_preview: bool = False,
    final_output: str | None = None,
    preferred_filter_ids: set[str] | None = None,
    key: bytes | None = None,
    key_base64: str | None = None,
    key_file: str | None = None,
    stage_callback: StageCallback | None = None,
) -> dict[str, Any]:
    """Execute the full DAVINCI pipeline."""
    input_path = Path(input_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    filter_index_path = Path(filter_index_path).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if stage_callback:
        stage_callback(
            "LOAD",
            15,
            {
                "input_path": str(input_path),
                "index_path": str(filter_index_path),
                "output_dir": str(output_dir),
            },
        )

    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    if not filter_index_path.exists():
        raise FileNotFoundError(f"Filter index not found: {filter_index_path}")
    if skip_flut_apply and auto_apply != "none":
        raise ValueError("auto_apply requires real FLUT rendering; disable --skip-flut-apply")

    resolved_catalog = catalog or infer_catalog_name(filter_index_path)
    all_filters = load_filter_index(filter_index_path, catalog=resolved_catalog)

    if stage_callback:
        stage_callback("ANALYZE_WARMTH", 25, None)

    scene_result_dict = analyze_scene(
        input_path,
        scene_filters=scene_filters_for_catalog(resolved_catalog, index_path=filter_index_path),
        catalog=resolved_catalog,
        index_path=filter_index_path,
    )
    scene = scene_result_dict["scene"]
    confidence = scene_result_dict["confidence"]

    if stage_callback:
        stage_callback("ANALYZE_STATS", 40, {"color_stats": scene_result_dict["color_stats"]})
        stage_callback(
            "ANALYZE_SCENE",
            55,
            {
                "scene": scene,
                "confidence": confidence,
                "color_stats": scene_result_dict["color_stats"],
            },
        )

    recommended = select_recommended_filters(
        scene_result_dict=scene_result_dict,
        all_filters=all_filters,
        full_preview=full_preview,
    )
    recommended = apply_favorite_boost(recommended, favorite_filter_ids=preferred_filter_ids)
    recommendation_details = build_recommendation_details(
        scene,
        recommended,
        catalog=resolved_catalog,
        index_path=filter_index_path,
    )

    if stage_callback:
        stage_callback(
            "RECOMMEND",
            70,
            {"scene": scene, "recommendations": recommendation_details},
        )

    resolved_key = key
    if not skip_flut_apply and resolved_key is None:
        resolved_key = resolve_key(
            key_base64=key_base64,
            key_file=key_file,
            default_key_files=default_key_candidates(filter_index_path),
        )

    if not skip_flut_apply:
        missing_files = [
            str(item["flut_file"])
            for item in recommended
            if item.get("flut_file") and not Path(str(item["flut_file"])).exists()
        ]
        if missing_files:
            raise FileNotFoundError(
                "Missing FLUT files in pipeline input: " + ", ".join(missing_files)
            )

    contact_sheet_path = output_dir / f"contact_sheet_{scene}.png"
    contact_cache_key = make_render_cache_key(
        input_path=input_path,
        catalog=resolved_catalog,
        filter_ids=_cache_filter_tokens(recommended),
        intensity=0.0 if skip_flut_apply else intensity,
        algorithm=algorithm,
        output_type="contact_sheet_skip" if skip_flut_apply else "contact_sheet_apply",
    )
    cached_contact = lookup_render_cache(
        contact_cache_key,
        output_suffix=contact_sheet_path.suffix or "png",
    )
    contact_sheet_cache_hit = cached_contact is not None
    if stage_callback:
        stage_callback(
            "RENDER_CONTACT_SHEET",
            90,
            {"path": str(contact_sheet_path), "cache_hit": contact_sheet_cache_hit},
        )

    if cached_contact is not None:
        shutil.copy2(cached_contact, contact_sheet_path)
    else:
        if skip_flut_apply:
            generate_contact_sheet(
                input_path=input_path,
                filters=[{**item, "flut_file": ""} for item in recommended],
                output_path=contact_sheet_path,
                include_original=True,
            )
        else:
            generate_contact_sheet(
                input_path=input_path,
                filters=recommended,
                output_path=contact_sheet_path,
                include_original=True,
                intensity=intensity,
                key=resolved_key,
            )
        store_render_cache(
            contact_sheet_path,
            key=contact_cache_key,
            output_suffix=contact_sheet_path.suffix or "png",
            metadata={"scene": scene, "recommended_count": len(recommended)},
        )

    final_output_path: Path | None = None
    final_render_cache_hit = False
    if auto_apply == "top1" and recommended:
        top_filter = recommended[0]
        if not top_filter.get("flut_file"):
            raise ValueError(f"Top recommendation has no FLUT file: {top_filter['display_name']}")
        final_output_path = _resolve_final_output_path(
            output_dir=output_dir,
            input_path=input_path,
            filter_id=top_filter["filter_id"],
            final_output=final_output,
        )
        final_output_suffix = final_output_path.suffix or input_path.suffix or ".png"
        final_cache_key = make_render_cache_key(
            input_path=input_path,
            catalog=resolved_catalog,
            filter_ids=_cache_filter_tokens([top_filter]),
            intensity=intensity,
            algorithm=algorithm,
            output_type="final_render",
        )
        cached_final = lookup_render_cache(final_cache_key, output_suffix=final_output_suffix)
        final_render_cache_hit = cached_final is not None
        if stage_callback:
            stage_callback(
                "APPLY_TOP1",
                95,
                {
                    "display_name": top_filter["display_name"],
                    "total": len(recommended),
                    "cache_hit": final_render_cache_hit,
                },
            )
        if cached_final is not None:
            shutil.copy2(cached_final, final_output_path)
        else:
            apply_flut_to_image(
                flut_path=top_filter["flut_file"],
                input_path=input_path,
                output_path=final_output_path,
                intensity=intensity,
                algorithm=algorithm,
                key=resolved_key,
            )
            store_render_cache(
                final_output_path,
                key=final_cache_key,
                output_suffix=final_output_suffix,
                metadata={"filter_id": top_filter["filter_id"]},
            )

    if stage_callback:
        stage_callback(
            "DONE",
            100,
            {"scene": scene, "confidence": confidence},
        )

    return {
        "ascii": _build_ascii_output(scene, confidence),
        "scene": scene_result_dict,
        "contact_sheet_path": str(contact_sheet_path),
        "recommended_filters": recommendation_details,
        "final_output_path": str(final_output_path) if final_output_path else None,
        "input_path": str(input_path),
        "index_path": str(filter_index_path),
        "catalog": resolved_catalog,
        "cache": {
            "contact_sheet_hit": contact_sheet_cache_hit,
            "final_render_hit": final_render_cache_hit,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DAVINCI Pipeline")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--index", required=True, help="Filter index.json path")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG, help="Catalog name for built-in recommendation mapping")
    parser.add_argument("--prompt", default="帮我调色", help="Prompt text shown in the CLI experience")
    parser.add_argument("--intensity", type=float, default=0.85)
    parser.add_argument("--algorithm", choices=["tetrahedral", "trilinear"], default="tetrahedral")
    parser.add_argument("--key-base64", help="Base64 AES key")
    parser.add_argument("--key-file", help="AES key file path")
    parser.add_argument("--skip-flut-apply", action="store_true", help="Skip real .flut decryption (testing)")
    parser.add_argument("--auto-open", action="store_true", help="Open generated output after render")
    parser.add_argument(
        "--auto-apply",
        choices=["none", "top1"],
        default="none",
        help="Optionally render the top recommendation as a final image",
    )
    parser.add_argument("--final-output", help="Optional explicit output path for the final image")
    parser.add_argument("--full-preview", action="store_true", help="Render all filters instead of curated recommendations")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    experience = ConsoleExperience(prompt=args.prompt, catalog=args.catalog)
    experience.start()

    try:
        result = run_pipeline(
            input_path=args.input,
            output_dir=args.output_dir,
            filter_index_path=args.index,
            catalog=args.catalog,
            key_base64=args.key_base64,
            key_file=args.key_file,
            intensity=args.intensity,
            algorithm=args.algorithm,
            skip_flut_apply=args.skip_flut_apply,
            auto_apply=args.auto_apply,
            final_output=args.final_output,
            full_preview=args.full_preview,
            stage_callback=experience.on_stage,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    experience.finish(result)

    if args.auto_open:
        open_targets = [Path(result["contact_sheet_path"])]
        if result.get("final_output_path"):
            open_targets.append(Path(result["final_output_path"]))
        for path in open_targets:
            success, error = open_result(path)
            experience.report_open(path, success, error)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
