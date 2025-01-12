"""Module with test cases for the TimeRange class."""
from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.time_range import DailyTimeRange, PeriodicTimeRange, TimeRange


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

    def test_duration(self, time_range: TimeRange) -> None:
        """Test the duration property."""
        assert time_range.duration == timedelta(days=10)

    def test_duration_relative(self) -> None:
        """Test the duration property with a relative delta."""
        t_range = TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        assert t_range.duration == timedelta(days=31)

        t_range = TimeRange(datetime(2023, 2, 1), relativedelta(months=1))
        assert t_range.duration == timedelta(days=28)

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
        assert new_time_range.duration == timedelta(days=10)


@pytest.fixture
def daily_time_range() -> DailyTimeRange:
    """Return a DailyTimeRange instance."""
    return DailyTimeRange(datetime(2023, 1, 1))


class TestDailyTimeRange:
    """Test cases for the DailyTimeRange class."""

    def test_initial_date(self, time_range: TimeRange) -> None:
        """Test the initial_date property."""
        assert time_range.initial_date == datetime(2023, 1, 1)

    def test_last_date(self, time_range: TimeRange) -> None:
        """Test the last_date property."""
        assert time_range.last_date == datetime(2023, 1, 10)

    def test_duration(self, time_range: TimeRange) -> None:
        """Test the duration property."""
        assert time_range.duration == timedelta(days=10)

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
        assert new_time_range.duration == timedelta(days=1)


@pytest.fixture
def periodic_time_range(time_range: TimeRange) -> PeriodicTimeRange:
    """Return a PeriodicTimeRange instance."""
    return PeriodicTimeRange(
        time_range, relativedelta(months=1), datetime(2023, 12, 31)
    )


class TestPeriodicTimeRange:
    """Test cases for the PeriodicTimeRange class."""

    def test_initial_date(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the initial_date property."""
        assert periodic_time_range.initial_date == datetime(2023, 1, 1)

    def test_last_date(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the last_date property."""
        assert periodic_time_range.last_date == datetime(2023, 12, 31)

    def test_duration(self, periodic_time_range: PeriodicTimeRange) -> None:
        """Test the duration property."""
        assert periodic_time_range.duration == timedelta(days=365)

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
        assert new_time_range.duration == timedelta(days=364)
