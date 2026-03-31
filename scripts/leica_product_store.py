"""Persistent product state for the DAVINCI CLI."""

from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFILE_FILENAME = "profile.json"
FAVORITES_FILENAME = "favorites.json"
HISTORY_FILENAME = "history.json"
CURRENT_SESSION_FILENAME = "current_session"
WORKSPACE_META_FILENAME = "workspace.json"
ACTIVATION_FILENAME = "activation.json"
SESSIONS_DIRNAME = "sessions"
MAX_HISTORY_ENTRIES = 200
DEFAULT_WORKSPACE = "default"
WORKSPACE_METADATA_DEFAULT: dict[str, Any] = {
    "current": DEFAULT_WORKSPACE,
    "workspaces": {},
}
MAX_HISTORY_ENTRIES = 200

DEFAULT_PROFILE: dict[str, Any] = {
    "version": 1,
    "default_catalog": "leica",
    "intensity": 0.85,
    "algorithm": "tetrahedral",
    "experience": "studio",
    "theme": "blackroom",
    "top_k": 3,
}

DEFAULT_FAVORITES: dict[str, Any] = {
    "version": 1,
    "updated_at": None,
    "catalogs": {},
}

DEFAULT_ACTIVATION: dict[str, Any] = {
    "version": 1,
    "activated": False,
    "activated_at": None,
    "activation_url": None,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_cli_home() -> Path:
    for env_name in ("DAVINCI_CLI_HOME", "DAVINCI_HOME", "LEICA_CLI_HOME"):
        override = os.environ.get(env_name)
        if override:
            return Path(override).expanduser().resolve()

    davinci_home = (Path.home() / ".davinci").resolve()
    legacy_home = (Path.home() / ".leica-skill").resolve()
    if davinci_home.exists():
        return davinci_home
    if legacy_home.exists():
        return legacy_home
    return davinci_home


class ProductStore:
    """Read and write persistent CLI state."""

    def __init__(self, home: Path | str | None = None) -> None:
        self.home = Path(home or default_cli_home()).expanduser().resolve()
        self.sessions_dir = self.home / SESSIONS_DIRNAME
        self.profile_path = self.home / PROFILE_FILENAME
        self.favorites_path = self.home / FAVORITES_FILENAME
        self.history_path = self.home / HISTORY_FILENAME
        self.current_session_path = self.home / CURRENT_SESSION_FILENAME
        self.workspace_meta_path = self.home / WORKSPACE_META_FILENAME
        self.activation_path = self.home / ACTIVATION_FILENAME
        self._warnings: list[str] = []

    def ensure_home(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_meta_path.parent.mkdir(parents=True, exist_ok=True)

    def consume_warnings(self) -> list[str]:
        warnings = list(self._warnings)
        self._warnings.clear()
        return warnings

    def load_profile(self) -> dict[str, Any]:
        data = self._read_json_file(self.profile_path, default=deepcopy(DEFAULT_PROFILE))
        profile = deepcopy(DEFAULT_PROFILE)
        if isinstance(data, dict):
            profile.update({key: value for key, value in data.items() if value is not None})
        return self._normalize_profile(profile)

    def save_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_profile(profile)
        self._write_json_file(self.profile_path, normalized)
        return normalized

    def reset_profile(self) -> dict[str, Any]:
        return self.save_profile(deepcopy(DEFAULT_PROFILE))

    def load_favorites(self) -> dict[str, Any]:
        data = self._read_json_file(self.favorites_path, default=deepcopy(DEFAULT_FAVORITES))
        favorites = deepcopy(DEFAULT_FAVORITES)
        if isinstance(data, dict):
            favorites.update({key: value for key, value in data.items() if value is not None})
        catalogs = favorites.get("catalogs")
        if not isinstance(catalogs, dict):
            catalogs = {}
        normalized_catalogs: dict[str, list[str]] = {}
        for catalog, filter_ids in catalogs.items():
            if not isinstance(catalog, str) or not catalog.strip():
                continue
            normalized_catalogs[catalog] = _dedupe_strings(filter_ids if isinstance(filter_ids, list) else [])
        favorites["catalogs"] = normalized_catalogs
        return favorites

    def save_favorites(self, favorites: dict[str, Any]) -> dict[str, Any]:
        normalized = self.load_favorites()
        if isinstance(favorites, dict):
            catalogs = favorites.get("catalogs")
            if isinstance(catalogs, dict):
                normalized["catalogs"] = {
                    str(catalog): _dedupe_strings(filter_ids if isinstance(filter_ids, list) else [])
                    for catalog, filter_ids in catalogs.items()
                    if str(catalog).strip()
                }
        normalized["updated_at"] = utc_now_iso()
        self._write_json_file(self.favorites_path, normalized)
        return normalized

    def list_favorites(self, catalog: str | None = None) -> list[str]:
        favorites = self.load_favorites()["catalogs"]
        if catalog is None:
            merged: list[str] = []
            for filter_ids in favorites.values():
                for filter_id in filter_ids:
                    if filter_id not in merged:
                        merged.append(filter_id)
            return merged
        return list(favorites.get(catalog, []))

    def add_favorite(self, *, catalog: str, filter_id: str) -> dict[str, Any]:
        favorites = self.load_favorites()
        current = favorites["catalogs"].setdefault(catalog, [])
        if filter_id not in current:
            current.append(filter_id)
        return self.save_favorites(favorites)

    def remove_favorite(self, *, catalog: str, filter_id: str) -> dict[str, Any]:
        favorites = self.load_favorites()
        current = favorites["catalogs"].setdefault(catalog, [])
        favorites["catalogs"][catalog] = [item for item in current if item != filter_id]
        if not favorites["catalogs"][catalog]:
            favorites["catalogs"].pop(catalog, None)
        return self.save_favorites(favorites)

    def clear_favorites(self, *, catalog: str | None = None) -> dict[str, Any]:
        if catalog is None:
            return self.save_favorites(deepcopy(DEFAULT_FAVORITES))
        favorites = self.load_favorites()
        favorites["catalogs"].pop(catalog, None)
        return self.save_favorites(favorites)

    def load_history(self) -> list[dict[str, Any]]:
        data = self._read_json_file(self.history_path, default=[])
        if not isinstance(data, list):
            self._warnings.append(f"History store was invalid and has been reset: {self.history_path}")
            return []
        entries = [item for item in data if isinstance(item, dict)]
        entries.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
        return entries

    def append_history(self, event: dict[str, Any]) -> dict[str, Any]:
        history = self.load_history()
        payload = dict(event)
        payload.setdefault("event_id", uuid.uuid4().hex[:12])
        payload.setdefault("timestamp", utc_now_iso())
        history.insert(0, payload)
        history = history[:MAX_HISTORY_ENTRIES]
        self._write_json_file(self.history_path, history)
        return payload

    def clear_history(self) -> None:
        self._write_json_file(self.history_path, [])

    def load_activation(self) -> dict[str, Any]:
        data = self._read_json_file(self.activation_path, default=deepcopy(DEFAULT_ACTIVATION))
        activation = deepcopy(DEFAULT_ACTIVATION)
        if isinstance(data, dict):
            activation.update({key: value for key, value in data.items() if value is not None})
        activation["activated"] = bool(activation.get("activated"))
        activation["activated_at"] = activation.get("activated_at")
        activation["activation_url"] = activation.get("activation_url")
        activation["version"] = 1
        return activation

    def is_activated(self) -> bool:
        return bool(self.load_activation().get("activated"))

    def mark_activated(self, *, activation_url: str | None = None) -> dict[str, Any]:
        activation = self.load_activation()
        activation["activated"] = True
        activation["activated_at"] = utc_now_iso()
        activation["activation_url"] = activation_url
        self._write_json_file(self.activation_path, activation)
        return activation

    def reset_activation(self) -> dict[str, Any]:
        self._write_json_file(self.activation_path, deepcopy(DEFAULT_ACTIVATION))
        return self.load_activation()

    def create_session(
        self,
        *,
        input_path: str,
        catalog: str,
        index_path: str,
        output_dir: str,
        theme: str,
    ) -> dict[str, Any]:
        session_id = uuid.uuid4().hex[:12]
        workspace = self.current_workspace()
        payload = {
            "version": 1,
            "session_id": session_id,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "input_path": input_path,
            "catalog": catalog,
            "index_path": index_path,
            "output_dir": output_dir,
            "theme": theme,
            "workspace": workspace,
            "scene": None,
            "recommended_filters": [],
            "contact_sheet_path": None,
            "selected_filter": None,
            "applied": [],
            "cursor": -1,
            "events": [],
        }
        self.save_session(payload)
        self._write_text_file(self.current_session_path, session_id + "\n")
        return payload

    def load_session(self, session_id: str | None = None) -> dict[str, Any] | None:
        target_id = session_id or self.current_session_id()
        if not target_id:
            return None
        path = self.sessions_dir / f"{target_id}.json"
        if not path.exists():
            return None
        data = self._read_json_file(path, default=None)
        return data if isinstance(data, dict) else None

    def save_session(self, session: dict[str, Any]) -> dict[str, Any]:
        payload = dict(session)
        payload["updated_at"] = utc_now_iso()
        path = self.sessions_dir / f"{payload['session_id']}.json"
        self._write_json_file(path, payload)
        self._write_text_file(self.current_session_path, payload["session_id"] + "\n")
        return payload

    def current_session_id(self) -> str | None:
        if not self.current_session_path.exists():
            return None
        token = self.current_session_path.read_text(encoding="utf-8").strip()
        return token or None

    def list_sessions(self) -> list[dict[str, Any]]:
        self.ensure_home()
        sessions: list[dict[str, Any]] = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            data = self._read_json_file(path, default=None)
            if isinstance(data, dict):
                sessions.append(data)
        sessions.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return sessions

    def _workspace_meta(self) -> dict[str, Any]:
        raw = self._read_json_file(self.workspace_meta_path, default=deepcopy(WORKSPACE_METADATA_DEFAULT))
        if not isinstance(raw, dict):
            self._warnings.append(f"Invalid workspace metadata ignored: {self.workspace_meta_path}")
            return deepcopy(WORKSPACE_METADATA_DEFAULT)

        current = self._normalize_workspace_name(raw.get("current"))
        raw_workspaces = raw.get("workspaces")
        if not isinstance(raw_workspaces, dict):
            self._warnings.append(f"Invalid workspace list ignored: {self.workspace_meta_path}")
            raw_workspaces = {}

        workspaces: dict[str, dict[str, Any]] = {}
        for name, item in raw_workspaces.items():
            normalized_name = self._normalize_workspace_name(name)
            payload = item if isinstance(item, dict) else {}
            workspaces[normalized_name] = {
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "description": str(payload.get("description") or ""),
            }

        return {
            "current": current,
            "workspaces": workspaces,
        }

    def _write_workspace_meta(self, payload: dict[str, Any]) -> None:
        self._write_json_file(self.workspace_meta_path, payload)

    def current_workspace(self) -> str:
        meta = self._workspace_meta()
        current = meta.get("current")
        return self._normalize_workspace_name(str(current)) if current else DEFAULT_WORKSPACE

    def set_current_workspace(self, name: str) -> str:
        normalized = self._normalize_workspace_name(name)
        meta = self._workspace_meta()
        workspaces = meta.setdefault("workspaces", {})
        ws_entry = workspaces.setdefault(
            normalized,
            {
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "description": "",
            },
        )
        ws_entry["updated_at"] = utc_now_iso()
        meta["current"] = normalized
        self._write_workspace_meta(meta)
        return normalized

    def list_workspaces(self) -> list[str]:
        meta = self._workspace_meta()
        workspaces = meta.get("workspaces", {})
        return sorted(workspaces.keys())

    def workspace_status(self, name: str | None = None) -> dict[str, Any]:
        workspace = self._normalize_workspace_name(name) if name else self.current_workspace()
        sessions = self.sessions_by_workspace(workspace, include_closed=False)
        closed = self.sessions_by_workspace(workspace, include_closed=True)
        return {
            "workspace": workspace,
            "active_sessions": len(sessions),
            "closed_sessions": len([item for item in closed if item.get("closed_at")]),
            "last_updated": sessions[0].get("updated_at") if sessions else None,
        }

    def sessions_by_workspace(self, workspace: str, *, include_closed: bool = True) -> list[dict[str, Any]]:
        normalized = self._normalize_workspace_name(workspace)
        entries = []
        for session in self.list_sessions():
            session_workspace = self._normalize_workspace_name(session.get("workspace") or DEFAULT_WORKSPACE)
            if session_workspace != normalized:
                continue
            if not include_closed and session.get("closed_at"):
                continue
            entries.append(session)
        return entries

    def mark_session_closed(self, session_id: str, *, reason: str | None = None) -> dict[str, Any] | None:
        session = self.load_session(session_id)
        if not session:
            return None
        session.setdefault("closed_at", utc_now_iso())
        if reason and not session.get("close_reason"):
            session["close_reason"] = reason
        self.save_session(session)
        return session

    def _normalize_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(DEFAULT_PROFILE)
        normalized.update({key: value for key, value in profile.items() if value is not None})
        normalized["default_catalog"] = str(normalized["default_catalog"]).strip().lower() or "leica"
        normalized["intensity"] = max(
            0.0,
            min(self._coerce_float(normalized["intensity"], DEFAULT_PROFILE["intensity"], "profile.intensity"), 1.0),
        )
        normalized["algorithm"] = (
            "trilinear" if str(normalized["algorithm"]).strip().lower() == "trilinear" else "tetrahedral"
        )
        normalized["experience"] = (
            "auto" if str(normalized["experience"]).strip().lower() == "auto" else "studio"
        )
        theme = str(normalized["theme"]).strip().lower()
        normalized["theme"] = theme if theme in {"blackroom", "minimal", "cipher"} else "blackroom"
        normalized["top_k"] = max(1, self._coerce_int(normalized["top_k"], DEFAULT_PROFILE["top_k"], "profile.top_k"))
        normalized["version"] = 1
        return normalized

    def _normalize_workspace_name(self, name: str | None) -> str:
        if not name:
            return DEFAULT_WORKSPACE
        token = str(name).strip().lower()
        return token if token else DEFAULT_WORKSPACE

    def _read_json_file(self, path: Path, *, default: Any) -> Any:
        if not path.exists():
            return deepcopy(default)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._warnings.append(f"Corrupted JSON detected and ignored: {path}")
            return deepcopy(default)

    def _coerce_float(self, value: Any, default: float, field: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            self._warnings.append(f"Invalid numeric value reset for {field}")
            return float(default)

    def _coerce_int(self, value: Any, default: int, field: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            self._warnings.append(f"Invalid integer value reset for {field}")
            return int(default)

    def _write_json_file(self, path: Path, payload: Any) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._atomic_write(path, serialized)

    def _write_text_file(self, path: Path, payload: str) -> None:
        self._atomic_write(path, payload)

    def _atomic_write(self, path: Path, payload: str) -> None:
        self.ensure_home()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(path)


def _dedupe_strings(values: list[Any]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        token = value.strip()
        if token and token not in deduped:
            deduped.append(token)
    return deduped
