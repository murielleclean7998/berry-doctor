from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import os
import secrets
from ctypes import wintypes


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob_from_bytes(data: bytes) -> DATA_BLOB:
    if not data:
        blob = DATA_BLOB()
        blob._buffer = None  # type: ignore[attr-defined]
        return blob
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob._buffer = buffer  # type: ignore[attr-defined]
    return blob


def _blob_to_bytes(blob: DATA_BLOB) -> bytes:
    if not blob.cbData or not blob.pbData:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def _crypt_protect(data: bytes, entropy: bytes) -> bytes:
    if os.name != "nt":
        return data
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source = _blob_from_bytes(data)
    entropy_blob = _blob_from_bytes(entropy)
    target = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(target),
    ):
        raise ctypes.WinError()
    try:
        return _blob_to_bytes(target)
    finally:
        kernel32.LocalFree(target.pbData)


def _crypt_unprotect(data: bytes, entropy: bytes) -> bytes:
    if os.name != "nt":
        return data
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source = _blob_from_bytes(data)
    entropy_blob = _blob_from_bytes(entropy)
    target = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(target),
    ):
        raise ctypes.WinError()
    try:
        return _blob_to_bytes(target)
    finally:
        kernel32.LocalFree(target.pbData)


def protect_text(value: str, purpose: str) -> str:
    if not value:
        return ""
    if value.startswith(("dpapi:", "b64:")):
        return value
    raw = value.encode("utf-8")
    entropy = purpose.encode("utf-8")
    if os.name == "nt":
        protected = _crypt_protect(raw, entropy)
        return f"dpapi:{base64.b64encode(protected).decode('ascii')}"
    return f"b64:{base64.b64encode(raw).decode('ascii')}"


def unprotect_text(value: str, purpose: str) -> str:
    if not value:
        return ""
    if value.startswith("dpapi:"):
        encoded = value.removeprefix("dpapi:")
        raw = _crypt_unprotect(base64.b64decode(encoded), purpose.encode("utf-8"))
        return raw.decode("utf-8")
    if value.startswith("b64:"):
        return base64.b64decode(value.removeprefix("b64:")).decode("utf-8")
    return value


def generate_token(length: int = 18) -> str:
    return secrets.token_urlsafe(length)


def mask_secret(value: str, keep_start: int = 3, keep_end: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= keep_start + keep_end:
        return "*" * len(value)
    return f"{value[:keep_start]}{'*' * (len(value) - keep_start - keep_end)}{value[-keep_end:]}"


def verify_hmac_signature(body: bytes, secret: str, provided_signature: str | None) -> bool:
    if not secret:
        return True
    if not provided_signature:
        return False
    candidate = provided_signature.strip()
    if candidate.startswith("sha256="):
        candidate = candidate.split("=", 1)[1].strip()
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    expected_hex = digest.hexdigest()
    expected_b64 = base64.b64encode(digest.digest()).decode("ascii")
    return secrets.compare_digest(candidate, expected_hex) or secrets.compare_digest(candidate, expected_b64)


__all__ = [
    "generate_token",
    "mask_secret",
    "protect_text",
    "unprotect_text",
    "verify_hmac_signature",
]
