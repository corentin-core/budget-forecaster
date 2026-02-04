"""Module with test cases for the TimeRange class."""
import itertools
from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
)


@pytest.fixture
def time_range() -> TimeRange:
    """Return a TimeRange instance."""
    return TimeRange(datetime(2023, 1, 1), relativedelta(days=10))


class TestTimeRange:
    """Test cases for the TimeRange class."""

    def test_initial_date(self, time_range: TimeRange) -> None:
        """Test the initial_date property."""
        assert time_range.initial_date == datetime(2023, 1, 1)

    def test_last_date(self, time_range: TimeRange) -> None:
        """Test the last_date property."""
        assert time_range.last_date == datetime(2023, 1, 10)

    def test_total_duration(self, time_range: TimeRange) -> None:
        """Test the total_duration property."""
        assert time_range.total_duration == timedelta(days=10)

    def test_total_duration_relative(self) -> None:
        """Test the total_duration property with a relative delta."""
        t_range = TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        assert t_range.total_duration == timedelta(days=31)

        t_range = TimeRange(datetime(2023, 2, 1), relativedelta(months=1))
        assert t_range.total_duration == timedelta(days=28)

    def test_duration(self, time_range: TimeRange) -> None:
        """Test the duration property returns the relativedelta."""
        assert time_range.duration == relativedelta(days=10)

    def test_duration_months(self) -> None:
        """Test the duration property with months."""
        t_range = TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        assert t_range.duration == relativedelta(months=1)

    def test_contains_date_within_range(self, time_range: TimeRange) -> None:
        """Test the is_within method with dates within the range."""
        for date in (
            datetime(2023, 1, 1),
            datetime(2023, 1, 5),
            datetime(2023, 1, 10),
        ):
            assert time_range.is_within(date)

    def test_does_not_contain_date_outside_range(self, time_range: TimeRange) -> None:
        """Test the is_within method with dates outside the range."""
        assert not time_range.is_within(datetime(2022, 12, 31))
        assert not time_range.is_within(datetime(2023, 1, 11))

    def test_is_expired(self, time_range: TimeRange) -> None:
        """Test the is_expired method."""
        assert time_range.is_expired(datetime(2023, 1, 11))

    def test_is_not_expired(self, time_range: TimeRange) -> None:
        """Test the is_expired method."""
        assert not time_range.is_expired(datetime(2023, 1, 10))

    def test_is_future(self, time_range: TimeRange) -> None:
        """Test the is_future method."""
        assert time_range.is_future(datetime(2022, 12, 31))

    def test_is_not_future(self, time_range: TimeRange) -> None:
        """Test the is_future method."""
        assert not time_range.is_future(datetime(2023, 1, 1))

    def test_iterate_over_time_ranges(self, time_range: TimeRange) -> None:
        """Test the iterate_over_time_ranges method."""
        time_ranges = list(time_range.iterate_over_time_ranges())
        assert len(time_ranges) == 1
        assert time_ranges[0] == time_range

    def test_current_time_range(self, time_range: TimeRange) -> None:
        """Test the current_time_range method."""
        assert time_range.current_time_range(datetime(2023, 1, 5)) == time_range
        assert time_range.current_time_range(datetime(2022, 12, 31)) is None
        assert time_range.current_time_range(datetime(2023, 1, 11)) is None

    def test_next_time_range(self, time_range: TimeRange) -> None:
        """Test the next_time_range method."""
        assert time_range.next_time_range(datetime(2022, 12, 31)) == time_range
        assert time_range.next_time_range(datetime(2023, 1, 1)) is None

    def test_last_time_range(self, time_range: TimeRange) -> None:
        """Test the last_time_range method."""
        assert time_range.last_time_range(datetime(2023, 1, 10)) == time_range
        assert time_range.last_time_range(datetime(2022, 12, 31)) is None

    def test_replace_with_new_initial_date(self, time_range: TimeRange) -> None:
        """Test the replace method."""
        new_time_range = time_range.replace(initial_date=datetime(2023, 1, 2))
        assert new_time_range.initial_date == datetime(2023, 1, 2)
        assert new_time_range.last_date == datetime(2023, 1, 11)
        assert new_time_range.total_duration == timedelta(days=10)


