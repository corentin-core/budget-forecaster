"""Date range module."""
import abc
import itertools
from datetime import date, timedelta
from functools import total_ordering
from typing import Any, Iterator, Optional

from dateutil.relativedelta import relativedelta


@total_ordering
class DateRangeInterface(abc.ABC):
    """
    A date range is a period defined by a start date and a duration.
    It can be repeated at a given period.
    """

    @property
    @abc.abstractmethod
    def start_date(self) -> date:
        """Return the start date of the date range."""

    @property
    @abc.abstractmethod
    def last_date(self) -> date:
        """Return the last date of the date range."""

    @property
    @abc.abstractmethod
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""

    @property
    @abc.abstractmethod
    def duration(self) -> relativedelta:
        """Return the duration as a relativedelta."""

    @abc.abstractmethod
    def is_expired(self, target_date: date) -> bool:
        """Check if the date range is expired at the given date."""

    @abc.abstractmethod
    def is_future(self, target_date: date) -> bool:
        """Check if the date range is in the future at the given date."""

    @abc.abstractmethod
    def is_within(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        """Check if the date is within the date range."""

    @abc.abstractmethod
    def iterate_over_date_ranges(
        self, from_date: date | None = None
    ) -> Iterator["DateRangeInterface"]:
        """Iterate over the date ranges."""

    @abc.abstractmethod
    def current_date_range(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> Optional["DateRangeInterface"]:
        """Get the date range that is active at the given date."""

    @abc.abstractmethod
    def next_date_range(self, target_date: date) -> Optional["DateRangeInterface"]:
        """Get the next date range after the given date."""

    @abc.abstractmethod
    def last_date_range(self, target_date: date) -> Optional["DateRangeInterface"]:
        """Get the previous date range before the given date."""

    @abc.abstractmethod
    def replace(self, **kwargs: Any) -> "DateRangeInterface":
        """Return a new instance of the date range with the given parameters replaced."""

    @abc.abstractmethod
    def __eq__(self, other: object) -> bool:
        """Check if two date ranges are equal."""

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, DateRangeInterface):
            return NotImplemented
        return (self.start_date, self.last_date) < (
            other.start_date,
            other.last_date,
        )

    @abc.abstractmethod
    def __hash__(self) -> int:
        """Return the hash of the date range."""


class DateRange(DateRangeInterface):
    """A non-recurring date range."""

    def __init__(
        self,
        start_date: date,
        duration: relativedelta,
    ) -> None:
        self._start_date = start_date
        self._duration = duration

    @property
    def start_date(self) -> date:
        return self._start_date

    @property
    def last_date(self) -> date:
        return self._start_date + self._duration - timedelta(days=1)

    @property
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""
        return self.last_date - self.start_date + timedelta(days=1)

    @property
    def duration(self) -> relativedelta:
        """Return the duration as a relativedelta."""
        return self._duration

    def is_expired(self, target_date: date) -> bool:
        return self.last_date < target_date

    def is_future(self, target_date: date) -> bool:
        return self.start_date > target_date

    def is_within(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        return (
            self.start_date - approx_before
            <= target_date
            <= self.last_date + approx_after
        )

    def iterate_over_date_ranges(
        self, from_date: date | None = None
    ) -> Iterator[DateRangeInterface]:
        yield self

    def current_date_range(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> DateRangeInterface | None:
        if self.is_within(target_date, approx_before, approx_after):
            return self
        return None

    def next_date_range(self, target_date: date) -> DateRangeInterface | None:
        if self.is_future(target_date):
            return self
        return None

    def last_date_range(self, target_date: date) -> DateRangeInterface | None:
        if self.is_future(target_date):
            return None
        return self

    def replace(self, **kwargs: Any) -> "DateRange":
        new_start_date = kwargs.get("start_date", self.start_date)
        if not isinstance(new_start_date, date):
            raise TypeError(f"start_date must be date, got {type(new_start_date)}")
        new_duration = kwargs.get("duration", self._duration)
        if not isinstance(new_duration, relativedelta):
            raise TypeError(f"duration must be relativedelta, got {type(new_duration)}")
        return DateRange(
            start_date=new_start_date,
            duration=new_duration,
        )

    def __repr__(self) -> str:
        return f"{self.start_date} - {self.last_date}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DateRange):
            return NotImplemented
        return (
            self.start_date == other.start_date
            and self.total_duration == other.total_duration
        )

    def __hash__(self) -> int:
        return hash((self.start_date, self.total_duration))


class SingleDay(DateRange):
    """A date range that lasts one day."""

    def __init__(self, start_date: date) -> None:
        super().__init__(start_date, relativedelta(days=1))

    def replace(self, **kwargs: Any) -> "SingleDay":
        new_start_date = kwargs.get("start_date", self.start_date)
        if not isinstance(new_start_date, date):
            raise TypeError(f"start_date must be date, got {type(new_start_date)}")
        return SingleDay(
            start_date=new_start_date,
        )


class RecurringDateRange(DateRangeInterface):
    """A date range that repeats at a given period."""

    def __init__(
        self,
        initial_date_range: DateRangeInterface,
        period: relativedelta,
        expiration_date: date | None = None,
    ) -> None:
        self._initial_date_range = initial_date_range
        self._period = period
        self._expiration_date = expiration_date or date.max

    @property
    def start_date(self) -> date:
        return self._initial_date_range.start_date

    @property
    def last_date(self) -> date:
        return self._expiration_date

    @property
    def base_date_range(self) -> DateRangeInterface:
        """Return the base date range that repeats."""
        return self._initial_date_range

    @property
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""
        return self.last_date - self.start_date + timedelta(days=1)

    @property
    def duration(self) -> relativedelta:
        """Return the duration of each period as a relativedelta."""
        return self._initial_date_range.duration

    @property
    def period(self) -> relativedelta:
        """Return the period of the date range."""
        return self._period

    def is_expired(self, target_date: date) -> bool:
        return self._expiration_date < target_date

    def is_future(self, target_date: date) -> bool:
        return self._initial_date_range.is_future(target_date)

    def is_within(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        """Check if the date is within the date range."""
        return (
            self.current_date_range(target_date, approx_before, approx_after)
            is not None
        )

    def iterate_over_date_ranges(
        self, from_date: date | None = None
    ) -> Iterator[DateRangeInterface]:
        """Iterate over the date ranges."""
        start = 0
        if from_date is not None and from_date > self.start_date:
            days_diff = (from_date - self.start_date).days

            # Estimate period length in days using MAXIMUM values (31 days/month,
            # 366 days/year) to be conservative. Overestimating the period length
            # underestimates the number of periods, so we may start a bit early.
            # The while loop below corrects forward, which is safe. The opposite
            # (underestimating period → overestimating start) would skip iterations.
            approx_period_days = (
                self._period.years * 366
                + self._period.months * 31
                + self._period.weeks * 7
                + self._period.days
            )

            if approx_period_days > 0:
                start = max(0, days_diff // approx_period_days - 1)

            # Fine-tune: advance to the correct position
            while self.start_date + (start + 1) * self._period < from_date:
                start += 1

        date_ranges = (
            self._initial_date_range.replace(
                start_date=self.start_date + n * self._period
            )
            for n in itertools.count(start)
        )
        return itertools.takewhile(
            lambda dr: dr.last_date <= self.last_date, date_ranges
        )

    def split_at(
        self, split_date: date
    ) -> tuple["RecurringDateRange", "RecurringDateRange"]:
        """Split this date range at the given date.

        Finds the first iteration at or after the given date and returns
        a terminated version of this date range (ending the day before)
        and a new date range starting at that iteration with the original
        expiration date.

        Args:
            split_date: The date from which to split.

        Returns:
            Tuple of (terminated_date_range, new_date_range).

        Raises:
            ValueError: If no iteration exists at or after the given date,
                or if the date is not after the start date.
        """
        if split_date <= self.start_date:
            raise ValueError("Split date must be after the first iteration")

        first_new_iteration = next(
            (
                dr.start_date
                for dr in self.iterate_over_date_ranges()
                if dr.start_date >= split_date
            ),
            None,
        )
        if first_new_iteration is None:
            raise ValueError("No iteration found at or after split date")

        terminated = self.replace(
            expiration_date=first_new_iteration - timedelta(days=1)
        )
        continuation = self.replace(
            start_date=first_new_iteration,
        )
        return terminated, continuation

    def current_date_range(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> DateRangeInterface | None:
        """Get the date range that is active at the given date."""
        for date_range in self.iterate_over_date_ranges(target_date):
            if date_range.is_within(target_date, approx_before, approx_after):
                return date_range
            if date_range.is_future(target_date):
                break
        return None

    def next_date_range(self, target_date: date) -> DateRangeInterface | None:
        """Get the next date range after the given date."""
        for date_range in self.iterate_over_date_ranges(target_date):
            if date_range.is_future(target_date):
                return date_range
        return None

    def last_date_range(self, target_date: date) -> DateRangeInterface | None:
        """Get the last applicable date range before or at the given date."""
        for previous, current in itertools.pairwise(
            self.iterate_over_date_ranges(target_date)
        ):
            if current.is_within(target_date):
                return current
            if current.is_future(target_date):
                return previous
        return None

    def replace(self, **kwargs: Any) -> "RecurringDateRange":
        new_period = kwargs.get("period", self._period)
        if not isinstance(new_period, relativedelta):
            raise TypeError(f"period must be relativedelta, got {type(new_period)}")
        new_expiration_date = kwargs.get("expiration_date", self._expiration_date)
        if new_expiration_date is not None and not isinstance(
            new_expiration_date, date
        ):
            raise TypeError(
                f"expiration_date must be date or None, got {type(new_expiration_date)}"
            )
        return RecurringDateRange(
            initial_date_range=self._initial_date_range.replace(**kwargs),
            period=new_period,
            expiration_date=new_expiration_date,
        )

    def __repr__(self) -> str:
        return (
            f"{self._initial_date_range} every {self._period} until "
            f"{self._expiration_date if self._expiration_date != date.max else 'forever'}"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecurringDateRange):
            return NotImplemented
        return (
            self.start_date == other.start_date
            and self.total_duration == other.total_duration
            and self._period == other._period
            and self._expiration_date == other._expiration_date
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.start_date,
                self.total_duration,
                self._period,
                self._expiration_date,
            )
        )


class RecurringDay(RecurringDateRange):
    """A recurring date range that lasts one day."""

    def __init__(
        self,
        start_date: date,
        period: relativedelta,
        expiration_date: date | None = None,
    ) -> None:
        super().__init__(SingleDay(start_date), period, expiration_date)

    def replace(self, **kwargs: Any) -> "RecurringDay":
        new_start_date = kwargs.get("start_date", self.start_date)
        if not isinstance(new_start_date, date):
            raise TypeError(f"start_date must be date, got {type(new_start_date)}")
        new_period = kwargs.get("period", self._period)
        if not isinstance(new_period, relativedelta):
            raise TypeError(f"period must be relativedelta, got {type(new_period)}")
        new_expiration_date = kwargs.get("expiration_date", self._expiration_date)
        if new_expiration_date is not None and not isinstance(
            new_expiration_date, date
        ):
            raise TypeError(
                f"expiration_date must be date or None, got {type(new_expiration_date)}"
            )
        return RecurringDay(
            start_date=new_start_date,
            period=new_period,
            expiration_date=new_expiration_date,
        )
