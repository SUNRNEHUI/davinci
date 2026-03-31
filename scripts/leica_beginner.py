"""Beginner-first DAVINCI CLI flow."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

try:
    from .apply_flut_image import apply_flut_to_image
    from .blackroom_console import StudioConsoleExperience
    from .contact_sheet import generate_before_after_preview, generate_contact_sheet
    from .filter_browser import browse_filter_previews
    from .leica_catalog import (
        DEFAULT_CATALOG,
        beginner_family_descriptions,
        build_recommendation_details,
        family_label_for_catalog,
        load_filter_index,
        normalize_catalog_name,
        scene_filters_for_catalog,
        select_recommended_filters,
        shipped_catalog_names,
        shipped_index_path,
    )
    from .leica_pipeline import open_result
    from .leica_product_store import ProductStore
    from .scene_analyzer import analyze_scene
except ImportError:  # pragma: no cover - script execution fallback
    from apply_flut_image import apply_flut_to_image
    from blackroom_console import StudioConsoleExperience
    from contact_sheet import generate_before_after_preview, generate_contact_sheet
    from filter_browser import browse_filter_previews
    from leica_catalog import (
        DEFAULT_CATALOG,
        beginner_family_descriptions,
        build_recommendation_details,
        family_label_for_catalog,
        load_filter_index,
        normalize_catalog_name,
        scene_filters_for_catalog,
        select_recommended_filters,
        shipped_catalog_names,
        shipped_index_path,
    )
    from leica_pipeline import open_result
    from leica_product_store import ProductStore
    from scene_analyzer import analyze_scene


BeginnerInput = Callable[[str], str]

DEFAULT_PROMPT = "帮我调色"
PRODUCT_SITE_URL = "https://sensear.softsugar.com/"
DEFAULT_FEEDBACK_HINTS = [
    "1 / 2 / 3 选择一个效果",
    "换一个  再给我 3 个不同方向",
    "更暖 / 更冷 / 更复古 / 更通透 / 更像胶片 / 更自然",
    "看其他系列 / 看莱卡 / 看富士 / exit",
]

CATALOG_FEEDBACK_HINTS = [
    "输入编号直接保存当前滤镜",
    "方向键切换，回车保存",
    "输入 0 返回三方向推荐",
    "看其他系列 / 看莱卡 / 看富士",
]

INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "warm": ("暖", "warm"),
    "cool": ("冷", "cool"),
    "vintage": ("复古", "怀旧", "旧照片", "nostalgic", "vintage"),
    "film": ("胶片", "film"),
    "clean": ("通透", "干净", "清爽", "明亮", "clean"),
    "natural": ("自然", "真实", "日常", "natural"),
    "mono": ("黑白", "mono", "bw"),
    "vivid": ("鲜艳", "高饱和", "浓一点", "vivid"),
    "portrait": ("人像", "自拍", "portrait"),
    "landscape": ("风景", "天空", "植物", "户外", "旅行", "landscape", "outdoor"),
    "documentary": ("纪实", "街头", "street", "documentary"),
}

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "leica": ("leica", "莱卡"),
    "fuji": ("fuji", "fujifilm", "富士"),
    "kodak": ("kodak", "柯达"),
}


class BeginnerStartFlow:
    """Interactive product-style flow for complete beginners."""

    def __init__(
        self,
        *,
        store: ProductStore,
        input_path: Path | str,
        output_dir: Path | str,
        sources: list[tuple[str, Path]],
        prompt: str,
        intensity: float,
        algorithm: str,
        theme: str,
        stream: Any,
        input_fn: BeginnerInput,
        auto_open: bool,
        use_color: bool,
        pace_ms: int | None,
    ) -> None:
        self.store = store
        self.input_path = Path(input_path).expanduser().resolve()
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.proofs_dir = self.output_dir / "proofs"
        self.finals_dir = self.output_dir / "finals"
        self.proofs_dir.mkdir(parents=True, exist_ok=True)
        self.finals_dir.mkdir(parents=True, exist_ok=True)
        self.sources = [(normalize_catalog_name(catalog), Path(index_path).expanduser().resolve()) for catalog, index_path in sources]
        self.prompt = prompt.strip() or DEFAULT_PROMPT
        self.intensity = intensity
        self.algorithm = algorithm
        self.theme = theme
        self.stream = stream
        self.input_fn = input_fn
        self.auto_open = auto_open
        self.events: list[dict[str, Any]] = []
        self.open_events: list[dict[str, Any]] = []
        self.catalog_candidates = self._load_candidate_pool()
        self.primary_scene = self._resolve_primary_scene()
        self.current_options: list[dict[str, Any]] = []
        self.contact_sheet_path: str | None = None
        self.hero_output_path: str | None = None
        self.compare_output_path: str | None = None
        self.final_output_path: str | None = None
        self.final_compare_path: str | None = None
        self.selected_option: dict[str, Any] | None = None
        self.current_prompt = self.prompt
        self.round_index = 0
        self.current_family: str | None = None
        self.current_view = "directions"
        self.catalog_browser_enabled = False
        self._seen_filter_ids: set[str] = set()
        prompt_family = _parse_requested_family(self.prompt, [catalog for catalog, _ in self.sources])
        surface_catalog = prompt_family or (self.sources[0][0] if len(self.sources) == 1 else "multi")
        self.experience = StudioConsoleExperience(
            prompt=self.prompt,
            input_path=self.input_path,
            index_path=self.sources[0][1],
            output_dir=self.output_dir,
            catalog=surface_catalog,
            stream=stream,
            pace_ms=pace_ms,
            use_color=use_color,
            theme=theme,
            boot_hint="先看我打开的对比图，再输入 1 / 2 / 3，或者直接说 更暖 / 更复古 / 换一个。",
        )

    def start(self) -> dict[str, Any]:
        self.experience.start()
        overview_family = _parse_catalog_overview_family(self.prompt, self._available_catalogs())
        if overview_family is not None:
            self.current_prompt = DEFAULT_PROMPT
            self._generate_catalog_overview(overview_family, source_command=self.prompt)
            return self.summary()
        self.experience.show_panel(
            "WELCOME",
            [
                "把一张照片交给我，我会先给你 3 个不同方向的效果。",
                "你不需要懂滤镜名，也不需要先选系列。",
                "你可以直接说：帮我调色 / 复古一点 / 更通透 / 更像胶片 / 换一个",
            ],
            accent="cyan",
        )
        self.experience.show_panel(
            "ANALYSIS",
            [
                f"场景判断：{self.primary_scene.get('scene', '-')}",
                f"把握程度：{self.primary_scene.get('confidence', 0.0):.0%}",
                "我会优先给你差异明显、第一眼就能选的 3 个方向。",
            ],
            accent="green",
        )
        self._generate_set(self.prompt, mode="initial")
        return self.summary()

    def run_commands(self, commands: list[str]) -> dict[str, Any]:
        self.start()
        for line in commands:
            result = self.execute(line)
            if result.get("event") in {"exit"}:
                break
        return self.summary()

    def run_interactive(self) -> dict[str, Any]:
        self.start()
        while True:
            try:
                line = self.input_fn("davinci> ").strip()
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

        lowered = command.lower()
        if lowered in {"exit", "quit"}:
            self._emit("已结束。")
            return self._record_event("exit", {"message": "user_exit"})
        if lowered in {"help", "?"}:
            self._show_feedback_hints(title="HOW TO USE")
            return self._record_event("help", {"hints": list(DEFAULT_FEEDBACK_HINTS)})
        if lowered in {"brands", "系列", "风格系列"}:
            self._show_brands()
            return self._record_event("brands", {"families": beginner_family_descriptions(self._available_catalogs())})
        if command == "0" and self.current_view == "catalog":
            self._generate_set(self.current_prompt, mode="initial")
            return self._record_event("browse_exit", {"prompt": self.current_prompt})
        if command.isdigit():
            return self._select_option(int(command))
        if command in {"换一个", "再来一组"}:
            self._generate_set(command, mode="refresh")
            return self._record_event(
                "refresh",
                {"prompt": command, "options": [self._option_payload(option, idx) for idx, option in enumerate(self.current_options, start=1)]},
            )
        if command == "看其他系列":
            family = self._next_family_outside_current_set()
            if self.current_view == "catalog" and family is not None:
                self._generate_catalog_overview(family, source_command=command)
                return self._record_event(
                    "browse",
                    {
                        "prompt": command,
                        "requested_family": family,
                        "options": [self._option_payload(option, idx) for idx, option in enumerate(self.current_options, start=1)],
                    },
                )
            self._generate_set(command, mode="refresh", requested_family=family)
            return self._record_event(
                "refresh",
                {
                    "prompt": command,
                    "requested_family": family,
                    "options": [self._option_payload(option, idx) for idx, option in enumerate(self.current_options, start=1)],
                },
            )

        overview_family = _parse_catalog_overview_family(command, self._available_catalogs())
        if overview_family is not None:
            self._generate_catalog_overview(overview_family, source_command=command)
            return self._record_event(
                "browse",
                {
                    "prompt": command,
                    "requested_family": overview_family,
                    "options": [self._option_payload(option, idx) for idx, option in enumerate(self.current_options, start=1)],
                },
            )
        requested_family = _parse_requested_family(command, self._available_catalogs())
        if requested_family is not None or _parse_intent_tokens(command):
            self._generate_set(command, mode="refine", requested_family=requested_family)
            return self._record_event(
                "refine",
                {
                    "prompt": command,
                    "requested_family": requested_family,
                    "options": [self._option_payload(option, idx) for idx, option in enumerate(self.current_options, start=1)],
                },
            )

        self._show_feedback_hints(title="TRY THIS")
        return self._record_event("unknown", {"message": command}, ok=False)

    def summary(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "input_path": str(self.input_path),
            "output_dir": str(self.output_dir),
            "scene": self.primary_scene,
            "available_families": beginner_family_descriptions(self._available_catalogs()),
            "options": [self._option_payload(option, idx) for idx, option in enumerate(self.current_options, start=1)],
            "contact_sheet_path": self.contact_sheet_path,
            "hero_output_path": self.hero_output_path,
            "compare_output_path": self.compare_output_path,
            "final_output_path": self.final_output_path,
            "final_compare_path": self.final_compare_path,
            "selected_option": self.selected_option,
            "open_events": list(self.open_events),
            "events": list(self.events),
        }

    def _load_candidate_pool(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for catalog, index_path in self.sources:
            scene_result = analyze_scene(
                self.input_path,
                scene_filters=scene_filters_for_catalog(catalog, index_path=index_path),
                catalog=catalog,
                index_path=index_path,
            )
            filters = load_filter_index(index_path, catalog=catalog)
            recommended = select_recommended_filters(
                scene_result_dict=scene_result,
                all_filters=filters,
                full_preview=True,
            )
            details = build_recommendation_details(
                scene_result["scene"],
                recommended,
                catalog=catalog,
                index_path=index_path,
            )
            for detail in details:
                candidates.append(
                    {
                        **detail,
                        "_index_path": str(index_path),
                        "_scene_confidence": float(scene_result.get("confidence", 0.0)),
                        "_scene_recommended_ids": set(scene_result.get("recommended_filters", [])),
                    }
                )
        return candidates

    def _resolve_primary_scene(self) -> dict[str, Any]:
        if not self.catalog_candidates:
            return {"scene": "general", "confidence": 0.0}
        best = max(self.catalog_candidates, key=lambda item: float(item.get("_scene_confidence", 0.0)))
        return {
            "scene": best.get("scene", "general"),
            "confidence": float(best.get("_scene_confidence", 0.0)),
        }

    def _generate_set(
        self,
        prompt: str,
        *,
        mode: str,
        requested_family: str | None = None,
    ) -> None:
        self.round_index += 1
        self.current_view = "directions"
        self.current_prompt = prompt.strip() or DEFAULT_PROMPT
        anchor = self.selected_option or (self.current_options[0] if self.current_options else None)
        seen_filter_ids = set(self._seen_filter_ids if mode == "refresh" else ())
        options = _choose_beginner_options(
            self.catalog_candidates,
            scene=str(self.primary_scene.get("scene") or "general"),
            prompt=prompt,
            current_option=anchor if mode == "refine" else None,
            current_family=self.current_family,
            seen_filter_ids=seen_filter_ids,
            requested_family=requested_family,
            mode=mode,
            previous_options=self.current_options,
        )
        self.current_options = options
        self.current_family = self.current_options[0].get("catalog") if self.current_options else self.current_family
        self._seen_filter_ids.update(option["filter_id"] for option in options)
        self.contact_sheet_path, self.hero_output_path, self.compare_output_path = self._render_current_outputs()
        self._show_current_options(prompt, mode=mode, requested_family=requested_family)
        self._show_feedback_hints(title="NEXT")

    def _generate_catalog_overview(self, catalog: str, *, source_command: str) -> None:
        self.round_index += 1
        self.current_view = "catalog"
        self.current_family = catalog
        self.catalog_browser_enabled = self.auto_open and self._can_use_catalog_browser()
        self.current_options = [item for item in self.catalog_candidates if item.get("catalog") == catalog]
        self.contact_sheet_path, self.hero_output_path, self.compare_output_path = self._render_current_outputs(
            include_original=False
        )
        self._show_catalog_overview(source_command=source_command)
        if self.catalog_browser_enabled:
            selected_number = self._open_catalog_browser()
            if selected_number is not None:
                self._select_option(selected_number)
                return
        elif self.auto_open and self.contact_sheet_path:
            success, error = open_result(Path(self.contact_sheet_path))
            self.open_events.append({"path": str(self.contact_sheet_path), "success": success, "error": error})
            self.experience.report_open(Path(self.contact_sheet_path), success, error)
        self.experience.show_panel("NEXT", list(CATALOG_FEEDBACK_HINTS), accent="green")

    def _render_current_outputs(self, *, include_original: bool = True) -> tuple[str | None, str | None, str | None]:
        if not self.current_options:
            return None, None, None
        contact_sheet_path = self.proofs_dir / f"start_sheet_{self.round_index:02d}.png"
        sheet_filters = []
        for option in self.current_options:
            label_name = option["plain_name"]
            if self.current_view == "catalog":
                label_name = str(option.get("technical_name") or option.get("display_name") or option["plain_name"])
            sheet_filters.append(
                {
                    "filter_id": option["filter_id"],
                    "display_name": label_name,
                    "flut_file": option.get("flut_file"),
                    "key_file": str(Path(option["_index_path"]).parent / "runtime.key.b64"),
                }
            )
        generate_contact_sheet(
            input_path=self.input_path,
            filters=sheet_filters,
            output_path=contact_sheet_path,
            include_original=include_original,
            intensity=self.intensity,
        )

        if self.current_view == "catalog":
            return str(contact_sheet_path), None, None

        hero = self.current_options[0]
        hero_output_path = self.proofs_dir / f"{self.input_path.stem}_hero_{self.round_index:02d}_{hero['filter_id']}{self.input_path.suffix or '.png'}"
        apply_flut_to_image(
            flut_path=hero["flut_file"],
            input_path=self.input_path,
            output_path=hero_output_path,
            intensity=self.intensity,
            algorithm=self.algorithm,
        )
        compare_output_path = self.proofs_dir / (
            f"{self.input_path.stem}_compare_{self.round_index:02d}_{hero['filter_id']}.png"
        )
        generate_before_after_preview(
            input_path=self.input_path,
            rendered_path=hero_output_path,
            output_path=compare_output_path,
            left_label="ORIGINAL",
            right_label=hero["plain_name"].upper(),
        )

        if self.auto_open:
            for path in (contact_sheet_path, compare_output_path, hero_output_path):
                success, error = open_result(path)
                self.open_events.append({"path": str(path), "success": success, "error": error})
                self.experience.report_open(path, success, error)
        return str(contact_sheet_path), str(hero_output_path), str(compare_output_path)

    def _show_current_options(self, prompt: str, *, mode: str, requested_family: str | None = None) -> None:
        if mode == "initial":
            title = "THREE DIRECTIONS"
            prefix = "我先给你 3 个方向："
        elif mode == "refine":
            title = "REFINED DIRECTIONS"
            prefix = f"我按“{prompt}”把方向继续收紧了一点："
        else:
            title = "NEW DIRECTIONS"
            prefix = "我给你换了一组明显不同的方向："
        lines = [prefix]
        family_name: str | None = None
        if requested_family:
            family_name = self.current_options[0]["family_name"] if self.current_options else requested_family
        elif len(self._available_catalogs()) == 1 and self.current_options:
            family_name = self.current_options[0]["family_name"]
        if family_name:
            lines.append(f"当前主系列：{family_name}")
        for idx, option in enumerate(self.current_options, start=1):
            lines.extend(
                [
                    f"{idx}. {option['plain_name']}",
                    f"   {option['effect_summary']}",
                    f"   适合：{' / '.join(option.get('best_for') or ['日常'])}",
                    f"   系列：{option['family_name']}",
                ]
            )
        self.experience.show_panel(title, lines, accent="red")
        if self.contact_sheet_path:
            self.experience.show_panel(
                "OUTPUT READY",
                [
                    "我已经帮你准备好预览。先看图，再决定。",
                    f"三方向对比：{self.contact_sheet_path}",
                    f"前后对比：{self.compare_output_path or '-'}",
                    f"当前推荐：{self.hero_output_path or '-'}",
                    f"本轮结果目录：{self.output_dir}",
                    "原图不会被覆盖。",
                    "下一步：输入 1 / 2 / 3 选一个，或输入 更暖 / 更复古 / 更像胶片 / 换一个。",
                ],
                accent="cyan",
            )

    def _show_catalog_overview(self, *, source_command: str) -> None:
        del source_command
        family_name = self.current_options[0]["family_name"] if self.current_options else (self.current_family or "Catalog")
        title = f"{str(family_name).upper()} FILTERS"
        lines = [f"{family_name} 全部滤镜："]
        for idx, option in enumerate(self.current_options, start=1):
            technical_name = str(option.get("technical_name") or option.get("display_name") or option.get("plain_name"))
            lines.append(f"{idx:02d}. {option['plain_name']} ({technical_name})")
        self.experience.show_panel(title, lines, accent="red")
        if self.contact_sheet_path:
            if self.catalog_browser_enabled:
                lead_line = "已打开单张预览；方向键切换，回车直接保存。"
            elif self.auto_open:
                lead_line = "已打开总览图，先看图，再选编号。"
            else:
                lead_line = "先看图，再选编号。"
            self.experience.show_panel(
                "OUTPUT READY",
                [
                    lead_line,
                    f"系列总览：{self.contact_sheet_path}",
                    "输入编号直接保存，输入 0 返回三方向推荐。",
                ],
                accent="cyan",
            )

    def _show_feedback_hints(self, *, title: str) -> None:
        hints = CATALOG_FEEDBACK_HINTS if self.current_view == "catalog" else DEFAULT_FEEDBACK_HINTS
        self.experience.show_panel(title, list(hints), accent="green")

    def _show_brands(self) -> None:
        lines = ["风格系列：", "不知道选什么时，先按你想要的感觉说。"]
        for item in beginner_family_descriptions(self._available_catalogs()):
            lines.append(f"{item['family_name']} :: {item['summary']}")
        lines.extend(
            [
                "可以直接说：看莱卡 / 看富士 / 更复古 / 更像胶片 / 更自然",
                "如果还是拿不准，就直接输入：换一个",
            ]
        )
        self.experience.show_panel("STYLE FAMILIES", lines, accent="cyan")

    def _select_option(self, number: int) -> dict[str, Any]:
        idx = number - 1
        if idx < 0 or idx >= len(self.current_options):
            self._show_feedback_hints(title="OUT OF RANGE")
            return self._record_event("error", {"message": f"invalid choice: {number}"}, ok=False)
        option = self.current_options[idx]
        needs_render = not (idx == 0 and self.hero_output_path)
        if needs_render:
            self.experience.show_panel(
                "SAVING LOOK",
                [
                    f"正在生成：{option['plain_name']}",
                    "已收到你的选择，正在按原图尺寸输出成片。",
                    "这一步可能需要几秒，取决于图片大小。",
                ],
                accent="cyan",
            )
        if idx == 0 and self.hero_output_path:
            final_output_path = Path(self.hero_output_path)
        else:
            final_output_path = self.finals_dir / f"{self.input_path.stem}_{option['filter_id']}{self.input_path.suffix or '.png'}"
            apply_flut_to_image(
                flut_path=option["flut_file"],
                input_path=self.input_path,
                output_path=final_output_path,
                intensity=self.intensity,
                algorithm=self.algorithm,
            )
        self.final_output_path = str(final_output_path)
        self.final_compare_path = self._render_final_compare(option)
        self.selected_option = self._option_payload(option, number)
        self.selected_option["output_path"] = self.final_output_path
        self.selected_option["compare_path"] = self.final_compare_path
        if self.auto_open:
            success, error = open_result(final_output_path)
            self.open_events.append({"path": str(final_output_path), "success": success, "error": error})
            self.experience.report_open(final_output_path, success, error)
        self.experience.show_panel(
            "FINAL LOOK",
            [
                f"已为你选中：{option['plain_name']}",
                f"效果说明：{option['effect_summary']}",
                f"前后对比：{self.final_compare_path or '-'}",
                f"保存位置：{self.final_output_path}",
                f"成片目录：{self.finals_dir}",
                f"更多风格包 / 价格 / 商用方案：{PRODUCT_SITE_URL}",
                "原图不会被覆盖。",
                "如果还想继续改，你可以输入：更暖 / 更冷 / 更复古 / 更通透 / 换一个",
            ],
            accent="green",
        )
        self.store.append_history(
            {
                "command": "start",
                "catalog": option.get("catalog", DEFAULT_CATALOG),
                "input_path": str(self.input_path),
                "index_path": option.get("_index_path"),
                "output_path": self.final_output_path,
                "filter_id": option.get("filter_id"),
                "display_name": option.get("technical_name") or option.get("display_name"),
                "scene": self.primary_scene.get("scene"),
                "session_id": None,
            }
        )
        return self._record_event("select", {"selected_option": self.selected_option})

    def _available_catalogs(self) -> list[str]:
        return sorted({catalog for catalog, _ in self.sources})

    def _next_family_outside_current_set(self) -> str | None:
        for catalog in self._available_catalogs():
            if catalog != self.current_family:
                return catalog
        return None

    def _can_use_catalog_browser(self) -> bool:
        stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
        stream_tty = bool(getattr(self.stream, "isatty", lambda: False)())
        return stdin_tty and stream_tty

    def _open_catalog_browser(self) -> int | None:
        family_name = self.current_options[0]["family_name"] if self.current_options else (self.current_family or "Catalog")
        selected_index, error = browse_filter_previews(
            input_path=self.input_path,
            options=self.current_options,
            intensity=self.intensity,
            title=f"DAVINCI {family_name}",
        )
        self.open_events.append(
            {
                "path": "interactive-filter-browser",
                "success": error is None,
                "error": error,
            }
        )
        if error is None:
            if selected_index is None:
                return None
            return selected_index + 1

        if self.contact_sheet_path:
            success, open_error = open_result(Path(self.contact_sheet_path))
            self.open_events.append({"path": str(self.contact_sheet_path), "success": success, "error": open_error})
            self.experience.report_open(Path(self.contact_sheet_path), success, open_error)
        return None

    def _render_final_compare(self, option: dict[str, Any]) -> str | None:
        compare_path = self.finals_dir / f"{self.input_path.stem}_compare_{option['filter_id']}.png"
        if self.final_output_path:
            generate_before_after_preview(
                input_path=self.input_path,
                rendered_path=self.final_output_path,
                output_path=compare_path,
                left_label="ORIGINAL",
                right_label=option["plain_name"].upper(),
            )
            return str(compare_path)
        generate_contact_sheet(
            input_path=self.input_path,
            filters=[
                {
                    "filter_id": option["filter_id"],
                    "display_name": option["plain_name"],
                    "flut_file": option.get("flut_file"),
                    "key_file": str(Path(option["_index_path"]).parent / "runtime.key.b64"),
                }
            ],
            output_path=compare_path,
            include_original=True,
            intensity=self.intensity,
        )
        return str(compare_path)

    def _option_payload(self, option: dict[str, Any], position: int) -> dict[str, Any]:
        return {
            "position": position,
            "catalog": option.get("catalog"),
            "filter_id": option.get("filter_id"),
            "plain_name": option.get("plain_name"),
            "display_name": option.get("display_name"),
            "technical_name": option.get("technical_name"),
            "family_name": option.get("family_name"),
            "effect_summary": option.get("effect_summary"),
            "best_for": option.get("best_for"),
            "intent_tags": option.get("intent_tags"),
            "reason": option.get("reason"),
        }

    def _record_event(self, event: str, payload: dict[str, Any], *, ok: bool = True) -> dict[str, Any]:
        record = {
            "event": event,
            "ok": ok,
            "payload": payload,
        }
        self.events.append(record)
        return record

    def _emit(self, text: str) -> None:
        print(text, file=self.stream)


def beginner_help_text(
    output_root: str | None = None,
    *,
    families: list[dict[str, str]] | None = None,
) -> str:
    output_hint = output_root or "~/Pictures/DAVINCI"
    demo_hint = f"{output_hint}/_demo"
    family_lines: list[str] = []
    for item in families or []:
        family_lines.append(f"- {item['family_name']}：{item['summary']}")
    return "\n".join(
        [
            "SenseAR DAVINCI 快速上手",
            "",
            "只记住这 4 个入口：",
            "davinci",
            "davinci demo",
            "davinci start",
            "davinci continue",
            "",
            "如果你只是想先看看这个产品：",
            "- 输入 `davinci`",
            "- 或直接输入 `davinci demo` 看内置演示",
            "",
            "如果你要处理自己的照片：",
            "- 输入 `davinci start`",
            "开始后支持三种方式：",
            "- 把照片直接拖进终端",
            "- 直接粘贴照片路径",
            "- 直接回车打开选图窗口（macOS）",
            '- 输入 `demo`，先看看产品效果',
            "",
            "如果你想继续上一次：",
            "- 输入 `davinci continue`",
            "",
            "你不需要先懂滤镜名，也不需要先决定 Leica / Fuji / Kodak。",
            "你可以直接说：",
            "- 帮我调色",
            "- 复古一点",
            "- 更通透",
            "- 更暖",
            "- 更冷",
            "- 更像胶片",
            "- 看莱卡",
            "- 看富士",
            "- 不喜欢，换一个",
            "",
            "你会得到：",
            "- 先分析照片更像人像、风景还是纪实",
            "- 先给你 3 个差异明显的方向",
            "- 自动打开三方向对比图和前后对比图",
            f"- 结果默认保存在：{output_hint}",
            f"- demo 默认保存在：{demo_hint}",
            "- 不会覆盖原图",
            "",
            "想先理解系列差异：",
            "davinci brands",
            "",
            *(
                ["内置风格系列：", *family_lines, ""]
                if family_lines
                else []
            ),
            "如果你还没有安装 `davinci` 命令：",
            "python3 -m pip install -e .",
            "",
            "进阶入口：",
            'python3 -m scripts.leica_cli start --input "/path/photo.jpg"',
        ]
    )


def beginner_brands_text(catalogs: list[str] | None = None) -> str:
    families = beginner_family_descriptions(catalogs or shipped_catalog_names())
    lines = [
        "DAVINCI 风格方向",
        "",
        "不知道 Leica / Fuji / Kodak 是什么也没关系，先按感觉选。",
        "",
    ]
    for item in families:
        lines.append(f"{item['family_name']}")
        lines.append(item["summary"])
        lines.append(f"适合你在这种时候选：{item['when_to_choose']}")
        lines.append(f"更常见于：{' / '.join(item['best_for'])}")
        lines.append(f"你可以直接说：{' / '.join(item['ask_for'])}")
        lines.append("")
    lines.extend(
        [
            "如果你还是拿不准：",
            "- 直接输入 `davinci start`",
            "- 把照片交给 DAVINCI 先出 3 个方向",
            "- 再按眼睛选，不用记滤镜名",
            "",
            "最简单的开始方式：",
            "- davinci demo",
            "- davinci start",
        ]
    )
    return "\n".join(lines).rstrip()


def _parse_intent_tokens(text: str) -> set[str]:
    lowered = text.strip().lower()
    tokens: set[str] = set()
    for tag, keywords in INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            tokens.add(tag)
    if not tokens and lowered in {DEFAULT_PROMPT.lower(), "调色", "grade", "start"}:
        tokens.add("balanced")
    return tokens


def _parse_requested_family(text: str, available_catalogs: list[str]) -> str | None:
    lowered = text.strip().lower()
    for family, keywords in FAMILY_KEYWORDS.items():
        if family not in available_catalogs:
            continue
        if any(keyword in lowered for keyword in keywords):
            return family
    return None


def _is_plain_family_command(text: str, family: str) -> bool:
    stripped = text.strip().lower()
    return stripped in {keyword.lower() for keyword in FAMILY_KEYWORDS.get(family, ())}


def _parse_catalog_overview_family(text: str, available_catalogs: list[str]) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    lowered = stripped.lower()
    requested_family = _parse_requested_family(stripped, available_catalogs)
    if requested_family is None:
        return None
    if _is_plain_family_command(stripped, requested_family):
        return requested_family
    if any(token in stripped for token in ("全部", "全览", "滤镜")):
        return requested_family
    if any(token in lowered for token in ("看", "看看", "browse", "show", "list")):
        return requested_family
    return None


def _bucket_for_option(option: dict[str, Any]) -> str:
    tags = {str(tag).strip().lower() for tag in option.get("intent_tags", [])}
    if "mono" in tags:
        return "mono"
    if "warm" in tags or "golden" in tags or "amber" in tags:
        return "warm"
    if "film" in tags or "nostalgia" in tags:
        return "film"
    if "vivid" in tags or "landscape" in tags:
        return "vivid"
    if "cool" in tags or "cinematic" in tags or "urban" in tags:
        return "cool"
    if "vintage" in tags:
        return "vintage"
    return "clean"


def _bucket_order(scene: str, intents: set[str], mode: str) -> list[str]:
    if "mono" in intents:
        order = ["mono", "clean", "film"]
    elif "cool" in intents:
        order = ["cool", "clean", "film"]
    elif "vivid" in intents or "landscape" in intents:
        order = ["vivid", "clean", "warm"]
    elif "warm" in intents:
        order = ["warm", "film", "clean"]
    elif "film" in intents:
        order = ["film", "vintage", "clean"]
    elif "vintage" in intents:
        order = ["vintage", "film", "warm"]
    elif "clean" in intents or "natural" in intents or "portrait" in intents:
        order = ["clean", "warm", "film"]
    elif scene == "street":
        order = ["mono", "film", "cool"]
    elif scene == "landscape":
        order = ["vivid", "clean", "cool"]
    else:
        order = ["clean", "warm", "film"]

    if mode == "refresh":
        rotated = [bucket for bucket in ["cool", "warm", "film", "vintage", "vivid", "clean", "mono"] if bucket not in order]
        order = rotated[:2] + order
    return _dedupe_order(order)


def _dedupe_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _score_option(
    option: dict[str, Any],
    *,
    intents: set[str],
    requested_family: str | None,
    anchor: dict[str, Any] | None,
    current_family: str | None,
    seen_filter_ids: set[str],
    mode: str,
) -> float:
    score = float(option.get("_scene_confidence", 0.0))
    if option.get("filter_id") in option.get("_scene_recommended_ids", set()):
        score += 3.0
    if option.get("favorite_boost"):
        score += 0.5
    if requested_family and option.get("catalog") == requested_family:
        score += 4.0

    tags = {str(tag).strip().lower() for tag in option.get("intent_tags", [])}
    for intent in intents:
        if intent in tags:
            score += 4.0
        elif intent == "film" and {"vintage", "warm"} & tags:
            score += 2.5
        elif intent == "warm" and {"film", "vintage", "golden"} & tags:
            score += 2.0
        elif intent == "clean" and {"natural", "portrait"} & tags:
            score += 1.5
        elif intent == "vintage" and {"warm", "nostalgia", "film"} & tags:
            score += 2.0
        elif intent == "natural" and {"clean", "balanced"} & tags:
            score += 1.5

    if anchor is not None:
        anchor_tags = {str(tag).strip().lower() for tag in anchor.get("intent_tags", [])}
        score += 1.75 * len(tags & anchor_tags)
        if option.get("catalog") == anchor.get("catalog"):
            score += 2.0 if mode == "refine" else 0.75
    elif current_family and option.get("catalog") == current_family and mode == "refine" and requested_family is None:
        score += 1.5
    if option.get("filter_id") in seen_filter_ids:
        score -= 100.0
    return score


def _pick_bucket_candidate(
    candidates: list[dict[str, Any]],
    *,
    bucket: str,
    used_ids: set[str],
    used_catalogs: set[str],
    requested_family: str | None,
    bucket_avoid: set[str],
) -> dict[str, Any] | None:
    bucket_candidates = [
        item
        for item in candidates
        if _bucket_for_option(item) == bucket and item.get("filter_id") not in used_ids
    ]
    if not bucket_candidates:
        return None
    preferred = [item for item in bucket_candidates if item.get("filter_id") not in bucket_avoid]
    if preferred:
        bucket_candidates = preferred
    if requested_family is None:
        fresh_catalog = [item for item in bucket_candidates if item.get("catalog") not in used_catalogs]
        if fresh_catalog:
            return fresh_catalog[0]
    return bucket_candidates[0]


def _choose_beginner_options(
    candidates: list[dict[str, Any]],
    *,
    scene: str,
    prompt: str,
    current_option: dict[str, Any] | None,
    current_family: str | None,
    seen_filter_ids: set[str],
    requested_family: str | None,
    mode: str,
    previous_options: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    intents = _parse_intent_tokens(prompt)
    if mode == "refresh" and not intents:
        intents = {"vintage", "cool"}
    previous_options = previous_options or []
    previous_filter_ids = {str(item.get("filter_id")) for item in previous_options}
    previous_buckets = {_bucket_for_option(item) for item in previous_options}
    scoped_candidates = list(candidates)
    if requested_family is not None:
        family_candidates = [item for item in scoped_candidates if item.get("catalog") == requested_family]
        if len(family_candidates) >= 3:
            scoped_candidates = family_candidates
    elif mode == "refine" and current_option is not None:
        same_family = [item for item in scoped_candidates if item.get("catalog") == current_option.get("catalog")]
        if len(same_family) >= 3:
            scoped_candidates = same_family
    scored = sorted(
        scoped_candidates,
        key=lambda item: _score_option(
            item,
            intents=intents,
            requested_family=requested_family,
            anchor=current_option,
            current_family=current_family,
            seen_filter_ids=seen_filter_ids,
            mode=mode,
        ),
        reverse=True,
    )
    order = _bucket_order(scene, intents, mode)
    chosen: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_catalogs: set[str] = set()

    for bucket in order:
        candidate = _pick_bucket_candidate(
            scored,
            bucket=bucket,
            used_ids=used_ids,
            used_catalogs=used_catalogs,
            requested_family=requested_family,
            bucket_avoid=previous_filter_ids if mode == "refresh" and bucket in previous_buckets else set(),
        )
        if candidate is None:
            continue
        chosen.append(candidate)
        used_ids.add(candidate["filter_id"])
        used_catalogs.add(candidate.get("catalog"))
        if len(chosen) >= 3:
            return chosen

    for candidate in scored:
        if candidate.get("filter_id") in used_ids:
            continue
        if mode == "refresh" and len(chosen) < 2 and _bucket_for_option(candidate) in previous_buckets:
            continue
        if requested_family is None and len(used_catalogs) < 2 and candidate.get("catalog") in used_catalogs:
            continue
        chosen.append(candidate)
        used_ids.add(candidate["filter_id"])
        used_catalogs.add(candidate.get("catalog"))
        if len(chosen) >= 3:
            break

    if len(chosen) < 3:
        for candidate in scored:
            if candidate.get("filter_id") in used_ids:
                continue
            chosen.append(candidate)
            used_ids.add(candidate["filter_id"])
            if len(chosen) >= 3:
                break

    return chosen
