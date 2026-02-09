"""Module with test cases for the TimeRange class."""
import itertools
from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)


@pytest.fixture
def time_range() -> DateRange:
    """Return a TimeRange instance."""
    return DateRange(date(2023, 1, 1), relativedelta(days=10))


class TestTimeRange:
    """Test cases for the TimeRange class."""

    def test_initial_date(self, time_range: DateRange) -> None:
        """Test the initial_date property."""
        assert time_range.start_date == date(2023, 1, 1)

    def test_last_date(self, time_range: DateRange) -> None:
        """Test the last_date property."""
        assert time_range.last_date == date(2023, 1, 10)

    def test_total_duration(self, time_range: DateRange) -> None:
        """Test the total_duration property."""
        assert time_range.total_duration == timedelta(days=10)

    def test_total_duration_relative(self) -> None:
        """Test the total_duration property with a relative delta."""
        t_range = DateRange(date(2023, 1, 1), relativedelta(months=1))
        assert t_range.total_duration == timedelta(days=31)

        t_range = DateRange(date(2023, 2, 1), relativedelta(months=1))
        assert t_range.total_duration == timedelta(days=28)

    def test_duration(self, time_range: DateRange) -> None:
        """Test the duration property returns the relativedelta."""
        assert time_range.duration == relativedelta(days=10)

    def test_duration_months(self) -> None:
        """Test the duration property with months."""
        t_range = DateRange(date(2023, 1, 1), relativedelta(months=1))
        assert t_range.duration == relativedelta(months=1)

    def test_contains_date_within_range(self, time_range: DateRange) -> None:
        """Test the is_within method with dates within the range."""
        for test_date in (
            date(2023, 1, 1),
            date(2023, 1, 5),
            date(2023, 1, 10),
        ):
            assert time_range.is_within(test_date)

    def test_does_not_contain_date_outside_range(self, time_range: DateRange) -> None:
        """Test the is_within method with dates outside the range."""
        assert not time_range.is_within(date(2022, 12, 31))
        assert not time_range.is_within(date(2023, 1, 11))

    def test_is_expired(self, time_range: DateRange) -> None:
        """Test the is_expired method."""
        assert time_range.is_expired(date(2023, 1, 11))

    def test_is_not_expired(self, time_range: DateRange) -> None:
        """Test the is_expired method."""
        assert not time_range.is_expired(date(2023, 1, 10))

    def test_is_future(self, time_range: DateRange) -> None:
        """Test the is_future method."""
        assert time_range.is_future(date(2022, 12, 31))

    def test_is_not_future(self, time_range: DateRange) -> None:
        """Test the is_future method."""
        assert not time_range.is_future(date(2023, 1, 1))

    def test_iterate_over_time_ranges(self, time_range: DateRange) -> None:
        """Test the iterate_over_time_ranges method."""
        time_ranges = list(time_range.iterate_over_date_ranges())
        assert len(time_ranges) == 1
        assert time_ranges[0] == time_range

    def test_current_time_range(self, time_range: DateRange) -> None:
        """Test the current_time_range method."""
        assert time_range.current_date_range(date(2023, 1, 5)) == time_range
        assert time_range.current_date_range(date(2022, 12, 31)) is None
        assert time_range.current_date_range(date(2023, 1, 11)) is None

    def test_next_time_range(self, time_range: DateRange) -> None:
        """Test the next_time_range method."""
        assert time_range.next_date_range(date(2022, 12, 31)) == time_range
        assert time_range.next_date_range(date(2023, 1, 1)) is None

    def test_last_time_range(self, time_range: DateRange) -> None:
        """Test the last_time_range method."""
        assert time_range.last_date_range(date(2023, 1, 10)) == time_range
        assert time_range.last_date_range(date(2022, 12, 31)) is None

    def test_replace_with_new_initial_date(self, time_range: DateRange) -> None:
        """Test the replace method."""
        new_time_range = time_range.replace(start_date=date(2023, 1, 2))
        assert new_time_range.start_date == date(2023, 1, 2)
        assert new_time_range.last_date == date(2023, 1, 11)
        assert new_time_range.total_duration == timedelta(days=10)