@pytest.fixture
def daily_time_range() -> DailyTimeRange:
    """Return a DailyTimeRange instance."""
    return DailyTimeRange(datetime(2023, 1, 1))


class TestDailyTimeRange:
    """Test cases for the DailyTimeRange class."""

    def test_initial_date(self, daily_time_range: DailyTimeRange) -> None:
        """Test the initial_date property."""
        assert daily_time_range.initial_date == datetime(2023, 1, 1)

    def test_last_date(self, daily_time_range: DailyTimeRange) -> None:
        """Test the last_date property."""
        assert daily_time_range.last_date == datetime(2023, 1, 1)

    def test_total_duration(self, daily_time_range: DailyTimeRange) -> None:
        """Test the total_duration property."""
        assert daily_time_range.total_duration == timedelta(days=1)

    def test_duration(self, daily_time_range: DailyTimeRange) -> None:
        """Test the duration property returns the relativedelta."""
        assert daily_time_range.duration == relativedelta(days=1)

    def test_contains_date_within_range(self, daily_time_range: DailyTimeRange) -> None:
        """Test the is_within method with dates within the range."""
        assert daily_time_range.is_within(datetime(2023, 1, 1))

    def test_does_not_contain_date_outside_range(
        self, daily_time_range: DailyTimeRange
    ) -> None:
        """Test the is_within method with dates outside the range."""
        assert not daily_time_range.is_within(datetime(2022, 12, 31))
        assert not daily_time_range.is_within(datetime(2023, 1, 2))

    def test_is_expired(self, daily_time_range: DailyTimeRange) -> None:
        """Test the is_expired method."""
        assert daily_time_range.is_expired(datetime(2023, 1, 2))

    def test_is_not_expired(self, daily_time_range: DailyTimeRange) -> None:
        """Test the is_expired method."""
        assert not daily_time_range.is_expired(datetime(2023, 1, 1))

    def test_is_future(self, daily_time_range: DailyTimeRange) -> None:
        """Test the is_future method."""
        assert daily_time_range.is_future(datetime(2022, 12, 31))

    def test_is_not_future(self, daily_time_range: DailyTimeRange) -> None:
        """Test the is_future method."""
        assert not daily_time_range.is_future(datetime(2023, 1, 1))

    def test_iterate_over_time_ranges(self, daily_time_range: DailyTimeRange) -> None:
        """Test the iterate_over_time_ranges method."""
        time_ranges = list(daily_time_range.iterate_over_time_ranges())
        assert len(time_ranges) == 1
        assert time_ranges[0] == daily_time_range

    def test_current_time_range(self, daily_time_range: DailyTimeRange) -> None:
        """Test the current_time_range method."""
        assert (
            daily_time_range.current_time_range(datetime(2023, 1, 1))
            == daily_time_range
        )
        assert daily_time_range.current_time_range(datetime(2022, 12, 31)) is None
        assert daily_time_range.current_time_range(datetime(2023, 1, 2)) is None

    def test_next_time_range(self, daily_time_range: DailyTimeRange) -> None:
        """Test the next_time_range method."""
        assert (
            daily_time_range.next_time_range(datetime(2022, 12, 31)) == daily_time_range
        )
        assert daily_time_range.next_time_range(datetime(2023, 1, 1)) is None

    def test_last_time_range(self, daily_time_range: DailyTimeRange) -> None:
        """Test the last_time_range method."""
        assert (
            daily_time_range.last_time_range(datetime(2023, 1, 1)) == daily_time_range
        )
        assert daily_time_range.last_time_range(datetime(2022, 12, 31)) is None

    def test_replace_with_new_initial_date(
        self, daily_time_range: DailyTimeRange
    ) -> None:
        """Test the replace method."""
        new_time_range = daily_time_range.replace(initial_date=datetime(2023, 1, 2))
        assert new_time_range.initial_date == datetime(2023, 1, 2)
        assert new_time_range.last_date == datetime(2023, 1, 2)
        assert new_time_range.total_duration == timedelta(days=1)


