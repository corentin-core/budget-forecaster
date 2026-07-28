"""Refresh-token encryption round-trips and rejects the wrong key."""

import pytest
from cryptography.fernet import InvalidToken

from budget_forecaster.infrastructure.bank_sources.swile_oauth.crypto import (
    decrypt,
    encrypt,
)

_SECRET = "web-secret-key"
_TOKEN = "opaque-refresh-token-43-chars-xxxxxxxxxxxxx"


def test_round_trip_returns_original_token() -> None:
    """Decrypting an encrypted token with the same key yields the original."""
    assert decrypt(encrypt(_TOKEN, _SECRET), _SECRET) == _TOKEN


def test_ciphertext_does_not_expose_the_token() -> None:
    """The ciphertext does not contain the plaintext token."""
    assert _TOKEN not in encrypt(_TOKEN, _SECRET)


def test_wrong_key_cannot_decrypt() -> None:
    """A different secret key fails to decrypt."""
    blob = encrypt(_TOKEN, _SECRET)
    with pytest.raises(InvalidToken):
        decrypt(blob, "another-secret-key")
