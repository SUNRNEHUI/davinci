"""Stateful product session flow for the FLUT CLI."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Callable

try:
    from .apply_flut_image import apply_flut_to_image
    from .blackroom_console import StudioConsoleExperience
    from .leica_catalog import (
        build_recommendation_details,
        find_filter,
        load_filter_index,
        scene_filters_for_catalog,
        select_recommended_filters,
    )
    from .leica_pipeline import open_result, run_pipeline
    from .leica_product_store import ProductStore, utc_now_iso
    from .leica_recommend_rank import apply_favorite_boost
    from .scene_analyzer import analyze_scene
except ImportError:  # pragma: no cover - script execution fallback
    from apply_flut_image import apply_flut_to_image
    from blackroom_console import StudioConsoleExperience
    from leica_catalog import (
        build_recommendation_details,
        find_filter,
        load_filter_index,
        scene_filters_for_catalog,
        select_recommended_filters,
    )
    from leica_pipeline import open_result, run_pipeline
    from leica_product_store import ProductStore, utc_now_iso
    from leica_recommend_rank import apply_favorite_boost
    from scene_analyzer import analyze_scene


SessionInput = Callable[[str], str]


class SessionCommandError(ValueError):
    pass


class FilterSession:
    """Interactive or scripted filter workbench."""

    def __init__(
        self,
        *,
        store: ProductStore,
        input_path: Path | str,
        output_dir: Path | str,
        index_path: Path | str,
        catalog: str,
        intensity: float,
        algorithm: str,
        top_k: int,
        theme: str,
        stream: Any,
        input_fn: SessionInput,
        existing_session: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.intensity = intensity
        self.algorithm = algorithm
        self.top_k = max(top_k, 1)
        self.stream = stream
        self.input_fn = input_fn
        self.resumed = existing_session is not None

        if existing_session is not None:
            self.session = dict(existing_session)
            self.input_path = Path(self.session["input_path"]).expanduser().resolve()
            self.output_dir = Path(self.session["output_dir"]).expanduser().resolve()
            self.index_path = Path(self.session["index_path"]).expanduser().resolve()
            self.catalog = str(self.session["catalog"])
            self.theme = str(self.session.get("theme") or theme)
        else:
            self.input_path = Path(input_path).expanduser().resolve()
            self.output_dir = Path(output_dir).expanduser().resolve()
            self.index_path = Path(index_path).expanduser().resolve()
            self.catalog = catalog
            self.theme = theme
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.filters = load_filter_index(self.index_path, catalog=self.catalog)
        self.favorite_ids = self.store.list_favorites(self.catalog)
        if not self.resumed:
            self.session = self.store.create_session(
                input_path=str(self.input_path),
                catalog=self.catalog,
                index_path=str(self.index_path),
                output_dir=str(self.output_dir),
                theme=self.theme,
            )
        self.events: list[dict[str, Any]] = []
        self.experience = self._build_experience()

    def start(self) -> dict[str, Any]:
        if self.experience is not None:
            self.experience.start()
        if self.resumed and (self.session.get("scene") or self.session.get("recommended_filters")):
            self._emit(
                f"[RESUME] session={self.session['session_id']} "
                f"scene={(self.session.get('scene') or {}).get('scene', '-')}"
            )
            return self.summary()
        self._run_analysis()
        self._run_recommend(self.top_k)
        return self.summary()

    def run_commands(self, commands: list[str]) -> dict[str, Any]:
        self.start()
        for line in commands:
            result = self.execute(line)
            if result.get("event") in {"exit", "close"}:
                break
        return self.summary()

    def run_interactive(self) -> dict[str, Any]:
        self.start()
        self._emit("Session ready. Type `help` for commands.")
        while True:
            try:
                line = self.input_fn(f"{self._prompt_label()}> ").strip()
            except EOFError:
                line = "exit"
            result = self.execute(line)
            if result.get("event") == "exit":
                break
        return self.summary()

    def execute(self, line: str) -> dict[str, Any]:
        command = line.strip()
        if not command:
            return self._record_event("noop", {"message": "empty"})

        parts = shlex.split(command)
        if not parts:
            return self._record_event("noop", {"message": "empty"})

        verb = parts[0].lower()
        args = parts[1:]
        handlers = {
            "help": self._cmd_help,
            "?": self._cmd_help,
            "status": self._cmd_status,
            "analyze": self._cmd_analyze,
            "recommend": self._cmd_recommend,
            "preview": self._cmd_preview,
            "apply": self._cmd_apply,
            "favorite": self._cmd_favorite,
            "history": self._cmd_history,
            "undo": self._cmd_undo,
            "redo": self._cmd_redo,
            "open": self._cmd_open,
            "compare": self._cmd_compare,
            "show": self._cmd_show,
            "close": self._cmd_close,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }
        handler = handlers.get(verb)
        if handler is None:
            return self._record_event("error", {"message": f"Unknown session command: {verb}"}, ok=False)
        try:
            return handler(args)
        except (ValueError, FileNotFoundError) as exc:
            return self._record_event("error", {"message": str(exc), "command": command}, ok=False)

    def summary(self) -> dict[str, Any]:
        session = self.store.load_session(self.session["session_id"]) or self.session
        return {
            "session_id": session["session_id"],
            "catalog": session["catalog"],
            "workspace": session.get("workspace"),
            "theme": session.get("theme"),
            "input_path": session["input_path"],
            "index_path": session["index_path"],
            "output_dir": session["output_dir"],
            "scene": session.get("scene"),
            "recommended_filters": session.get("recommended_filters", []),
            "contact_sheet_path": session.get("contact_sheet_path"),
            "selected_filter": session.get("selected_filter"),
            "cursor": session.get("cursor", -1),
            "applied": session.get("applied", []),
            "events": list(self.events),
            "closed_at": session.get("closed_at"),
            "close_reason": session.get("close_reason"),
        }

    def _build_experience(self) -> StudioConsoleExperience | None:
        return StudioConsoleExperience(
            prompt="session",
            input_path=self.input_path,
            index_path=self.index_path,
            output_dir=self.output_dir,
            catalog=self.catalog,
            stream=self.stream,
            pace_ms=0,
            use_color=getattr(self.stream, "isatty", lambda: False)(),
            theme=self.theme,
        )

    def _cmd_help(self, _: list[str]) -> dict[str, Any]:
        lines = [
            "help",
            "status",
            "analyze",
            "recommend [top_k]",
            "preview",
            "apply <filter>",
            "favorite [filter]",
            "history",
            "undo",
            "redo",
            "compare <slot_a> <slot_b>",
            "show",
            "close",
            "open [contact|current]",
            "exit",
        ]
        self._emit("\n".join(lines))
        return self._record_event("help", {"commands": lines})

    def _cmd_status(self, _: list[str]) -> dict[str, Any]:
        summary = self.summary()
        selected = summary["selected_filter"]["display_name"] if summary.get("selected_filter") else "none"
        self._emit(
            f"[STATUS] session={summary['session_id']} scene={summary['scene']['scene'] if summary['scene'] else '-'} "
            f"selected={selected}"
        )
        return self._record_event("status", summary)

    def _cmd_analyze(self, _: list[str]) -> dict[str, Any]:
        scene = self._run_analysis()
        self._emit(
            f"[ANALYZE] scene={scene['scene']} confidence={scene['confidence']:.0%}"
        )
        return self._record_event("analyze", scene)

    def _cmd_recommend(self, args: list[str]) -> dict[str, Any]:
        top_k = self.top_k
        if args:
            top_k = max(int(args[0]), 1)
        recommendations = self._run_recommend(top_k)
        lines = [
            f"{idx}. {item['display_name']} ({item['filter_id']})"
            + (" [favorite]" if item.get("favorite_boost") else "")
            for idx, item in enumerate(recommendations, start=1)
        ]
        self._emit("[RECOMMEND]")
        for line in lines:
            self._emit(line)
        return self._record_event("recommend", {"top_k": top_k, "recommendations": recommendations})

    def _cmd_preview(self, _: list[str]) -> dict[str, Any]:
        result = run_pipeline(
            input_path=self.input_path,
            output_dir=self.output_dir,
            filter_index_path=self.index_path,
            catalog=self.catalog,
            intensity=self.intensity,
            algorithm=self.algorithm,
            auto_apply="none",
            preferred_filter_ids=set(self.favorite_ids),
        )
        self.session["scene"] = result["scene"]
        self.session["recommended_filters"] = result["recommended_filters"]
        self.session["contact_sheet_path"] = result["contact_sheet_path"]
        self.store.save_session(self.session)
        self._emit(f"[PREVIEW] contact_sheet={result['contact_sheet_path']}")
        return self._record_event(
            "preview",
            {
                "contact_sheet_path": result["contact_sheet_path"],
                "scene": result["scene"],
                "recommendations": result["recommended_filters"],
            },
        )

    def _cmd_apply(self, args: list[str]) -> dict[str, Any]:
        if not args:
            raise SessionCommandError("apply requires a filter query")
        query = " ".join(args)
        filter_item = self._resolve_session_filter(query)
        output_path = self._session_output_path(filter_item["filter_id"])
        apply_flut_to_image(
            flut_path=filter_item["flut_file"],
            input_path=self.input_path,
            output_path=output_path,
            intensity=self.intensity,
            algorithm=self.algorithm,
        )
        selection = {
            "position": len(self.session.get("applied", [])) + 1,
            "catalog": filter_item.get("catalog", self.catalog),
            "filter_id": filter_item["filter_id"],
            "display_name": filter_item["display_name"],
            "reason": filter_item.get("reason"),
            "favorite_boost": bool(filter_item.get("favorite_boost")),
            "output_path": str(output_path),
            "timestamp": utc_now_iso(),
        }
        applied = self.session.setdefault("applied", [])
        cursor = int(self.session.get("cursor", -1))
        if cursor < len(applied) - 1:
            del applied[cursor + 1 :]
        applied.append(selection)
        self.session["cursor"] = len(applied) - 1
        self.session["selected_filter"] = selection
        self.store.save_session(self.session)
        self.store.append_history(
            {
                "command": "session.apply",
                "catalog": self.catalog,
                "input_path": str(self.input_path),
                "index_path": str(self.index_path),
                "output_path": str(output_path),
                "filter_id": filter_item["filter_id"],
                "display_name": filter_item["display_name"],
                "scene": (self.session.get("scene") or {}).get("scene"),
                "session_id": self.session["session_id"],
            }
        )
        self._emit(f"[APPLY] {selection['display_name']} -> {output_path}")
        return self._record_event("apply", selection)

    def _cmd_favorite(self, args: list[str]) -> dict[str, Any]:
        if args:
            filter_item = self._resolve_session_filter(" ".join(args))
            filter_id = filter_item["filter_id"]
            display_name = filter_item["display_name"]
        else:
            selected = self.session.get("selected_filter")
            if not selected:
                raise SessionCommandError("favorite requires a filter query or an existing selection")
            filter_id = selected["filter_id"]
            display_name = selected["display_name"]
        self.store.add_favorite(catalog=self.catalog, filter_id=filter_id)
        self.favorite_ids = self.store.list_favorites(self.catalog)
        self._emit(f"[FAVORITE] {display_name}")
        return self._record_event("favorite", {"catalog": self.catalog, "filter_id": filter_id})

    def _cmd_history(self, _: list[str]) -> dict[str, Any]:
        applied = list(self.session.get("applied", []))
        cursor = int(self.session.get("cursor", -1))
        if not applied:
            self._emit("[HISTORY] empty")
        else:
            self._emit("[HISTORY]")
            for idx, item in enumerate(applied, start=1):
                marker = "*" if (idx - 1) == cursor else " "
                self._emit(f"{marker} {idx}. {item['display_name']} -> {item['output_path']}")
        return self._record_event("history", {"cursor": cursor, "applied": applied})

    def _cmd_compare(self, args: list[str]) -> dict[str, Any]:
        if len(args) != 2:
            raise SessionCommandError("compare requires two slot indexes")
        recommended = self.session.get("recommended_filters", [])
        selections: list[dict[str, Any]] = []
        for raw in args:
            idx = int(raw) - 1
            if idx < 0 or idx >= len(recommended):
                raise SessionCommandError(f"compare index {raw} not in range")
            selections.append(recommended[idx])
        self._emit("[COMPARE]")
        for idx, item in enumerate(selections, start=1):
            self._emit(
                f"{idx}. {item['display_name']} ({item['filter_id']}) reason={item.get('reason','-')} fav={item.get('favorite_boost',False)}"
            )
        return self._record_event("compare", {"choices": selections})

    def _cmd_show(self, _: list[str]) -> dict[str, Any]:
        summary = self.summary()
        self._emit(
            f"[SESSION SHOW] scene={summary['scene']['scene'] if summary['scene'] else '-'} "
            f"recommendations={len(summary['recommended_filters'])} applied={len(summary['applied'])}"
        )
        if summary["closed_at"]:
            self._emit(f"closed_at={summary['closed_at']}")
        return self._record_event("show", summary)

    def _cmd_close(self, _: list[str]) -> dict[str, Any]:
        return self._close_session(reason="user_close")

    def _cmd_undo(self, _: list[str]) -> dict[str, Any]:
        cursor = int(self.session.get("cursor", -1))
        if cursor < 0:
            raise SessionCommandError("No applied selection to undo")
        cursor -= 1
        self.session["cursor"] = cursor
        self.session["selected_filter"] = self.session["applied"][cursor] if cursor >= 0 else None
        self.store.save_session(self.session)
        payload = {
            "cursor": cursor,
            "selected_filter": self.session.get("selected_filter"),
        }
        self._emit(
            "[UNDO] " + (
                self.session["selected_filter"]["display_name"]
                if self.session.get("selected_filter")
                else "no active selection"
            )
        )
        return self._record_event("undo", payload)

    def _cmd_redo(self, _: list[str]) -> dict[str, Any]:
        applied = self.session.get("applied", [])
        cursor = int(self.session.get("cursor", -1))
        if cursor + 1 >= len(applied):
            raise SessionCommandError("No redo state available")
        cursor += 1
        self.session["cursor"] = cursor
        self.session["selected_filter"] = applied[cursor]
        self.store.save_session(self.session)
        payload = {
            "cursor": cursor,
            "selected_filter": self.session["selected_filter"],
        }
        self._emit(f"[REDO] {self.session['selected_filter']['display_name']}")
        return self._record_event("redo", payload)

    def _cmd_open(self, args: list[str]) -> dict[str, Any]:
        target = "current"
        if args:
            target = args[0].lower()
        if target == "contact":
            path = self.session.get("contact_sheet_path")
        else:
            selected = self.session.get("selected_filter")
            path = selected.get("output_path") if selected else None
        if not path:
            raise SessionCommandError(f"No output available for open target: {target}")
        success, error = open_result(Path(path))
        self._emit(f"[OPEN] success={success} path={path}")
        return self._record_event("open", {"target": target, "path": path, "success": success, "error": error})

    def _cmd_exit(self, _: list[str]) -> dict[str, Any]:
        result = self._close_session(reason="user_exit")
        result["event"] = "exit"
        return result

    def _run_analysis(self) -> dict[str, Any]:
        scene = analyze_scene(
            self.input_path,
            scene_filters=scene_filters_for_catalog(self.catalog, index_path=self.index_path),
            catalog=self.catalog,
            index_path=self.index_path,
        )
        self.session["scene"] = scene
        self.store.save_session(self.session)
        return scene

    def _run_recommend(self, top_k: int) -> list[dict[str, Any]]:
        scene = self.session.get("scene") or self._run_analysis()
        recommended = select_recommended_filters(
            scene_result_dict=scene,
            all_filters=self.filters,
            full_preview=False,
        )
        recommended = apply_favorite_boost(recommended, favorite_filter_ids=self.favorite_ids)[: max(top_k, 1)]
        details = build_recommendation_details(
            scene["scene"],
            recommended,
            catalog=self.catalog,
            index_path=self.index_path,
        )
        self.session["recommended_filters"] = details
        self.store.save_session(self.session)
        return details

    def _close_session(self, *, reason: str) -> dict[str, Any]:
        closed = self.store.mark_session_closed(self.session["session_id"], reason=reason) or self.session
        self.session.update(closed)
        self._emit(f"[SESSION] closed {self.session['session_id']}")
        return self._record_event("close", {"session_id": self.session["session_id"], "closed_at": self.session["closed_at"]})

    def _prompt_label(self) -> str:
        if self.theme in {"minimal", "cipher"}:
            return self.theme
        return "blackroom"

    def _resolve_session_filter(self, query: str) -> dict[str, Any]:
        shortlist = self.session.get("recommended_filters", [])
        if shortlist:
            try:
                _, selected = find_filter(shortlist, query)
                return selected
            except ValueError:
                pass
        _, selected = find_filter(self.filters, query)
        return selected

    def _session_output_path(self, filter_id: str) -> Path:
        counter = len(self.session.get("applied", [])) + 1
        suffix = self.input_path.suffix or ".png"
        return (self.output_dir / f"{self.input_path.stem}_{self.session['session_id']}_{counter:02d}_{filter_id}{suffix}").resolve()

    def _record_event(self, event: str, payload: dict[str, Any], *, ok: bool = True) -> dict[str, Any]:
        record = {
            "event": event,
            "ok": ok,
            "timestamp": utc_now_iso(),
            "payload": payload,
        }
        self.events.append(record)
        session_events = self.session.setdefault("events", [])
        session_events.append(record)
        self.store.save_session(self.session)
        return record

    def _emit(self, text: str) -> None:
        print(text, file=self.stream)


def load_script_commands(script_path: Path | str) -> list[str]:
    path = Path(script_path).expanduser().resolve()
    commands: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        commands.append(stripped)
    return commands
