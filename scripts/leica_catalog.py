"""Shared FLUT catalog helpers for CLI and pipeline flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .runtime_paths import catalog_root
except ImportError:  # pragma: no cover - script execution fallback
    from runtime_paths import catalog_root

CATALOG_ROOT = catalog_root()
DEFAULT_CATALOG = "leica"
CATALOG_ALIASES = {
    "fujifilm": "fuji",
}
MANIFEST_FILENAME = "manifest.json"

CATALOG_REASON_MAPS: dict[str, dict[str, str]] = {
    "leica": {
        "leica_leica_bw_hc": "Deep blacks for street and structure.",
        "leica_leica_bw_nat": "Gentle mono for portraits and skin.",
        "leica_leica_bleach": "Desaturated grit for harsh light.",
        "leica_leica_blue": "Cool cast for rain, dusk and glass.",
        "leica_leica_brass": "Warm golden tone for interiors.",
        "leica_leica_chrome": "Punchy contrast for clean daylight.",
        "leica_leica_classic": "Balanced Leica look, easy default.",
        "leica_leica_contemporary": "Modern palette for design scenes.",
        "leica_leica_eternal": "Soft nostalgia for quiet moments.",
        "leica_leica_greg_williams": "Cinematic portrait rendering.",
        "leica_leica_nat": "Neutral color when subtle wins.",
        "leica_leica_selenium": "Warm mono depth for moody frames.",
        "leica_leica_sepia": "Vintage brown tone for memory shots.",
        "leica_leica_teal": "Cool separation for coast and city.",
        "leica_leica_vivid": "Higher color energy for landscapes.",
    },
}

CATALOG_FAMILY_LABELS: dict[str, str] = {
    "leica": "Leica",
    "fuji": "Fuji",
    "kodak": "Kodak",
}

CATALOG_FAMILY_SUMMARIES: dict[str, str] = {
    "leica": "更纪实、更有层次、更适合氛围和黑白。",
    "fuji": "更清透、更日常、更像胶片直出。",
    "kodak": "更暖、更复古、更有回忆感。",
}

CATALOG_FAMILY_GUIDES: dict[str, dict[str, Any]] = {
    "leica": {
        "when_to_choose": "想要更有氛围、层次、黑白、纪实感时。",
        "best_for": ["街头", "建筑", "情绪人像"],
        "ask_for": ["看莱卡", "更有氛围", "来点黑白"],
    },
    "fuji": {
        "when_to_choose": "想要更自然、清透、日常、像直出的胶片感时。",
        "best_for": ["旅行", "日常", "轻人像"],
        "ask_for": ["看富士", "更自然", "更像胶片直出"],
    },
    "kodak": {
        "when_to_choose": "想要更暖、更旧、更像回忆照片时。",
        "best_for": ["旅行", "生活感", "复古照片"],
        "ask_for": ["看柯达", "更复古", "更暖一点"],
    },
}

BEGINNER_FILTER_METADATA: dict[str, dict[str, Any]] = {
    "leica_leica_bw_hc": {
        "plain_name": "黑白纪实",
        "effect_summary": "对比更强、层次更硬、情绪更重。",
        "best_for": ["街头", "建筑", "纪实"],
        "intent_tags": ["mono", "documentary", "contrast", "moody"],
    },
    "leica_leica_bw_nat": {
        "plain_name": "柔和黑白",
        "effect_summary": "黑白更柔和，肤色和层次更耐看。",
        "best_for": ["人像", "日常", "安静场景"],
        "intent_tags": ["mono", "portrait", "gentle", "natural"],
    },
    "leica_leica_bleach": {
        "plain_name": "低饱和情绪感",
        "effect_summary": "颜色更灰、更克制，情绪感更重。",
        "best_for": ["街头", "阴天", "情绪片"],
        "intent_tags": ["vintage", "cool", "moody", "film"],
    },
    "leica_leica_blue": {
        "plain_name": "冷调电影感",
        "effect_summary": "整体更冷，玻璃、雨天和城市感更明显。",
        "best_for": ["城市", "雨天", "夜景边缘"],
        "intent_tags": ["cool", "cinematic", "urban"],
    },
    "leica_leica_brass": {
        "plain_name": "暖金室内",
        "effect_summary": "偏暖偏金，室内和灯光更有质感。",
        "best_for": ["室内", "咖啡馆", "暖光"],
        "intent_tags": ["warm", "interior", "vintage"],
    },
    "leica_leica_chrome": {
        "plain_name": "通透高对比",
        "effect_summary": "更利落、更通透，白天画面更抓眼。",
        "best_for": ["城市", "白天", "建筑"],
        "intent_tags": ["clean", "contrast", "natural"],
    },
    "leica_leica_classic": {
        "plain_name": "自然经典",
        "effect_summary": "平衡、稳定、好上手，适合大多数照片。",
        "best_for": ["日常", "通用", "初次尝试"],
        "intent_tags": ["natural", "balanced", "clean"],
    },
    "leica_leica_contemporary": {
        "plain_name": "现代冷静感",
        "effect_summary": "更现代、更利落，适合设计感场景。",
        "best_for": ["建筑", "室内", "设计画面"],
        "intent_tags": ["clean", "cool", "design"],
    },
    "leica_leica_eternal": {
        "plain_name": "怀旧柔雾",
        "effect_summary": "更柔和、更怀旧，像被时间磨过一层。",
        "best_for": ["旅行", "生活感", "回忆感"],
        "intent_tags": ["vintage", "film", "soft", "warm"],
    },
    "leica_leica_greg_williams": {
        "plain_name": "电影人像",
        "effect_summary": "人像更像电影剧照，氛围感更强。",
        "best_for": ["人像", "街拍", "人物特写"],
        "intent_tags": ["portrait", "cinematic", "film"],
    },
    "leica_leica_nat": {
        "plain_name": "自然轻调",
        "effect_summary": "改动克制，保留真实质感。",
        "best_for": ["日常", "人像", "记录"],
        "intent_tags": ["natural", "clean", "subtle"],
    },
    "leica_leica_selenium": {
        "plain_name": "暖调黑白",
        "effect_summary": "黑白里带一点暖意，情绪更深。",
        "best_for": ["街头", "人像", "怀旧氛围"],
        "intent_tags": ["mono", "warm", "vintage", "moody"],
    },
    "leica_leica_sepia": {
        "plain_name": "复古棕调",
        "effect_summary": "偏棕偏旧，像老相册里的照片。",
        "best_for": ["回忆感", "旅行", "生活照片"],
        "intent_tags": ["vintage", "warm", "nostalgia", "film"],
    },
    "leica_leica_teal": {
        "plain_name": "青冷城市感",
        "effect_summary": "冷暖分离更明显，城市感更强。",
        "best_for": ["城市", "海边", "设计感场景"],
        "intent_tags": ["cool", "cinematic", "urban"],
    },
    "leica_leica_vivid": {
        "plain_name": "高能彩色",
        "effect_summary": "颜色更亮、更冲，风景更抓眼。",
        "best_for": ["风景", "蓝天", "植物"],
        "intent_tags": ["vivid", "landscape", "color"],
    },
    "fuji_provia": {
        "plain_name": "平衡自然",
        "effect_summary": "均衡、稳妥，适合大多数日常照片。",
        "best_for": ["日常", "旅行", "通用"],
        "intent_tags": ["natural", "balanced", "clean"],
    },
    "fuji_astia": {
        "plain_name": "柔和人像",
        "effect_summary": "肤色更轻、更柔和，适合人物。",
        "best_for": ["人像", "自拍", "日常"],
        "intent_tags": ["portrait", "soft", "clean"],
    },
    "fuji_classic_chrome": {
        "plain_name": "胶片纪实",
        "effect_summary": "低一点饱和，更像纪实胶片。",
        "best_for": ["街头", "旅行", "纪实"],
        "intent_tags": ["film", "vintage", "documentary"],
    },
    "fuji_classic_neg": {
        "plain_name": "暖调负片",
        "effect_summary": "更暖、更旧一点，像被阳光晒过的彩色负片。",
        "best_for": ["旅行", "生活感", "回忆感"],
        "intent_tags": ["warm", "film", "vintage", "nostalgia"],
    },
    "fuji_acros": {
        "plain_name": "富士黑白",
        "effect_summary": "黑白更干净，层次克制，适合纪实和日常。",
        "best_for": ["街头", "纪实", "建筑"],
        "intent_tags": ["mono", "documentary", "clean"],
    },
    "fuji_eterna": {
        "plain_name": "电影柔灰",
        "effect_summary": "更柔、更灰，电影感更强。",
        "best_for": ["人像", "情绪片", "视频感画面"],
        "intent_tags": ["cinematic", "film", "soft", "cool"],
    },
    "fuji_eterna_bleach_bypass": {
        "plain_name": "漂白旁路",
        "effect_summary": "更硬、更灰、更有情绪压迫感。",
        "best_for": ["城市", "阴天", "情绪片"],
        "intent_tags": ["film", "cool", "moody", "contrast"],
    },
    "fuji_nostalgic_neg": {
        "plain_name": "暖调回忆",
        "effect_summary": "偏暖、偏旧，像被阳光晒过的回忆。",
        "best_for": ["旅行", "生活感", "回忆感"],
        "intent_tags": ["warm", "vintage", "film", "nostalgia"],
    },
    "fuji_pro_neg_hi": {
        "plain_name": "利落人像",
        "effect_summary": "人像更利落，亮部更干净。",
        "best_for": ["人像", "街拍", "日常"],
        "intent_tags": ["portrait", "clean", "contrast"],
    },
    "fuji_pro_neg_std": {
        "plain_name": "自然人像",
        "effect_summary": "克制、自然，肤色更稳。",
        "best_for": ["人像", "日常", "婚礼纪实"],
        "intent_tags": ["portrait", "natural", "subtle"],
    },
    "fuji_reala_ace": {
        "plain_name": "清透彩色",
        "effect_summary": "颜色舒服，通透但不过分。",
        "best_for": ["日常", "旅行", "建筑"],
        "intent_tags": ["clean", "natural", "color"],
    },
    "fuji_velvia": {
        "plain_name": "高饱和风景",
        "effect_summary": "颜色更浓，天空和植物更醒目。",
        "best_for": ["风景", "山水", "植物"],
        "intent_tags": ["vivid", "landscape", "color"],
    },
}

CATALOG_SCENE_FILTERS: dict[str, dict[str, list[str]]] = {
    "leica": {
        "portrait": [
            "leica_leica_classic",
            "leica_leica_bw_nat",
            "leica_leica_greg_williams",
            "leica_leica_chrome",
            "leica_leica_brass",
        ],
        "landscape": [
            "leica_leica_vivid",
            "leica_leica_teal",
            "leica_leica_nat",
            "leica_leica_contemporary",
            "leica_leica_blue",
        ],
        "street": [
            "leica_leica_bw_hc",
            "leica_leica_bleach",
            "leica_leica_selenium",
            "leica_leica_eternal",
            "leica_leica_sepia",
        ],
        "general": [
            "leica_leica_classic",
            "leica_leica_nat",
            "leica_leica_vivid",
            "leica_leica_contemporary",
            "leica_leica_chrome",
            "leica_leica_eternal",
            "leica_leica_brass",
        ],
    },
}


def normalize_catalog_name(catalog: str | None) -> str:
    token = (catalog or DEFAULT_CATALOG).strip().lower()
    token = CATALOG_ALIASES.get(token, token)
    return token or DEFAULT_CATALOG


def shipped_catalog_names() -> list[str]:
    if not CATALOG_ROOT.exists():
        return []
    names = []
    for path in sorted(CATALOG_ROOT.iterdir()):
        if not path.is_dir():
            continue
        if (path / "index.json").exists():
            names.append(path.name)
    return names


def shipped_index_path(catalog: str = DEFAULT_CATALOG) -> Path:
    resolved_catalog = normalize_catalog_name(catalog)
    return CATALOG_ROOT / resolved_catalog / "index.json"


def shipped_manifest_path(catalog: str = DEFAULT_CATALOG) -> Path:
    resolved_catalog = normalize_catalog_name(catalog)
    return CATALOG_ROOT / resolved_catalog / MANIFEST_FILENAME


def infer_catalog_name(index_path: Path | str) -> str:
    path = Path(index_path).expanduser().resolve()
    try:
        relative = path.relative_to(CATALOG_ROOT)
    except ValueError:
        manifest = _load_manifest_file(path.parent / MANIFEST_FILENAME)
        if manifest and manifest.get("catalog"):
            return normalize_catalog_name(str(manifest["catalog"]))
        return normalize_catalog_name(path.parent.name)
    parts = relative.parts
    if parts:
        return normalize_catalog_name(parts[0])
    return DEFAULT_CATALOG


def load_filter_index(
    index_path: Path | str | None = None,
    *,
    catalog: str = DEFAULT_CATALOG,
) -> list[dict[str, Any]]:
    path = Path(index_path or shipped_index_path(catalog)).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    filters = data.get("filters")
    if not isinstance(filters, list):
        raise ValueError(f"Invalid filter index: expected 'filters' list in {path}")

    resolved_catalog = normalize_catalog_name(catalog if index_path is None else infer_catalog_name(path))
    manifest = load_catalog_manifest(index_path=path, catalog=resolved_catalog)
    manifest_filter_map = {
        item["filter_id"]: item
        for item in manifest.get("filters", [])
        if isinstance(item, dict) and item.get("filter_id")
    }

    validated: list[dict[str, Any]] = []
    for idx, item in enumerate(filters):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid filter index entry #{idx}: expected object")
        missing = [key for key in ("filter_id", "display_name") if not item.get(key)]
        if missing:
            raise ValueError(
                f"Invalid filter index entry #{idx}: missing required fields {', '.join(missing)}"
            )
        entry = dict(item)
        manifest_entry = manifest_filter_map.get(entry["filter_id"], {})
        entry.update({key: value for key, value in manifest_entry.items() if key not in {"flut_file"}})
        entry.setdefault("catalog", resolved_catalog)
        validated.append(entry)
    return resolve_filter_paths(validated, index_path=path)


def resolve_filter_paths(
    filters: list[dict[str, Any]],
    *,
    index_path: Path,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    base_dir = index_path.parent
    catalog = infer_catalog_name(index_path)
    for item in filters:
        entry = dict(item)
        entry.setdefault("catalog", catalog)
        flut_file = entry.get("flut_file")
        if flut_file:
            flut_path = Path(str(flut_file))
            if not flut_path.is_absolute():
                flut_path = (base_dir / flut_path).resolve()
            entry["flut_file"] = str(flut_path)
        resolved.append(entry)
    return resolved


def load_catalog_manifest(
    *,
    catalog: str | None = None,
    index_path: Path | str | None = None,
) -> dict[str, Any]:
    if index_path is not None:
        path = Path(index_path).expanduser().resolve()
        return _load_manifest_near_index(path, catalog=normalize_catalog_name(catalog) if catalog else None)

    resolved_catalog = normalize_catalog_name(catalog)
    return _load_manifest_file(shipped_manifest_path(resolved_catalog)) or {}


def scene_filters_for_catalog(
    catalog: str = DEFAULT_CATALOG,
    *,
    index_path: Path | str | None = None,
) -> dict[str, list[str]]:
    resolved_catalog = normalize_catalog_name(catalog)
    manifest = load_catalog_manifest(catalog=resolved_catalog, index_path=index_path)
    scene_filters = manifest.get("scene_filters")
    if _valid_scene_filters(scene_filters):
        return scene_filters
    return CATALOG_SCENE_FILTERS.get(resolved_catalog, CATALOG_SCENE_FILTERS[DEFAULT_CATALOG])


def reason_map_for_catalog(
    catalog: str = DEFAULT_CATALOG,
    *,
    index_path: Path | str | None = None,
) -> dict[str, str]:
    resolved_catalog = normalize_catalog_name(catalog)
    manifest = load_catalog_manifest(catalog=resolved_catalog, index_path=index_path)
    reason_map = dict(CATALOG_REASON_MAPS.get(resolved_catalog, CATALOG_REASON_MAPS[DEFAULT_CATALOG]))
    for item in manifest.get("filters", []):
        if not isinstance(item, dict):
            continue
        filter_id = item.get("filter_id")
        reason = item.get("reason")
        if isinstance(filter_id, str) and filter_id and isinstance(reason, str) and reason.strip():
            reason_map[filter_id] = reason
    return reason_map


def select_recommended_filters(
    *,
    scene_result_dict: dict[str, Any],
    all_filters: list[dict[str, Any]],
    full_preview: bool,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    if full_preview:
        selected = list(all_filters)
    else:
        by_id = {item["filter_id"]: item for item in all_filters}
        scene_ids = scene_result_dict.get("recommended_filters", [])
        recommended = [by_id[item_id] for item_id in scene_ids if item_id in by_id]

        limit = min(6, len(all_filters))
        minimum = min(4, limit)
        target_count = min(max(len(recommended), minimum), limit)

        if len(recommended) < target_count:
            existing_ids = {item["filter_id"] for item in recommended}
            for item in all_filters:
                if item["filter_id"] in existing_ids:
                    continue
                recommended.append(item)
                if len(recommended) >= target_count:
                    break
        selected = recommended or all_filters[:limit]

    if top_k is not None:
        return selected[: max(top_k, 0)]
    return selected


def build_recommendation_details(
    scene: str,
    recommended: list[dict[str, Any]],
    *,
    catalog: str = DEFAULT_CATALOG,
    index_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    resolved_catalog = normalize_catalog_name(catalog)
    reason_map = reason_map_for_catalog(resolved_catalog, index_path=index_path)
    details: list[dict[str, Any]] = []
    for item in recommended:
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            reason = reason_map.get(
                item["filter_id"],
                "Balanced recommendation for this scene.",
            )
        details.append(
            {
                **item,
                "catalog": item.get("catalog", resolved_catalog),
                "scene": scene,
                "reason": reason,
                **beginner_metadata_for_filter(
                    {
                        **item,
                        "catalog": item.get("catalog", resolved_catalog),
                    }
                ),
            }
        )
    return details


def family_label_for_catalog(catalog: str | None) -> str:
    resolved_catalog = normalize_catalog_name(catalog)
    return CATALOG_FAMILY_LABELS.get(resolved_catalog, resolved_catalog.title())


def family_summary_for_catalog(catalog: str | None) -> str:
    resolved_catalog = normalize_catalog_name(catalog)
    return CATALOG_FAMILY_SUMMARIES.get(
        resolved_catalog,
        "这是一组独立风格系列，用来提供不同的颜色方向。",
    )


def beginner_family_descriptions(catalogs: list[str] | None = None) -> list[dict[str, Any]]:
    names = catalogs or shipped_catalog_names()
    output: list[dict[str, Any]] = []
    for name in names:
        catalog = normalize_catalog_name(name)
        guide = CATALOG_FAMILY_GUIDES.get(catalog, {})
        output.append(
            {
                "catalog": catalog,
                "family_name": family_label_for_catalog(name),
                "summary": family_summary_for_catalog(name),
                "when_to_choose": guide.get("when_to_choose") or "想换一个明显不同的颜色方向时。",
                "best_for": list(guide.get("best_for") or ["日常", "通用"]),
                "ask_for": list(guide.get("ask_for") or [f"看{family_label_for_catalog(name)}"]),
            }
        )
    return output


def beginner_metadata_for_filter(item: dict[str, Any]) -> dict[str, Any]:
    filter_id = str(item.get("filter_id") or "").strip()
    catalog = normalize_catalog_name(str(item.get("catalog") or DEFAULT_CATALOG))
    display_name = str(item.get("display_name") or filter_id or family_label_for_catalog(catalog)).strip()
    reason = str(item.get("reason") or "").strip()

    explicit = {}
    for key in ("plain_name", "effect_summary", "best_for", "intent_tags"):
        value = item.get(key)
        if key in {"best_for", "intent_tags"} and isinstance(value, list):
            explicit[key] = [str(token).strip() for token in value if str(token).strip()]
        elif isinstance(value, str) and value.strip():
            explicit[key] = value.strip()

    curated = BEGINNER_FILTER_METADATA.get(filter_id, {})
    merged = {**curated, **explicit}
    fallback = _fallback_beginner_metadata(
        display_name=display_name,
        reason=reason,
        catalog=catalog,
    )
    plain_name = str(merged.get("plain_name") or fallback["plain_name"]).strip()
    effect_summary = str(merged.get("effect_summary") or fallback["effect_summary"]).strip()
    best_for = _normalize_text_list(merged.get("best_for"), fallback["best_for"])
    intent_tags = _normalize_text_list(merged.get("intent_tags"), fallback["intent_tags"])
    return {
        "plain_name": plain_name,
        "effect_summary": effect_summary,
        "best_for": best_for,
        "intent_tags": intent_tags,
        "family_name": family_label_for_catalog(catalog),
        "technical_name": display_name,
    }


def find_filter(
    filters: list[dict[str, Any]],
    query: str,
) -> tuple[int, dict[str, Any]]:
    token = query.strip()
    if not token:
        raise ValueError("Filter query cannot be empty")

    number = token[1:] if token.startswith("#") else token
    if number.isdigit():
        idx = int(number) - 1
        if 0 <= idx < len(filters):
            return idx, filters[idx]
        raise ValueError(f"Filter selection out of range: {token}")

    lowered = token.lower()
    for idx, item in enumerate(filters):
        if item["filter_id"].lower() == lowered:
            return idx, item

    normalized = _normalize_filter_token(token)
    exact_display_matches: list[tuple[int, dict[str, Any]]] = []
    partial_matches: list[tuple[int, dict[str, Any]]] = []
    for idx, item in enumerate(filters):
        display_norm = _normalize_filter_token(item["display_name"])
        filter_norm = _normalize_filter_token(item["filter_id"])
        aliases = [
            _normalize_filter_token(alias)
            for alias in item.get("aliases", [])
            if isinstance(alias, str) and alias.strip()
        ]
        if normalized in {display_norm, filter_norm, *aliases}:
            exact_display_matches.append((idx, item))
        elif normalized in display_norm or normalized in filter_norm or any(normalized in alias for alias in aliases):
            partial_matches.append((idx, item))

    if len(exact_display_matches) == 1:
        return exact_display_matches[0]
    if len(partial_matches) == 1:
        return partial_matches[0]
    if exact_display_matches or partial_matches:
        matches = exact_display_matches or partial_matches
        labels = ", ".join(item["display_name"] for _, item in matches[:5])
        raise ValueError(f"Filter query is ambiguous: {query}. Matches: {labels}")

    raise ValueError(f"Unknown filter: {query}")


def _normalize_filter_token(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _valid_scene_filters(scene_filters: Any) -> bool:
    if not isinstance(scene_filters, dict):
        return False
    for scene, filter_ids in scene_filters.items():
        if not isinstance(scene, str) or not isinstance(filter_ids, list):
            return False
        if not all(isinstance(filter_id, str) and filter_id.strip() for filter_id in filter_ids):
            return False
    return True


def _load_manifest_near_index(index_path: Path, *, catalog: str | None) -> dict[str, Any]:
    manifest = _load_manifest_file(index_path.parent / MANIFEST_FILENAME)
    if manifest:
        return manifest
    if catalog:
        return _load_manifest_file(shipped_manifest_path(catalog)) or {}
    return {}


def _load_manifest_file(path: Path) -> dict[str, Any] | None:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid catalog manifest: expected object in {path}")
    filters = data.get("filters", [])
    if filters is not None and not isinstance(filters, list):
        raise ValueError(f"Invalid catalog manifest: expected filters list in {path}")
    return data


def _normalize_text_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        normalized = [str(token).strip() for token in value if str(token).strip()]
        if normalized:
            return normalized
    return list(fallback)


def _fallback_beginner_metadata(
    *,
    display_name: str,
    reason: str,
    catalog: str,
) -> dict[str, Any]:
    token = _normalize_filter_token(display_name)
    if "bw" in token or "black" in token or "mono" in token:
        return {
            "plain_name": "黑白纪实",
            "effect_summary": reason or "黑白更明显，对比和情绪感更强。",
            "best_for": ["街头", "建筑", "纪实"],
            "intent_tags": ["mono", "documentary", "contrast"],
        }
    if "sepia" in token:
        return {
            "plain_name": "复古棕调",
            "effect_summary": reason or "偏棕偏旧，更像老照片。",
            "best_for": ["回忆感", "旅行", "日常"],
            "intent_tags": ["vintage", "warm", "nostalgia"],
        }
    if "vivid" in token or "velvia" in token:
        return {
            "plain_name": "高饱和风景",
            "effect_summary": reason or "颜色更浓，风景更抓眼。",
            "best_for": ["风景", "天空", "植物"],
            "intent_tags": ["vivid", "landscape", "color"],
        }
    if "astia" in token:
        return {
            "plain_name": "柔和人像",
            "effect_summary": reason or "人物更柔和，肤色更耐看。",
            "best_for": ["人像", "自拍", "日常"],
            "intent_tags": ["portrait", "soft", "clean"],
        }
    if "provia" in token or "standard" in token or "classic" in token:
        return {
            "plain_name": "自然经典",
            "effect_summary": reason or "平衡、自然、好上手。",
            "best_for": ["日常", "旅行", "通用"],
            "intent_tags": ["natural", "balanced", "clean"],
        }
    if "eterna" in token or "eternal" in token:
        return {
            "plain_name": "胶片柔雾",
            "effect_summary": reason or "更柔和、更有胶片氛围。",
            "best_for": ["人像", "旅行", "情绪感画面"],
            "intent_tags": ["film", "soft", "vintage"],
        }
    if "chrome" in token:
        return {
            "plain_name": "通透高对比",
            "effect_summary": reason or "更利落、更通透，层次更清楚。",
            "best_for": ["城市", "建筑", "白天"],
            "intent_tags": ["clean", "contrast", "natural"],
        }
    if "bleach" in token:
        return {
            "plain_name": "低饱和情绪感",
            "effect_summary": reason or "颜色更灰更克制，情绪感更强。",
            "best_for": ["街头", "阴天", "情绪片"],
            "intent_tags": ["vintage", "moody", "film"],
        }
    if "blue" in token or "teal" in token:
        return {
            "plain_name": "冷调电影感",
            "effect_summary": reason or "整体更冷，城市和夜色更有氛围。",
            "best_for": ["城市", "海边", "夜色"],
            "intent_tags": ["cool", "cinematic", "urban"],
        }
    if "portrait" in token:
        return {
            "plain_name": "自然人像",
            "effect_summary": reason or "人物更自然，肤色更舒服。",
            "best_for": ["人像", "自拍", "日常"],
            "intent_tags": ["portrait", "natural", "clean"],
        }
    if "landscape" in token:
        return {
            "plain_name": "风景增强",
            "effect_summary": reason or "颜色和层次更适合风景。",
            "best_for": ["风景", "旅行", "户外"],
            "intent_tags": ["landscape", "color", "clean"],
        }
    family_label = family_label_for_catalog(catalog)
    return {
        "plain_name": f"{family_label} 风格",
        "effect_summary": reason or "给这张照片一个更完整的颜色方向。",
        "best_for": ["日常", "通用"],
        "intent_tags": ["balanced", "natural"],
    }
