"""Module with tests for the OperationMatcher class."""
# pylint: disable=too-many-lines
from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    SingleDay,
)
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.operation_range import OperationRange
from budget_forecaster.services.operation.operation_matcher import OperationMatcher


@pytest.fixture
def historic_operations() -> list[HistoricOperation]:
    """Return a list of historic operations."""
    return [
        HistoricOperation(
            unique_id=1,
            description="Operation 1",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(105.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 20),
        ),
        HistoricOperation(
            unique_id=3,
            description="Operation 3",
            amount=Amount(105.1),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 20),
        ),
        HistoricOperation(
            unique_id=4,
            description="Operation 4",
            amount=Amount(95.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 21),
        ),
        HistoricOperation(
            unique_id=5,
            description="Operation 5",
            amount=Amount(94.9),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 26),
        ),
        HistoricOperation(
            unique_id=6,
            description="Operation 6",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 1),
        ),
        HistoricOperation(
            unique_id=7,
            description="Operation 7",
            amount=Amount(100.0),
            category=Category.OTHER,
            operation_date=date(2023, 1, 1),
        ),
        HistoricOperation(
            unique_id=8,
            description="Operation 8",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 2, 1),
        ),
        HistoricOperation(
            unique_id=9,
            description="Operation 9",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 2, 6),
        ),
    ]


