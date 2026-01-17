"""Module with tests for the OperationMatcher class."""
# pylint: disable=too-many-lines
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


class TestOperationMatcherOperationLinks:
    """Tests for operation link functionality in OperationMatcher."""

    def test_operation_link_takes_priority_over_heuristic_mismatch(
        self, operation_range: OperationRange
    ) -> None:
        """Test that a linked operation matches even if heuristics fail."""
        # Create an operation that does NOT match heuristically
        # (different category, wrong amount, etc.)
        non_matching_operation = HistoricOperation(
            unique_id=100,
            description="Non matching operation",
            amount=Amount(500.0),  # Wrong amount (expected 100)
            category=Category.OTHER,  # Wrong category (expected GROCERIES)
            date=datetime(2023, 6, 15),  # Wrong date
        )

        # Without link, should not match
        matcher_no_link = OperationMatcher(operation_range)
        assert not matcher_no_link.match(non_matching_operation)

        # With link, should match regardless of heuristics
        matcher_with_link = OperationMatcher(
            operation_range,
            operation_links={100: datetime(2023, 1, 1)},
        )
        assert matcher_with_link.match(non_matching_operation)

    def test_add_and_remove_operation_link(
        self, operation_range: OperationRange
    ) -> None:
        """Test adding and removing operation links dynamically."""
        operation = HistoricOperation(
            unique_id=101,
            description="Test operation",
            amount=Amount(500.0),
            category=Category.OTHER,
            date=datetime(2023, 6, 15),
        )

        matcher = OperationMatcher(operation_range)

        # Initially no link
        assert not matcher.is_linked(operation)
        assert not matcher.match(operation)

        # Add link
        matcher.add_operation_link(101, datetime(2023, 1, 1))
        assert matcher.is_linked(operation)
        assert matcher.match(operation)

        # Remove link
        matcher.remove_operation_link(101)
        assert not matcher.is_linked(operation)
        assert not matcher.match(operation)

    def test_get_iteration_for_operation(self, operation_range: OperationRange) -> None:
        """Test getting the iteration date for a linked operation."""
        operation = HistoricOperation(
            unique_id=102,
            description="Test operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        iteration_date = datetime(2023, 1, 1)
        matcher = OperationMatcher(
            operation_range,
            operation_links={102: iteration_date},
        )

        assert matcher.get_iteration_for_operation(operation) == iteration_date

        # Non-linked operation returns None
        other_operation = HistoricOperation(
            unique_id=103,
            description="Other operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )
        assert matcher.get_iteration_for_operation(other_operation) is None

    def test_operation_links_preserved_in_replace(
        self, operation_range: OperationRange
    ) -> None:
        """Test that operation links are preserved when using replace()."""
        matcher = OperationMatcher(
            operation_range,
            operation_links={100: datetime(2023, 1, 1)},
        )

        new_operation_range = OperationRange(
            "New Test Operation",
            Amount(200, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 2, 1), relativedelta(months=1)),
        )
        new_matcher = matcher.replace(operation_range=new_operation_range)

        # Operation links should be preserved
        assert new_matcher.operation_links == {100: datetime(2023, 1, 1)}

    def test_operation_links_property_returns_copy(
        self, operation_range: OperationRange
    ) -> None:
        """Test that operation_links property returns a copy, not the original dict."""
        original_links = {100: datetime(2023, 1, 1)}
        matcher = OperationMatcher(operation_range, operation_links=original_links)

        # Modify the returned dict
        returned_links = matcher.operation_links
        returned_links[200] = datetime(2023, 2, 1)

        # Original should not be affected
        assert 200 not in matcher.operation_links

    def test_heuristic_match_still_works_without_operation_links(
        self,
        operation_range: OperationRange,
        historic_operations: list[HistoricOperation],
    ) -> None:
        """Test that heuristic matching still works when no operation links exist."""
        matcher = OperationMatcher(
            operation_range, approximation_date_range=timedelta()
        )
        # This should behave exactly like before - using heuristic matching
        assert set(matcher.matches(historic_operations)) == {
            historic_operations[i] for i in (0, 1, 3, 5)
        }

    def test_match_heuristic_method(self, operation_range: OperationRange) -> None:
        """Test that match_heuristic ignores operation links."""
        # Operation that doesn't match heuristically
        operation = HistoricOperation(
            unique_id=104,
            description="Non matching",
            amount=Amount(500.0),
            category=Category.OTHER,
            date=datetime(2023, 6, 15),
        )

        # Even with link, match_heuristic should return False
        matcher = OperationMatcher(
            operation_range,
            operation_links={104: datetime(2023, 1, 1)},
        )
        assert not matcher.match_heuristic(operation)
        assert matcher.match(operation)  # But match() returns True due to link


class TestComputeMatchScore:
    """Tests for the compute_match_score function."""

    def test_perfect_match_score(self) -> None:
        """Test that a perfect match returns high score (minus description if no hints)."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        # Perfect match on amount, date, category (no description hints)
        # Should get 40 + 30 + 20 = 90 (no description points without hints)
        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        assert score == 90.0

    def test_perfect_match_with_description_hints(self) -> None:
        """Test that matching description hints adds to score."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="GROCERIES STORE ABC",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        matcher = OperationMatcher(
            op_range,
            description_hints={"GROCERIES", "ABC"},
        )

        # Perfect match including description
        score = compute_match_score(operation, op_range, datetime(2023, 1, 15), matcher)
        assert score == 100.0

    def test_category_mismatch_reduces_score(self) -> None:
        """Test that wrong category reduces score by 20 points."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(100.0),
            category=Category.OTHER,  # Wrong category
            date=datetime(2023, 1, 15),
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        # Should get 40 (amount) + 30 (date) + 0 (category) = 70
        assert score == 70.0

    def test_amount_tolerance_within_range(self) -> None:
        """Test that amount within tolerance gets full points."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # 5% tolerance means 95-105 should get full amount score
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(105.0),  # At tolerance boundary
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        assert score == 90.0  # Full score (40 + 30 + 20)

    def test_amount_beyond_tolerance_reduces_score(self) -> None:
        """Test that amount beyond tolerance reduces score."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # 20% difference is 15% beyond 5% tolerance
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(120.0),  # 20% off
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 15))
        # Amount score: 40 * (1 - 0.15) = 34
        # Date score: 30
        # Category score: 20
        assert 80.0 < score < 90.0

    def test_date_beyond_tolerance_reduces_score(self) -> None:
        """Test that date beyond tolerance reduces score."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        # 20 days from iteration is 15 days beyond 5 day tolerance
        operation = HistoricOperation(
            unique_id=1,
            description="Test",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 21),  # 20 days from iteration
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 1))
        # Amount score: 40
        # Date score: 30 * (1 - 15/30) = 15
        # Category score: 20
        assert score == 75.0

    def test_complete_mismatch_low_score(self) -> None:
        """Test that a complete mismatch returns low score."""
        from budget_forecaster.operation_range.operation_matcher import (
            compute_match_score,
        )

        op_range = OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        operation = HistoricOperation(
            unique_id=1,
            description="Completely different",
            amount=Amount(1000.0),  # 10x different
            category=Category.OTHER,
            date=datetime(2023, 6, 15),  # 165+ days away
        )

        score = compute_match_score(operation, op_range, datetime(2023, 1, 1))
        # Amount: way beyond tolerance -> 0
        # Date: way beyond tolerance -> 0
        # Category: mismatch -> 0
        assert score == 0.0
