#!/usr/bin/env python3
"""FLUT v1 codec.

Reference implementation for packaging CUBE LUT files into private encrypted
FLUT format and recovering them with the right key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"FLUT"
VERSION = 1
ALGO_AES256_GCM = 1
HEADER_STRUCT = struct.Struct(">4sBBBBI12s")
DEFAULT_KEY_FILENAMES = ("runtime.key.b64", ".runtime.key.b64")


@dataclass(frozen=True)
class FLUTHeader:
    magic: bytes
    version: int
    algorithm: int
    flags: int
    reserved: int
    metadata_len: int
    nonce: bytes


def _canonical_metadata_bytes(metadata: dict[str, Any]) -> bytes:
    return json.dumps(
        metadata,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_key_base64(value: str) -> bytes:
    raw = base64.b64decode(value.strip(), validate=True)
    if len(raw) != 32:
        raise ValueError("Key must decode to exactly 32 bytes for AES-256-GCM")
    return raw


def default_key_candidates(anchor: str | Path) -> list[Path]:
    """Return bundled key candidates near a FLUT payload or index file."""
    anchor = Path(anchor).expanduser().resolve()
    base_dir = anchor if anchor.is_dir() else anchor.parent
    return [base_dir / filename for filename in DEFAULT_KEY_FILENAMES]


def _try_key_files(candidates: Iterable[str | Path]) -> bytes | None:
    for candidate in candidates:
        path = Path(candidate).expanduser().resolve()
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Key file is empty: {path}")
        return decode_key_base64(content)
    return None


def resolve_key(
    *,
    key_base64: str | None,
    key_file: str | None,
    default_key_files: Iterable[str | Path] | None = None,
    env_var: str = "DAVINCI_KEY_B64",
) -> bytes:
    if key_base64:
        return decode_key_base64(key_base64)

    if key_file:
        content = Path(key_file).read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Key file is empty: {key_file}")
        return decode_key_base64(content)

    env_candidates = [env_var]
    if env_var != "DAVINCI_KEY_B64":
        env_candidates.append("DAVINCI_KEY_B64")
    if "LEICASKILL_KEY_B64" not in env_candidates:
        env_candidates.append("LEICASKILL_KEY_B64")
    for candidate in env_candidates:
        env_value = os.environ.get(candidate)
        if env_value:
            return decode_key_base64(env_value)

    if default_key_files:
        bundled = _try_key_files(default_key_files)
        if bundled is not None:
            return bundled

    raise ValueError(
        "Missing key: provide --key-base64, --key-file, set DAVINCI_KEY_B64, "
        "or ship runtime.key.b64 beside the FLUT/index files"
    )


def build_metadata(
    *,
    payload: bytes,
    skill_id: str,
    skill_version: str,
    filter_id: str,
    display_name: str,
    lut_domain: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "skill_version": skill_version,
        "filter_id": filter_id,
        "display_name": display_name,
        "lut_domain": lut_domain,
        "source_format": "cube",
        "payload_sha256": _payload_sha256(payload),
        "created_at": created_at,
    }


def pack_flut_bytes(
    *,
    cube_payload: bytes,
    key: bytes,
    metadata: dict[str, Any],
    nonce: bytes | None = None,
) -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256-GCM key must be 32 bytes")

    if nonce is None:
        nonce = os.urandom(12)
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")

    metadata_bytes = _canonical_metadata_bytes(metadata)
    aes = AESGCM(key)
    ciphertext = aes.encrypt(nonce, cube_payload, metadata_bytes)

    header = HEADER_STRUCT.pack(
        MAGIC,
        VERSION,
        ALGO_AES256_GCM,
        0,
        0,
        len(metadata_bytes),
        nonce,
    )
    return header + metadata_bytes + ciphertext


def parse_header(blob: bytes) -> FLUTHeader:
    if len(blob) < HEADER_STRUCT.size:
        raise ValueError("FLUT file too short")

    unpacked = HEADER_STRUCT.unpack(blob[: HEADER_STRUCT.size])
    header = FLUTHeader(*unpacked)
    if header.magic != MAGIC:
        raise ValueError("Invalid FLUT magic")
    if header.version != VERSION:
        raise ValueError(f"Unsupported FLUT version: {header.version}")
    if header.algorithm != ALGO_AES256_GCM:
        raise ValueError(f"Unsupported FLUT algorithm id: {header.algorithm}")
    return header


def unpack_flut_bytes(*, flut_blob: bytes, key: bytes) -> tuple[dict[str, Any], bytes]:
    if len(key) != 32:
        raise ValueError("AES-256-GCM key must be 32 bytes")

    header = parse_header(flut_blob)
    offset = HEADER_STRUCT.size
    metadata_end = offset + header.metadata_len
    if metadata_end > len(flut_blob):
        raise ValueError("Corrupted FLUT: metadata length exceeds file size")

    metadata_bytes = flut_blob[offset:metadata_end]
    ciphertext = flut_blob[metadata_end:]
    if not ciphertext:
        raise ValueError("Corrupted FLUT: missing encrypted payload")

    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Corrupted FLUT metadata JSON: {exc}") from exc

    aes = AESGCM(key)
    try:
        cube_payload = aes.decrypt(header.nonce, ciphertext, metadata_bytes)
    except InvalidTag as exc:
        raise ValueError("FLUT authentication failed (wrong key or tampered file)") from exc

    expected_hash = metadata.get("payload_sha256")
    if isinstance(expected_hash, str) and expected_hash:
        actual_hash = _payload_sha256(cube_payload)
        if actual_hash != expected_hash:
            raise ValueError("FLUT payload hash mismatch")

    return metadata, cube_payload


def pack_flut_file(
    *,
    input_cube: str,
    output_flut: str,
    key: bytes,
    metadata: dict[str, Any],
) -> None:
    cube_payload = Path(input_cube).read_bytes()
    flut_blob = pack_flut_bytes(cube_payload=cube_payload, key=key, metadata=metadata)
    Path(output_flut).write_bytes(flut_blob)


def unpack_flut_file(*, input_flut: str, output_cube: str, key: bytes) -> dict[str, Any]:
    blob = Path(input_flut).read_bytes()
    metadata, payload = unpack_flut_bytes(flut_blob=blob, key=key)
    Path(output_cube).write_bytes(payload)
    return metadata
