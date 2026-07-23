"""Tests for the Enable Banking consent service."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    Consent,
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
    NoConsentError,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_store import (
    ConsentStore,
)


def _store(tmp_path: Path) -> ConsentStore:
    """Build a store backed by a temporary file."""
    return ConsentStore(tmp_path / "consent.json")


def _consent(account_uids: tuple[str, ...], valid_until: datetime) -> Consent:
    """Build a consent with the given accounts and expiry."""
    return Consent(
        session_id="s1",
        account_uids=account_uids,
        valid_until=valid_until,
        aspsp_name="BNP",
        aspsp_country="FR",
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _future() -> datetime:
    """An expiry comfortably in the future."""
    return datetime.now(timezone.utc) + timedelta(days=90)


def _past() -> datetime:
    """An expiry in the past."""
    return datetime.now(timezone.utc) - timedelta(days=1)


def test_list_banks_delegates_to_client(tmp_path: Path) -> None:
    """list_banks returns the client's ASPSPs for the country."""
    client = MagicMock()
    client.list_aspsps.return_value = ({"name": "BNP"},)
    service = ConsentService(client, _store(tmp_path))

    assert service.list_banks("FR") == ({"name": "BNP"},)
    client.list_aspsps.assert_called_once_with("FR")


def test_start_enrollment_requests_future_expiry_and_state(tmp_path: Path) -> None:
    """start_enrollment asks the bank for a future expiry and a correlation state."""
    client = MagicMock()
    client.start_authorization.return_value = "https://bank.example/consent"
    service = ConsentService(client, _store(tmp_path))

    url = service.start_enrollment("BNP", "FR")

    assert url == "https://bank.example/consent"
    call = client.start_authorization.call_args.kwargs
    assert call["aspsp_name"] == "BNP"
    assert call["country"] == "FR"
    assert call["state"]
    assert call["valid_until"].endswith("Z")
    requested = datetime.fromisoformat(call["valid_until"])
    assert requested > datetime.now(timezone.utc)


def test_complete_enrollment_persists_consent_from_uid_strings(
    tmp_path: Path,
) -> None:
    """A session with uid strings is stored with its accounts and expiry."""
    client = MagicMock()
    client.create_session.return_value = {
        "session_id": "sess-9",
        "accounts": ["acc-1", "acc-2"],
        "access": {"valid_until": "2026-12-31T00:00:00Z"},
    }
    store = _store(tmp_path)
    service = ConsentService(client, store)

    consent = service.complete_enrollment("auth-code", "BNP", "FR")

    assert consent.session_id == "sess-9"
    assert consent.account_uids == ("acc-1", "acc-2")
    assert consent.valid_until == datetime(2026, 12, 31, tzinfo=timezone.utc)
    assert store.load() == consent
    client.create_session.assert_called_once_with("auth-code")


def test_complete_enrollment_reads_uid_objects(tmp_path: Path) -> None:
    """Account uids given as objects are read from their uid field."""
    client = MagicMock()
    client.create_session.return_value = {
        "session_id": "sess-9",
        "accounts": [{"uid": "acc-1"}],
        "access": {"valid_until": "2026-12-31T00:00:00Z"},
    }
    service = ConsentService(client, _store(tmp_path))

    consent = service.complete_enrollment("auth-code", "BNP")

    assert consent.account_uids == ("acc-1",)


def test_complete_enrollment_rejects_session_without_expiry(tmp_path: Path) -> None:
    """A session missing access.valid_until is an error, not a stored consent."""
    client = MagicMock()
    client.create_session.return_value = {
        "session_id": "sess-9",
        "accounts": ["acc-1"],
    }
    store = _store(tmp_path)
    service = ConsentService(client, store)

    with pytest.raises(ValueError):
        service.complete_enrollment("auth-code", "BNP")
    assert store.load() is None


def test_state_reports_expired_when_no_consent(tmp_path: Path) -> None:
    """With no stored consent the state is expired with no expiry date."""
    service = ConsentService(MagicMock(), _store(tmp_path))

    state = service.state()

    assert state.status is ConsentStatus.EXPIRED
    assert state.valid_until is None


def test_state_reports_stored_consent_status(tmp_path: Path) -> None:
    """A stored valid consent surfaces its status and expiry."""
    store = _store(tmp_path)
    consent = _consent(("acc-1",), _future())
    store.save(consent)
    service = ConsentService(MagicMock(), store)

    state = service.state()

    assert state.status is ConsentStatus.VALID
    assert state.valid_until == consent.valid_until


def test_renew_starts_authorization_for_stored_bank(tmp_path: Path) -> None:
    """renew opens a fresh authorization targeting the stored bank."""
    client = MagicMock()
    client.start_authorization.return_value = "https://bank.example/renew"
    store = _store(tmp_path)
    store.save(_consent(("acc-1",), _future()))
    service = ConsentService(client, store)

    url = service.renew()

    assert url == "https://bank.example/renew"
    call = client.start_authorization.call_args.kwargs
    assert call["aspsp_name"] == "BNP"
    assert call["country"] == "FR"


def test_renew_without_consent_raises(tmp_path: Path) -> None:
    """Renewing with nothing stored raises."""
    service = ConsentService(MagicMock(), _store(tmp_path))

    with pytest.raises(NoConsentError):
        service.renew()


def test_resolve_account_uid_returns_single_account(tmp_path: Path) -> None:
    """With one account and no preference, that account is resolved."""
    store = _store(tmp_path)
    store.save(_consent(("acc-1",), _future()))
    service = ConsentService(MagicMock(), store)

    assert service.resolve_account_uid() == "acc-1"


def test_resolve_account_uid_honours_preferred(tmp_path: Path) -> None:
    """A preferred account present in the consent is resolved as-is."""
    store = _store(tmp_path)
    store.save(_consent(("acc-1", "acc-2"), _future()))
    service = ConsentService(MagicMock(), store)

    assert service.resolve_account_uid("acc-2") == "acc-2"


def test_resolve_account_uid_rejects_unknown_preferred(tmp_path: Path) -> None:
    """A preferred account absent from the consent is rejected."""
    store = _store(tmp_path)
    store.save(_consent(("acc-1",), _future()))
    service = ConsentService(MagicMock(), store)

    with pytest.raises(NoConsentError):
        service.resolve_account_uid("acc-9")


def test_resolve_account_uid_rejects_ambiguous_selection(tmp_path: Path) -> None:
    """Several accounts and no preference is ambiguous and rejected."""
    store = _store(tmp_path)
    store.save(_consent(("acc-1", "acc-2"), _future()))
    service = ConsentService(MagicMock(), store)

    with pytest.raises(NoConsentError):
        service.resolve_account_uid()


def test_resolve_account_uid_rejects_expired_consent(tmp_path: Path) -> None:
    """An expired consent cannot resolve an account to sync."""
    store = _store(tmp_path)
    store.save(_consent(("acc-1",), _past()))
    service = ConsentService(MagicMock(), store)

    with pytest.raises(NoConsentError):
        service.resolve_account_uid()


def test_resolve_account_uid_without_consent_raises(tmp_path: Path) -> None:
    """Resolving with nothing stored raises."""
    service = ConsentService(MagicMock(), _store(tmp_path))

    with pytest.raises(NoConsentError):
        service.resolve_account_uid()
