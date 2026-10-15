"""Authenticated encryption for text and file chunks."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = "IRONVAULT"
VERSION = 1
KDF_ITERATIONS = 600_000
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32


class CryptoError(ValueError):
    """Raised when an envelope is invalid, corrupted, or cannot be opened."""


def _derive_key(password: str, salt: bytes) -> bytes:
    if not password:
        raise CryptoError("Please enter a password before continuing.")
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=salt, iterations=KDF_ITERATIONS).derive(password.encode("utf-8"))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _unb64(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise CryptoError("Encrypted data is corrupted or invalid.") from exc


def _envelope_header(salt: bytes, nonce: bytes) -> dict[str, object]:
    return {"magic": MAGIC, "version": VERSION, "algorithm": "AES-256-GCM", "kdf": "PBKDF2-HMAC-SHA256", "iterations": KDF_ITERATIONS, "salt": _b64(salt), "nonce": _b64(nonce)}


def encrypt_text(plaintext: str, password: str) -> str:
    if not plaintext:
        raise CryptoError("Please enter text before encrypting.")
    salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
    header = _envelope_header(salt, nonce)
    aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(_derive_key(password, salt)).encrypt(nonce, plaintext.encode("utf-8"), aad)
    return json.dumps({"header": header, "ciphertext": _b64(ciphertext)}, sort_keys=True, separators=(",", ":"))


def decrypt_text(encrypted: str, password: str) -> str:
    if not encrypted.strip():
        raise CryptoError("Please enter encrypted text before decrypting.")
    try:
        envelope = json.loads(encrypted)
        header = envelope["header"]
        if header["magic"] != MAGIC or header["version"] != VERSION:
            raise CryptoError("Unsupported encrypted data format.")
        salt, nonce = _unb64(header["salt"]), _unb64(header["nonce"])
        ciphertext = _unb64(envelope["ciphertext"])
        aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return AESGCM(_derive_key(password, salt)).decrypt(nonce, ciphertext, aad).decode("utf-8")
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, InvalidTag) as exc:
        raise CryptoError("Decryption failed. The password may be incorrect or the encrypted data may have been modified.") from exc


def password_strength(password: str) -> tuple[str, int]:
    score = sum((len(password) >= 8, len(password) >= 14, any(c.islower() for c in password) and any(c.isupper() for c in password), any(c.isdigit() for c in password), any(not c.isalnum() for c in password)))
    return [("Very weak", 12), ("Weak", 28), ("Fair", 48), ("Strong", 72), ("Excellent", 100)][min(score, 4)]


def derive_file_key(password: str, salt: bytes) -> bytes:
    return _derive_key(password, salt)


def make_file_header(password: str, original_name: str, chunk_size: int) -> tuple[dict[str, object], bytes]:
    salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
    header = _envelope_header(salt, nonce)
    header.update({"chunk_size": chunk_size, "original_name": original_name})
    return header, _derive_key(password, salt)


def chunk_nonce(base_nonce: bytes, index: int) -> bytes:
    if index >= 2**32:
        raise CryptoError("File is too large for the supported encrypted format.")
    return base_nonce[:8] + index.to_bytes(4, "big")


def _aad(header: dict[str, object], index: int) -> bytes:
    return json.dumps({"header": header, "chunk": index}, sort_keys=True, separators=(",", ":")).encode("utf-8")


def authenticate_header(header: dict[str, object], key: bytes) -> bytes:
    nonce = _unb64(str(header["nonce"]))
    aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return AESGCM(key).encrypt(nonce, b"IRONVAULT_HEADER", aad)


def verify_header(header: dict[str, object], key: bytes, tag: bytes) -> None:
    nonce = _unb64(str(header["nonce"]))
    aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        AESGCM(key).decrypt(nonce, tag, aad)
    except InvalidTag as exc:
        raise CryptoError("Decryption failed. The password may be incorrect or the encrypted data may have been modified.") from exc


def encrypt_chunk(data: bytes, key: bytes, nonce: bytes, index: int, header: dict[str, object]) -> bytes:
    return AESGCM(key).encrypt(chunk_nonce(nonce, index), data, _aad(header, index))


def decrypt_chunk(data: bytes, key: bytes, nonce: bytes, index: int, header: dict[str, object]) -> bytes:
    try:
        return AESGCM(key).decrypt(chunk_nonce(nonce, index), data, _aad(header, index))
    except InvalidTag as exc:
        raise CryptoError("Unable to decrypt this file. The encrypted data appears to be corrupted or invalid.") from exc
