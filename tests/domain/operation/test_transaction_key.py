"""Tests for the version-independent transaction key."""

import pytest

from budget_forecaster.domain.operation.transaction_key import transaction_key


def test_v4_and_v7_ids_of_one_transaction_share_a_key() -> None:
    """Only the part after the version nibble counts, case-insensitively."""
    old = transaction_key("3F2A9C1E-5B7D-4ADE-B7EC-2218DF32EDE5")
    new = transaction_key("019f6a2b-8c3d-7ade-b7ec-2218df32ede5")

    assert old == new == "ade-b7ec-2218df32ede5"


@pytest.mark.parametrize(
    "source_ref",
    [
        "2026080300001-ab12",
        "3f2a9c1e-5b7d-1ade-b7ec-2218df32ede5",
        "3f2a9c1e-5b7d-4ade-b7ec-2218df32ede5-extra",
    ],
    ids=["opaque", "uuid v1", "trailing text"],
)
def test_other_refs_have_no_key(source_ref: str) -> None:
    """Refs that are not a UUIDv4 or v7 are matched exactly, never by tail."""
    assert transaction_key(source_ref) is None
