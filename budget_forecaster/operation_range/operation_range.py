"""Module for operation ranges."""
import abc
from datetime import datetime
from functools import total_ordering
from typing import Any

from budget_forecaster.amount import Amount
from budget_forecaster.time_range import TimeRangeInterface
from budget_forecaster.types import Category


@total_ordering
class OperationRangeInterface(abc.ABC):
    """
    An operation range is an amount of money allocated to
    an operation category and over a given time range.
    """

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """The description of the operation."""

    @property
    @abc.abstractmethod
    def amount(self) -> float:
        """The amount of the operation."""

    @property
    @abc.abstractmethod
    def currency(self) -> str:
        """The currency of the operation."""

    @property
    @abc.abstractmethod
    def category(self) -> Category:
        """The category of the operation."""

    @property
    @abc.abstractmethod
    def time_range(self) -> TimeRangeInterface:
        """The time range of the operation."""

    @abc.abstractmethod
    def amount_on_period(self, start_date: datetime, end_date: datetime) -> float:
        """Return the amount of the operation on the period."""

    @abc.abstractmethod
    def replace(self, **kwargs: Any) -> "OperationRangeInterface":
        """Return a new instance of the operation range with the given parameters replaced."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OperationRangeInterface):
            return NotImplemented
        return (
            self.description == other.description
            and self.amount == other.amount
            and self.currency == other.currency
            and self.category == other.category
            and self.time_range == other.time_range
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, OperationRangeInterface):
            return NotImplemented
        return self.time_range < other.time_range

    def __hash__(self) -> int:
        return hash(
            (
                self.description,
                self.amount,
                self.currency,
                self.category,
                self.time_range,
            )
        )


class OperationRange(OperationRangeInterface):
    """Base class for operation ranges."""

    def __init__(
        self,
        description: str,
        amount: Amount,
        category: Category,
        time_range: TimeRangeInterface,
    ) -> None:
        self.__description = description
        self.__amount = amount
        self.__category = category
        self.__time_range = time_range

    @property
    def description(self) -> str:
        return self.__description

    @property
    def amount(self) -> float:
        return self.__amount.value

    @property
    def currency(self) -> str:
        return self.__amount.currency

    @property
    def category(self) -> Category:
        return self.__category

    @property
    def time_range(self) -> TimeRangeInterface:
        return self.__time_range

    def amount_on_period(self, start_date: datetime, end_date: datetime) -> float:
        assert (
            start_date <= end_date
        ), f"Start date should be before end date, got {start_date} - {end_date}"

        if self.time_range.is_expired(start_date) or self.time_range.is_future(
            end_date
        ):
            return 0.0

        amount = 0.0
        for time_range in self.time_range.iterate_over_time_ranges():
            if time_range.is_expired(start_date):
                continue

            if time_range.is_future(end_date):
                break

            if (
                time_range.initial_date >= start_date
                and time_range.last_date <= end_date
            ):
                # we have a complete period
                amount += self.amount
                continue

            amount_per_day = self.amount / time_range.duration.days
            # incomplete period, two cases:
            # 1. time_range.initial_date < start_date
            # 2. time_range.last_date > end_date
            days_in_period = (
                (time_range.last_date - start_date).days + 1
                if time_range.initial_date < start_date
                else (end_date - time_range.initial_date).days + 1
            )
            amount += amount_per_day * days_in_period

        return amount

    def replace(self, **kwargs: Any) -> "OperationRange":
        new_description = kwargs.get("description", self.__description)
        assert isinstance(new_description, str), "description should be a string"
        new_amount = kwargs.get("amount", self.__amount)
        assert isinstance(new_amount, Amount), "amount should be an Amount"
        new_category = kwargs.get("category", self.__category)
        assert isinstance(new_category, Category), "category should be a Category"
        new_time_range = kwargs.get("time_range", self.__time_range)
        assert isinstance(
            new_time_range, TimeRangeInterface
        ), "time_range should be a TimeRangeInterface"
        return OperationRange(
            description=new_description,
            amount=new_amount,
            category=new_category,
            time_range=new_time_range,
        )

    def __repr__(self) -> str:
        return (
            f"{self.time_range} - {self.category} - {self.description} "
            f"- {self.amount} {self.currency}"
        )
