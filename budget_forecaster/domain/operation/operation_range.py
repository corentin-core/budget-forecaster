"""Module for operation ranges."""
import abc
from datetime import date
from functools import total_ordering
from typing import Any

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRangeInterface
from budget_forecaster.core.types import Category


@total_ordering
class OperationRangeInterface(abc.ABC):
    """
    An operation range is an amount of money allocated to
    an operation category and over a given date range.
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
    def date_range(self) -> DateRangeInterface:
        """The date range of the operation."""

    @abc.abstractmethod
    def amount_on_period(self, start_date: date, end_date: date) -> float:
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
            and self.date_range == other.date_range
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, OperationRangeInterface):
            return NotImplemented
        return self.date_range < other.date_range

    def __hash__(self) -> int:
        return hash(
            (
                self.description,
                self.amount,
                self.currency,
                self.category,
                self.date_range,
            )
        )


class OperationRange(OperationRangeInterface):
    """Base class for operation ranges."""

    def __init__(
        self,
        description: str,
        amount: Amount,
        category: Category,
        date_range: DateRangeInterface,
    ) -> None:
        self._description = description
        self._amount = amount
        self._category = category
        self._date_range = date_range

    @property
    def description(self) -> str:
        return self._description

    @property
    def amount(self) -> float:
        return self._amount.value

    @property
    def currency(self) -> str:
        return self._amount.currency

    @property
    def category(self) -> Category:
        return self._category

    @property
    def date_range(self) -> DateRangeInterface:
        return self._date_range

    def amount_on_period(self, start_date: date, end_date: date) -> float:
        if start_date > end_date:
            raise ValueError(
                f"start_date must be <= end_date, got {start_date} > {end_date}"
            )

        if self.date_range.is_expired(start_date) or self.date_range.is_future(
            end_date
        ):
            return 0.0

        amount = 0.0
        for dr in self.date_range.iterate_over_date_ranges():
            if dr.is_expired(start_date):
                continue

            if dr.is_future(end_date):
                break

            if dr.start_date >= start_date and dr.last_date <= end_date:
                # we have a complete period
                amount += self.amount
                continue

            amount_per_day = self.amount / dr.total_duration.days
            # incomplete period, two cases:
            # 1. dr.start_date < start_date
            # 2. dr.last_date > end_date
            days_in_period = (
                (dr.last_date - start_date).days + 1
                if dr.start_date < start_date
                else (end_date - dr.start_date).days + 1
            )
            amount += amount_per_day * days_in_period

        return amount

    def replace(self, **kwargs: Any) -> "OperationRange":
        new_description = kwargs.get("description", self._description)
        if not isinstance(new_description, str):
            raise TypeError(f"description must be str, got {type(new_description)}")
        new_amount = kwargs.get("amount", self._amount)
        if not isinstance(new_amount, Amount):
            raise TypeError(f"amount must be Amount, got {type(new_amount)}")
        new_category = kwargs.get("category", self._category)
        if not isinstance(new_category, Category):
            raise TypeError(f"category must be Category, got {type(new_category)}")
        new_date_range = kwargs.get("date_range", self._date_range)
        if not isinstance(new_date_range, DateRangeInterface):
            raise TypeError(
                f"date_range must be DateRangeInterface, got {type(new_date_range)}"
            )
        return OperationRange(
            description=new_description,
            amount=new_amount,
            category=new_category,
            date_range=new_date_range,
        )

    def __repr__(self) -> str:
        return (
            f"{self.date_range} - {self.category} - {self.description} "
            f"- {self.amount} {self.currency}"
        )
