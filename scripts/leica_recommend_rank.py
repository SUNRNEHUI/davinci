"""Recommendation reranking helpers for product behavior."""

from __future__ import annotations

from typing import Any


def apply_favorite_boost(
    filters: list[dict[str, Any]],
    *,
    favorite_filter_ids: list[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    favorite_ids = {item for item in (favorite_filter_ids or []) if isinstance(item, str) and item.strip()}
    if not favorite_ids:
        return [dict(item, favorite_boost=False) for item in filters]

    boosted: list[dict[str, Any]] = []
    regular: list[dict[str, Any]] = []
    for item in filters:
        entry = dict(item)
        entry["favorite_boost"] = entry.get("filter_id") in favorite_ids
        if entry["favorite_boost"]:
            boosted.append(entry)
        else:
            regular.append(entry)
    return boosted + regular
