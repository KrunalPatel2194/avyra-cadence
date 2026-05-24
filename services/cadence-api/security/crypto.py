"""Fernet encryption helpers for at-rest secrets (Google refresh tokens).

Key is the FERNET_KEY env var (32 url-safe base64 bytes). Generate with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If the key changes, all previously-encrypted tokens become unreadable — users
must re-authenticate. We don't implement key rotation in v1; when we need it,
add a key-version byte prefix to the ciphertext.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.FERNET_KEY.strip()
    if not key:
        raise RuntimeError("FERNET_KEY not set — refusing to encrypt/decrypt at-rest secrets")
    return Fernet(key.encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError("Fernet decrypt failed — key rotated or ciphertext corrupt") from e