@pytest.fixture
def periodic_time_range(time_range: TimeRange) -> PeriodicTimeRange:
    """Return a PeriodicTimeRange instance."""
    return PeriodicTimeRange(
        time_range, relativedelta(months=1), datetime(2023, 12, 31)
    )


class TestPeriodicTimeRange:  # pylint: disable=too-many-public-methods
    """Test cases for the PeriodicTimeRange class."""

    def test_initial_date(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the initial_date property."""
        assert periodic_time_range.initial_date == datetime(2023, 1, 1)

    def test_last_date(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the last_date property."""
        assert periodic_time_range.last_date == datetime(2023, 12, 31)

    def test_total_duration(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the total_duration property."""
        assert periodic_time_range.total_duration == timedelta(days=365)

    def test_duration(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the duration property returns the period's relativedelta."""
        assert periodic_time_range.duration == relativedelta(days=10)

    def test_base_time_range(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the base_time_range property."""
        base = periodic_time_range.base_time_range
        assert base.initial_date == datetime(2023, 1, 1)
        assert base.duration == relativedelta(days=10)

    def test_contains_date_within_range(
        self, periodic_time_range: PeriodicTimeRange
    ) -> None:
        """Test the is_within method with dates within the range."""
        for month in range(1, 13):
            for date in (
                datetime(2023, month, 1),
                datetime(2023, month, 5),
                datetime(2023, month, 10),
            ):
                assert periodic_time_range.is_within(date)

    def test_does_not_contain_date_outside_range(
        self, periodic_time_range: PeriodicTimeRange
    ) -> None:
        """Test the is_within method with dates outside the range."""
        for month in range(1, 13):
            assert not periodic_time_range.is_within(datetime(2023, month, 11))
            assert not periodic_time_range.is_within(
                datetime(2023, month, 1) - relativedelta(days=1)
            )

    def test_is_expired(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the is_expired method."""
        assert periodic_time_range.is_expired(datetime(2024, 1, 1))

    def test_is_not_expired(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the is_expired method."""
        assert not periodic_time_range.is_expired(datetime(2023, 6, 1))

    def test_is_future(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the is_future method."""
        assert periodic_time_range.is_future(datetime(2022, 12, 31))

    def test_is_not_future(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the is_future method."""
        assert not periodic_time_range.is_future(datetime(2023, 1, 1))

    def test_iterate_over_time_ranges(
        self, periodic_time_range: PeriodicTimeRange
    ) -> None:
        """Test the iterate_over_time_ranges method."""
        time_ranges = list(periodic_time_range.iterate_over_time_ranges())
        assert len(time_ranges) == 12
        for month, t_range in enumerate(time_ranges, start=1):
            assert t_range == TimeRange(
                datetime(2023, month, 1), relativedelta(days=10)
            )

    def test_iterate_over_time_ranges_no_date_drift(self) -> None:
        """Test that monthly iterations don't drift when starting from day 31.

        Regression test: when adding months iteratively (date + period),
        dates can drift (Oct 31 -> Nov 30 -> Dec 30 -> Jan 30...).
        The correct behavior is to compute from initial_date + n*period
        to preserve the original day-of-month where possible.
        """
        # Start on Oct 31 with monthly period
        initial = DailyTimeRange(datetime(2025, 10, 31))
        ptr = PeriodicTimeRange(initial, relativedelta(months=1), datetime(2026, 6, 1))

        iterations = [tr.initial_date for tr in ptr.iterate_over_time_ranges()]

        # Expected: stay on 31st when month has 31 days, otherwise end of month
        expected = [
            datetime(2025, 10, 31),  # Oct has 31 days
            datetime(2025, 11, 30),  # Nov has 30 days
            datetime(2025, 12, 31),  # Dec has 31 days (NOT 30!)
            datetime(2026, 1, 31),  # Jan has 31 days (NOT 30!)
            datetime(2026, 2, 28),  # Feb has 28 days
            datetime(2026, 3, 31),  # Mar has 31 days (NOT 28!)
            datetime(2026, 4, 30),  # Apr has 30 days
            datetime(2026, 5, 31),  # May has 31 days
        ]
        assert iterations == expected

    def test_iterate_over_time_ranges_from_distant_date(self) -> None:
        """Test that iteration from a distant date is efficient (O(1) start).

        Regression test: the old implementation used a while loop to find the
        start position, which was O(n) where n = number of periods to skip.
        The optimized version calculates the start position arithmetically.
        """
        # Monthly period starting in 2020, no expiration
        initial = DailyTimeRange(datetime(2020, 1, 15))
        ptr = PeriodicTimeRange(initial, relativedelta(months=1), None)

        # Iterate starting from 10 years later (would be 120 iterations with old impl)
        from_date = datetime(2030, 6, 20)
        iterations = list(itertools.islice(ptr.iterate_over_time_ranges(from_date), 3))

        # Should start from June 2030 (first iteration >= from_date is July 15)
        assert len(iterations) == 3
        assert iterations[0].initial_date == datetime(2030, 6, 15)
        assert iterations[1].initial_date == datetime(2030, 7, 15)
        assert iterations[2].initial_date == datetime(2030, 8, 15)

    def test_iterate_over_time_ranges_mixed_period(self) -> None:
        """Test iteration with a mixed period (months + days)."""
        # Period of 1 month and 15 days
        initial = DailyTimeRange(datetime(2025, 1, 1))
        ptr = PeriodicTimeRange(
            initial, relativedelta(months=1, days=15), datetime(2026, 12, 31)
        )

        # Iterate from a date several periods ahead
        # Iterations: Jan 1, Feb 16, Mar 31, May 16, Jun 30, Aug 15, ...
        from_date = datetime(2025, 6, 1)
        iterations = list(itertools.islice(ptr.iterate_over_time_ranges(from_date), 3))

        # from_date is Jun 1, so first returned should be May 16 (last before Jun 1)
        assert iterations[0].initial_date == datetime(2025, 5, 16)
        assert iterations[1].initial_date == datetime(2025, 6, 30)
        assert iterations[2].initial_date == datetime(2025, 8, 15)

    def test_iterate_over_time_ranges_conservative_estimate(self) -> None:
        """Test that conservative period estimation doesn't skip iterations.

        Regression test: when estimating period length, we must use maximum
        values (31 days/month) to avoid skipping iterations. With 30 days/month,
        over 10 years of monthly periods we'd overshoot by ~3 iterations.
        """
        # Monthly period starting Jan 31 (maximizes actual period length)
        initial = DailyTimeRange(datetime(2020, 1, 31))
        ptr = PeriodicTimeRange(initial, relativedelta(months=1), None)

        # 10 years later: with 30-day estimate, we'd calculate ~122 periods
        # but actual is ~120, so we'd skip iterations
        from_date = datetime(2030, 3, 15)
        iterations = list(itertools.islice(ptr.iterate_over_time_ranges(from_date), 3))

        # First iteration should be Feb 28/29 2030 (last iteration before Mar 15)
        # NOT skipped due to overestimation
        assert iterations[0].initial_date == datetime(2030, 2, 28)
        assert iterations[1].initial_date == datetime(2030, 3, 31)
        assert iterations[2].initial_date == datetime(2030, 4, 30)

    def test_split_at(self) -> None:
        """Test split_at returns terminated range and continuation range."""
        initial = DailyTimeRange(datetime(2025, 1, 15))
        ptr = PeriodicTimeRange(
            initial, relativedelta(months=1), datetime(2025, 12, 31)
        )

        terminated, continuation = ptr.split_at(datetime(2025, 4, 1))

        # Terminated range ends day before first new iteration (April 15)
        assert terminated.last_date == datetime(2025, 4, 14)
        # Continuation starts at first iteration >= split date
        assert continuation.initial_date == datetime(2025, 4, 15)
        assert continuation.period == ptr.period
        # Continuation keeps original expiration date
        assert continuation.last_date == datetime(2025, 12, 31)

    def test_split_at_exact_iteration(self) -> None:
        """Test split_at when date matches an iteration exactly."""
        initial = DailyTimeRange(datetime(2025, 1, 15))
        ptr = PeriodicTimeRange(
            initial, relativedelta(months=1), datetime(2025, 12, 31)
        )

        terminated, continuation = ptr.split_at(datetime(2025, 4, 15))

        assert terminated.last_date == datetime(2025, 4, 14)
        assert continuation.initial_date == datetime(2025, 4, 15)
        assert continuation.period == ptr.period

    def test_split_at_raises_if_before_initial(self) -> None:
        """Test split_at raises ValueError if date is before or at initial date."""
        initial = DailyTimeRange(datetime(2025, 1, 15))
        ptr = PeriodicTimeRange(
            initial, relativedelta(months=1), datetime(2025, 12, 31)
        )

        with pytest.raises(ValueError, match="after the first iteration"):
            ptr.split_at(datetime(2025, 1, 15))

        with pytest.raises(ValueError, match="after the first iteration"):
            ptr.split_at(datetime(2025, 1, 1))

    def test_split_at_raises_if_no_iteration_after(self) -> None:
        """Test split_at raises ValueError if no iteration exists at or after date."""
        initial = DailyTimeRange(datetime(2025, 1, 15))
        ptr = PeriodicTimeRange(initial, relativedelta(months=1), datetime(2025, 3, 31))

        with pytest.raises(ValueError, match="No iteration found"):
            ptr.split_at(datetime(2025, 6, 1))

    def test_current_time_range(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the current_time_range method."""
        for month in range(1, 13):
            assert periodic_time_range.current_time_range(
                datetime(2023, month, 5)
            ) == TimeRange(datetime(2023, month, 1), relativedelta(days=10))

    def test_current_time_range_no_expiration(self) -> None:
        """Test the current_time_range method with no expiration date."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(initial_time_range, relativedelta(months=1), None)
        assert t_range.current_time_range(datetime(2023, 2, 5)) == TimeRange(
            datetime(2023, 2, 1), relativedelta(days=10)
        )

    def test_current_time_range_returns_none(
        self, periodic_time_range: PeriodicTimeRange
    ) -> None:
        """Test the current_time_range method when it should return None."""
        assert periodic_time_range.current_time_range(datetime(2024, 1, 1)) is None

    def test_next_time_range(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the next_time_range method."""
        for month in range(1, 12):
            assert periodic_time_range.next_time_range(
                datetime(2023, month, 5)
            ) == TimeRange(datetime(2023, month + 1, 1), relativedelta(days=10))

    def test_next_time_range_no_expiration(self) -> None:
        """Test the next_time_range method with no expiration date."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(initial_time_range, relativedelta(months=1), None)
        assert t_range.next_time_range(datetime(2023, 1, 5)) == TimeRange(
            datetime(2023, 2, 1), relativedelta(days=10)
        )

    def test_next_time_range_returns_none(self) -> None:
        """Test the next_time_range method when it should return None."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(
            initial_time_range, relativedelta(months=1), datetime(2023, 2, 1)
        )
        assert t_range.next_time_range(datetime(2023, 2, 5)) is None

    def test_last_time_range(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the last_time_range method."""
        for month in range(1, 12):
            assert periodic_time_range.last_time_range(
                datetime(2023, month, 5)
            ) == TimeRange(datetime(2023, month, 1), relativedelta(days=10))

    def test_last_time_range_no_expiration(self) -> None:
        """Test the last_time_range method with no expiration date."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(initial_time_range, relativedelta(months=1), None)
        assert t_range.last_time_range(datetime(2023, 1, 5)) == TimeRange(
            datetime(2023, 1, 1), relativedelta(days=10)
        )

    def test_last_time_range_returns_none(self) -> None:
        """Test the last_time_range method when it should return None."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(
            initial_time_range, relativedelta(months=1), datetime(2023, 2, 1)
        )
        assert t_range.last_time_range(datetime(2023, 1, 1)) is None

    def test_replace_with_new_initial_date(
        self, periodic_time_range: PeriodicTimeRange
    ) -> None:
        """Test the replace method."""
        new_time_range = periodic_time_range.replace(initial_date=datetime(2023, 1, 2))
        assert new_time_range.initial_date == datetime(2023, 1, 2)
        assert new_time_range.last_date == datetime(2023, 12, 31)
        assert new_time_range.total_duration == timedelta(days=364)


class TestTimeRangeReplaceTypeErrors:
    """Tests for TypeError when passing invalid types to replace() methods."""

    def test_time_range_replace_invalid_initial_date(self) -> None:
        """Test TimeRange.replace() raises TypeError for invalid initial_date."""
        t_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        with pytest.raises(TypeError, match="initial_date must be datetime"):
            t_range.replace(initial_date="2023-01-01")

    def test_time_range_replace_invalid_duration(self) -> None:
        """Test TimeRange.replace() raises TypeError for invalid duration."""
        t_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        with pytest.raises(TypeError, match="duration must be relativedelta"):
            t_range.replace(duration=10)

    def test_daily_time_range_replace_invalid_initial_date(self) -> None:
        """Test DailyTimeRange.replace() raises TypeError for invalid initial_date."""
        t_range = DailyTimeRange(datetime(2023, 1, 1))
        with pytest.raises(TypeError, match="initial_date must be datetime"):
            t_range.replace(initial_date="2023-01-01")

    def test_periodic_time_range_replace_invalid_period(self) -> None:
        """Test PeriodicTimeRange.replace() raises TypeError for invalid period."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(
            initial_time_range, relativedelta(months=1), datetime(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="period must be relativedelta"):
            t_range.replace(period=30)

    def test_periodic_time_range_replace_invalid_expiration_date(self) -> None:
        """Test PeriodicTimeRange.replace() raises TypeError for invalid expiration_date."""
        initial_time_range = TimeRange(datetime(2023, 1, 1), relativedelta(days=10))
        t_range = PeriodicTimeRange(
            initial_time_range, relativedelta(months=1), datetime(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="expiration_date must be datetime"):
            t_range.replace(expiration_date="2023-12-31")

    def test_periodic_daily_time_range_replace_invalid_initial_date(self) -> None:
        """Test PeriodicDailyTimeRange.replace() raises TypeError for invalid initial_date."""
        t_range = PeriodicDailyTimeRange(
            datetime(2023, 1, 1), relativedelta(months=1), datetime(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="initial_date must be datetime"):
            t_range.replace(initial_date="2023-01-01")

    def test_periodic_daily_time_range_replace_invalid_period(self) -> None:
        """Test PeriodicDailyTimeRange.replace() raises TypeError for invalid period."""
        t_range = PeriodicDailyTimeRange(
            datetime(2023, 1, 1), relativedelta(months=1), datetime(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="period must be relativedelta"):
            t_range.replace(period=30)

    def test_periodic_daily_time_range_replace_invalid_expiration_date(self) -> None:
        """Test PeriodicDailyTimeRange.replace() raises TypeError for invalid expiration_date."""
        t_range = PeriodicDailyTimeRange(
            datetime(2023, 1, 1), relativedelta(months=1), datetime(2023, 12, 31)
        )
        with pytest.raises(TypeError, match="expiration_date must be datetime"):
            t_range.replace(expiration_date="2023-12-31")
