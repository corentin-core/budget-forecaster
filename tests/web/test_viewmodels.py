"""Unit tests for the read-only view-model helpers."""

from datetime import date, datetime

import pandas as pd
import pytest

from budget_forecaster.web.viewmodels import (
    Consumption,
    add_months,
    consumption,
    month_to_date,
)


class TestAddMonths:
    """Month arithmetic, including year boundaries."""

    @pytest.mark.parametrize(
        "start,delta,expected",
        [
            (date(2026, 7, 23), 0, date(2026, 7, 1)),
            (date(2026, 3, 5), -6, date(2025, 9, 1)),
        ],
    )
    def test_within_and_back(self, start: date, delta: int, expected: date) -> None:
        """A delta lands on the first of the target month."""
        assert add_months(start, delta) == expected

    @pytest.mark.parametrize(
        "start,delta,expected",
        [
            (date(2026, 1, 15), -1, date(2025, 12, 1)),
            (date(2026, 12, 10), 1, date(2027, 1, 1)),
            (date(2026, 6, 1), 12, date(2027, 6, 1)),
        ],
    )
    def test_crosses_year_boundary(
        self, start: date, delta: int, expected: date
    ) -> None:
        """A delta crossing December/January rolls the year correctly."""
        assert add_months(start, delta) == expected


class TestMonthToDate:
    """Normalizing a monthly-summary key to a first-of-month date."""

    @pytest.mark.parametrize(
        "raw",
        [
            date(2026, 7, 23),
            datetime(2026, 7, 23, 9, 30),
            pd.Timestamp("2026-07-15"),
            "2026-07-15",
        ],
    )
    def test_normalizes_to_first_of_month(self, raw: object) -> None:
        """Any supported key type collapses to the month's first day."""
        assert month_to_date(raw) == date(2026, 7, 1)

    def test_rejects_unsupported_type(self) -> None:
        """An unsupported key type raises TypeError."""
        with pytest.raises(TypeError):
            month_to_date(12345)


class TestConsumption:
    """Actual-vs-planned bar state, including the alert branches."""

    def test_none_when_nothing_planned(self) -> None:
        """No planned amount yields no bar."""
        assert consumption(-50.0, 0.0, is_income=False) is None

    def test_expense_under_budget_is_good(self) -> None:
        """An expense below its budget is not flagged."""
        assert consumption(-50.0, -100.0, is_income=False) == Consumption(
            ratio=0.5, over=False, bad=False
        )

    def test_expense_over_budget_is_bad(self) -> None:
        """An expense above its budget is flagged over and bad."""
        assert consumption(-120.0, -100.0, is_income=False) == Consumption(
            ratio=1.2, over=True, bad=True
        )

    def test_income_under_expected_is_not_bad(self) -> None:
        """Under-realized income (salary not received yet) is normal, not bad."""
        result = consumption(50.0, 100.0, is_income=True)
        assert result is not None and not result.bad and not result.over

    def test_sign_mismatch_is_bad(self) -> None:
        """An expense where income was planned is always bad."""
        result = consumption(-30.0, 100.0, is_income=True)
        assert result is not None and result.bad