@pytest.fixture
def daily_time_range() -> SingleDay:
    """Return a DailyTimeRange instance."""
    return SingleDay(date(2023, 1, 1))


class TestDailyTimeRange:
    """Test cases for the DailyTimeRange class."""

    def test_initial_date(self, daily_time_range: SingleDay) -> None:
        """Test the initial_date property."""
        assert daily_time_range.start_date == date(2023, 1, 1)

    def test_last_date(self, daily_time_range: SingleDay) -> None:
        """Test the last_date property."""
        assert daily_time_range.last_date == date(2023, 1, 1)

    def test_total_duration(self, daily_time_range: SingleDay) -> None:
        """Test the total_duration property."""
        assert daily_time_range.total_duration == timedelta(days=1)

    def test_duration(self, daily_time_range: SingleDay) -> None:
        """Test the duration property returns the relativedelta."""
        assert daily_time_range.duration == relativedelta(days=1)

    def test_contains_date_within_range(self, daily_time_range: SingleDay) -> None:
        """Test the is_within method with dates within the range."""
        assert daily_time_range.is_within(date(2023, 1, 1))

    def test_does_not_contain_date_outside_range(
        self, daily_time_range: SingleDay
    ) -> None:
        """Test the is_within method with dates outside the range."""
        assert not daily_time_range.is_within(date(2022, 12, 31))
        assert not daily_time_range.is_within(date(2023, 1, 2))

    def test_is_expired(self, daily_time_range: SingleDay) -> None:
        """Test the is_expired method."""
        assert daily_time_range.is_expired(date(2023, 1, 2))

    def test_is_not_expired(self, daily_time_range: SingleDay) -> None:
        """Test the is_expired method."""
        assert not daily_time_range.is_expired(date(2023, 1, 1))

    def test_is_future(self, daily_time_range: SingleDay) -> None:
        """Test the is_future method."""
        assert daily_time_range.is_future(date(2022, 12, 31))

    def test_is_not_future(self, daily_time_range: SingleDay) -> None:
        """Test the is_future method."""
        assert not daily_time_range.is_future(date(2023, 1, 1))

    def test_iterate_over_time_ranges(self, daily_time_range: SingleDay) -> None:
        """Test the iterate_over_time_ranges method."""
        time_ranges = list(daily_time_range.iterate_over_date_ranges())
        assert len(time_ranges) == 1
        assert time_ranges[0] == daily_time_range

    def test_current_time_range(self, daily_time_range: SingleDay) -> None:
        """Test the current_time_range method."""
        assert daily_time_range.current_date_range(date(2023, 1, 1)) == daily_time_range
        assert daily_time_range.current_date_range(date(2022, 12, 31)) is None
        assert daily_time_range.current_date_range(date(2023, 1, 2)) is None

    def test_next_time_range(self, daily_time_range: SingleDay) -> None:
        """Test the next_time_range method."""
        assert daily_time_range.next_date_range(date(2022, 12, 31)) == daily_time_range
        assert daily_time_range.next_date_range(date(2023, 1, 1)) is None

    def test_last_time_range(self, daily_time_range: SingleDay) -> None:
        """Test the last_time_range method."""
        assert daily_time_range.last_date_range(date(2023, 1, 1)) == daily_time_range
        assert daily_time_range.last_date_range(date(2022, 12, 31)) is None

    def test_replace_with_new_initial_date(self, daily_time_range: SingleDay) -> None:
        """Test the replace method."""
        new_time_range = daily_time_range.replace(start_date=date(2023, 1, 2))
        assert new_time_range.start_date == date(2023, 1, 2)
        assert new_time_range.last_date == date(2023, 1, 2)
        assert new_time_range.total_duration == timedelta(days=1)


@pytest.fixture
def periodic_time_range(time_range: DateRange) -> RecurringDateRange:
    """Return a PeriodicTimeRange instance."""
    return RecurringDateRange(time_range, relativedelta(months=1), date(2023, 12, 31))


