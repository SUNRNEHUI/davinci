"""Catalog validation for shipped and external FLUT bundles."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

try:
    from .leica_catalog import (
        MANIFEST_FILENAME,
        infer_catalog_name,
        load_filter_index,
        normalize_catalog_name,
    )
except ImportError:  # pragma: no cover - script execution fallback
    from leica_catalog import (
        MANIFEST_FILENAME,
        infer_catalog_name,
        load_filter_index,
        normalize_catalog_name,
    )


REQUIRED_MANIFEST_FIELDS = (
    "catalog",
    "display_name",
    "filters",
    "scene_filters",
    "skill_id",
    "skill_version",
)
REQUIRED_MANIFEST_FILTER_FIELDS = (
    "filter_id",
    "display_name",
    "flut_file",
    "source_cube",
    "reason",
)
MANIFEST_INDEX_MISMATCH_CODES = {
    "manifest_missing_filter",
    "index_missing_filter",
    "manifest_index_display_name_mismatch",
    "manifest_index_flut_file_mismatch",
    "scene_filter_unknown_filter_id",
}


def validate_catalog_bundle(
    *,
    index_path: Path | str,
    catalog: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    path = Path(index_path).expanduser().resolve()
    requested_catalog = normalize_catalog_name(catalog) if catalog else None
    inferred_catalog = infer_catalog_name(path) if path.exists() else requested_catalog
    resolved_catalog = requested_catalog or inferred_catalog or "leica"
    manifest_path = path.parent / MANIFEST_FILENAME
    runtime_key_path = path.parent / "runtime.key.b64"

    report: dict[str, Any] = {
        "ok": True,
        "catalog": resolved_catalog,
        "requested_catalog": requested_catalog,
        "inferred_catalog": inferred_catalog,
        "index_path": str(path),
        "manifest_path": str(manifest_path),
        "runtime_key_path": str(runtime_key_path),
        "errors": [],
        "warnings": [],
        "summary": {
            "filter_count": 0,
            "flut_count": 0,
            "manifest_present": manifest_path.exists(),
            "runtime_key_present": runtime_key_path.exists(),
        },
    }

    if not path.exists():
        _error(report, f"Index file not found: {path}")
        return _finalize(report, strict=strict)

    raw_index = _load_json(path, report, label="index")
    index_filters = raw_index.get("filters", []) if isinstance(raw_index, dict) else []
    if not isinstance(index_filters, list):
        _error(report, f"Index 'filters' must be a list: {path}")
        index_filters = []

    try:
        filters = load_filter_index(path, catalog=resolved_catalog)
    except Exception as exc:
        _error(report, str(exc))
        filters = []

    filter_ids = [item.get("filter_id") for item in filters if isinstance(item, dict)]
    report["summary"]["filter_count"] = len(filter_ids)
    report["summary"]["flut_count"] = len(
        [item for item in filters if isinstance(item, dict) and item.get("flut_file")]
    )

    if requested_catalog and inferred_catalog and requested_catalog != inferred_catalog:
        _error(
            report,
            f"Catalog mismatch: requested {requested_catalog} but index implies {inferred_catalog}",
        )

    seen_ids: set[str] = set()
    for idx, item in enumerate(index_filters):
        if not isinstance(item, dict):
            _error(report, f"Index filter #{idx} must be an object")
            continue
        filter_id = item.get("filter_id")
        display_name = item.get("display_name")
        flut_file = item.get("flut_file")
        if not isinstance(filter_id, str) or not filter_id.strip():
            _error(report, f"Index filter #{idx} missing filter_id")
            continue
        if filter_id in seen_ids:
            _error(report, f"Index contains duplicate filter_id: {filter_id}")
        seen_ids.add(filter_id)
        if not isinstance(display_name, str) or not display_name.strip():
            _error(report, f"Index filter {filter_id} missing display_name")
        if not isinstance(flut_file, str) or not flut_file.strip():
            _error(report, f"Index filter {filter_id} missing flut_file")
            continue
        flut_path = (path.parent / flut_file).resolve()
        if not flut_path.exists():
            _error(report, f"Missing FLUT file for {filter_id}: {flut_path}")
        elif flut_path.stat().st_size <= 0:
            _error(report, f"Empty FLUT file for {filter_id}: {flut_path}")

    manifest = None
    if manifest_path.exists():
        manifest = _load_json(manifest_path, report, label="manifest")
        if isinstance(manifest, dict):
            _validate_manifest(report, manifest=manifest, index_filter_ids=set(filter_ids))
    elif strict:
        _error(report, f"Manifest file not found: {manifest_path}")
    else:
        _warn(report, f"Manifest file not found: {manifest_path}")

    if runtime_key_path.exists():
        if runtime_key_path.stat().st_size <= 0:
            _error(report, f"Runtime key file is empty: {runtime_key_path}")
    elif strict:
        _error(report, f"Runtime key file not found: {runtime_key_path}")
    else:
        _warn(report, f"Runtime key file not found: {runtime_key_path}")

    return _finalize(report, strict=strict)


def format_validation_report(report: dict[str, Any]) -> str:
    lines = [
        f"[CATALOG VALIDATE] {report['catalog']}",
        f"index={report['index_path']}",
        f"manifest={report['manifest_path']}",
        f"filters={report['summary']['filter_count']} flut={report['summary']['flut_count']}",
    ]
    if report["errors"]:
        lines.append("errors=")
        lines.extend(f"- {item}" for item in report["errors"])
    if report["warnings"]:
        lines.append("warnings=")
        lines.extend(f"- {item}" for item in report["warnings"])
    if not report["errors"] and not report["warnings"]:
        lines.append("status=clean")
    elif not report["errors"]:
        lines.append("status=warnings")
    else:
        lines.append("status=failed")
    return "\n".join(lines)


def doctor_catalog_bundle(
    *,
    index_path: Path | str,
    catalog: str | None = None,
    strict: bool = False,
    favorite_filter_ids: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    validation = validate_catalog_bundle(index_path=index_path, catalog=catalog, strict=strict)
    path = Path(validation["index_path"]).expanduser().resolve()
    manifest_path = Path(validation["manifest_path"]).expanduser().resolve()
    runtime_key_path = Path(validation["runtime_key_path"]).expanduser().resolve()

    index_payload = _read_json_file(path)
    index_filters = _extract_filter_list(index_payload)
    index_filter_map = _build_filter_map(index_filters)
    index_filter_ids = set(index_filter_map)

    manifest_payload = _read_json_file(manifest_path) if manifest_path.exists() else None
    manifest_filters = _extract_filter_list(manifest_payload)
    manifest_filter_map = _build_filter_map(manifest_filters)

    issues: list[dict[str, Any]] = []
    issues.extend(
        analyze_manifest_required_fields(
            manifest=manifest_payload,
            resolved_catalog=validation["catalog"],
            strict=strict,
        )
    )
    issues.extend(
        analyze_runtime_key_file(
            runtime_key_path=runtime_key_path,
            strict=strict,
        )
    )
    issues.extend(
        analyze_manifest_index_mismatches(
            manifest=manifest_payload,
            index_filter_map=index_filter_map,
            manifest_filter_map=manifest_filter_map,
        )
    )
    issues.extend(
        analyze_stale_favorite_candidates(
            index_filter_ids=index_filter_ids,
            favorite_filter_ids=favorite_filter_ids,
            manifest=manifest_payload,
        )
    )

    error_count = sum(1 for item in issues if item["severity"] == "error")
    warning_count = sum(1 for item in issues if item["severity"] == "warning")
    info_count = sum(1 for item in issues if item["severity"] == "info")
    missing_manifest_field_count = sum(
        1 for item in issues if item["code"] in {"manifest_missing_field", "manifest_filter_missing_field"}
    )
    stale_favorites_count = sum(1 for item in issues if item["code"] == "stale_favorite_candidate")
    manifest_index_mismatch_count = sum(1 for item in issues if item["code"] in MANIFEST_INDEX_MISMATCH_CODES)
    missing_key_file = any(item["code"] == "runtime_key_missing" for item in issues)
    validation_error_count = len(validation["errors"])
    validation_warning_count = len(validation["warnings"])

    ok = bool(validation["ok"]) and error_count == 0 and not (strict and warning_count > 0)
    if ok and warning_count == 0:
        status = "clean"
    elif ok:
        status = "warnings"
    else:
        status = "failed"

    return {
        "ok": ok,
        "status": status,
        "strict": strict,
        "catalog": validation["catalog"],
        "requested_catalog": validation["requested_catalog"],
        "inferred_catalog": validation["inferred_catalog"],
        "index_path": validation["index_path"],
        "manifest_path": validation["manifest_path"],
        "runtime_key_path": validation["runtime_key_path"],
        "issues": issues,
        "suggested_fixes": _ordered_unique([item["suggestion"] for item in issues if item.get("suggestion")]),
        "summary": {
            "issue_count": len(issues),
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "validation_error_count": validation_error_count,
            "validation_warning_count": validation_warning_count,
            "missing_manifest_field_count": missing_manifest_field_count,
            "stale_favorites_count": stale_favorites_count,
            "manifest_index_mismatch_count": manifest_index_mismatch_count,
            "missing_key_file": missing_key_file,
        },
        "validation": validation,
    }


def format_doctor_report(report: dict[str, Any]) -> str:
    lines = [
        f"[CATALOG DOCTOR] {report['catalog']}",
        f"index={report['index_path']}",
        f"manifest={report['manifest_path']}",
        f"runtime_key={report['runtime_key_path']}",
        (
            "issues="
            f"{report['summary']['issue_count']} "
            f"errors={report['summary']['error_count']} "
            f"warnings={report['summary']['warning_count']}"
        ),
    ]
    validation = report.get("validation", {})
    validation_errors = validation.get("errors", [])
    validation_warnings = validation.get("warnings", [])
    if validation_errors:
        lines.append("validation_errors=")
        lines.extend(f"- {item}" for item in validation_errors)
    if validation_warnings:
        lines.append("validation_warnings=")
        lines.extend(f"- {item}" for item in validation_warnings)
    if report["issues"]:
        lines.append("findings=")
        for item in report["issues"]:
            lines.append(f"- [{item['severity']}/{item['code']}] {item['message']}")
            if item.get("suggestion"):
                lines.append(f"  fix: {item['suggestion']}")
    lines.append(f"status={report['status']}")
    return "\n".join(lines)


def analyze_manifest_required_fields(
    *,
    manifest: dict[str, Any] | list[Any] | None,
    resolved_catalog: str,
    strict: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    severity_warning = "error" if strict else "warning"
    if manifest is None:
        issues.append(
            _make_issue(
                code="manifest_missing_file",
                severity=severity_warning,
                message="Manifest file is missing.",
                suggestion="Add manifest.json beside index.json with catalog metadata and filters.",
            )
        )
        return issues
    if not isinstance(manifest, dict):
        issues.append(
            _make_issue(
                code="manifest_invalid_type",
                severity="error",
                message="Manifest JSON must be an object.",
                suggestion="Rewrite manifest.json as a JSON object with top-level fields.",
            )
        )
        return issues

    for field in REQUIRED_MANIFEST_FIELDS:
        value = manifest.get(field)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            issues.append(
                _make_issue(
                    code="manifest_missing_field",
                    severity=severity_warning,
                    message=f"Manifest missing required field: {field}",
                    suggestion=f"Add '{field}' to manifest.json.",
                    context={"field": field},
                )
            )

    manifest_catalog = manifest.get("catalog")
    if isinstance(manifest_catalog, str) and manifest_catalog.strip():
        normalized_catalog = normalize_catalog_name(manifest_catalog)
        if normalized_catalog != resolved_catalog:
            issues.append(
                _make_issue(
                    code="manifest_catalog_mismatch",
                    severity="warning",
                    message=(
                        f"Manifest catalog ({normalized_catalog}) does not match resolved catalog "
                        f"({resolved_catalog})."
                    ),
                    suggestion=(
                        f"Update manifest 'catalog' to '{resolved_catalog}' or run doctor with "
                        f"--catalog {normalized_catalog}."
                    ),
                    context={"manifest_catalog": normalized_catalog, "resolved_catalog": resolved_catalog},
                )
            )

    filters = manifest.get("filters")
    if not isinstance(filters, list):
        return issues
    for idx, item in enumerate(filters):
        if not isinstance(item, dict):
            issues.append(
                _make_issue(
                    code="manifest_filter_invalid_type",
                    severity="error",
                    message=f"Manifest filter #{idx} must be an object.",
                    suggestion=f"Rewrite filters[{idx}] as an object with required fields.",
                    context={"index": idx},
                )
            )
            continue
        filter_id = item.get("filter_id")
        filter_label = filter_id if isinstance(filter_id, str) and filter_id.strip() else f"#{idx}"
        for field in REQUIRED_MANIFEST_FILTER_FIELDS:
            value = item.get(field)
            missing = value is None or (isinstance(value, str) and not value.strip())
            if missing:
                issues.append(
                    _make_issue(
                        code="manifest_filter_missing_field",
                        severity=severity_warning,
                        message=f"Manifest filter {filter_label} missing required field: {field}",
                        suggestion=f"Add '{field}' for manifest filter {filter_label}.",
                        context={"filter_id": filter_label, "field": field},
                    )
                )
    return issues


def analyze_stale_favorite_candidates(
    *,
    index_filter_ids: set[str],
    favorite_filter_ids: list[str] | set[str] | None,
    manifest: dict[str, Any] | list[Any] | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    candidate_sources: list[tuple[str, list[str]]] = []
    if favorite_filter_ids is not None:
        candidate_sources.append(("favorite_filter_ids", _normalize_filter_ids(favorite_filter_ids)))

    if isinstance(manifest, dict):
        manifest_candidates = manifest.get("favorite_candidates")
        if isinstance(manifest_candidates, list):
            candidate_sources.append(("manifest.favorite_candidates", _normalize_filter_ids(manifest_candidates)))

    for source_name, candidates in candidate_sources:
        stale_ids = sorted({item for item in candidates if item not in index_filter_ids})
        for filter_id in stale_ids:
            issues.append(
                _make_issue(
                    code="stale_favorite_candidate",
                    severity="warning",
                    message=f"Favorite candidate not found in index: {filter_id}",
                    suggestion=f"Remove '{filter_id}' from {source_name} or add it to index.json.",
                    context={"filter_id": filter_id, "source": source_name},
                )
            )
    return issues


def analyze_runtime_key_file(
    *,
    runtime_key_path: Path,
    strict: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    severity_warning = "error" if strict else "warning"
    if not runtime_key_path.exists():
        issues.append(
            _make_issue(
                code="runtime_key_missing",
                severity=severity_warning,
                message="Runtime key file is missing.",
                suggestion="Create runtime.key.b64 beside index.json before encrypted FLUT rendering.",
            )
        )
        return issues
    if runtime_key_path.stat().st_size <= 0:
        issues.append(
            _make_issue(
                code="runtime_key_empty",
                severity="error",
                message="Runtime key file is empty.",
                suggestion="Write a valid base64 key into runtime.key.b64.",
            )
        )
        return issues
    text = runtime_key_path.read_text(encoding="utf-8").strip()
    if not text:
        issues.append(
            _make_issue(
                code="runtime_key_empty",
                severity="error",
                message="Runtime key file is empty.",
                suggestion="Write a valid base64 key into runtime.key.b64.",
            )
        )
        return issues
    try:
        base64.b64decode(text, validate=True)
    except Exception:
        issues.append(
            _make_issue(
                code="runtime_key_invalid_base64",
                severity="error",
                message="Runtime key file is not valid base64.",
                suggestion="Regenerate runtime.key.b64 with a valid base64-encoded key.",
            )
        )
    return issues


def analyze_manifest_index_mismatches(
    *,
    manifest: dict[str, Any] | list[Any] | None,
    index_filter_map: dict[str, dict[str, Any]],
    manifest_filter_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(manifest, dict):
        return issues

    index_ids = set(index_filter_map)
    manifest_ids = set(manifest_filter_map)
    for filter_id in sorted(index_ids - manifest_ids):
        issues.append(
            _make_issue(
                code="manifest_missing_filter",
                severity="warning",
                message=f"Index filter missing from manifest: {filter_id}",
                suggestion=f"Add filter '{filter_id}' to manifest.json filters list.",
                context={"filter_id": filter_id},
            )
        )
    for filter_id in sorted(manifest_ids - index_ids):
        issues.append(
            _make_issue(
                code="index_missing_filter",
                severity="warning",
                message=f"Manifest filter missing from index: {filter_id}",
                suggestion=f"Add '{filter_id}' to index.json or remove stale manifest entry.",
                context={"filter_id": filter_id},
            )
        )

    for filter_id in sorted(index_ids & manifest_ids):
        index_item = index_filter_map[filter_id]
        manifest_item = manifest_filter_map[filter_id]
        index_display_name = index_item.get("display_name")
        manifest_display_name = manifest_item.get("display_name")
        if (
            isinstance(index_display_name, str)
            and isinstance(manifest_display_name, str)
            and index_display_name.strip()
            and manifest_display_name.strip()
            and index_display_name != manifest_display_name
        ):
            issues.append(
                _make_issue(
                    code="manifest_index_display_name_mismatch",
                    severity="warning",
                    message=(
                        f"display_name mismatch for {filter_id}: "
                        f"index={index_display_name!r}, manifest={manifest_display_name!r}"
                    ),
                    suggestion=f"Unify display_name for '{filter_id}' across index.json and manifest.json.",
                    context={"filter_id": filter_id},
                )
            )
        index_flut_file = index_item.get("flut_file")
        manifest_flut_file = manifest_item.get("flut_file")
        if (
            isinstance(index_flut_file, str)
            and isinstance(manifest_flut_file, str)
            and index_flut_file.strip()
            and manifest_flut_file.strip()
            and index_flut_file != manifest_flut_file
        ):
            issues.append(
                _make_issue(
                    code="manifest_index_flut_file_mismatch",
                    severity="warning",
                    message=(
                        f"flut_file mismatch for {filter_id}: "
                        f"index={index_flut_file!r}, manifest={manifest_flut_file!r}"
                    ),
                    suggestion=f"Point '{filter_id}' to the same flut_file in index.json and manifest.json.",
                    context={"filter_id": filter_id},
                )
            )

    scene_filters = manifest.get("scene_filters")
    if scene_filters is None:
        return issues
    if not isinstance(scene_filters, dict):
        return issues
    known_ids = set(manifest_filter_map)
    for scene, scene_ids in scene_filters.items():
        if not isinstance(scene, str) or not isinstance(scene_ids, list):
            continue
        for filter_id in scene_ids:
            if isinstance(filter_id, str) and filter_id and filter_id not in known_ids:
                issues.append(
                    _make_issue(
                        code="scene_filter_unknown_filter_id",
                        severity="error",
                        message=f"scene_filters[{scene!r}] references unknown filter_id: {filter_id}",
                        suggestion=f"Remove '{filter_id}' from scene_filters[{scene!r}] or add it to manifest filters.",
                        context={"scene": scene, "filter_id": filter_id},
                    )
                )
    return issues


def _validate_manifest(
    report: dict[str, Any],
    *,
    manifest: dict[str, Any],
    index_filter_ids: set[str],
) -> None:
    filters = manifest.get("filters", [])
    if not isinstance(filters, list):
        _error(report, "Manifest 'filters' must be a list")
        return

    manifest_ids: list[str] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(filters):
        if not isinstance(item, dict):
            _error(report, f"Manifest filter #{idx} must be an object")
            continue
        filter_id = item.get("filter_id")
        if not isinstance(filter_id, str) or not filter_id.strip():
            _error(report, f"Manifest filter #{idx} missing filter_id")
            continue
        if filter_id in seen_ids:
            _error(report, f"Manifest contains duplicate filter_id: {filter_id}")
        seen_ids.add(filter_id)
        manifest_ids.append(filter_id)

    missing_in_manifest = sorted(index_filter_ids - set(manifest_ids))
    missing_in_index = sorted(set(manifest_ids) - index_filter_ids)
    for filter_id in missing_in_manifest:
        _warn(report, f"Index filter missing from manifest: {filter_id}")
    for filter_id in missing_in_index:
        _warn(report, f"Manifest filter missing from index: {filter_id}")

    scene_filters = manifest.get("scene_filters", {})
    if scene_filters is None:
        scene_filters = {}
    if not isinstance(scene_filters, dict):
        _error(report, "Manifest 'scene_filters' must be an object")
        return
    for scene, filter_ids in scene_filters.items():
        if not isinstance(scene, str) or not isinstance(filter_ids, list):
            _error(report, f"Manifest scene_filters entry is invalid for {scene!r}")
            continue
        for filter_id in filter_ids:
            if filter_id not in seen_ids:
                _error(report, f"Manifest scene_filters[{scene!r}] references unknown filter_id: {filter_id}")


def _load_json(path: Path, report: dict[str, Any], *, label: str) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _error(report, f"Invalid {label} JSON: {path}: {exc}")
        return None


def _read_json_file(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _extract_filter_list(payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    filters = payload.get("filters")
    if not isinstance(filters, list):
        return []
    return [item for item in filters if isinstance(item, dict)]


def _build_filter_map(filters: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for item in filters:
        filter_id = item.get("filter_id")
        if isinstance(filter_id, str) and filter_id.strip() and filter_id not in mapped:
            mapped[filter_id] = item
    return mapped


def _normalize_filter_ids(raw_filter_ids: list[Any] | set[Any] | tuple[Any, ...]) -> list[str]:
    normalized: list[str] = []
    for item in raw_filter_ids:
        if not isinstance(item, str):
            continue
        token = item.strip()
        if token:
            normalized.append(token)
    return normalized


def _make_issue(
    *,
    code: str,
    severity: str,
    message: str,
    suggestion: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
        "context": context or {},
    }


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        token = str(item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _warn(report: dict[str, Any], message: str) -> None:
    report["warnings"].append(message)


def _error(report: dict[str, Any], message: str) -> None:
    report["errors"].append(message)


def _finalize(report: dict[str, Any], *, strict: bool) -> dict[str, Any]:
    if strict and report["warnings"]:
        report["errors"].extend(report["warnings"])
        report["warnings"] = []
    report["ok"] = not report["errors"]
    return report
