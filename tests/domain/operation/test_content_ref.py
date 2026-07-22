"""Tests for the stable content reference."""

from datetime import date

from budget_forecaster.domain.operation.content_ref import content_ref


def test_is_deterministic() -> None:
    """The same content always yields the same key within and across calls."""
    ref = content_ref("MONOPRIX", -12.5, date(2025, 1, 10))

    assert ref == content_ref("MONOPRIX", -12.5, date(2025, 1, 10))
    assert isinstance(ref, str)


def test_identical_content_collapses() -> None:
    """Same description, amount and day map to the same key."""
    assert content_ref("A", -1.0, date(2025, 1, 1)) == content_ref(
        "A", -1.0, date(2025, 1, 1)
    )


def test_differs_on_description() -> None:
    """A different description yields a different key."""
    assert content_ref("A", -1.0, date(2025, 1, 1)) != content_ref(
        "B", -1.0, date(2025, 1, 1)
    )


def test_differs_on_amount() -> None:
    """A different amount yields a different key."""
    assert content_ref("A", -1.0, date(2025, 1, 1)) != content_ref(
        "A", -2.0, date(2025, 1, 1)
    )


def test_differs_on_date() -> None:
    """A different day yields a different key."""
    assert content_ref("A", -1.0, date(2025, 1, 1)) != content_ref(
        "A", -1.0, date(2025, 1, 2)
    )


def test_amount_compared_at_cent_precision() -> None:
    """Float noise below a cent does not change the key."""
    assert content_ref("A", 10.1 + 0.2, date(2025, 1, 1)) == content_ref(
        "A", 10.3, date(2025, 1, 1)
    )
