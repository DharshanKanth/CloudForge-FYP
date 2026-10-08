"""Symmetric encryption for stored cloud credentials.

Credentials are encrypted at rest with Fernet (AES-128-CBC + HMAC) using a key
derived from the application SECRET_KEY. They are only ever decrypted inside
the backend when a Terraform run needs them, and are never serialised to API
responses.
"""
import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.security import SECRET_KEY


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_credentials(data: dict) -> str:
    """Encrypt a credentials dict into an opaque token string."""
    return _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("ascii")


def decrypt_credentials(token: str) -> dict:
    """Decrypt a token produced by :func:`encrypt_credentials`.

    Raises ``ValueError`` if the token is invalid or was encrypted with a
    different SECRET_KEY (e.g. after a rotation).
    """
    try:
        raw = _fernet().decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeError, TypeError) as exc:
        raise ValueError("Stored credentials could not be decrypted") from exc
    return json.loads(raw.decode("utf-8"))
