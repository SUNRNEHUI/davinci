"""Shared test helpers for FLUT runtime bundles."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from flut_codec import build_metadata, pack_flut_bytes


def make_runtime_bundle(
    root: Path,
    *,
    filter_id: str = "leica_leica_classic",
    display_name: str = "Leica Classic",
    catalog: str = "leica",
    include_manifest: bool = False,
) -> tuple[bytes, Path]:
    cube = (
        b'TITLE "Invert2"\n'
        b"LUT_3D_SIZE 2\n"
        b"1.0 1.0 1.0\n"
        b"0.0 1.0 1.0\n"
        b"1.0 0.0 1.0\n"
        b"0.0 0.0 1.0\n"
        b"1.0 1.0 0.0\n"
        b"0.0 1.0 0.0\n"
        b"1.0 0.0 0.0\n"
        b"0.0 0.0 0.0\n"
    )
    key = os.urandom(32)
    metadata = build_metadata(
        payload=cube,
        skill_id=f"{catalog}.skill.test",
        skill_version="1.0.0",
        filter_id=filter_id,
        display_name=display_name,
        lut_domain="rec709",
        created_at="2026-03-28T00:00:00Z",
    )

    bundle_dir = root / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    flut_path = bundle_dir / f"{filter_id}.flut"
    flut_path.write_bytes(pack_flut_bytes(cube_payload=cube, key=key, metadata=metadata))
    (bundle_dir / "runtime.key.b64").write_text(
        base64.b64encode(key).decode("ascii"),
        encoding="utf-8",
    )

    index_path = bundle_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "filters": [
                    {
                        "filter_id": filter_id,
                        "display_name": display_name,
                        "flut_file": flut_path.name,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    if include_manifest:
        (bundle_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "catalog": catalog,
                    "filters": [
                        {
                            "filter_id": filter_id,
                            "display_name": display_name,
                            "source_cube": "Demo.cube",
                            "flut_file": flut_path.name,
                            "reason": "Helper bundle reason.",
                        }
                    ],
                    "scene_filters": {
                        "general": [filter_id],
                    },
                }
            ),
            encoding="utf-8",
        )
    return key, index_path