class TestPeriodicTimeRange:  # pylint: disable=too-many-public-methods
    """Test cases for the PeriodicTimeRange class."""

    def test_initial_date(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the initial_date property."""
        assert periodic_time_range.start_date == date(2023, 1, 1)

    def test_last_date(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the last_date property."""
        assert periodic_time_range.last_date == date(2023, 12, 31)

    def test_total_duration(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the total_duration property."""
        assert periodic_time_range.total_duration == timedelta(days=365)

    def test_duration(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the duration property returns the period's relativedelta."""
        assert periodic_time_range.duration == relativedelta(days=10)

    def test_base_time_range(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the base_time_range property."""
        base = periodic_time_range.base_date_range
        assert base.start_date == date(2023, 1, 1)
        assert base.duration == relativedelta(days=10)

    def test_contains_date_within_range(
        self, periodic_time_range: RecurringDateRange
    ) -> None:
        """Test the is_within method with dates within the range."""
        for month in range(1, 13):
            for test_date in (
                date(2023, month, 1),
                date(2023, month, 5),
                date(2023, month, 10),
            ):
                assert periodic_time_range.is_within(test_date)

    def test_does_not_contain_date_outside_range(
        self, periodic_time_range: RecurringDateRange
    ) -> None:
        """Test the is_within method with dates outside the range."""
        for month in range(1, 13):
            assert not periodic_time_range.is_within(date(2023, month, 11))
            assert not periodic_time_range.is_within(
                date(2023, month, 1) - relativedelta(days=1)
            )

    def test_is_expired(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the is_expired method."""
        assert periodic_time_range.is_expired(date(2024, 1, 1))

    def test_is_not_expired(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the is_expired method."""
        assert not periodic_time_range.is_expired(date(2023, 6, 1))

    def test_is_future(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the is_future method."""
        assert periodic_time_range.is_future(date(2022, 12, 31))

    def test_is_not_future(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the is_future method."""
        assert not periodic_time_range.is_future(date(2023, 1, 1))

    def test_iterate_over_time_ranges(
        self, periodic_time_range: RecurringDateRange
    ) -> None:
        """Test the iterate_over_time_ranges method."""
        time_ranges = list(periodic_time_range.iterate_over_date_ranges())
        assert len(time_ranges) == 12
        for month, t_range in enumerate(time_ranges, start=1):
            assert t_range == DateRange(date(2023, month, 1), relativedelta(days=10))

    def test_iterate_over_time_ranges_no_date_drift(self) -> None:
        """Test that monthly iterations don't drift when starting from day 31.

        Regression test: when adding months iteratively (date + period),
        dates can drift (Oct 31 -> Nov 30 -> Dec 30 -> Jan 30...).
        The correct behavior is to compute from initial_date + n*period
        to preserve the original day-of-month where possible.
        """
        # Start on Oct 31 with monthly period
        initial = SingleDay(date(2025, 10, 31))
        ptr = RecurringDateRange(initial, relativedelta(months=1), date(2026, 6, 1))

        iterations = [tr.start_date for tr in ptr.iterate_over_date_ranges()]

        # Expected: stay on 31st when month has 31 days, otherwise end of month
        expected = [
            date(2025, 10, 31),  # Oct has 31 days
            date(2025, 11, 30),  # Nov has 30 days
            date(2025, 12, 31),  # Dec has 31 days (NOT 30!)
            date(2026, 1, 31),  # Jan has 31 days (NOT 30!)
            date(2026, 2, 28),  # Feb has 28 days
            date(2026, 3, 31),  # Mar has 31 days (NOT 28!)
            date(2026, 4, 30),  # Apr has 30 days
            date(2026, 5, 31),  # May has 31 days
        ]
        assert iterations == expected

    def test_iterate_over_time_ranges_from_distant_date(self) -> None:
        """Test that iteration from a distant date is efficient (O(1) start).

        Regression test: the old implementation used a while loop to find the
        start position, which was O(n) where n = number of periods to skip.
        The optimized version calculates the start position arithmetically.
        """
        # Monthly period starting in 2020, no expiration
        initial = SingleDay(date(2020, 1, 15))
        ptr = RecurringDateRange(initial, relativedelta(months=1), None)

        # Iterate starting from 10 years later (would be 120 iterations with old impl)
        from_date = date(2030, 6, 20)
        iterations = list(itertools.islice(ptr.iterate_over_date_ranges(from_date), 3))

        # Should start from June 2030 (first iteration >= from_date is July 15)
        assert len(iterations) == 3
        assert iterations[0].start_date == date(2030, 6, 15)
        assert iterations[1].start_date == date(2030, 7, 15)
        assert iterations[2].start_date == date(2030, 8, 15)

    def test_iterate_over_time_ranges_mixed_period(self) -> None:
        """Test iteration with a mixed period (months + days)."""
        # Period of 1 month and 15 days
        initial = SingleDay(date(2025, 1, 1))
        ptr = RecurringDateRange(
            initial, relativedelta(months=1, days=15), date(2026, 12, 31)
        )

        # Iterate from a date several periods ahead
        # Iterations: Jan 1, Feb 16, Mar 31, May 16, Jun 30, Aug 15, ...
        from_date = date(2025, 6, 1)
        iterations = list(itertools.islice(ptr.iterate_over_date_ranges(from_date), 3))

        # from_date is Jun 1, so first returned should be May 16 (last before Jun 1)
        assert iterations[0].start_date == date(2025, 5, 16)
        assert iterations[1].start_date == date(2025, 6, 30)
        assert iterations[2].start_date == date(2025, 8, 15)

    def test_iterate_over_time_ranges_conservative_estimate(self) -> None:
        """Test that conservative period estimation doesn't skip iterations.

        Regression test: when estimating period length, we must use maximum
        values (31 days/month) to avoid skipping iterations. With 30 days/month,
        over 10 years of monthly periods we'd overshoot by ~3 iterations.
        """
        # Monthly period starting Jan 31 (maximizes actual period length)
        initial = SingleDay(date(2020, 1, 31))
        ptr = RecurringDateRange(initial, relativedelta(months=1), None)

        # 10 years later: with 30-day estimate, we'd calculate ~122 periods
        # but actual is ~120, so we'd skip iterations
        from_date = date(2030, 3, 15)
        iterations = list(itertools.islice(ptr.iterate_over_date_ranges(from_date), 3))

        # First iteration should be Feb 28/29 2030 (last iteration before Mar 15)
        # NOT skipped due to overestimation
        assert iterations[0].start_date == date(2030, 2, 28)
        assert iterations[1].start_date == date(2030, 3, 31)
        assert iterations[2].start_date == date(2030, 4, 30)

    def test_split_at(self) -> None:
        """Test split_at returns terminated range and continuation range."""
        initial = SingleDay(date(2025, 1, 15))
        ptr = RecurringDateRange(initial, relativedelta(months=1), date(2025, 12, 31))

        terminated, continuation = ptr.split_at(date(2025, 4, 1))

        # Terminated range ends day before first new iteration (April 15)
        assert terminated.last_date == date(2025, 4, 14)
        # Continuation starts at first iteration >= split date
        assert continuation.start_date == date(2025, 4, 15)
        assert continuation.period == ptr.period
        # Continuation keeps original expiration date
        assert continuation.last_date == date(2025, 12, 31)

    def test_split_at_exact_iteration(self) -> None:
        """Test split_at when date matches an iteration exactly."""
        initial = SingleDay(date(2025, 1, 15))
        ptr = RecurringDateRange(initial, relativedelta(months=1), date(2025, 12, 31))

        terminated, continuation = ptr.split_at(date(2025, 4, 15))

        assert terminated.last_date == date(2025, 4, 14)
        assert continuation.start_date == date(2025, 4, 15)
        assert continuation.period == ptr.period

    def test_split_at_raises_if_before_initial(self) -> None:
        """Test split_at raises ValueError if date is before or at initial date."""
        initial = SingleDay(date(2025, 1, 15))
        ptr = RecurringDateRange(initial, relativedelta(months=1), date(2025, 12, 31))

        with pytest.raises(ValueError, match="after the first iteration"):
            ptr.split_at(date(2025, 1, 15))

        with pytest.raises(ValueError, match="after the first iteration"):
            ptr.split_at(date(2025, 1, 1))

    def test_split_at_raises_if_no_iteration_after(self) -> None:
        """Test split_at raises ValueError if no iteration exists at or after date."""
        initial = SingleDay(date(2025, 1, 15))
        ptr = RecurringDateRange(initial, relativedelta(months=1), date(2025, 3, 31))

        with pytest.raises(ValueError, match="No iteration found"):
            ptr.split_at(date(2025, 6, 1))

    def test_current_time_range(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the current_time_range method."""
        for month in range(1, 13):
            assert periodic_time_range.current_date_range(
                date(2023, month, 5)
            ) == DateRange(date(2023, month, 1), relativedelta(days=10))

    def test_current_time_range_no_expiration(self) -> None:
        """Test the current_time_range method with no expiration date."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(initial_time_range, relativedelta(months=1), None)
        assert t_range.current_date_range(date(2023, 2, 5)) == DateRange(
            date(2023, 2, 1), relativedelta(days=10)
        )

    def test_current_time_range_returns_none(
        self, periodic_time_range: RecurringDateRange
    ) -> None:
        """Test the current_time_range method when it should return None."""
        assert periodic_time_range.current_date_range(date(2024, 1, 1)) is None

    def test_next_time_range(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the next_time_range method."""
        for month in range(1, 12):
            assert periodic_time_range.next_date_range(
                date(2023, month, 5)
            ) == DateRange(date(2023, month + 1, 1), relativedelta(days=10))

    def test_next_time_range_no_expiration(self) -> None:
        """Test the next_time_range method with no expiration date."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(initial_time_range, relativedelta(months=1), None)
        assert t_range.next_date_range(date(2023, 1, 5)) == DateRange(
            date(2023, 2, 1), relativedelta(days=10)
        )

    def test_next_time_range_returns_none(self) -> None:
        """Test the next_time_range method when it should return None."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(
            initial_time_range, relativedelta(months=1), date(2023, 2, 1)
        )
        assert t_range.next_date_range(date(2023, 2, 5)) is None

    def test_last_time_range(self, periodic_time_range: RecurringDateRange) -> None:
        """Test the last_time_range method."""
        for month in range(1, 12):
            assert periodic_time_range.last_date_range(
                date(2023, month, 5)
            ) == DateRange(date(2023, month, 1), relativedelta(days=10))

    def test_last_time_range_no_expiration(self) -> None:
        """Test the last_time_range method with no expiration date."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(initial_time_range, relativedelta(months=1), None)
        assert t_range.last_date_range(date(2023, 1, 5)) == DateRange(
            date(2023, 1, 1), relativedelta(days=10)
        )

    def test_last_time_range_returns_none(self) -> None:
        """Test the last_time_range method when it should return None."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(
            initial_time_range, relativedelta(months=1), date(2023, 2, 1)
        )
        assert t_range.last_date_range(date(2023, 1, 1)) is None

    def test_replace_with_new_initial_date(
        self, periodic_time_range: RecurringDateRange
    ) -> None:
        """Test the replace method."""
        new_time_range = periodic_time_range.replace(start_date=date(2023, 1, 2))
        assert new_time_range.start_date == date(2023, 1, 2)
        assert new_time_range.last_date == date(2023, 12, 31)
        assert new_time_range.total_duration == timedelta(days=364)


class TestTimeRangeReplaceTypeErrors:
    """Tests for TypeError when passing invalid types to replace() methods."""

    def test_time_range_replace_invalid_initial_date(self) -> None:
        """Test TimeRange.replace() raises TypeError for invalid initial_date."""
        t_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        with pytest.raises(TypeError, match="start_date must be date"):
            t_range.replace(start_date="2023-01-01")

    def test_time_range_replace_invalid_duration(self) -> None:
        """Test TimeRange.replace() raises TypeError for invalid duration."""
        t_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        with pytest.raises(TypeError, match="duration must be relativedelta"):
            t_range.replace(duration=10)

    def test_daily_time_range_replace_invalid_initial_date(self) -> None:
        """Test DailyTimeRange.replace() raises TypeError for invalid initial_date."""
        t_range = SingleDay(date(2023, 1, 1))
        with pytest.raises(TypeError, match="start_date must be date"):
            t_range.replace(start_date="2023-01-01")

    def test_periodic_time_range_replace_invalid_period(self) -> None:
        """Test PeriodicTimeRange.replace() raises TypeError for invalid period."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(
            initial_time_range, relativedelta(months=1), date(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="period must be relativedelta"):
            t_range.replace(period=30)

    def test_periodic_time_range_replace_invalid_expiration_date(self) -> None:
        """Test PeriodicTimeRange.replace() raises TypeError for invalid expiration_date."""
        initial_time_range = DateRange(date(2023, 1, 1), relativedelta(days=10))
        t_range = RecurringDateRange(
            initial_time_range, relativedelta(months=1), date(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="expiration_date must be date"):
            t_range.replace(expiration_date="2023-12-31")

    def test_periodic_daily_time_range_replace_invalid_initial_date(self) -> None:
        """Test PeriodicDailyTimeRange.replace() raises TypeError for invalid initial_date."""
        t_range = RecurringDay(
            date(2023, 1, 1), relativedelta(months=1), date(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="start_date must be date"):
            t_range.replace(start_date="2023-01-01")

    def test_periodic_daily_time_range_replace_invalid_period(self) -> None:
        """Test PeriodicDailyTimeRange.replace() raises TypeError for invalid period."""
        t_range = RecurringDay(
            date(2023, 1, 1), relativedelta(months=1), date(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="period must be relativedelta"):
            t_range.replace(period=30)

    def test_periodic_daily_time_range_replace_invalid_expiration_date(self) -> None:
        """Test PeriodicDailyTimeRange.replace() raises TypeError for invalid expiration_date."""
        t_range = RecurringDay(
            date(2023, 1, 1), relativedelta(months=1), date(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="expiration_date must be date"):
            t_range.replace(expiration_date="2023-12-31")


class TestDateRangeProtocol:
    """Tests for DateRange protocol methods: __repr__, __eq__, __lt__, __hash__."""

    def test_date_range_repr(self) -> None:
        """DateRange repr shows start and last date."""
        dr = DateRange(date(2023, 1, 1), relativedelta(days=10))
        result = repr(dr)
        assert "2023-01-01" in result
        assert "2023-01-10" in result

    def test_date_range_eq_with_non_date_range(self) -> None:
        """DateRange equality with non-DateRange returns False."""
        dr = DateRange(date(2023, 1, 1), relativedelta(days=10))
        assert dr != "not a date range"

    def test_date_range_lt_with_non_date_range(self) -> None:
        """DateRange comparison with non-DateRange raises TypeError."""
        dr = DateRange(date(2023, 1, 1), relativedelta(days=10))
        with pytest.raises(TypeError):
            _ = dr < "not a date range"  # type: ignore[operator]

    def test_recurring_date_range_repr(self) -> None:
        """RecurringDateRange repr shows period and expiration."""
        rdr = RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            date(2023, 12, 31),
        )
        result = repr(rdr)
        assert "2023-01-01" in result
        assert "2023-12-31" in result

    def test_recurring_date_range_repr_no_expiration(self) -> None:
        """RecurringDateRange repr shows 'forever' when no expiration."""
        rdr = RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
        )
        result = repr(rdr)
        assert "forever" in result

    def test_recurring_date_range_eq_with_non_recurring(self) -> None:
        """RecurringDateRange equality with non-RecurringDateRange returns False."""
        rdr = RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
        )
        assert rdr != "not a range"

    def test_recurring_date_range_hash(self) -> None:
        """Equal RecurringDateRanges have the same hash."""
        rdr1 = RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            date(2023, 12, 31),
        )
        rdr2 = RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            date(2023, 12, 31),
        )
        assert hash(rdr1) == hash(rdr2)

    def test_recurring_date_range_last_date_range_within(self) -> None:
        """last_date_range returns the current range when target is within it."""
        rdr = RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            date(2023, 12, 31),
        )
        result = rdr.last_date_range(date(2023, 3, 15))
        assert result is not None
        assert result.start_date == date(2023, 3, 1)
