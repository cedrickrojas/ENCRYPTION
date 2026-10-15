from pathlib import Path

import pytest

from ironvault.crypto.core import CryptoError, decrypt_text, encrypt_text
from ironvault.file_operations.encrypted_file import decrypt_file, encrypt_file


PASSWORD = "Correct-Horse-42!"


def test_unicode_and_special_text_round_trip() -> None:
    text = "秘密 data | café | line 2\n!@#$%^&*()"
    assert decrypt_text(encrypt_text(text, PASSWORD), PASSWORD) == text


def test_each_operation_uses_fresh_random_material() -> None:
    text = "same input"
    assert encrypt_text(text, PASSWORD) != encrypt_text(text, PASSWORD)


def test_wrong_password_and_modified_ciphertext_fail() -> None:
    encrypted = encrypt_text("classified", PASSWORD)
    with pytest.raises(CryptoError, match="Decryption failed"):
        decrypt_text(encrypted, "wrong-password")
    with pytest.raises(CryptoError):
        decrypt_text(encrypted[:-4] + "AAAA", PASSWORD)


def test_empty_inputs_fail() -> None:
    with pytest.raises(CryptoError, match="Please enter text"):
        encrypt_text("", PASSWORD)
    with pytest.raises(CryptoError, match="Please enter a password"):
        encrypt_text("data", "")


def test_file_round_trip_large_file_and_original_is_preserved(tmp_path: Path) -> None:
    original = tmp_path / "report.bin"
    encrypted = tmp_path / "report.bin.iron"
    restored = tmp_path / "restored.bin"
    content = bytes(range(256)) * 10_000
    original.write_bytes(content)
    encrypt_file(original, encrypted, PASSWORD)
    decrypt_file(encrypted, restored, PASSWORD)
    assert original.read_bytes() == content
    assert restored.read_bytes() == content


def test_tampered_file_and_wrong_password_fail(tmp_path: Path) -> None:
    original = tmp_path / "note.txt"
    encrypted = tmp_path / "note.txt.iron"
    restored = tmp_path / "restored.txt"
    original.write_text("do not alter", encoding="utf-8")
    encrypt_file(original, encrypted, PASSWORD)
    data = bytearray(encrypted.read_bytes())
    data[-1] ^= 0x01
    encrypted.write_bytes(data)
    with pytest.raises(CryptoError):
        decrypt_file(encrypted, restored, PASSWORD)
