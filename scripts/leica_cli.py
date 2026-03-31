#!/usr/bin/env python3
"""Unified vertical CLI for DAVINCI analysis, recommendation, and rendering."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

try:
    from .apply_flut_image import apply_flut_to_image
    from .blackroom_console import (
        StudioConsoleExperience,
        _box,
        _gradient_logo_lines,
        _logo_lines,
        available_themes,
    )
    from .leica_beginner import BeginnerStartFlow, beginner_brands_text, beginner_help_text
    from .leica_catalog_validate import (
        doctor_catalog_bundle,
        format_doctor_report,
        format_validation_report,
        validate_catalog_bundle,
    )
    from .leica_catalog import (
        DEFAULT_CATALOG,
        beginner_family_descriptions,
        build_recommendation_details,
        find_filter,
        infer_catalog_name,
        load_catalog_manifest,
        load_filter_index,
        normalize_catalog_name,
        scene_filters_for_catalog,
        select_recommended_filters,
        shipped_catalog_names,
        shipped_index_path,
    )
    from .leica_pipeline import ConsoleExperience, open_result, run_pipeline
    from .leica_product_store import ProductStore
    from .leica_recommend_rank import apply_favorite_boost
    from .leica_render_cache import clear_render_cache, inspect_render_cache
    from .leica_session import FilterSession, load_script_commands
    from .runtime_paths import examples_root
    from .scene_analyzer import analyze_scene
except ImportError:  # pragma: no cover - script execution fallback
    from apply_flut_image import apply_flut_to_image
    from blackroom_console import (
        StudioConsoleExperience,
        _box,
        _gradient_logo_lines,
        _logo_lines,
        available_themes,
    )
    from leica_beginner import BeginnerStartFlow, beginner_brands_text, beginner_help_text
    from leica_catalog_validate import (
        doctor_catalog_bundle,
        format_doctor_report,
        format_validation_report,
        validate_catalog_bundle,
    )
    from leica_catalog import (
        DEFAULT_CATALOG,
        beginner_family_descriptions,
        build_recommendation_details,
        find_filter,
        infer_catalog_name,
        load_catalog_manifest,
        load_filter_index,
        normalize_catalog_name,
        scene_filters_for_catalog,
        select_recommended_filters,
        shipped_catalog_names,
        shipped_index_path,
    )
    from leica_pipeline import ConsoleExperience, open_result, run_pipeline
    from leica_product_store import ProductStore
    from leica_recommend_rank import apply_favorite_boost
    from leica_render_cache import clear_render_cache, inspect_render_cache
    from leica_session import FilterSession, load_script_commands
    from runtime_paths import examples_root
    from scene_analyzer import analyze_scene


PRODUCT_OUTPUT_DIRNAME = "DAVINCI"
ACTIVATION_URL = "https://www.sensetime.com/cn/product-detail?categoryId=51133575"
EXAMPLE_IMAGE = examples_root() / "input_demo.png"


def build_parser(profile: dict[str, Any] | None = None) -> argparse.ArgumentParser:
    profile = profile or {}
    theme_choices = available_themes()
    default_catalog = str(profile.get("default_catalog") or DEFAULT_CATALOG)
    default_intensity = float(profile.get("intensity", 0.85))
    default_algorithm = str(profile.get("algorithm") or "tetrahedral")
    default_experience = str(profile.get("experience") or "studio")
    default_theme = str(profile.get("theme") or "blackroom")
    default_top_k = int(profile.get("top_k", 3))

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "DAVINCI vertical CLI for analysis, recommendation, and protected rendering.\n\n"
            "First run:\n"
            "  davinci\n"
            "  davinci demo\n\n"
            "With your own photo:\n"
            "  davinci start\n"
            "  # then drag your photo path, paste it, or press Enter to pick one"
        ),
        epilog="Use `davinci help` for the simpler beginner guide.",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)
    parser.set_defaults(handler=cmd_home)

    home_parser = subparsers.add_parser("home", help="Show the DAVINCI product entry screen")
    home_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    home_parser.set_defaults(handler=cmd_home)

    activate_parser = subparsers.add_parser("activate", help="Open the official DAVINCI page and complete one-time activation")
    activate_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    activate_parser.set_defaults(handler=cmd_activate)

    start_parser = subparsers.add_parser("start", help="Beginner-friendly DAVINCI entry")
    start_parser.add_argument("--input", help="Input image path")
    start_parser.add_argument("--pick", action="store_true", help="Open a file picker to choose the image")
    start_parser.add_argument("--catalog", help="Limit to one built-in style family, such as leica or fuji")
    start_parser.add_argument("--index", help="Optional explicit index.json path for one style family")
    start_parser.add_argument("--output-dir", help="Directory for beginner flow outputs")
    start_parser.add_argument("--prompt", default="帮我调色", help="Plain-language request, such as 复古一点")
    start_parser.add_argument("--intensity", type=float, default=default_intensity, help="Blend intensity [0,1]")
    start_parser.add_argument(
        "--algorithm",
        choices=["tetrahedral", "trilinear"],
        default=default_algorithm,
        help="LUT interpolation algorithm",
    )
    start_parser.add_argument("--theme", choices=theme_choices, default=default_theme, help="Start presentation theme")
    start_parser.add_argument("--pace-ms", type=int, default=None, help="Delay between stage panels")
    start_parser.add_argument("--no-color", action="store_true", help="Disable ANSI accent colors")
    start_parser.add_argument("--no-open", action="store_true", help="Do not auto-open generated outputs")
    start_parser.add_argument("--command", action="append", dest="start_commands", help="One scripted beginner command")
    start_parser.add_argument("--script", help="Path to a file containing scripted beginner commands")
    start_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    start_parser.set_defaults(handler=cmd_start)

    demo_parser = subparsers.add_parser("demo", help="Run DAVINCI on the built-in sample photo")
    demo_parser.add_argument("--theme", choices=theme_choices, default=default_theme, help="Demo presentation theme")
    demo_parser.add_argument("--prompt", default="帮我调色", help="Demo request text")
    demo_parser.add_argument("--catalog", help="Optional style family limit for the demo")
    demo_parser.add_argument("--output-dir", help="Directory for demo outputs")
    demo_parser.add_argument("--intensity", type=float, default=default_intensity, help="Blend intensity [0,1]")
    demo_parser.add_argument(
        "--algorithm",
        choices=["tetrahedral", "trilinear"],
        default=default_algorithm,
        help="LUT interpolation algorithm",
    )
    demo_parser.add_argument("--pace-ms", type=int, default=None, help="Delay between stage panels")
    demo_parser.add_argument("--no-color", action="store_true", help="Disable ANSI accent colors")
    demo_parser.add_argument("--no-open", action="store_true", help="Do not auto-open generated outputs")
    demo_parser.add_argument("--command", action="append", dest="demo_commands", help="One scripted beginner command")
    demo_parser.add_argument("--script", help="Path to a file containing scripted demo commands")
    demo_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    demo_parser.set_defaults(handler=cmd_demo)

    continue_parser = subparsers.add_parser("continue", help="Continue from the current session or latest result")
    continue_parser.add_argument("--session-id", help="Resume a specific saved session")
    continue_parser.add_argument("--open", action="store_true", help="Open the best available artifact")
    continue_parser.add_argument("--interactive", action="store_true", help="Resume the saved session workbench interactively")
    continue_parser.add_argument("--command", action="append", dest="continue_commands", help="One scripted command for the resumed session")
    continue_parser.add_argument("--script", help="Path to a file containing scripted session commands")
    continue_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    continue_parser.set_defaults(handler=cmd_continue)

    brands_parser = subparsers.add_parser("brands", help="Show beginner-friendly style family summaries")
    brands_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    brands_parser.set_defaults(handler=cmd_brands)

    help_parser = subparsers.add_parser("help", help="Show beginner-friendly product help")
    help_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    help_parser.set_defaults(handler=cmd_help)

    catalog_list_parser = subparsers.add_parser("list-catalogs", help="List built-in filter catalogs")
    catalog_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    catalog_list_parser.set_defaults(handler=cmd_list_catalogs)

    list_parser = subparsers.add_parser("list-filters", help="List filters from one catalog or index")
    _add_catalog_args(list_parser, default_catalog=default_catalog)
    list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    list_parser.set_defaults(handler=cmd_list_filters)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze scene and color stats")
    analyze_parser.add_argument("--input", required=True, help="Input image path")
    _add_catalog_args(analyze_parser, default_catalog=default_catalog)
    analyze_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    analyze_parser.set_defaults(handler=cmd_analyze)

    recommend_parser = subparsers.add_parser("recommend", help="Recommend looks for an image")
    recommend_parser.add_argument("--input", required=True, help="Input image path")
    _add_catalog_args(recommend_parser, default_catalog=default_catalog)
    recommend_parser.add_argument("--top-k", type=int, default=default_top_k, help="Number of recommendations to return")
    recommend_parser.add_argument(
        "--full-preview",
        action="store_true",
        help="Return the full catalog instead of the curated scene subset",
    )
    recommend_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    recommend_parser.set_defaults(handler=cmd_recommend)

    render_parser = subparsers.add_parser("render", help="Apply one filter directly")
    render_parser.add_argument("--input", required=True, help="Input image path")
    render_parser.add_argument(
        "--filter",
        required=True,
        help="Filter selection: 1-based index, filter_id, or display name",
    )
    _add_catalog_args(render_parser, default_catalog=default_catalog)
    render_parser.add_argument("--output", help="Explicit output image path")
    render_parser.add_argument("--output-dir", help="Output directory used when --output is omitted")
    render_parser.add_argument("--intensity", type=float, default=default_intensity, help="Blend intensity [0,1]")
    render_parser.add_argument(
        "--algorithm",
        choices=["tetrahedral", "trilinear"],
        default=default_algorithm,
        help="LUT interpolation algorithm",
    )
    render_parser.add_argument("--open", action="store_true", help="Open the rendered image")
    render_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    render_parser.set_defaults(handler=cmd_render)

    auto_parser = subparsers.add_parser(
        "auto",
        help="Analyze, recommend, render contact sheet, and optionally apply a final look",
    )
    _add_surface_args(
        auto_parser,
        allow_plain=True,
        default_catalog=default_catalog,
        default_intensity=default_intensity,
        default_algorithm=default_algorithm,
        default_mode="top1" if default_experience == "studio" else "preview",
    )
    auto_parser.set_defaults(handler=cmd_auto)

    studio_parser = subparsers.add_parser(
        "studio",
        help="Run the premium blackroom console on top of the auto pipeline",
    )
    _add_surface_args(
        studio_parser,
        allow_plain=False,
        default_catalog=default_catalog,
        default_intensity=default_intensity,
        default_algorithm=default_algorithm,
        default_mode="top1",
    )
    studio_parser.add_argument(
        "--pace-ms",
        type=int,
        default=None,
        help="Delay between stage panels. Default is terminal-aware.",
    )
    studio_parser.add_argument("--no-color", action="store_true", help="Disable ANSI accent colors")
    studio_parser.set_defaults(handler=cmd_studio)

    profile_parser = subparsers.add_parser("profile", help="Manage persistent CLI defaults")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command", required=True)
    profile_show_parser = profile_subparsers.add_parser("show", help="Show the active profile")
    profile_show_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    profile_show_parser.set_defaults(handler=cmd_profile_show)
    profile_set_parser = profile_subparsers.add_parser("set", help="Update the active profile")
    profile_set_parser.add_argument("--default-catalog", help="Default catalog name")
    profile_set_parser.add_argument("--intensity", type=float, help="Default blend intensity [0,1]")
    profile_set_parser.add_argument(
        "--algorithm",
        choices=["tetrahedral", "trilinear"],
        help="Default interpolation algorithm",
    )
    profile_set_parser.add_argument("--experience", choices=["auto", "studio"], help="Default theatrical surface")
    profile_set_parser.add_argument("--theme", choices=theme_choices, help="Default studio/session theme")
    profile_set_parser.add_argument("--top-k", type=int, help="Default recommendation count")
    profile_set_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    profile_set_parser.set_defaults(handler=cmd_profile_set)
    profile_reset_parser = profile_subparsers.add_parser("reset", help="Reset profile to built-in defaults")
    profile_reset_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    profile_reset_parser.set_defaults(handler=cmd_profile_reset)

    favorites_parser = subparsers.add_parser("favorites", help="Manage favorite filters")
    favorites_subparsers = favorites_parser.add_subparsers(dest="favorites_command", required=True)
    favorites_list_parser = favorites_subparsers.add_parser("list", help="List favorites")
    _add_catalog_args(favorites_list_parser, default_catalog=default_catalog)
    favorites_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    favorites_list_parser.set_defaults(handler=cmd_favorites_list)
    favorites_add_parser = favorites_subparsers.add_parser("add", help="Add a favorite filter")
    favorites_add_parser.add_argument("--filter", required=True, help="Filter selection query")
    _add_catalog_args(favorites_add_parser, default_catalog=default_catalog)
    favorites_add_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    favorites_add_parser.set_defaults(handler=cmd_favorites_add)
    favorites_remove_parser = favorites_subparsers.add_parser("remove", help="Remove a favorite filter")
    favorites_remove_parser.add_argument("--filter", required=True, help="Filter selection query or raw filter_id")
    _add_catalog_args(favorites_remove_parser, default_catalog=default_catalog)
    favorites_remove_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    favorites_remove_parser.set_defaults(handler=cmd_favorites_remove)
    favorites_clear_parser = favorites_subparsers.add_parser("clear", help="Clear favorites")
    _add_catalog_args(favorites_clear_parser, default_catalog=default_catalog)
    favorites_clear_parser.add_argument("--all", action="store_true", help="Clear all catalogs instead of one")
    favorites_clear_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    favorites_clear_parser.set_defaults(handler=cmd_favorites_clear)

    history_parser = subparsers.add_parser("history", help="Inspect global render history")
    history_subparsers = history_parser.add_subparsers(dest="history_command", required=True)
    history_list_parser = history_subparsers.add_parser("list", help="List recent history events")
    history_list_parser.add_argument("--limit", type=int, default=10, help="Maximum number of events to return")
    history_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    history_list_parser.set_defaults(handler=cmd_history_list)
    history_clear_parser = history_subparsers.add_parser("clear", help="Clear global history")
    history_clear_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    history_clear_parser.set_defaults(handler=cmd_history_clear)

    workspace_parser = subparsers.add_parser("workspace", help="Manage named product workspaces")
    workspace_subparsers = workspace_parser.add_subparsers(dest="workspace_command", required=True)
    workspace_show_parser = workspace_subparsers.add_parser("show", help="Show one workspace status")
    workspace_show_parser.add_argument("--name", help="Workspace name; defaults to current")
    workspace_show_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    workspace_show_parser.set_defaults(handler=cmd_workspace_show)
    workspace_switch_parser = workspace_subparsers.add_parser("switch", help="Switch the current workspace")
    workspace_switch_parser.add_argument("name", help="Workspace name")
    workspace_switch_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    workspace_switch_parser.set_defaults(handler=cmd_workspace_switch)
    workspace_list_parser = workspace_subparsers.add_parser("list", help="List known workspaces")
    workspace_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    workspace_list_parser.set_defaults(handler=cmd_workspace_list)

    sessions_parser = subparsers.add_parser("sessions", help="Inspect persisted sessions outside the workbench")
    sessions_subparsers = sessions_parser.add_subparsers(dest="sessions_command", required=True)
    sessions_list_parser = sessions_subparsers.add_parser("list", help="List stored sessions")
    sessions_list_parser.add_argument("--workspace", help="Limit to one workspace; defaults to current")
    sessions_list_parser.add_argument("--all-workspaces", action="store_true", help="Ignore current workspace and list every session")
    sessions_list_parser.add_argument("--all", action="store_true", help="Include closed sessions")
    sessions_list_parser.add_argument("--limit", type=int, default=20, help="Maximum sessions to return")
    sessions_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    sessions_list_parser.set_defaults(handler=cmd_sessions_list)
    sessions_show_parser = sessions_subparsers.add_parser("show", help="Show one stored session")
    sessions_show_parser.add_argument("--session-id", help="Session id; defaults to current session")
    sessions_show_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    sessions_show_parser.set_defaults(handler=cmd_sessions_show)
    sessions_close_parser = sessions_subparsers.add_parser("close", help="Mark one stored session as closed")
    sessions_close_parser.add_argument("--session-id", help="Session id; defaults to current session")
    sessions_close_parser.add_argument("--reason", help="Optional close reason")
    sessions_close_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    sessions_close_parser.set_defaults(handler=cmd_sessions_close)

    cache_parser = subparsers.add_parser("cache", help="Inspect pipeline render cache")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", required=True)
    cache_list_parser = cache_subparsers.add_parser("list", help="List cache entries")
    cache_list_parser.add_argument("--limit", type=int, default=20, help="Maximum cache entries to return")
    cache_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    cache_list_parser.set_defaults(handler=cmd_cache_list)
    cache_clear_parser = cache_subparsers.add_parser("clear", help="Clear all cache entries")
    cache_clear_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    cache_clear_parser.set_defaults(handler=cmd_cache_clear)

    catalog_parser = subparsers.add_parser("catalog", help="Catalog quality checks")
    catalog_subparsers = catalog_parser.add_subparsers(dest="catalog_command", required=True)
    catalog_validate_parser = catalog_subparsers.add_parser("validate", help="Validate one catalog bundle")
    _add_catalog_args(catalog_validate_parser, default_catalog=default_catalog)
    catalog_validate_parser.add_argument("--strict", action="store_true", help="Promote warnings to errors")
    catalog_validate_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    catalog_validate_parser.set_defaults(handler=cmd_catalog_validate)
    catalog_doctor_parser = catalog_subparsers.add_parser("doctor", help="Diagnose catalog issues and suggest fixes")
    _add_catalog_args(catalog_doctor_parser, default_catalog=default_catalog)
    catalog_doctor_parser.add_argument("--strict", action="store_true", help="Promote warnings to errors")
    catalog_doctor_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    catalog_doctor_parser.set_defaults(handler=cmd_catalog_doctor)

    session_parser = subparsers.add_parser("session", help="Run a stateful filter workbench")
    session_parser.add_argument("--input", required=True, help="Input image path")
    _add_catalog_args(session_parser, default_catalog=default_catalog)
    session_parser.add_argument("--output-dir", help="Directory for session artifacts")
    session_parser.add_argument("--intensity", type=float, default=default_intensity, help="Blend intensity [0,1]")
    session_parser.add_argument(
        "--algorithm",
        choices=["tetrahedral", "trilinear"],
        default=default_algorithm,
        help="LUT interpolation algorithm",
    )
    session_parser.add_argument("--top-k", type=int, default=default_top_k, help="Recommendation count for bootstrap")
    session_parser.add_argument("--theme", choices=theme_choices, default=default_theme, help="Session presentation theme")
    session_parser.add_argument("--command", action="append", dest="session_commands", help="One scripted session command")
    session_parser.add_argument("--script", help="Path to a file containing scripted session commands")
    session_parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    session_parser.set_defaults(handler=cmd_session)

    studio_parser.add_argument("--theme", choices=theme_choices, default=default_theme, help="Studio presentation theme")

    return parser


def _add_catalog_args(parser: argparse.ArgumentParser, *, default_catalog: str) -> None:
    parser.add_argument(
        "--catalog",
        default=default_catalog,
        help="Built-in catalog name, such as leica or fuji",
    )
    parser.add_argument("--index", help="Optional explicit index.json path")


def _add_surface_args(
    parser: argparse.ArgumentParser,
    *,
    allow_plain: bool,
    default_catalog: str,
    default_intensity: float,
    default_algorithm: str,
    default_mode: str,
) -> None:
    parser.add_argument("--input", required=True, help="Input image path")
    _add_catalog_args(parser, default_catalog=default_catalog)
    parser.add_argument("--output-dir", help="Directory for contact sheet and final image")
    parser.add_argument("--prompt", default="帮我调色", help="Prompt text shown in experience mode")
    parser.add_argument("--intensity", type=float, default=default_intensity, help="Blend intensity [0,1]")
    parser.add_argument(
        "--algorithm",
        choices=["tetrahedral", "trilinear"],
        default=default_algorithm,
        help="LUT interpolation algorithm",
    )
    parser.add_argument(
        "--mode",
        choices=["top1", "preview"],
        default=default_mode,
        help="top1 applies the strongest recommendation, preview only builds the contact sheet",
    )
    parser.add_argument(
        "--full-preview",
        action="store_true",
        help="Render all filters in the contact sheet instead of curated recommendations",
    )
    parser.add_argument(
        "--choose",
        action="store_true",
        help="Prompt after the contact sheet so the user can choose a filter number",
    )
    parser.add_argument(
        "--select-filter",
        help="Skip prompting and apply a specific filter from the generated shortlist by index/name/id",
    )
    if allow_plain:
        parser.add_argument(
            "--plain",
            action="store_true",
            help="Disable the immersive console and print a short summary instead",
        )
    parser.add_argument("--open", action="store_true", help="Open generated outputs")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")


def cmd_list_catalogs(args: argparse.Namespace) -> int:
    catalogs = shipped_catalog_names()
    payload = {
        "command": "list-catalogs",
        "catalogs": [
            {
                "catalog": name,
                "index_path": str(shipped_index_path(name).expanduser().resolve()),
            }
            for name in catalogs
        ],
    }
    if args.json:
        _print_json(payload)
        return 0

    print("[CATALOGS]")
    for item in payload["catalogs"]:
        print(f"- {item['catalog']} -> {item['index_path']}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    import io

    if _needs_first_activation(args):
        _print_startup_logo(getattr(args, "theme", "blackroom"))
    activation_rc = _maybe_run_first_activation(args, source="start")
    if activation_rc is not None:
        return activation_rc

    resolved_input = _resolve_start_input(args)
    if resolved_input == "__demo__":
        demo_args = argparse.Namespace(
            theme=args.theme,
            prompt=args.prompt,
            catalog=args.catalog,
            output_dir=args.output_dir,
            intensity=args.intensity,
            algorithm=args.algorithm,
            pace_ms=args.pace_ms,
            no_color=args.no_color,
            no_open=args.no_open,
            demo_commands=list(args.start_commands or []),
            script=args.script,
            json=args.json,
            store=_store(args),
        )
        return cmd_demo(demo_args)
    input_path = Path(str(resolved_input)).expanduser().resolve()
    output_dir = _resolve_auto_output_dir(input_path, args.output_dir)
    commands = list(args.start_commands or [])
    if args.script:
        commands.extend(load_script_commands(args.script))
    stream: Any = io.StringIO() if args.json else sys.stdout
    flow = BeginnerStartFlow(
        store=_store(args),
        input_path=input_path,
        output_dir=output_dir,
        sources=_resolve_beginner_sources(args.catalog, args.index),
        prompt=args.prompt,
        intensity=args.intensity,
        algorithm=args.algorithm,
        theme=args.theme,
        stream=stream,
        input_fn=input,
        auto_open=(not args.no_open) and (not args.json),
        use_color=not args.no_color,
        pace_ms=args.pace_ms,
    )
    if commands:
        summary = flow.run_commands(commands)
    elif args.json:
        summary = flow.start()
    else:
        summary = flow.run_interactive()
    if args.json:
        payload = {"command": "start", **summary}
        _print_json(payload)
    return 0


def cmd_home(args: argparse.Namespace) -> int:
    store = _store(args)
    payload = _build_home_payload(store)
    if getattr(args, "json", False):
        _print_json(payload)
        return 0

    _print_home_screen(payload, theme=store.load_profile()["theme"])
    if not _can_prompt():
        return 0

    response = input(
        "请输入 1 / 2 / 3，或直接拖入照片路径；直接回车先看演示: "
    ).strip()
    token = _normalize_input_token(response)
    choice = token.lower()
    if choice in {"", "demo", "演示"}:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-demo")
        if activation_rc is not None:
            return activation_rc
        return cmd_demo(_default_demo_args(store))
    if choice in {"1", "leica", "莱卡"}:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-leica")
        if activation_rc is not None:
            return activation_rc
        return _run_home_guided_flow(store, preferred_catalog="leica", start_prompt="看莱卡")
    if choice in {"2", "fuji", "富士"}:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-fuji")
        if activation_rc is not None:
            return activation_rc
        return _run_home_guided_flow(store, preferred_catalog="fuji", start_prompt="看富士")
    if choice in {"3", "recommend", "auto", "推荐", "不确定"}:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-recommend")
        if activation_rc is not None:
            return activation_rc
        return _run_home_guided_flow(store, preferred_catalog=None)
    if "看莱卡" in choice:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-leica")
        if activation_rc is not None:
            return activation_rc
        return _run_home_guided_flow(store, preferred_catalog="leica", start_prompt="看莱卡")
    if "看富士" in choice:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-fuji")
        if activation_rc is not None:
            return activation_rc
        return _run_home_guided_flow(store, preferred_catalog="fuji", start_prompt="看富士")
    if choice in {"pick", "选择", "选图"}:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-pick")
        if activation_rc is not None:
            return activation_rc
        return cmd_start(_default_pick_start_args(store))
    if choice in {"start", "开始"}:
        activation_rc = _maybe_run_first_activation(args, store=store, source="home-start")
        if activation_rc is not None:
            return activation_rc
        return cmd_start(_default_start_args(store))
    if choice in {"continue", "继续"}:
        return cmd_continue(_default_continue_args(store))
    if choice in {"brands", "系列", "风格"}:
        return cmd_brands(argparse.Namespace(json=False, store=store))
    if choice in {"help", "帮助"}:
        return cmd_help(argparse.Namespace(json=False, store=store))
    activation_rc = _maybe_run_first_activation(args, store=store, source="home-photo")
    if activation_rc is not None:
        return activation_rc
    return _run_home_photo_flow(store, response, preferred_catalog=None)


def cmd_activate(args: argparse.Namespace) -> int:
    store = _store(args)
    activation = store.load_activation()
    payload = {
        "command": "activate",
        "activated": bool(activation.get("activated")),
        "activated_at": activation.get("activated_at"),
        "activation_url": activation.get("activation_url") or ACTIVATION_URL,
    }
    if payload["activated"]:
        if getattr(args, "json", False):
            _print_json(payload)
        else:
            print("[ACTIVATE]")
            print("DAVINCI 已激活。")
            print(f"url={payload['activation_url']}")
            print(f"activated_at={payload['activated_at']}")
        return 0

    if not _can_prompt():
        payload["message"] = "Run `davinci activate` in an interactive terminal to finish activation."
        if getattr(args, "json", False):
            _print_json(payload)
            return 0
        print(f"[ACTIVATE] 请先打开这个网址：{ACTIVATION_URL}", file=sys.stderr)
        return 2

    rc, activated_payload = _run_activation_flow(store, source="manual")
    if getattr(args, "json", False):
        _print_json(activated_payload)
    return rc


def _run_home_guided_flow(
    store: ProductStore,
    *,
    preferred_catalog: str | None,
    start_prompt: str | None = None,
) -> int:
    response = input("把照片拖到这里，输入文件路径，或直接回车打开选图窗口: ").strip()
    return _run_home_photo_flow(store, response, preferred_catalog=preferred_catalog, start_prompt=start_prompt)


def _run_home_photo_flow(
    store: ProductStore,
    response: str,
    *,
    preferred_catalog: str | None,
    start_prompt: str | None = None,
) -> int:
    token = _normalize_input_token(response)
    if not token:
        token = _pick_image_path()
    input_path = Path(token).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    prompt = start_prompt or _prompt_for_home_direction(preferred_catalog)
    start_args = _default_start_args(store)
    start_args.input = str(input_path)
    start_args.catalog = None
    start_args.prompt = prompt
    return cmd_start(start_args)


def _prompt_for_home_direction(preferred_catalog: str | None) -> str:
    del preferred_catalog
    choice = input("你想要哪种感觉？1 胶片感  2 纪实感，直接回车=胶片感: ").strip().lower()
    if choice in {"2", "纪实", "纪实感", "documentary", "doc"}:
        return "看莱卡"
    if choice in {"1", "", "胶片", "胶片感", "film", "filmic"}:
        return "看富士"
    return "看富士"


def cmd_demo(args: argparse.Namespace) -> int:
    import io

    if _needs_first_activation(args):
        _print_startup_logo(getattr(args, "theme", "blackroom"))
    activation_rc = _maybe_run_first_activation(args, source="demo")
    if activation_rc is not None:
        return activation_rc

    if not EXAMPLE_IMAGE.exists():
        raise FileNotFoundError(f"Bundled demo image not found: {EXAMPLE_IMAGE}")

    input_path = EXAMPLE_IMAGE.resolve()
    output_dir = _resolve_demo_output_dir(input_path, args.output_dir)
    commands = list(args.demo_commands or [])
    if args.script:
        commands.extend(load_script_commands(args.script))
    stream: Any = io.StringIO() if args.json else sys.stdout
    flow = BeginnerStartFlow(
        store=_store(args),
        input_path=input_path,
        output_dir=output_dir,
        sources=_resolve_beginner_sources(args.catalog, None),
        prompt=args.prompt,
        intensity=args.intensity,
        algorithm=args.algorithm,
        theme=args.theme,
        stream=stream,
        input_fn=input,
        auto_open=(not args.no_open) and (not args.json),
        use_color=not args.no_color,
        pace_ms=args.pace_ms,
    )
    summary = flow.run_commands(commands) if commands else flow.start()
    payload = {
        "command": "demo",
        "demo_image": str(input_path),
        "next_steps": [
            "davinci start",
            "davinci brands",
            "davinci continue",
        ],
        "results_root": str(output_dir),
        **summary,
    }
    if args.json:
        _print_json(payload)
    else:
        _print_demo_next_steps(args.theme, output_dir)
    return 0


def cmd_continue(args: argparse.Namespace) -> int:
    import io

    store = _store(args)
    commands = list(args.continue_commands or [])
    if args.script:
        commands.extend(load_script_commands(args.script))

    session = _resolve_continue_session(store, args.session_id)
    if session is not None:
        if session.get("closed_at") and (args.interactive or commands):
            raise ValueError("Cannot continue interactively from a closed session")

        if args.interactive or commands:
            stream: Any = io.StringIO() if args.json else sys.stdout
            resumed = FilterSession(
                store=store,
                input_path=session["input_path"],
                output_dir=session["output_dir"],
                index_path=session["index_path"],
                catalog=session["catalog"],
                intensity=store.load_profile()["intensity"],
                algorithm=store.load_profile()["algorithm"],
                top_k=store.load_profile()["top_k"],
                theme=session.get("theme") or store.load_profile()["theme"],
                stream=stream,
                input_fn=input,
                existing_session=session,
            )
            summary = resumed.run_commands(commands) if commands else resumed.run_interactive()
            payload = {"command": "continue", "resume_type": "session", **summary}
            if args.json:
                _print_json(payload)
            return 0

        payload = _build_continue_session_payload(session, open_artifact=args.open)
        if args.json:
            _print_json(payload)
            return 0
        _print_continue_text(payload)
        return 0

    if args.interactive or commands:
        payload = _build_continue_empty_payload()
        if args.json:
            _print_json(payload)
            return 0
        _print_continue_text(payload)
        return 0

    latest = _resolve_continue_history(store)
    if latest is None:
        payload = _build_continue_empty_payload()
        if args.json:
            _print_json(payload)
            return 0
        _print_continue_text(payload)
        return 0
    payload = _build_continue_history_payload(latest, open_artifact=args.open)
    if args.json:
        _print_json(payload)
        return 0
    _print_continue_text(payload)
    return 0


def cmd_brands(args: argparse.Namespace) -> int:
    families = beginner_family_descriptions(shipped_catalog_names())
    payload = {
        "command": "brands",
        "families": families,
        "next_steps": [
            "davinci demo",
            "davinci start",
        ],
        "text": beginner_brands_text(),
    }
    if args.json:
        _print_json(payload)
        return 0
    print(payload["text"])
    return 0


def cmd_help(args: argparse.Namespace) -> int:
    families = beginner_family_descriptions(shipped_catalog_names())
    payload = {
        "command": "help",
        "families": families,
        "text": beginner_help_text(str(_default_output_root()), families=families),
    }
    if args.json:
        _print_json(payload)
        return 0
    print(payload["text"])
    return 0


def cmd_list_filters(args: argparse.Namespace) -> int:
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    filters = load_filter_index(index_path, catalog=catalog)
    payload = {
        "command": "list-filters",
        "catalog": catalog,
        "count": len(filters),
        "index_path": str(index_path),
        "filters": [
            {
                "position": idx,
                "catalog": item.get("catalog", catalog),
                "filter_id": item["filter_id"],
                "display_name": item["display_name"],
                "flut_file": item.get("flut_file"),
            }
            for idx, item in enumerate(filters, start=1)
        ],
    }
    if args.json:
        _print_json(payload)
        return 0

    print(f"[CATALOG] {catalog}")
    print(f"index={payload['index_path']}")
    for item in payload["filters"]:
        print(f"{item['position']:>2}. {item['display_name']} ({item['filter_id']})")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser().resolve()
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    scene_result = analyze_scene(
        input_path,
        scene_filters=scene_filters_for_catalog(catalog, index_path=index_path),
        catalog=catalog,
        index_path=index_path,
    )
    payload = {
        "command": "analyze",
        "catalog": catalog,
        "index_path": str(index_path),
        "input_path": str(input_path),
        **scene_result,
    }
    if args.json:
        _print_json(payload)
        return 0

    print(f"[ANALYZE] {input_path}")
    print(f"catalog={catalog} scene={scene_result['scene']} confidence={scene_result['confidence']:.0%}")
    stats = scene_result["color_stats"]
    print(
        "stats="
        f"warm={stats['warm_ratio']:.3f} "
        f"cool={stats['cool_ratio']:.3f} "
        f"sat={stats['saturation_avg']:.3f} "
        f"brightness={stats['brightness_avg']:.3f} "
        f"contrast={stats['contrast']:.3f}"
    )
    print("recommended_ids=" + ", ".join(scene_result["recommended_filters"]))
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser().resolve()
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    scene_result = analyze_scene(
        input_path,
        scene_filters=scene_filters_for_catalog(catalog, index_path=index_path),
        catalog=catalog,
        index_path=index_path,
    )
    all_filters = load_filter_index(index_path, catalog=catalog)
    top_k = max(args.top_k, 1)
    recommended = select_recommended_filters(
        scene_result_dict=scene_result,
        all_filters=all_filters,
        full_preview=args.full_preview,
    )
    recommended = apply_favorite_boost(
        recommended,
        favorite_filter_ids=_store(args).list_favorites(catalog),
    )[:top_k]
    details = build_recommendation_details(
        scene_result["scene"],
        recommended,
        catalog=catalog,
        index_path=index_path,
    )
    payload = {
        "command": "recommend",
        "catalog": catalog,
        "input_path": str(input_path),
        "index_path": str(index_path),
        "scene": scene_result["scene"],
        "confidence": scene_result["confidence"],
        "color_stats": scene_result["color_stats"],
        "recommendations": [
            {
                "rank": idx,
                "catalog": item.get("catalog", catalog),
                "filter_id": item["filter_id"],
                "display_name": item["display_name"],
                "reason": item["reason"],
                "scene": item["scene"],
                "flut_file": item.get("flut_file"),
                "favorite_boost": bool(item.get("favorite_boost")),
            }
            for idx, item in enumerate(details, start=1)
        ],
    }
    if args.json:
        _print_json(payload)
        return 0

    print(f"[RECOMMEND] {input_path}")
    print(f"catalog={catalog} scene={payload['scene']} confidence={payload['confidence']:.0%}")
    for item in payload["recommendations"]:
        print(
            f"{item['rank']}. {item['display_name']} "
            f"({item['filter_id']}) - {item['reason']}"
        )
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser().resolve()
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    filters = load_filter_index(index_path, catalog=catalog)
    position, filter_item = find_filter(filters, args.filter)
    output_path = _resolve_render_output_path(
        input_path=input_path,
        filter_id=filter_item["filter_id"],
        output=args.output,
        output_dir=args.output_dir,
    )
    result = apply_flut_to_image(
        flut_path=filter_item["flut_file"],
        input_path=input_path,
        output_path=output_path,
        intensity=args.intensity,
        algorithm=args.algorithm,
    )

    open_status: dict[str, Any] | None = None
    if args.open:
        success, error = open_result(output_path)
        open_status = {"success": success, "error": error}

    payload = {
        "command": "render",
        "catalog": catalog,
        "input_path": str(input_path),
        "index_path": str(index_path),
        "output_path": str(output_path),
        "filter": {
            "position": position + 1,
            "catalog": filter_item.get("catalog", catalog),
            "filter_id": filter_item["filter_id"],
            "display_name": filter_item["display_name"],
            "flut_file": filter_item.get("flut_file"),
        },
        "algorithm": result["algorithm"],
        "intensity": result["intensity"],
        "open_result": open_status,
    }
    _record_history_event(
        args,
        command="render",
        catalog=catalog,
        input_path=input_path,
        index_path=index_path,
        output_path=output_path,
        filter_item=filter_item,
        scene=None,
        session_id=None,
    )
    if args.json:
        _print_json(payload)
        return 0

    print(f"[RENDER] {filter_item['display_name']} -> {output_path}")
    print(f"catalog={catalog} algorithm={result['algorithm']} intensity={result['intensity']:.3f}")
    if open_status is not None:
        print(f"open_success={open_status['success']}")
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    return _run_pipeline_surface(args, experience_mode="auto")


def cmd_studio(args: argparse.Namespace) -> int:
    return _run_pipeline_surface(args, experience_mode="studio")


def cmd_profile_show(args: argparse.Namespace) -> int:
    payload = {
        "command": "profile.show",
        "profile": _store(args).load_profile(),
    }
    if args.json:
        _print_json(payload)
        return 0
    print("[PROFILE]")
    for key, value in payload["profile"].items():
        print(f"{key}={value}")
    return 0


def cmd_profile_set(args: argparse.Namespace) -> int:
    store = _store(args)
    profile = store.load_profile()
    updates = {
        "default_catalog": args.default_catalog,
        "intensity": args.intensity,
        "algorithm": args.algorithm,
        "experience": args.experience,
        "theme": args.theme,
        "top_k": args.top_k,
    }
    profile.update({key: value for key, value in updates.items() if value is not None})
    payload = {
        "command": "profile.set",
        "profile": store.save_profile(profile),
    }
    if args.json:
        _print_json(payload)
        return 0
    print("[PROFILE UPDATED]")
    for key, value in payload["profile"].items():
        print(f"{key}={value}")
    return 0


def cmd_profile_reset(args: argparse.Namespace) -> int:
    payload = {
        "command": "profile.reset",
        "profile": _store(args).reset_profile(),
    }
    if args.json:
        _print_json(payload)
        return 0
    print("[PROFILE RESET]")
    for key, value in payload["profile"].items():
        print(f"{key}={value}")
    return 0


def cmd_favorites_list(args: argparse.Namespace) -> int:
    store = _store(args)
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    filters = load_filter_index(index_path, catalog=catalog)
    by_id = {item["filter_id"]: item for item in filters}
    entries = []
    for filter_id in store.list_favorites(catalog):
        item = by_id.get(filter_id)
        entries.append(
            {
                "catalog": catalog,
                "filter_id": filter_id,
                "display_name": item["display_name"] if item else filter_id,
                "stale": item is None,
            }
        )
    payload = {
        "command": "favorites.list",
        "catalog": catalog,
        "index_path": str(index_path),
        "favorites": entries,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[FAVORITES] {catalog}")
    if not entries:
        print("(empty)")
        return 0
    for idx, item in enumerate(entries, start=1):
        suffix = " [stale]" if item["stale"] else ""
        print(f"{idx}. {item['display_name']} ({item['filter_id']}){suffix}")
    return 0


def cmd_favorites_add(args: argparse.Namespace) -> int:
    store = _store(args)
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    filters = load_filter_index(index_path, catalog=catalog)
    _, filter_item = find_filter(filters, args.filter)
    store.add_favorite(catalog=catalog, filter_id=filter_item["filter_id"])
    payload = {
        "command": "favorites.add",
        "catalog": catalog,
        "index_path": str(index_path),
        "filter": {
            "filter_id": filter_item["filter_id"],
            "display_name": filter_item["display_name"],
        },
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[FAVORITE ADDED] {filter_item['display_name']} ({filter_item['filter_id']})")
    return 0


def cmd_favorites_remove(args: argparse.Namespace) -> int:
    store = _store(args)
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    filters = load_filter_index(index_path, catalog=catalog)
    try:
        _, filter_item = find_filter(filters, args.filter)
        filter_id = filter_item["filter_id"]
        display_name = filter_item["display_name"]
    except ValueError:
        filter_id = args.filter.strip()
        display_name = filter_id
    store.remove_favorite(catalog=catalog, filter_id=filter_id)
    payload = {
        "command": "favorites.remove",
        "catalog": catalog,
        "index_path": str(index_path),
        "filter": {
            "filter_id": filter_id,
            "display_name": display_name,
        },
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[FAVORITE REMOVED] {display_name} ({filter_id})")
    return 0


def cmd_favorites_clear(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.all:
        store.clear_favorites(catalog=None)
        payload = {"command": "favorites.clear", "scope": "all"}
    else:
        store.clear_favorites(catalog=normalize_catalog_name(args.catalog))
        payload = {"command": "favorites.clear", "scope": normalize_catalog_name(args.catalog)}
    if args.json:
        _print_json(payload)
        return 0
    print(f"[FAVORITES CLEARED] {payload['scope']}")
    return 0


def cmd_history_list(args: argparse.Namespace) -> int:
    entries = _store(args).load_history()[: max(args.limit, 0)]
    payload = {
        "command": "history.list",
        "count": len(entries),
        "events": entries,
    }
    if args.json:
        _print_json(payload)
        return 0
    print("[HISTORY]")
    if not entries:
        print("(empty)")
        return 0
    for item in entries:
        output_path = item.get("output_path") or "-"
        display_name = item.get("display_name") or item.get("filter_id") or "-"
        print(f"{item['timestamp']} {item['command']} {display_name} -> {output_path}")
    return 0


def cmd_history_clear(args: argparse.Namespace) -> int:
    _store(args).clear_history()
    payload = {"command": "history.clear", "cleared": True}
    if args.json:
        _print_json(payload)
        return 0
    print("[HISTORY CLEARED]")
    return 0


def cmd_workspace_show(args: argparse.Namespace) -> int:
    store = _store(args)
    status = store.workspace_status(args.name)
    payload = {
        "command": "workspace.show",
        "current_workspace": store.current_workspace(),
        "status": status,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[WORKSPACE] {status['workspace']}")
    print(f"active_sessions={status['active_sessions']} closed_sessions={status['closed_sessions']}")
    print(f"last_updated={status['last_updated']}")
    return 0


def cmd_workspace_switch(args: argparse.Namespace) -> int:
    store = _store(args)
    workspace = store.set_current_workspace(args.name)
    payload = {
        "command": "workspace.switch",
        "current_workspace": workspace,
        "status": store.workspace_status(workspace),
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[WORKSPACE SWITCHED] {workspace}")
    return 0


def cmd_workspace_list(args: argparse.Namespace) -> int:
    store = _store(args)
    current = store.current_workspace()
    names = sorted(set(store.list_workspaces()) | {current})
    payload = {
        "command": "workspace.list",
        "current_workspace": current,
        "workspaces": [
            {
                **store.workspace_status(name),
                "current": name == current,
            }
            for name in names
        ],
    }
    if args.json:
        _print_json(payload)
        return 0
    print("[WORKSPACES]")
    for item in payload["workspaces"]:
        marker = "*" if item["current"] else " "
        print(
            f"{marker} {item['workspace']} active={item['active_sessions']} "
            f"closed={item['closed_sessions']} last_updated={item['last_updated']}"
        )
    return 0


def cmd_sessions_list(args: argparse.Namespace) -> int:
    store = _store(args)
    current_session_id = store.current_session_id()
    if args.all_workspaces:
        sessions = store.list_sessions()
        workspace_scope = "*"
    else:
        workspace_scope = args.workspace or store.current_workspace()
        sessions = store.sessions_by_workspace(workspace_scope, include_closed=args.all)
    if not args.all:
        sessions = [item for item in sessions if not item.get("closed_at")]
    sessions = sessions[: max(args.limit, 0)]
    entries = [
        {
            "session_id": item["session_id"],
            "workspace": item.get("workspace"),
            "catalog": item.get("catalog"),
            "input_path": item.get("input_path"),
            "scene": (item.get("scene") or {}).get("scene"),
            "selected_filter": (item.get("selected_filter") or {}).get("display_name"),
            "closed_at": item.get("closed_at"),
            "updated_at": item.get("updated_at"),
            "current": item["session_id"] == current_session_id,
        }
        for item in sessions
    ]
    payload = {
        "command": "sessions.list",
        "workspace": workspace_scope,
        "count": len(entries),
        "sessions": entries,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[SESSIONS] workspace={workspace_scope}")
    if not entries:
        print("(empty)")
        return 0
    for item in entries:
        marker = "*" if item["current"] else " "
        state = "closed" if item["closed_at"] else "open"
        print(
            f"{marker} {item['session_id']} {item['catalog']} {item['scene'] or '-'} "
            f"{item['selected_filter'] or '-'} state={state}"
        )
    return 0


def cmd_sessions_show(args: argparse.Namespace) -> int:
    store = _store(args)
    session_id = args.session_id or store.current_session_id()
    if not session_id:
        print("[ERROR] No current session available.", file=sys.stderr)
        return 2
    session = store.load_session(session_id)
    if session is None:
        print(f"[ERROR] Session not found: {session_id}", file=sys.stderr)
        return 2
    payload = {
        "command": "sessions.show",
        "session": session,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[SESSION] {session['session_id']}")
    print(f"workspace={session.get('workspace')} catalog={session.get('catalog')}")
    print(f"scene={(session.get('scene') or {}).get('scene')} selected={(session.get('selected_filter') or {}).get('display_name')}")
    print(f"closed_at={session.get('closed_at')}")
    return 0


def cmd_sessions_close(args: argparse.Namespace) -> int:
    store = _store(args)
    session_id = args.session_id or store.current_session_id()
    if not session_id:
        print("[ERROR] No current session available.", file=sys.stderr)
        return 2
    session = store.mark_session_closed(session_id, reason=args.reason)
    if session is None:
        print(f"[ERROR] Session not found: {session_id}", file=sys.stderr)
        return 2
    payload = {
        "command": "sessions.close",
        "session": session,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"[SESSION CLOSED] {session['session_id']}")
    print(f"closed_at={session.get('closed_at')} reason={session.get('close_reason')}")
    return 0


def cmd_cache_list(args: argparse.Namespace) -> int:
    entries = inspect_render_cache()
    entries.sort(key=lambda item: str(item.get("stored_at") or ""), reverse=True)
    entries = entries[: max(args.limit, 0)]
    payload = {
        "command": "cache.list",
        "count": len(entries),
        "entries": entries,
    }
    if args.json:
        _print_json(payload)
        return 0
    print("[CACHE]")
    if not entries:
        print("(empty)")
        return 0
    for item in entries:
        print(
            f"{item.get('stored_at')} {item.get('output_type')} "
            f"{item.get('catalog')} filters={','.join(item.get('filter_ids', []))}"
        )
    return 0


def cmd_cache_clear(args: argparse.Namespace) -> int:
    clear_render_cache()
    payload = {"command": "cache.clear", "cleared": True}
    if args.json:
        _print_json(payload)
        return 0
    print("[CACHE CLEARED]")
    return 0


def cmd_catalog_validate(args: argparse.Namespace) -> int:
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    payload = {
        "command": "catalog.validate",
        **validate_catalog_bundle(index_path=index_path, catalog=catalog, strict=args.strict),
    }
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 2
    print(format_validation_report(payload))
    return 0 if payload["ok"] else 2


def cmd_catalog_doctor(args: argparse.Namespace) -> int:
    store = _store(args)
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    payload = {
        "command": "catalog.doctor",
        **doctor_catalog_bundle(
            index_path=index_path,
            catalog=catalog,
            strict=args.strict,
            favorite_filter_ids=store.list_favorites(catalog),
        ),
    }
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 2
    print(format_doctor_report(payload))
    return 0 if payload["ok"] else 2


def cmd_session(args: argparse.Namespace) -> int:
    import io

    input_path = Path(args.input).expanduser().resolve()
    output_dir = _resolve_auto_output_dir(input_path, args.output_dir)
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)
    commands = list(args.session_commands or [])
    if args.script:
        commands.extend(load_script_commands(args.script))
    if args.json and not commands:
        raise ValueError("session --json requires --command or --script")
    stream: Any = io.StringIO() if args.json else sys.stdout
    session = FilterSession(
        store=_store(args),
        input_path=input_path,
        output_dir=output_dir,
        index_path=index_path,
        catalog=catalog,
        intensity=args.intensity,
        algorithm=args.algorithm,
        top_k=args.top_k,
        theme=args.theme,
        stream=stream,
        input_fn=input,
    )
    summary = session.run_commands(commands) if commands else session.run_interactive()
    payload = {
        "command": "session",
        "catalog": catalog,
        **summary,
    }
    if args.json:
        _print_json(payload)
    return 0


def _run_pipeline_surface(args: argparse.Namespace, *, experience_mode: str) -> int:
    input_path = Path(args.input).expanduser().resolve()
    output_dir = _resolve_auto_output_dir(input_path, args.output_dir)
    catalog, index_path = _resolve_catalog_and_index(args.catalog, args.index)

    if args.json and args.choose:
        raise ValueError("--choose requires interactive text mode; remove --json or use --select-filter")

    auto_apply = "none" if (args.choose or args.select_filter) else ("top1" if args.mode == "top1" else "none")

    experience: ConsoleExperience | StudioConsoleExperience | None = None
    stage_callback = None
    if not args.json:
        if experience_mode == "studio":
            experience = StudioConsoleExperience(
                prompt=args.prompt,
                input_path=input_path,
                index_path=index_path,
                output_dir=output_dir,
                catalog=catalog,
                pace_ms=getattr(args, "pace_ms", None),
                use_color=not getattr(args, "no_color", False),
                theme=getattr(args, "theme", "blackroom"),
            )
            experience.start()
            stage_callback = experience.on_stage
        elif not getattr(args, "plain", False):
            experience = ConsoleExperience(prompt=args.prompt)
            experience.start()
            stage_callback = experience.on_stage

    result = run_pipeline(
        input_path=input_path,
        output_dir=output_dir,
        filter_index_path=index_path,
        catalog=catalog,
        intensity=args.intensity,
        algorithm=args.algorithm,
        auto_apply=auto_apply,
        full_preview=args.full_preview,
        stage_callback=stage_callback,
        preferred_filter_ids=set(_store(args).list_favorites(catalog)),
    )

    if args.select_filter:
        result = _apply_surface_selection(
            result=result,
            input_path=input_path,
            output_dir=output_dir,
            selection_query=args.select_filter,
            intensity=args.intensity,
            algorithm=args.algorithm,
            experience=experience,
        )
    elif args.choose:
        result = _choose_surface_filter(
            result=result,
            input_path=input_path,
            output_dir=output_dir,
            intensity=args.intensity,
            algorithm=args.algorithm,
            experience=experience,
        )

    open_events: list[dict[str, Any]] = []
    if args.open:
        targets = [Path(result["contact_sheet_path"])]
        if result.get("final_output_path"):
            targets.append(Path(result["final_output_path"]))
        seen: set[str] = set()
        for path in targets:
            path_str = str(path)
            if path_str in seen:
                continue
            seen.add(path_str)
            success, error = open_result(path)
            open_events.append({"path": path_str, "success": success, "error": error})
            if experience is not None:
                experience.report_open(path, success, error)

    history_filter = None
    if result.get("selected_filter"):
        history_filter = result["selected_filter"]
    elif result.get("final_output_path") and result["recommended_filters"]:
        history_filter = result["recommended_filters"][0]
    if history_filter is not None and result.get("final_output_path"):
        _record_history_event(
            args,
            command="studio" if experience_mode == "studio" else "auto",
            catalog=catalog,
            input_path=input_path,
            index_path=index_path,
            output_path=Path(result["final_output_path"]),
            filter_item=history_filter,
            scene=result["scene"]["scene"],
            session_id=None,
        )

    payload = {
        "command": "studio" if experience_mode == "studio" else "auto",
        "experience": experience_mode,
        "catalog": catalog,
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "index_path": str(index_path),
        "mode": args.mode,
        "scene": result["scene"],
        "recommended_filters": result["recommended_filters"],
        "contact_sheet_path": result["contact_sheet_path"],
        "final_output_path": result["final_output_path"],
        "selected_filter": result.get("selected_filter"),
        "theme": getattr(args, "theme", None),
        "cache": result.get("cache", {}),
        "open_events": open_events,
    }

    if experience is not None:
        experience.finish(result)

    if args.json:
        _print_json(payload)
    elif getattr(args, "plain", False):
        print(
            f"[AUTO] catalog={catalog} scene={payload['scene']['scene']} "
            f"confidence={payload['scene']['confidence']:.0%}"
        )
        print(f"contact_sheet={payload['contact_sheet_path']}")
        if payload["final_output_path"]:
            print(f"final_output={payload['final_output_path']}")
        print(
            "recommended="
            + ", ".join(item["display_name"] for item in payload["recommended_filters"])
        )
    return 0


def _resolve_catalog_and_index(catalog: str, index: str | None) -> tuple[str, Path]:
    if index:
        index_path = Path(index).expanduser().resolve()
        inferred_catalog = infer_catalog_name(index_path)
        explicit_catalog = normalize_catalog_name(catalog)
        known_catalogs = set(shipped_catalog_names())
        if inferred_catalog not in known_catalogs:
            manifest = load_catalog_manifest(index_path=index_path)
            manifest_catalog = manifest.get("catalog") if isinstance(manifest, dict) else None
            if isinstance(manifest_catalog, str) and manifest_catalog.strip():
                normalized_manifest_catalog = normalize_catalog_name(manifest_catalog)
                if explicit_catalog != DEFAULT_CATALOG and explicit_catalog != normalized_manifest_catalog:
                    raise ValueError(
                        f"Catalog mismatch: --catalog {explicit_catalog} does not match index {normalized_manifest_catalog}"
                    )
                return normalized_manifest_catalog, index_path
            inferred_from_filter_ids = _infer_catalog_from_filter_ids(index_path)
            if inferred_from_filter_ids and explicit_catalog == DEFAULT_CATALOG:
                return inferred_from_filter_ids, index_path
            return explicit_catalog, index_path
        if explicit_catalog != DEFAULT_CATALOG and explicit_catalog != inferred_catalog:
            raise ValueError(
                f"Catalog mismatch: --catalog {explicit_catalog} does not match index {inferred_catalog}"
            )
        return inferred_catalog, index_path

    resolved_catalog = normalize_catalog_name(catalog)
    index_path = shipped_index_path(resolved_catalog).expanduser().resolve()
    return resolved_catalog, index_path


def _resolve_beginner_sources(catalog: str | None, index: str | None) -> list[tuple[str, Path]]:
    if index:
        resolved_catalog, index_path = _resolve_catalog_and_index(catalog or DEFAULT_CATALOG, index)
        return [(resolved_catalog, index_path)]
    if catalog:
        resolved_catalog = normalize_catalog_name(catalog)
        return [(resolved_catalog, shipped_index_path(resolved_catalog).expanduser().resolve())]
    return [
        (name, shipped_index_path(name).expanduser().resolve())
        for name in shipped_catalog_names()
    ]


def _infer_catalog_from_filter_ids(index_path: Path) -> str | None:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    filters = payload.get("filters")
    if not isinstance(filters, list):
        return None
    prefixes: set[str] = set()
    for item in filters:
        if not isinstance(item, dict):
            return None
        filter_id = item.get("filter_id")
        if not isinstance(filter_id, str) or not filter_id.strip():
            continue
        prefix = filter_id.split("_", 1)[0].strip().lower()
        if prefix:
            prefixes.add(normalize_catalog_name(prefix))
    if len(prefixes) == 1:
        return next(iter(prefixes))
    return None


def _choose_surface_filter(
    *,
    result: dict[str, Any],
    input_path: Path,
    output_dir: Path,
    intensity: float,
    algorithm: str,
    experience: ConsoleExperience | StudioConsoleExperience | None,
) -> dict[str, Any]:
    filters = result["recommended_filters"]
    if not filters:
        return result

    if isinstance(experience, StudioConsoleExperience):
        experience.show_selection_prompt(filters)
    else:
        print("[SELECTION]")
        for idx, item in enumerate(filters, start=1):
            print(f"{idx}. {item['display_name']} - {item['reason']}")

    while True:
        raw = input(f"Select filter [1-{len(filters)}, Enter=1, q=skip]: ").strip()
        if not raw:
            raw = "1"
        if raw.lower() in {"q", "quit", "skip"}:
            return result
        try:
            return _apply_surface_selection(
                result=result,
                input_path=input_path,
                output_dir=output_dir,
                selection_query=raw,
                intensity=intensity,
                algorithm=algorithm,
                experience=experience,
            )
        except ValueError as exc:
            print(f"[ERROR] {exc}")


def _apply_surface_selection(
    *,
    result: dict[str, Any],
    input_path: Path,
    output_dir: Path,
    selection_query: str,
    intensity: float,
    algorithm: str,
    experience: ConsoleExperience | StudioConsoleExperience | None,
) -> dict[str, Any]:
    filters = result["recommended_filters"]
    position, filter_item = find_filter(filters, selection_query)
    output_path = _resolve_render_output_path(
        input_path=input_path,
        filter_id=filter_item["filter_id"],
        output=None,
        output_dir=str(output_dir),
    )
    apply_flut_to_image(
        flut_path=filter_item["flut_file"],
        input_path=input_path,
        output_path=output_path,
        intensity=intensity,
        algorithm=algorithm,
    )
    selected_filter = {
        "position": position + 1,
        "catalog": filter_item.get("catalog", result.get("catalog", DEFAULT_CATALOG)),
        "filter_id": filter_item["filter_id"],
        "display_name": filter_item["display_name"],
        "reason": filter_item.get("reason"),
        "output_path": str(output_path),
    }
    if isinstance(experience, StudioConsoleExperience):
        experience.report_selection(selected_filter)
    elif experience is not None:
        print(f"[SELECTED] {selected_filter['position']}. {selected_filter['display_name']}")
    result["final_output_path"] = str(output_path)
    result["selected_filter"] = selected_filter
    return result


def _resolve_render_output_path(
    *,
    input_path: Path,
    filter_id: str,
    output: str | None,
    output_dir: str | None,
) -> Path:
    if output:
        return Path(output).expanduser().resolve()

    base_dir = Path(output_dir).expanduser().resolve() if output_dir else _default_output_root() / input_path.stem
    base_dir.mkdir(parents=True, exist_ok=True)
    suffix = input_path.suffix or ".png"
    return (base_dir / f"{input_path.stem}_{filter_id}{suffix}").resolve()


def _resolve_auto_output_dir(input_path: Path, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    return (_default_output_root() / input_path.stem).resolve()


def _resolve_demo_output_dir(input_path: Path, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    return (_default_output_root() / "_demo" / input_path.stem).resolve()


def _default_output_root() -> Path:
    for env_name in ("DAVINCI_OUTPUT_ROOT", "LEICA_OUTPUT_ROOT"):
        override = os.environ.get(env_name)
        if override:
            return Path(override).expanduser().resolve()
    return (Path.home() / "Pictures" / PRODUCT_OUTPUT_DIRNAME).resolve()


def _resolve_start_input(args: argparse.Namespace) -> str:
    if args.input:
        return _normalize_input_token(str(args.input))
    if getattr(args, "pick", False):
        return _pick_image_path()
    if getattr(args, "json", False):
        raise ValueError("start --json requires --input")
    response = input('把照片拖到这里，输入 "demo" 先看演示，直接回车打开选择器，输入 "exit" 退出: ').strip()
    if not response:
        return _pick_image_path()
    token = _normalize_input_token(response)
    lowered = token.lower()
    if lowered in {"exit", "quit"}:
        raise ValueError("No input image provided")
    if lowered == "demo":
        return "__demo__"
    return token


def _normalize_input_token(raw: str) -> str:
    token = raw.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1]
    return token.strip()


def _pick_image_path() -> str:
    if sys.platform != "darwin":
        raise ValueError("File picker is currently supported on macOS only. Please pass --input.")
    script = 'POSIX path of (choose file with prompt "选择一张要处理的照片" of type {"public.image"})'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("Image selection was cancelled.")
    selected = result.stdout.strip()
    if not selected:
        raise ValueError("No input image provided")
    return selected


def _can_prompt() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)())


def _open_activation_url(url: str) -> tuple[bool, str | None]:
    try:
        opened = webbrowser.open(url)
        if opened:
            return True, None
        return False, "browser open returned false"
    except Exception as exc:
        return False, str(exc)


def _run_activation_flow(store: ProductStore, *, source: str) -> tuple[int, dict[str, Any]]:
    success, error = _open_activation_url(ACTIVATION_URL)
    print("[ACTIVATE]")
    print("首次激活需要先打开官网页面。")
    if success:
        print(f"已打开：{ACTIVATION_URL}")
    else:
        print(f"自动打开失败，请手动打开：{ACTIVATION_URL}")
        if error:
            print(f"reason={error}")
    token = input("看完后按回车完成激活，输入 q 取消: ").strip().lower()
    if token in {"q", "quit", "exit"}:
        payload = {
            "command": "activate",
            "activated": False,
            "cancelled": True,
            "activation_url": ACTIVATION_URL,
            "source": source,
            "opened": success,
            "error": error,
        }
        print("已取消激活。")
        return 1, payload

    activation = store.mark_activated(activation_url=ACTIVATION_URL)
    payload = {
        "command": "activate",
        "activated": True,
        "activated_at": activation.get("activated_at"),
        "activation_url": ACTIVATION_URL,
        "source": source,
        "opened": success,
        "error": error,
    }
    print("激活完成。")
    return 0, payload


def _needs_first_activation(args: argparse.Namespace, store: ProductStore | None = None) -> bool:
    if getattr(args, "json", False):
        return False
    if not _can_prompt():
        return False
    resolved_store = store or _store(args)
    return not resolved_store.is_activated()


def _maybe_run_first_activation(
    args: argparse.Namespace,
    *,
    store: ProductStore | None = None,
    source: str | None = None,
) -> int | None:
    resolved_store = store or _store(args)
    if not _needs_first_activation(args, resolved_store):
        return None
    rc, _ = _run_activation_flow(
        resolved_store,
        source=source or str(getattr(args, "command", "") or "interactive"),
    )
    if rc != 0:
        return rc
    return None


def _resolve_continue_session(store: ProductStore, session_id: str | None) -> dict[str, Any] | None:
    if session_id:
        return store.load_session(session_id)
    current = store.load_session()
    if current is not None:
        return current
    current_workspace = store.current_workspace()
    sessions = store.sessions_by_workspace(current_workspace, include_closed=False)
    return sessions[0] if sessions else None


def _resolve_continue_history(store: ProductStore) -> dict[str, Any] | None:
    history = store.load_history()
    for entry in history:
        output_path = entry.get("output_path")
        if not output_path:
            continue
        if Path(str(output_path)).expanduser().exists():
            return entry
    return None


def _build_continue_session_payload(session: dict[str, Any], *, open_artifact: bool) -> dict[str, Any]:
    targets = _continue_targets_for_session(session)
    available_targets = [target for target in targets if Path(target).exists()]
    open_events = _open_targets(available_targets[:1]) if open_artifact else []
    selected = session.get("selected_filter") or {}
    return {
        "command": "continue",
        "resume_type": "session",
        "session": {
            "session_id": session.get("session_id"),
            "workspace": session.get("workspace"),
            "catalog": session.get("catalog"),
            "input_path": session.get("input_path"),
            "output_dir": session.get("output_dir"),
            "scene": (session.get("scene") or {}).get("scene"),
            "selected_filter": selected.get("display_name") or selected.get("filter_id"),
            "closed_at": session.get("closed_at"),
            "can_resume_interactive": not bool(session.get("closed_at")),
        },
        "targets": targets,
        "available_targets": available_targets,
        "open_events": open_events,
        "next_steps": [
            "davinci continue --open",
            "davinci continue --interactive",
            "davinci start",
            "davinci demo",
        ],
    }


def _build_continue_history_payload(entry: dict[str, Any], *, open_artifact: bool) -> dict[str, Any]:
    targets = []
    output_path = entry.get("output_path")
    if output_path:
        targets.append(str(Path(output_path).expanduser().resolve()))
    available_targets = [target for target in targets if Path(target).exists()]
    open_events = _open_targets(available_targets[:1]) if open_artifact else []
    return {
        "command": "continue",
        "resume_type": "history",
        "history": {
            "command": entry.get("command"),
            "catalog": entry.get("catalog"),
            "input_path": entry.get("input_path"),
            "output_path": entry.get("output_path"),
            "display_name": entry.get("display_name"),
            "filter_id": entry.get("filter_id"),
            "timestamp": entry.get("timestamp"),
        },
        "targets": targets,
        "available_targets": available_targets,
        "open_events": open_events,
        "next_steps": [
            "davinci continue --open",
            "davinci start",
            "davinci demo",
        ],
    }


def _build_continue_empty_payload() -> dict[str, Any]:
    return {
        "command": "continue",
        "resume_type": "empty",
        "message": "现在还没有可继续的内容。先看产品演示，或者先处理一张自己的照片。",
        "next_steps": [
            "davinci",
            "davinci demo",
            "davinci start",
        ],
        "results_root": str(_default_output_root()),
        "targets": [],
        "available_targets": [],
        "open_events": [],
    }


def _continue_targets_for_session(session: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    selected = session.get("selected_filter") or {}
    for path in (
        selected.get("output_path"),
        session.get("contact_sheet_path"),
    ):
        if not path:
            continue
        resolved = str(Path(path).expanduser().resolve())
        if not Path(resolved).exists():
            continue
        if resolved not in targets:
            targets.append(resolved)
    return targets


def _open_targets(targets: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for target in targets:
        success, error = open_result(Path(target))
        events.append({"path": target, "success": success, "error": error})
    return events


def _print_continue_text(payload: dict[str, Any]) -> None:
    if payload["resume_type"] == "empty":
        print("[CONTINUE]")
        print(payload["message"])
        if payload.get("results_root"):
            print(f"results={payload['results_root']}")
        for item in payload.get("next_steps", []):
            print(f"next={item}")
        return

    if payload["resume_type"] == "session":
        session = payload["session"]
        print("[CONTINUE]")
        print("我找到了一个还没结束的工作台。")
        print(f"session={session['session_id']} workspace={session.get('workspace')}")
        print(f"catalog={session.get('catalog')} scene={session.get('scene') or '-'}")
        print(f"selected={session.get('selected_filter') or '-'} closed_at={session.get('closed_at')}")
        for target in payload.get("available_targets", []):
            print(f"target={target}")
        if payload.get("targets") and not payload.get("available_targets"):
            print("target=历史记录存在，但文件已不在本机当前位置")
        for item in payload.get("next_steps", []):
            print(f"next={item}")
        return

    history = payload["history"]
    print("[CONTINUE]")
    print("我找到了你上一次做出来的结果。")
    print(f"last_command={history.get('command')} filter={history.get('display_name') or history.get('filter_id')}")
    print(f"input={history.get('input_path')}")
    print(f"output={history.get('output_path')}")
    if payload.get("targets") and not payload.get("available_targets"):
        print("status=历史记录还在，但输出文件已不在本机当前位置")
    for item in payload.get("next_steps", []):
        print(f"next={item}")


def _store(args: argparse.Namespace) -> ProductStore:
    return args.store


def _build_home_payload(store: ProductStore) -> dict[str, Any]:
    has_continue = _resolve_continue_session(store, None) is not None or _resolve_continue_history(store) is not None
    return {
        "command": "home",
        "product": "DAVINCI",
        "welcome": "欢迎使用达芬奇调色台",
        "tagline": "给我一张照片，我先给你 3 个方向，再让你决定。",
        "product_promise": "我可以把你的照片调成经典的 Leica 或 Fuji 风格。",
        "demo_image": str(EXAMPLE_IMAGE.resolve()) if EXAMPLE_IMAGE.exists() else None,
        "results_root": str(_default_output_root()),
        "has_continue": has_continue,
        "brand_summaries": {
            catalog: str(guide["summary"])
            for catalog, guide in _HOME_BRAND_CHOICES.items()
        },
        "what_you_get": [
            "自动判断更像人像、风景还是纪实",
            "先给你 3 个差异明显的方向，而不是一长串滤镜名",
            "自动打开对比图，再让你决定",
        ],
        "families": beginner_family_descriptions(shipped_catalog_names()),
        "install": {
            "venv": [
                "python3 -m venv .venv",
                "source .venv/bin/activate",
                "python3 -m pip install -U pip",
                "python3 -m pip install -r requirements.txt",
            ],
            "entrypoint": "python3 -m pip install -e .",
        },
        "next_steps": [
            {
                "label": "先看产品演示",
                "command": "davinci demo",
                "fallback": "python3 -m scripts.leica_cli demo",
                "why": "不用准备照片，先看完整效果流程。",
            },
            {
                "label": "处理自己的照片",
                "command": "davinci start",
                "fallback": "python3 -m scripts.leica_cli start",
                "why": "支持拖入路径、粘贴路径、回车选图。",
            },
            {
                "label": "继续上一次工作",
                "command": "davinci continue",
                "fallback": "python3 -m scripts.leica_cli continue",
                "why": "继续当前会话，或重新打开上次真实存在的结果。",
            },
            {
                "label": "看看风格系列",
                "command": "davinci brands",
                "fallback": "python3 -m scripts.leica_cli brands",
                "why": "先用白话理解 Leica / Fuji / Kodak 的差别。",
            },
            {
                "label": "查看傻瓜式帮助",
                "command": "davinci help",
                "fallback": "python3 -m scripts.leica_cli help",
                "why": "看一份不讲术语、只讲怎么用的导览。",
            },
        ],
    }


def _default_demo_args(store: ProductStore) -> argparse.Namespace:
    profile = store.load_profile()
    return argparse.Namespace(
        theme=profile["theme"],
        prompt="帮我调色",
        catalog=None,
        output_dir=None,
        intensity=profile["intensity"],
        algorithm=profile["algorithm"],
        pace_ms=None,
        no_color=False,
        no_open=False,
        demo_commands=None,
        script=None,
        json=False,
        store=store,
    )


def _default_start_args(store: ProductStore) -> argparse.Namespace:
    profile = store.load_profile()
    return argparse.Namespace(
        input=None,
        pick=False,
        catalog=None,
        index=None,
        output_dir=None,
        prompt="帮我调色",
        intensity=profile["intensity"],
        algorithm=profile["algorithm"],
        theme=profile["theme"],
        pace_ms=None,
        no_color=False,
        no_open=False,
        start_commands=None,
        script=None,
        json=False,
        store=store,
    )


def _default_pick_start_args(store: ProductStore) -> argparse.Namespace:
    args = _default_start_args(store)
    args.pick = True
    return args


def _default_continue_args(store: ProductStore) -> argparse.Namespace:
    return argparse.Namespace(
        session_id=None,
        open=False,
        interactive=False,
        continue_commands=None,
        script=None,
        json=False,
        store=store,
    )


_HOME_BRAND_CHOICES: dict[str, dict[str, Any]] = {
    "leica": {
        "family_name": "Leica",
        "summary": "更有氛围，适合纪实、街头、黑白、人像",
    },
    "fuji": {
        "family_name": "Fuji",
        "summary": "更清透，适合日常、旅行、胶片感",
    },
}


def _print_startup_logo(theme: str) -> None:
    resolved_theme = theme if theme in available_themes() else "blackroom"
    if resolved_theme == "blackroom" and _supports_color_output():
        for line in _gradient_logo_lines():
            print(line)
        print("")
    else:
        for line in _logo_lines():
            print(line)
        print("")


def _print_home_screen(payload: dict[str, Any], *, theme: str) -> None:
    resolved_theme = theme if theme in available_themes() else "blackroom"
    _print_startup_logo(resolved_theme)

    lines = [
        payload["welcome"],
        "",
        payload["tagline"],
        payload["product_promise"],
        "",
        "1. 先看 Leica 风格",
        f"   {payload['brand_summaries']['leica']}",
        "2. 先看 Fuji 风格",
        f"   {payload['brand_summaries']['fuji']}",
        "3. 我不确定，直接帮我推荐",
        "",
        "拖入照片或输入文件路径开始",
        "直接回车：先看演示",
    ]
    if payload.get("has_continue"):
        lines.append("其他：continue 继续上一次")
    else:
        lines.append("其他：help 查看帮助")
    lines.append("原图不会被覆盖")
    print(_box("DAVINCI", lines, theme=resolved_theme))


def _supports_color_output() -> bool:
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def _print_demo_next_steps(theme: str, output_dir: Path) -> None:
    resolved_theme = theme if theme in available_themes() else "blackroom"
    print(
        _box(
            "USE YOUR OWN PHOTO NEXT",
            [
                "如果这组演示效果对路，下一步直接处理你自己的照片。",
                "运行：davinci start",
                "然后把照片拖进终端，或直接回车打开选择器。",
                "如果你还想先理解不同风格系列：davinci brands",
                f"这次演示的结果在：{output_dir}",
                "原图不会被覆盖。",
            ],
            theme=resolved_theme,
        )
    )


def _record_history_event(
    args: argparse.Namespace,
    *,
    command: str,
    catalog: str,
    input_path: Path,
    index_path: Path,
    output_path: Path,
    filter_item: dict[str, Any],
    scene: str | None,
    session_id: str | None,
) -> None:
    _store(args).append_history(
        {
            "command": command,
            "catalog": catalog,
            "input_path": str(input_path),
            "index_path": str(index_path),
            "output_path": str(output_path),
            "filter_id": filter_item.get("filter_id"),
            "display_name": filter_item.get("display_name"),
            "scene": scene,
            "session_id": session_id,
        }
    )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    store = ProductStore()
    profile = store.load_profile()
    parser = build_parser(profile)
    args = parser.parse_args(argv)
    args.store = store
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
