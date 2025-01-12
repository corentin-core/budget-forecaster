"""Module with tests for the OperationMatcher class."""
from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.time_range import DailyTimeRange, PeriodicTimeRange, TimeRange
from budget_forecaster.types import Category


@pytest.fixture
def historic_operations() -> list[HistoricOperation]:
    """Return a list of historic operations."""
    return [
        HistoricOperation(
            unique_id=1,
            description="Operation 1",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(105.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 20),
        ),
        HistoricOperation(
            unique_id=3,
            description="Operation 3",
            amount=Amount(105.1),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 20),
        ),
        HistoricOperation(
            unique_id=4,
            description="Operation 4",
            amount=Amount(95.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 21),
        ),
        HistoricOperation(
            unique_id=5,
            description="Operation 5",
            amount=Amount(94.9),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 26),
        ),
        HistoricOperation(
            unique_id=6,
            description="Operation 6",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 1),
        ),
        HistoricOperation(
            unique_id=7,
            description="Operation 7",
            amount=Amount(100.0),
            category=Category.OTHER,
            date=datetime(2023, 1, 1),
        ),
        HistoricOperation(
            unique_id=8,
            description="Operation 8",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 2, 1),
        ),
        HistoricOperation(
            unique_id=9,
            description="Operation 9",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 2, 6),
        ),
    ]


@pytest.fixture
def daily_operation_range() -> OperationRange:
    """Return a daily operation range."""
    return OperationRange(
        "Test Daily Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        DailyTimeRange(datetime(2023, 1, 1)),
    )


class TestOperationMatcherDailyTimeRange:
    """Tests for the OperationMatcher class with daily time ranges."""

    def test_matches_operations_correctly(
        self,
        daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher matches operations correctly."""
        matcher = OperationMatcher(
            daily_operation_range, approximation_date_range=timedelta()
        )
        assert set(matcher.matches(historic_operations)) == {historic_operations[5]}

    def test_matches_operations_with_description_hints(
        self, daily_operation_range: OperationRange
    ) -> None:
        """Test that the OperationMatcher matches operations correctly with description hints."""
        matcher = OperationMatcher(
            daily_operation_range,
            approximation_date_range=timedelta(),
            description_hints={"1"},
        )
        operations = [
            HistoricOperation(
                unique_id=1,
                description="Test Operation 1",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 1),
            ),
            HistoricOperation(
                unique_id=2,
                description="Test Operation 2",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 1),
            ),
            HistoricOperation(
                unique_id=3,
                description="Other Operation",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 1),
            ),
        ]
        assert set(matcher.matches(operations)) == {operations[0]}

    def test_latest_matching_operations(
        self,
        daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the latest matching operations."""
        # add flexibility on the date range
        matcher = OperationMatcher(
            daily_operation_range, approximation_date_range=timedelta(days=5)
        )
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 1), historic_operations
            )
        ) == {historic_operations[5]}
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 6), historic_operations
            )
        ) == {historic_operations[5]}
        assert (
            set(
                matcher.latest_matching_operations(
                    datetime(2023, 12, 31), historic_operations
                )
            )
            == set()
        )
        assert (
            set(
                matcher.latest_matching_operations(
                    datetime(2023, 1, 7), historic_operations
                )
            )
            == set()
        )

    def test_late_time_ranges(
        self,
        daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the late time ranges."""
        # add flexibility on the date range
        matcher = OperationMatcher(
            daily_operation_range, approximation_date_range=timedelta(days=5)
        )
        # time range is not late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 12, 31), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 1, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_time_ranges(datetime(2023, 1, 2), ())) == {
            DailyTimeRange(datetime(2023, 1, 1))
        }
        assert set(matcher.late_time_ranges(datetime(2023, 1, 6), ())) == {
            DailyTimeRange(datetime(2023, 1, 1))
        }
        # operation is already executed
        assert (
            set(matcher.late_time_ranges(datetime(2023, 1, 6), historic_operations))
            == set()
        )
        late_operation_executed = HistoricOperation(
            unique_id=10,
            description="Operation 10",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 3),
        )
        # operation was late but executed at current date
        assert (
            set(
                matcher.late_time_ranges(
                    datetime(2023, 1, 6), (late_operation_executed,)
                )
            )
            == set()
        )
        anticipated_operation_executed = HistoricOperation(
            unique_id=11,
            description="Operation 11",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2022, 12, 30),
        )
        # operation was already executed at current date
        assert (
            set(
                matcher.late_time_ranges(
                    datetime(2023, 1, 6), (anticipated_operation_executed,)
                )
            )
            == set()
        )

    def test_anticipated_time_ranges(
        self,
        daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the anticipated time ranges."""
        matcher = OperationMatcher(
            daily_operation_range, approximation_date_range=timedelta(days=5)
        )
        anticipated_operation = HistoricOperation(
            unique_id=12,
            description="Operation 12",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2022, 12, 27),
        )
        historic_operations.append(anticipated_operation)
        # the expected operation is a future operation and is already executed
        assert set(
            matcher.anticipated_time_ranges(datetime(2022, 12, 27), historic_operations)
        ) == {(DailyTimeRange(datetime(2023, 1, 1)), anticipated_operation)}
        assert set(
            matcher.anticipated_time_ranges(datetime(2022, 12, 31), historic_operations)
        ) == {(DailyTimeRange(datetime(2023, 1, 1)), anticipated_operation)}
        # the expected operation is not a future operation
        assert (
            set(
                matcher.anticipated_time_ranges(
                    datetime(2023, 1, 1), historic_operations
                )
            )
            == set()
        )
        # this operation has not happened yet
        assert (
            set(
                matcher.anticipated_time_ranges(
                    datetime(2022, 12, 23), historic_operations
                )
            )
            == set()
        )


