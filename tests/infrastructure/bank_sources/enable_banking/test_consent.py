"""Tests for the Enable Banking consent model."""

from datetime import datetime, timedelta, timezone

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    Consent,
    ConsentStatus,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _consent(valid_until: datetime) -> Consent:
    """Build a consent expiring at valid_until."""
    return Consent(
        session_id="s1",
        account_uids=("acc-1",),
        valid_until=valid_until,
        aspsp_name="BNP",
        aspsp_country="FR",
        created_at=_NOW,
    )


def test_status_valid_far_from_expiry() -> None:
    """A consent well before its expiry is valid."""
    consent = _consent(_NOW + timedelta(days=90))

    assert consent.status(_NOW) is ConsentStatus.VALID


def test_status_expiring_within_threshold() -> None:
    """A consent within the expiring window is flagged as expiring."""
    consent = _consent(_NOW + timedelta(days=10))

    assert consent.status(_NOW, expiring_within=timedelta(days=14)) is (
        ConsentStatus.EXPIRING
    )


def test_status_expiring_at_threshold_boundary() -> None:
    """Exactly at the threshold still counts as expiring, not valid."""
    consent = _consent(_NOW + timedelta(days=14))

    assert consent.status(_NOW, expiring_within=timedelta(days=14)) is (
        ConsentStatus.EXPIRING
    )


def test_status_expired_at_expiry_instant() -> None:
    """A consent is expired once the expiry instant is reached."""
    consent = _consent(_NOW)

    assert consent.status(_NOW) is ConsentStatus.EXPIRED


def test_status_expired_after_expiry() -> None:
    """A consent past its expiry is expired."""
    consent = _consent(_NOW - timedelta(days=1))

    assert consent.status(_NOW) is ConsentStatus.EXPIRED


def test_round_trip_serialization_preserves_fields() -> None:
    """to_dict/from_dict preserves every field, including tz-aware datetimes."""
    consent = Consent(
        session_id="s1",
        account_uids=("acc-1", "acc-2"),
        valid_until=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
        aspsp_name="BNP",
        aspsp_country="FR",
        created_at=_NOW,
    )

    assert Consent.from_dict(consent.to_dict()) == consent


def test_from_dict_reads_trailing_z_datetime() -> None:
    """A stored ...Z expiry is parsed back as an aware UTC datetime."""
    data = {
        "session_id": "s1",
        "account_uids": ["acc-1"],
        "valid_until": "2026-12-31T00:00:00Z",
        "aspsp_name": "BNP",
        "aspsp_country": "FR",
        "created_at": "2026-07-01T00:00:00Z",
    }

    consent = Consent.from_dict(data)

    assert consent.valid_until == datetime(2026, 12, 31, tzinfo=timezone.utc)
