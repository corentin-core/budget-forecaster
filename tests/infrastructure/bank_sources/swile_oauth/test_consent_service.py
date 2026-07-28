"""Enrollment stores a rotated token; authenticate mints an access token."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import TokenBundle
from budget_forecaster.infrastructure.bank_sources.swile_oauth.consent_service import (
    NotEnrolledError,
    SwileConsentService,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)


def _service(
    tmp_path: Path, client: MagicMock
) -> tuple[SwileConsentService, SwileTokenStore]:
    store = SwileTokenStore(tmp_path / "token.json", "web-secret-key")
    return SwileConsentService(client, store), store


def test_not_enrolled_before_enrollment(tmp_path: Path) -> None:
    """No token stored reads as not enrolled."""
    service, _ = _service(tmp_path, MagicMock())
    assert service.is_enrolled() is False


def test_enroll_stores_the_rotated_token(tmp_path: Path) -> None:
    """Enroll validates the pasted token and stores the rotated one."""
    client = MagicMock()
    client.refresh.return_value = TokenBundle("acc", "rotated-rt", 1800)
    service, store = _service(tmp_path, client)

    service.enroll("pasted-rt")

    client.refresh.assert_called_once_with("pasted-rt")
    assert store.load() == "rotated-rt"
    assert service.is_enrolled() is True


def test_authenticate_refreshes_and_restores_token(tmp_path: Path) -> None:
    """Authenticate returns the access token and re-stores the rotated token."""
    client = MagicMock()
    client.refresh.side_effect = [
        TokenBundle("acc-1", "rt-2", 1800),
        TokenBundle("acc-2", "rt-3", 1800),
    ]
    service, store = _service(tmp_path, client)
    service.enroll("rt-1")

    access_token = service.authenticate()

    assert access_token == "acc-2"
    assert store.load() == "rt-3"


def test_authenticate_without_enrollment_raises(tmp_path: Path) -> None:
    """Authenticate without a stored token raises NotEnrolledError."""
    service, _ = _service(tmp_path, MagicMock())
    with pytest.raises(NotEnrolledError):
        service.authenticate()


def test_clear_forgets_the_token(tmp_path: Path) -> None:
    """Clear drops the enrollment."""
    client = MagicMock()
    client.refresh.return_value = TokenBundle("acc", "rt", 1800)
    service, _ = _service(tmp_path, client)
    service.enroll("rt-1")

    service.clear()

    assert service.is_enrolled() is False