@pytest.fixture
def operation_range() -> OperationRange:
    """Return an operation range."""
    return OperationRange(
        "Test Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
    )


class TestOperationMatcherTimeRange:
    """Tests for the OperationMatcher class with time ranges."""

    def test_matches_operations_correctly(
        self,
        operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher matches operations correctly."""
        matcher = OperationMatcher(
            operation_range, approximation_date_range=timedelta()
        )
        assert set(matcher.matches(historic_operations)) == {
            historic_operations[i] for i in (0, 1, 3, 5)
        }

    def test_matches_operations_with_description_hints(
        self,
        operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher matches operations correctly with description hints."""
        matcher = OperationMatcher(
            operation_range,
            approximation_date_range=timedelta(),
            description_hints={"1"},
        )
        assert set(matcher.matches(historic_operations)) == {historic_operations[0]}

    def test_latest_matching_operations(
        self,
        operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the latest matching operations."""
        # add flexibility on the date range
        matcher = OperationMatcher(
            operation_range, approximation_date_range=timedelta(days=5)
        )
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 6), historic_operations
            )
        ) == {historic_operations[5]}
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 21), historic_operations
            )
        ) == {historic_operations[i] for i in (1, 3)}
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 2, 3), historic_operations
            )
        ) == {historic_operations[7]}
        assert (
            set(
                matcher.latest_matching_operations(
                    datetime(2023, 2, 7), historic_operations
                )
            )
            == set()
        )

    def test_late_time_ranges(
        self,
        operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the late time ranges."""
        # add flexibility on the date range
        matcher = OperationMatcher(
            operation_range, approximation_date_range=timedelta(days=5)
        )
        # time range is not late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 12, 31), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 2, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_time_ranges(datetime(2023, 1, 2), ())) == {
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        }
        assert set(matcher.late_time_ranges(datetime(2023, 1, 6), ())) == {
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        }
        # operation is already executed
        assert (
            set(matcher.late_time_ranges(datetime(2023, 1, 6), historic_operations))
            == set()
        )

    def test_anticipated_time_ranges(
        self,
        operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the anticipated time ranges."""
        historic_operations.append(
            HistoricOperation(
                unique_id=12,
                description="Operation 12",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2022, 12, 27),
            )
        )
        # add flexibility on the date range
        matcher = OperationMatcher(
            operation_range, approximation_date_range=timedelta(days=5)
        )
        # operation 12 was executed close enough from next time range
        assert set(
            matcher.anticipated_time_ranges(datetime(2022, 12, 27), historic_operations)
        ) == {
            (
                TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
                historic_operations[-1],
            )
        }
        # no future time range at this date
        assert (
            set(
                matcher.anticipated_time_ranges(
                    datetime(2023, 1, 1), historic_operations
                )
            )
            == set()
        )


@pytest.fixture
def periodic_daily_operation_range(
    daily_operation_range: OperationRange,
) -> OperationRange:
    """Return a periodic daily operation range."""
    return OperationRange(
        "Test Periodic Daily Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        PeriodicTimeRange(
            daily_operation_range.time_range,
            relativedelta(months=1),
            datetime(2023, 12, 31),
        ),
    )


class TestOperationMatcherPeriodicDailyTimeRange:
    """Tests for the OperationMatcher class with periodic daily time ranges."""

    def test_matches_operations_correctly(
        self,
        periodic_daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher matches operations correctly."""
        matcher = OperationMatcher(
            periodic_daily_operation_range, approximation_date_range=timedelta()
        )
        assert set(matcher.matches(historic_operations)) == {
            historic_operations[i] for i in (5, 7)
        }

    def test_latest_matching_operations(
        self,
        periodic_daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the latest matching operations."""
        matcher = OperationMatcher(periodic_daily_operation_range)

        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 6), historic_operations
            )
        ) == {historic_operations[5]}
        assert (
            set(
                matcher.latest_matching_operations(
                    datetime(2023, 1, 21), historic_operations
                )
            )
            == set()
        )
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 2, 3), historic_operations
            )
        ) == {historic_operations[7]}

    def test_late_time_ranges(
        self,
        periodic_daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the late time ranges."""
        # add flexibility on the date range
        matcher = OperationMatcher(
            periodic_daily_operation_range, approximation_date_range=timedelta(days=5)
        )
        # time range is not late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 12, 31), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 2, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_time_ranges(datetime(2023, 1, 2), ())) == {
            DailyTimeRange(datetime(2023, 1, 1))
        }
        assert set(matcher.late_time_ranges(datetime(2023, 1, 6), ())) == {
            DailyTimeRange(datetime(2023, 1, 1))
        }
        # operation is already executed
        assert (
            set(matcher.late_time_ranges(datetime(2023, 1, 6), historic_operations))
            == set()
        )

    def test_anticipated_time_ranges(
        self,
        periodic_daily_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the anticipated time ranges."""
        historic_operations.append(
            HistoricOperation(
                unique_id=12,
                description="Operation 12",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 27),
            )
        )
        matcher = OperationMatcher(periodic_daily_operation_range)
        assert set(
            matcher.anticipated_time_ranges(datetime(2023, 1, 27), historic_operations)
        ) == {(DailyTimeRange(datetime(2023, 2, 1)), historic_operations[-1])}
        assert (
            set(
                matcher.anticipated_time_ranges(
                    datetime(2023, 1, 26), historic_operations
                )
            )
            == set()
        )


@pytest.fixture
def periodic_operation_range(
    operation_range: OperationRange,
) -> OperationRange:
    """Return a periodic operation range."""
    return OperationRange(
        "Test Periodic Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        PeriodicTimeRange(
            operation_range.time_range, relativedelta(months=1), datetime(2023, 12, 31)
        ),
    )


class TestOperationMatcherPeriodicTimeRange:
    """Tests for the OperationMatcher class with periodic time ranges."""

    def test_matches_operations_correctly(
        self,
        periodic_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher matches operations correctly."""
        matcher = OperationMatcher(periodic_operation_range)
        assert set(matcher.matches(historic_operations)) == {
            historic_operations[i] for i in (0, 1, 3, 5, 7, 8)
        }

    def test_latest_matching_operations(
        self,
        periodic_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the latest matching operations."""
        matcher = OperationMatcher(periodic_operation_range)
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 6), historic_operations
            )
        ) == {historic_operations[5]}
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 1, 21), historic_operations
            )
        ) == {historic_operations[i] for i in (1, 3)}
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 2, 3), historic_operations
            )
        ) == {historic_operations[7]}
        assert set(
            matcher.latest_matching_operations(
                datetime(2023, 2, 7), historic_operations
            )
        ) == {historic_operations[8]}

    def test_late_time_ranges(
        self,
        periodic_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the late time ranges."""
        # add flexibility on the date range
        matcher = OperationMatcher(
            periodic_operation_range, approximation_date_range=timedelta(days=5)
        )
        # time range is not late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 1, 1), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_time_ranges(datetime(2023, 2, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_time_ranges(datetime(2023, 1, 2), ())) == {
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        }
        assert set(matcher.late_time_ranges(datetime(2023, 1, 6), ())) == {
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1))
        }
        # operation is already executed
        assert (
            set(matcher.late_time_ranges(datetime(2023, 1, 6), historic_operations))
            == set()
        )

    def test_anticipated_time_ranges(
        self,
        periodic_operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that the OperationMatcher returns the anticipated time ranges."""
        matcher = OperationMatcher(periodic_operation_range)
        historic_operations.append(
            HistoricOperation(
                unique_id=12,
                description="Operation 12",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 27),
            )
        )

        assert set(
            matcher.anticipated_time_ranges(datetime(2023, 1, 27), historic_operations)
        ) == {
            (
                TimeRange(datetime(2023, 2, 1), relativedelta(months=1)),
                historic_operations[-1],
            )
        }
        assert (
            set(
                matcher.anticipated_time_ranges(
                    datetime(2023, 1, 26), historic_operations
                )
            )
            == set()
        )
