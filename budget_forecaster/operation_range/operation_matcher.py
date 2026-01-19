"""Match operations to operation ranges."""
from datetime import datetime, timedelta
from typing import Any, Iterable, Iterator

from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import OperationLink
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.time_range import TimeRangeInterface
from budget_forecaster.types import IterationDate


class OperationMatcher:  # pylint: disable=too-many-public-methods
    """Check if an operation matches an operation range."""

    def __init__(
        self,
        operation_range: OperationRange,
        description_hints: set[str] | None = None,
        approximation_date_range: timedelta = timedelta(days=5),
        approximation_amount_ratio: float = 0.05,
        operation_links: tuple[OperationLink, ...] = (),
    ):
        """Initialize the matcher.

        Args:
            operation_range: The operation range to match against.
            description_hints: Keywords that must appear in operation descriptions.
            approximation_date_range: Tolerance for date matching.
            approximation_amount_ratio: Tolerance ratio for amount matching.
            operation_links: Tuple of OperationLinks for this target.
                Links take priority over heuristic matching.
        """
        self.__operation_range = operation_range
        self.__description_hints = description_hints or set()
        self.__approximation_date_range = approximation_date_range
        self.__approximation_amount_ratio = approximation_amount_ratio
        self.__operation_links = operation_links

        # Validate operation links
        for link in operation_links:
            self.__validate_iteration_date(link.iteration_date)

    @property
    def operation_range(self) -> OperationRange:
        """The operation range to match."""
        return self.__operation_range

    @property
    def description_hints(self) -> set[str]:
        """The description hints to match."""
        return self.__description_hints

    @property
    def approximation_date_range(self) -> timedelta:
        """The approximation date range to match."""
        return self.__approximation_date_range

    @property
    def approximation_amount_ratio(self) -> float:
        """The approximation amount ratio to match."""
        return self.__approximation_amount_ratio

    @property
    def operation_links(self) -> tuple[OperationLink, ...]:
        """Tuple of OperationLinks for this target."""
        return self.__operation_links

    def __validate_iteration_date(self, iteration_date: IterationDate) -> None:
        """Validate that iteration_date is a valid iteration of the operation range.

        Args:
            iteration_date: The date to validate.

        Raises:
            ValueError: If the date is not a valid iteration.
        """
        time_range = self.__operation_range.time_range.current_time_range(
            iteration_date
        )
        if time_range is None or time_range.initial_date != iteration_date:
            raise ValueError(
                f"Invalid iteration date {iteration_date} for operation range "
                f"'{self.__operation_range.description}'"
            )

    def is_linked(self, operation: HistoricOperation) -> bool:
        """Check if operation has a link to this matcher's operation_range.

        Args:
            operation: The historic operation to check.

        Returns:
            True if the operation has a link, False otherwise.
        """
        return any(
            link.operation_unique_id == operation.unique_id
            for link in self.__operation_links
        )

    def get_iteration_for_operation(
        self, operation: HistoricOperation
    ) -> IterationDate | None:
        """Get the specific iteration date this operation is linked to.

        For linked operations, returns the stored iteration date.
        For heuristic matches, returns None (caller should use date proximity).

        Args:
            operation: The historic operation to check.

        Returns:
            The iteration date if linked, None otherwise.
        """
        for link in self.__operation_links:
            if link.operation_unique_id == operation.unique_id:
                return link.iteration_date
        return None

    def update_params(
        self,
        description_hints: set[str] | None = None,
        approximation_date_range: timedelta = timedelta(days=5),
        approximation_amount_ratio: float = 0.05,
    ) -> "OperationMatcher":
        """Update the params of the matcher."""
        self.__description_hints = description_hints or self.description_hints
        self.__approximation_date_range = approximation_date_range
        self.__approximation_amount_ratio = approximation_amount_ratio
        return self

    def __out_of_range(self, operation: HistoricOperation) -> bool:
        initial_date = self.operation_range.time_range.initial_date
        last_date = self.operation_range.time_range.last_date
        return (
            operation.date < initial_date - self.approximation_date_range
            or operation.date
            > last_date
            + (
                self.approximation_date_range
                if last_date < datetime.max
                else timedelta(0)
            )
        )

    def match_description(self, operation: HistoricOperation) -> bool:
        """Check if the description of the operation matches the given hints."""
        if self.description_hints:
            return all(hint in operation.description for hint in self.description_hints)
        return False

    def match_amount(self, operation: HistoricOperation) -> bool:
        """Check if the amount of the operation is close to the amount of the operation range."""
        return (
            abs(operation.amount - self.operation_range.amount)
            <= abs(self.operation_range.amount) * self.approximation_amount_ratio
        )

    def match_category(self, operation: HistoricOperation) -> bool:
        """Check if the category of the operation matches the category of the operation range."""
        return operation.category == self.operation_range.category

    def match_date_range(self, operation: HistoricOperation) -> bool:
        """Check if the date of the operation is within the time range of the operation range."""
        return self.operation_range.time_range.is_within(
            operation.date,
            approx_before=self.approximation_date_range,
            approx_after=self.approximation_date_range,
        )

    def __match_heuristic(self, operation: HistoricOperation) -> bool:
        """Check if the operation matches using heuristic rules only.

        This method applies the original matching logic without considering
        operation links.

        Args:
            operation: The historic operation to check.

        Returns:
            True if the operation matches heuristically, False otherwise.
        """
        return (
            not self.__out_of_range(operation)
            and (not self.description_hints or self.match_description(operation))
            and self.match_amount(operation)
            and self.match_category(operation)
            and self.match_date_range(operation)
        )

    def match(self, operation: HistoricOperation) -> bool:
        """Check if the operation matches the planned operation.

        Operation links take priority over heuristic matching. If an operation
        has a link to this matcher's operation range, it will match
        regardless of heuristic criteria.

        Args:
            operation: The historic operation to check.

        Returns:
            True if the operation matches (via link or heuristically).
        """
        # Operation links take priority
        if self.is_linked(operation):
            return True

        # Fall back to heuristic matching
        return self.__match_heuristic(operation)

    def matches(
        self, operations: Iterable[HistoricOperation]
    ) -> Iterator[HistoricOperation]:
        """Get operations matching the operation range"""
        for operation in operations:
            if self.match(operation):
                yield operation

    def latest_matching_operations(
        self, current_date: datetime, operations: Iterable[HistoricOperation]
    ) -> Iterator[HistoricOperation]:
        """Returns the operations matching the last time range and close to current date."""
        for operation in self.matches(operations):
            if operation.time_range.is_within(
                current_date, approx_after=self.approximation_date_range
            ):
                yield operation

    def late_time_ranges(
        self, current_date: datetime, operations: Iterable[HistoricOperation]
    ) -> Iterator[TimeRangeInterface]:
        """Returns the time ranges which are late and close to current date."""
        not_assigned_operations = {
            op.unique_id: op for op in operations if self.match(op)
        }
        for time_range in self.operation_range.time_range.iterate_over_time_ranges(
            current_date - self.approximation_date_range
        ):
            if time_range.is_future(current_date):
                return
            if not time_range.is_within(
                current_date, approx_after=self.approximation_date_range
            ):
                continue
            for operation in not_assigned_operations.values():
                if time_range.is_within(
                    operation.date,
                    approx_before=self.approximation_date_range,
                    approx_after=self.approximation_date_range,
                ):
                    # the time range was executed
                    not_assigned_operations.pop(operation.unique_id)
                    break
            else:
                yield time_range

    def anticipated_time_ranges(
        self, current_date: datetime, operations: Iterable[HistoricOperation]
    ) -> Iterator[tuple[TimeRangeInterface, HistoricOperation]]:
        """Returns the time ranges which are anticipated and close to current date."""
        not_assigned_operations = {
            op.unique_id: op
            for op in self.latest_matching_operations(current_date, operations)
        }
        for time_range in self.operation_range.time_range.iterate_over_time_ranges(
            current_date - self.approximation_date_range
        ):
            if not time_range.is_future(current_date):
                continue
            if not time_range.is_within(
                current_date, approx_before=self.approximation_date_range
            ):
                # the time range is too far in the future
                return
            for operation in not_assigned_operations.values():
                if time_range.is_within(
                    operation.date, approx_before=self.approximation_date_range
                ):
                    # the time range was executed with anticipation
                    not_assigned_operations.pop(operation.unique_id)
                    yield time_range, operation
                    break

    def replace(self, **kwargs: Any) -> "OperationMatcher":
        """Return a new instance of the operation matcher with the given parameters replaced.

        Note: If operation_range is replaced, operation_links are cleared because
        the existing links reference iterations of the old operation range.
        """
        new_operation_range = kwargs.get("operation_range", self.operation_range)
        assert isinstance(new_operation_range, OperationRange)

        # Clear links if operation_range changes (links are tied to specific iterations)
        preserve_links = new_operation_range is self.operation_range

        return OperationMatcher(
            operation_range=new_operation_range,
            description_hints=self.description_hints,
            approximation_date_range=self.approximation_date_range,
            approximation_amount_ratio=self.approximation_amount_ratio,
            operation_links=self.__operation_links if preserve_links else (),
        )
