"""Versioned streaming file format for IRONVAULT."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Callable

from ironvault.crypto.core import CryptoError, MAGIC, VERSION, _unb64, authenticate_header, decrypt_chunk, derive_file_key, encrypt_chunk, make_file_header, verify_header

CHUNK_SIZE = 1024 * 1024
HEADER_PREFIX = b"IRONVAULT\x01"
MAX_HEADER_BYTES = 64 * 1024


def _write_record(handle, value: bytes) -> None:
    handle.write(struct.pack(">I", len(value)))
    handle.write(value)


def _read_record(handle) -> bytes:
    size_bytes = handle.read(4)
    if len(size_bytes) != 4:
        raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.")
    size = struct.unpack(">I", size_bytes)[0]
    if size == 0 or size > CHUNK_SIZE + 32:
        raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.")
    value = handle.read(size)
    if len(value) != size:
        raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.")
    return value


def encrypt_file(source: str | Path, destination: str | Path, password: str, progress: Callable[[int], None] | None = None) -> None:
    source_path, destination_path = Path(source), Path(destination)
    if not source_path.is_file():
        raise CryptoError("This file could not be found.")
    if source_path == destination_path:
        raise CryptoError("The encrypted file must be saved separately from the original.")
    header, key = make_file_header(password, source_path.name, CHUNK_SIZE)
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    header_tag = authenticate_header(header, key)
    total, processed = max(source_path.stat().st_size, 1), 0
    try:
        with source_path.open("rb") as source, destination_path.open("wb") as target:
            target.write(HEADER_PREFIX + struct.pack(">I", len(header_bytes)) + header_bytes + header_tag)
            index = 0
            while data := source.read(CHUNK_SIZE):
                _write_record(target, encrypt_chunk(data, key, _unb64(str(header["nonce"])), index, header))
                index += 1
                processed += len(data)
                if progress:
                    progress(min(100, int(processed * 100 / total)))
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise


def decrypt_file(source: str | Path, destination: str | Path, password: str, progress: Callable[[int], None] | None = None) -> None:
    source_path, destination_path = Path(source), Path(destination)
    if source_path.suffix.lower() != ".iron":
        raise CryptoError("This file format is not supported.")
    if source_path == destination_path:
        raise CryptoError("Choose a different location for the decrypted file.")
    total = max(source_path.stat().st_size, 1)
    try:
        with source_path.open("rb") as source:
            if source.read(len(HEADER_PREFIX)) != HEADER_PREFIX:
                raise CryptoError("This file format is not supported.")
            size_bytes = source.read(4)
            if len(size_bytes) != 4:
                raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.")
            header_size = struct.unpack(">I", size_bytes)[0]
            if header_size > MAX_HEADER_BYTES:
                raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.")
            try:
                header = json.loads(source.read(header_size))
            except json.JSONDecodeError as exc:
                raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.") from exc
            if header.get("magic") != MAGIC or header.get("version") != VERSION or header.get("algorithm") != "AES-256-GCM":
                raise CryptoError("Unsupported encrypted file format.")
            header_tag = source.read(32)
            if len(header_tag) != 32:
                raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.")
            key = derive_file_key(password, _unb64(str(header["salt"])))
            verify_header(header, key, header_tag)
            nonce, processed, index = _unb64(str(header["nonce"])), source.tell(), 0
            with destination_path.open("wb") as target:
                while source.tell() < source_path.stat().st_size:
                    target.write(decrypt_chunk(_read_record(source), key, nonce, index, header))
                    index += 1
                    processed = source.tell()
                    if progress:
                        progress(min(100, int(processed * 100 / total)))
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise
