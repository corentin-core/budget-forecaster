"""Tests for DurationInput widget and helper functions."""

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.tui.modals.duration_input import (
    DurationUnit,
    relativedelta_to_unit,
    unit_to_relativedelta,
)


class TestRelativeDeltaToUnit:
    """Tests for relativedelta_to_unit detection."""

    def test_months(self) -> None:
        """Months are detected correctly."""
        assert relativedelta_to_unit(relativedelta(months=3)) == (
            3,
            DurationUnit.MONTHS,
        )

    def test_years(self) -> None:
        """Years take priority over months."""
        assert relativedelta_to_unit(relativedelta(years=2)) == (
            2,
            DurationUnit.YEARS,
        )

    def test_days(self) -> None:
        """Days are detected correctly."""
        assert relativedelta_to_unit(relativedelta(days=10)) == (
            10,
            DurationUnit.DAYS,
        )

    def test_weeks(self) -> None:
        """Days divisible by 7 are detected as weeks."""
        assert relativedelta_to_unit(relativedelta(days=14)) == (
            2,
            DurationUnit.WEEKS,
        )

    def test_single_week(self) -> None:
        """7 days is detected as 1 week."""
        assert relativedelta_to_unit(relativedelta(weeks=1)) == (
            1,
            DurationUnit.WEEKS,
        )

    def test_fallback_empty(self) -> None:
        """Empty relativedelta defaults to 1 month."""
        assert relativedelta_to_unit(relativedelta()) == (1, DurationUnit.MONTHS)

    def test_years_priority_over_months(self) -> None:
        """Years+months gives priority to years."""
        assert relativedelta_to_unit(relativedelta(years=1, months=6)) == (
            1,
            DurationUnit.YEARS,
        )

    @pytest.mark.parametrize(
        ("value", "unit", "expected"),
        [
            (5, DurationUnit.DAYS, relativedelta(days=5)),
            (2, DurationUnit.WEEKS, relativedelta(weeks=2)),
            (3, DurationUnit.MONTHS, relativedelta(months=3)),
            (1, DurationUnit.YEARS, relativedelta(years=1)),
        ],
    )
    def test_unit_to_relativedelta(
        self, value: int, unit: DurationUnit, expected: relativedelta
    ) -> None:
        """Each unit produces the correct relativedelta."""
        assert unit_to_relativedelta(value, unit) == expected

    @pytest.mark.parametrize(
        "rd",
        [
            relativedelta(days=5),
            relativedelta(weeks=3),
            relativedelta(months=6),
            relativedelta(years=2),
        ],
    )
    def test_roundtrip(self, rd: relativedelta) -> None:
        """Converting to unit and back gives the same relativedelta."""
        value, unit = relativedelta_to_unit(rd)
        assert unit_to_relativedelta(value, unit) == rd