@pytest.fixture
def daily_operation_range() -> OperationRange:
    """Return a daily operation range."""
    return OperationRange(
        "Test Daily Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        SingleDay(date(2023, 1, 1)),
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
                operation_date=date(2023, 1, 1),
            ),
            HistoricOperation(
                unique_id=2,
                description="Test Operation 2",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 1, 1),
            ),
            HistoricOperation(
                unique_id=3,
                description="Other Operation",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 1, 1),
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
            matcher.latest_matching_operations(date(2023, 1, 1), historic_operations)
        ) == {historic_operations[5]}
        assert set(
            matcher.latest_matching_operations(date(2023, 1, 6), historic_operations)
        ) == {historic_operations[5]}
        assert (
            set(
                matcher.latest_matching_operations(
                    date(2023, 12, 31), historic_operations
                )
            )
            == set()
        )
        assert (
            set(
                matcher.latest_matching_operations(
                    date(2023, 1, 7), historic_operations
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
            set(matcher.late_date_ranges(date(2023, 12, 31), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_date_ranges(date(2023, 1, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_date_ranges(date(2023, 1, 2), ())) == {
            SingleDay(date(2023, 1, 1))
        }
        assert set(matcher.late_date_ranges(date(2023, 1, 6), ())) == {
            SingleDay(date(2023, 1, 1))
        }
        # operation is already executed
        assert (
            set(matcher.late_date_ranges(date(2023, 1, 6), historic_operations))
            == set()
        )
        late_operation_executed = HistoricOperation(
            unique_id=10,
            description="Operation 10",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 3),
        )
        # operation was late but executed at current date
        assert (
            set(matcher.late_date_ranges(date(2023, 1, 6), (late_operation_executed,)))
            == set()
        )
        anticipated_operation_executed = HistoricOperation(
            unique_id=11,
            description="Operation 11",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2022, 12, 30),
        )
        # operation was already executed at current date
        assert (
            set(
                matcher.late_date_ranges(
                    date(2023, 1, 6), (anticipated_operation_executed,)
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
            operation_date=date(2022, 12, 27),
        )
        historic_operations.append(anticipated_operation)
        # the expected operation is a future operation and is already executed
        assert set(
            matcher.anticipated_date_ranges(date(2022, 12, 27), historic_operations)
        ) == {(SingleDay(date(2023, 1, 1)), anticipated_operation)}
        assert set(
            matcher.anticipated_date_ranges(date(2022, 12, 31), historic_operations)
        ) == {(SingleDay(date(2023, 1, 1)), anticipated_operation)}
        # the expected operation is not a future operation
        assert (
            set(matcher.anticipated_date_ranges(date(2023, 1, 1), historic_operations))
            == set()
        )
        # this operation has not happened yet
        assert (
            set(
                matcher.anticipated_date_ranges(date(2022, 12, 23), historic_operations)
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
        DateRange(date(2023, 1, 1), relativedelta(months=1)),
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
            matcher.latest_matching_operations(date(2023, 1, 6), historic_operations)
        ) == {historic_operations[5]}
        assert set(
            matcher.latest_matching_operations(date(2023, 1, 21), historic_operations)
        ) == {historic_operations[i] for i in (1, 3)}
        assert set(
            matcher.latest_matching_operations(date(2023, 2, 3), historic_operations)
        ) == {historic_operations[7]}
        assert (
            set(
                matcher.latest_matching_operations(
                    date(2023, 2, 7), historic_operations
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
            set(matcher.late_date_ranges(date(2023, 12, 31), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_date_ranges(date(2023, 2, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_date_ranges(date(2023, 1, 2), ())) == {
            DateRange(date(2023, 1, 1), relativedelta(months=1))
        }
        assert set(matcher.late_date_ranges(date(2023, 1, 6), ())) == {
            DateRange(date(2023, 1, 1), relativedelta(months=1))
        }
        # operation is already executed
        assert (
            set(matcher.late_date_ranges(date(2023, 1, 6), historic_operations))
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
                operation_date=date(2022, 12, 27),
            )
        )
        # add flexibility on the date range
        matcher = OperationMatcher(
            operation_range, approximation_date_range=timedelta(days=5)
        )
        # operation 12 was executed close enough from next time range
        assert set(
            matcher.anticipated_date_ranges(date(2022, 12, 27), historic_operations)
        ) == {
            (
                DateRange(date(2023, 1, 1), relativedelta(months=1)),
                historic_operations[-1],
            )
        }
        # no future time range at this date
        assert (
            set(matcher.anticipated_date_ranges(date(2023, 1, 1), historic_operations))
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
        RecurringDateRange(
            daily_operation_range.date_range,
            relativedelta(months=1),
            date(2023, 12, 31),
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
            matcher.latest_matching_operations(date(2023, 1, 6), historic_operations)
        ) == {historic_operations[5]}
        assert (
            set(
                matcher.latest_matching_operations(
                    date(2023, 1, 21), historic_operations
                )
            )
            == set()
        )
        assert set(
            matcher.latest_matching_operations(date(2023, 2, 3), historic_operations)
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
            set(matcher.late_date_ranges(date(2023, 12, 31), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_date_ranges(date(2023, 2, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_date_ranges(date(2023, 1, 2), ())) == {
            SingleDay(date(2023, 1, 1))
        }
        assert set(matcher.late_date_ranges(date(2023, 1, 6), ())) == {
            SingleDay(date(2023, 1, 1))
        }
        # operation is already executed
        assert (
            set(matcher.late_date_ranges(date(2023, 1, 6), historic_operations))
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
                operation_date=date(2023, 1, 27),
            )
        )
        matcher = OperationMatcher(periodic_daily_operation_range)
        assert set(
            matcher.anticipated_date_ranges(date(2023, 1, 27), historic_operations)
        ) == {(SingleDay(date(2023, 2, 1)), historic_operations[-1])}
        assert (
            set(matcher.anticipated_date_ranges(date(2023, 1, 26), historic_operations))
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
        RecurringDateRange(
            operation_range.date_range, relativedelta(months=1), date(2023, 12, 31)
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
            matcher.latest_matching_operations(date(2023, 1, 6), historic_operations)
        ) == {historic_operations[5]}
        assert set(
            matcher.latest_matching_operations(date(2023, 1, 21), historic_operations)
        ) == {historic_operations[i] for i in (1, 3)}
        assert set(
            matcher.latest_matching_operations(date(2023, 2, 3), historic_operations)
        ) == {historic_operations[7]}
        assert set(
            matcher.latest_matching_operations(date(2023, 2, 7), historic_operations)
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
            set(matcher.late_date_ranges(date(2023, 1, 1), historic_operations))
            == set()
        )
        # time range is too late
        assert (
            set(matcher.late_date_ranges(date(2023, 2, 7), historic_operations))
            == set()
        )
        # operation is not executed and time range is late
        assert set(matcher.late_date_ranges(date(2023, 1, 2), ())) == {
            DateRange(date(2023, 1, 1), relativedelta(months=1))
        }
        assert set(matcher.late_date_ranges(date(2023, 1, 6), ())) == {
            DateRange(date(2023, 1, 1), relativedelta(months=1))
        }
        # operation is already executed
        assert (
            set(matcher.late_date_ranges(date(2023, 1, 6), historic_operations))
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
                operation_date=date(2023, 1, 27),
            )
        )

        assert set(
            matcher.anticipated_date_ranges(date(2023, 1, 27), historic_operations)
        ) == {
            (
                DateRange(date(2023, 2, 1), relativedelta(months=1)),
                historic_operations[-1],
            )
        }
        assert (
            set(matcher.anticipated_date_ranges(date(2023, 1, 26), historic_operations))
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
            operation_date=date(2023, 6, 15),  # Wrong date
        )

        # Without link, should not match
        matcher_no_link = OperationMatcher(operation_range)
        assert not matcher_no_link.match(non_matching_operation)

        # With link, should match regardless of heuristics
        link = OperationLink(
            operation_unique_id=100,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=date(2023, 1, 1),
        )
        matcher_with_link = OperationMatcher(
            operation_range,
            operation_links=(link,),
        )
        assert matcher_with_link.match(non_matching_operation)

    def test_invalid_iteration_date_raises_error(
        self, operation_range: OperationRange
    ) -> None:
        """Test that invalid iteration dates raise ValueError."""
        # Date that is not a valid iteration of the operation range
        invalid_date = date(2023, 1, 15)  # operation_range starts on Jan 1

        # Should raise in constructor
        invalid_link = OperationLink(
            operation_unique_id=100,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=invalid_date,
        )
        with pytest.raises(ValueError, match="Invalid iteration date"):
            OperationMatcher(
                operation_range,
                operation_links=(invalid_link,),
            )

    def test_get_iteration_for_operation(self, operation_range: OperationRange) -> None:
        """Test getting the iteration date for a linked operation."""
        operation = HistoricOperation(
            unique_id=102,
            description="Test operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 15),
        )

        iteration_date = date(2023, 1, 1)
        link = OperationLink(
            operation_unique_id=102,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=iteration_date,
        )
        matcher = OperationMatcher(
            operation_range,
            operation_links=(link,),
        )

        assert matcher.get_iteration_for_operation(operation) == iteration_date

        # Non-linked operation returns None
        other_operation = HistoricOperation(
            unique_id=103,
            description="Other operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 15),
        )
        assert matcher.get_iteration_for_operation(other_operation) is None

    def test_operation_links_preserved_in_replace(
        self, operation_range: OperationRange
    ) -> None:
        """Test operation links behavior with replace().

        Links are preserved when operation_range stays the same,
        but cleared when operation_range changes (because links reference
        iterations of the old operation range).
        """
        link = OperationLink(
            operation_unique_id=100,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=date(2023, 1, 1),
        )
        matcher = OperationMatcher(
            operation_range,
            operation_links=(link,),
        )

        # When operation_range is not replaced, links should be preserved
        same_range_matcher = matcher.replace()
        assert len(same_range_matcher.operation_links) == 1
        assert same_range_matcher.operation_links[0].operation_unique_id == 100

        # When operation_range is replaced, links should be cleared
        new_operation_range = OperationRange(
            "New Test Operation",
            Amount(200, "EUR"),
            Category.GROCERIES,
            DateRange(date(2023, 2, 1), relativedelta(months=1)),
        )
        new_matcher = matcher.replace(operation_range=new_operation_range)

        # Operation links should be cleared because they referenced the old range
        assert not new_matcher.operation_links

    def test_operation_links_property_returns_tuple(
        self, operation_range: OperationRange
    ) -> None:
        """Test that operation_links property returns the original immutable tuple."""
        link = OperationLink(
            operation_unique_id=100,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=date(2023, 1, 1),
        )
        matcher = OperationMatcher(operation_range, operation_links=(link,))

        # Should return the same tuple (tuples are immutable, no need to copy)
        assert matcher.operation_links == (link,)
        assert len(matcher.operation_links) == 1

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

    def test_link_on_specific_iteration_of_periodic_range(self) -> None:
        """Test that a link targets a specific iteration of a periodic operation range.

        Scenario: Monthly rent payment (periodic), operation linked to February iteration.
        The operation should match via the link, and get_iteration_for_operation should
        return the specific February date, not just any iteration.
        """
        # Create a periodic operation range: monthly rent starting Jan 1st
        periodic_range = OperationRange(
            "Monthly Rent",
            Amount(800, "EUR"),
            Category.RENT,
            RecurringDateRange(
                SingleDay(date(2023, 1, 1)),
                relativedelta(months=1),
                date(2023, 12, 31),
            ),
        )

        # Operation that arrived late (Feb 3rd instead of Feb 1st) with slightly different amount
        late_rent_operation = HistoricOperation(
            unique_id=200,
            description="TRANSFER LANDLORD",
            amount=Amount(800.0),
            category=Category.RENT,
            operation_date=date(2023, 2, 3),  # 2 days late
        )

        # Link to the February iteration specifically
        february_iteration = date(2023, 2, 1)
        link = OperationLink(
            operation_unique_id=200,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=february_iteration,
        )
        matcher = OperationMatcher(
            periodic_range,
            operation_links=(link,),
        )

        # Should match via link
        assert matcher.match(late_rent_operation)
        assert matcher.is_linked(late_rent_operation)

        # Should return the specific iteration date
        assert (
            matcher.get_iteration_for_operation(late_rent_operation)
            == february_iteration
        )

    def test_link_overrides_heuristic_on_wrong_iteration(self) -> None:
        """Test that a link can force match to a different iteration than heuristics would choose.

        Scenario: Operation date is closest to March iteration, but user linked it to February.
        The link should take priority.
        """
        periodic_range = OperationRange(
            "Monthly Subscription",
            Amount(50, "EUR"),
            Category.ENTERTAINMENT,
            RecurringDateRange(
                SingleDay(date(2023, 1, 15)),
                relativedelta(months=1),
                date(2023, 12, 31),
            ),
        )

        # Operation on Feb 28th - closer to March 15th than Feb 15th
        operation = HistoricOperation(
            unique_id=201,
            description="NETFLIX",
            amount=Amount(50.0),
            category=Category.ENTERTAINMENT,
            operation_date=date(2023, 2, 28),  # Closer to Mar 15 than Feb 15
        )

        # User explicitly links to February iteration
        february_iteration = date(2023, 2, 15)
        link = OperationLink(
            operation_unique_id=201,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=february_iteration,
        )
        matcher = OperationMatcher(
            periodic_range,
            operation_links=(link,),
        )

        # Should match and return the user-specified iteration
        assert matcher.match(operation)
        assert matcher.get_iteration_for_operation(operation) == february_iteration

    def test_multiple_operations_linked_to_different_iterations(self) -> None:
        """Test multiple operations linked to different iterations of the same periodic range."""
        periodic_range = OperationRange(
            "Weekly Groceries",
            Amount(100, "EUR"),
            Category.GROCERIES,
            RecurringDateRange(
                SingleDay(date(2023, 1, 1)),
                relativedelta(weeks=1),
                date(2023, 12, 31),
            ),
        )

        # Three operations linked to different weekly iterations
        op_week1 = HistoricOperation(
            unique_id=301,
            description="SUPERMARKET",
            amount=Amount(95.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 2),
        )
        op_week2 = HistoricOperation(
            unique_id=302,
            description="SUPERMARKET",
            amount=Amount(110.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 10),
        )
        op_week3 = HistoricOperation(
            unique_id=303,
            description="SUPERMARKET",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 14),
        )

        links = (
            OperationLink(
                operation_unique_id=301,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 1),  # Week 1
            ),
            OperationLink(
                operation_unique_id=302,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 8),  # Week 2
            ),
            OperationLink(
                operation_unique_id=303,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2023, 1, 15),  # Week 3
            ),
        )
        matcher = OperationMatcher(
            periodic_range,
            operation_links=links,
        )

        # All should match
        assert matcher.match(op_week1)
        assert matcher.match(op_week2)
        assert matcher.match(op_week3)

        # Each should return its specific iteration
        assert matcher.get_iteration_for_operation(op_week1) == date(2023, 1, 1)
        assert matcher.get_iteration_for_operation(op_week2) == date(2023, 1, 8)
        assert matcher.get_iteration_for_operation(op_week3) == date(2023, 1, 15)


class TestOperationMatcherReplaceErrors:
    """Tests for errors in OperationMatcher.replace()."""

    def test_replace_invalid_operation_range(
        self, operation_range: OperationRange
    ) -> None:
        """Test replace() raises TypeError for invalid operation_range."""
        matcher = OperationMatcher(operation_range)
        with pytest.raises(TypeError, match="operation_range must be OperationRange"):
            matcher.replace(operation_range="invalid")

    def test_replace_valid_operation_range(
        self, operation_range: OperationRange
    ) -> None:
        """Test replace() works with valid operation_range."""
        matcher = OperationMatcher(operation_range)
        new_range = OperationRange(
            "New Operation",
            Amount(200, "EUR"),
            Category.OTHER,
            DateRange(date(2023, 2, 1), relativedelta(months=1)),
        )
        new_matcher = matcher.replace(operation_range=new_range)
        assert new_matcher.operation_range == new_range
