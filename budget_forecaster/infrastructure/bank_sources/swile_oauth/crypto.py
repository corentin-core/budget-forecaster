"""Encrypt the Swile refresh token at rest.

The Fernet key is derived from the web app's secret key (already mandatory)
via HKDF-SHA256, so no extra secret has to be managed. The derived key is
deterministic: the same secret key always decrypts a token it encrypted.
"""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_INFO = b"budget-forecaster/swile-oauth/refresh-token"


def _fernet(secret_key: str) -> Fernet:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO)
    raw_key = hkdf.derive(secret_key.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(raw_key))


def encrypt(token: str, secret_key: str) -> str:
    """Encrypt a token; the result is a urlsafe ASCII string."""
    return _fernet(secret_key).encrypt(token.encode("utf-8")).decode("ascii")


def decrypt(blob: str, secret_key: str) -> str:
    """Decrypt a blob produced by encrypt with the same secret key."""
    return _fernet(secret_key).decrypt(blob.encode("ascii")).decode("utf-8")
