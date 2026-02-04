"""Time range module."""
import abc
import itertools
from datetime import datetime, timedelta
from functools import total_ordering
from typing import Any, Iterator, Optional

from dateutil.relativedelta import relativedelta


@total_ordering
class TimeRangeInterface(abc.ABC):
    """
    A time range is a period of time defined by a start date and a duration.
    It can be repeated at a given period.
    """

    @property
    @abc.abstractmethod
    def initial_date(self) -> datetime:
        """Return the initial date of the time range."""

    @property
    @abc.abstractmethod
    def last_date(self) -> datetime:
        """Return the last date of the time range."""

    @property
    @abc.abstractmethod
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""

    @property
    @abc.abstractmethod
    def duration(self) -> relativedelta:
        """Return the duration as a relativedelta."""

    @abc.abstractmethod
    def is_expired(self, date: datetime) -> bool:
        """Check if the time range is expired at the given date."""

    @abc.abstractmethod
    def is_future(self, date: datetime) -> bool:
        """Check if the time range is in the future at the given date."""

    @abc.abstractmethod
    def is_within(
        self,
        date: datetime,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        """Check if the date is within the time range."""

    @abc.abstractmethod
    def iterate_over_time_ranges(
        self, from_date: datetime | None = None
    ) -> Iterator["TimeRangeInterface"]:
        """Iterate over the time ranges."""

    @abc.abstractmethod
    def current_time_range(
        self,
        date: datetime,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> Optional["TimeRangeInterface"]:
        """Get the time range that is active at the given date."""

    @abc.abstractmethod
    def next_time_range(self, date: datetime) -> Optional["TimeRangeInterface"]:
        """Get the next time range after the given date."""

    @abc.abstractmethod
    def last_time_range(self, date: datetime) -> Optional["TimeRangeInterface"]:
        """Get the previous time range before the given date."""

    @abc.abstractmethod
    def replace(self, **kwargs: Any) -> "TimeRangeInterface":
        """Return a new instance of the time range with the given parameters replaced."""

    @abc.abstractmethod
    def __eq__(self, other: object) -> bool:
        """Check if two time ranges are equal."""

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, TimeRangeInterface):
            return NotImplemented
        return (self.initial_date, self.last_date) < (
            other.initial_date,
            other.last_date,
        )

    @abc.abstractmethod
    def __hash__(self) -> int:
        """Return the hash of the time range."""


class TimeRange(TimeRangeInterface):
    """A non recurring time range."""

    def __init__(
        self,
        initial_date: datetime,
        duration: relativedelta,
    ) -> None:
        self._initial_date = initial_date
        self._duration = duration

    @property
    def initial_date(self) -> datetime:
        return self._initial_date

    @property
    def last_date(self) -> datetime:
        return self._initial_date + self._duration - timedelta(days=1)

    @property
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""
        return self.last_date - self.initial_date + timedelta(days=1)

    @property
    def duration(self) -> relativedelta:
        """Return the duration as a relativedelta."""
        return self._duration

    def is_expired(self, date: datetime) -> bool:
        return self.last_date < date

    def is_future(self, date: datetime) -> bool:
        return self.initial_date > date

    def is_within(
        self,
        date: datetime,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        return (
            self.initial_date - approx_before <= date <= self.last_date + approx_after
        )

    def iterate_over_time_ranges(
        self, from_date: datetime | None = None
    ) -> Iterator[TimeRangeInterface]:
        yield self

    def current_time_range(
        self,
        date: datetime,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> TimeRangeInterface | None:
        if self.is_within(date, approx_before, approx_after):
            return self
        return None

    def next_time_range(self, date: datetime) -> TimeRangeInterface | None:
        if self.is_future(date):
            return self
        return None

    def last_time_range(self, date: datetime) -> TimeRangeInterface | None:
        if self.is_future(date):
            return None
        return self

    def replace(self, **kwargs: Any) -> "TimeRange":
        new_initial_date = kwargs.get("initial_date", self.initial_date)
        if not isinstance(new_initial_date, datetime):
            raise TypeError(
                f"initial_date must be datetime, got {type(new_initial_date)}"
            )
        new_duration = kwargs.get("duration", self._duration)
        if not isinstance(new_duration, relativedelta):
            raise TypeError(f"duration must be relativedelta, got {type(new_duration)}")
        return TimeRange(
            initial_date=new_initial_date,
            duration=new_duration,
        )

    def __repr__(self) -> str:
        return f"{self.initial_date} - {self.last_date}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeRange):
            return NotImplemented
        return (
            self.initial_date == other.initial_date
            and self.total_duration == other.total_duration
        )

    def __hash__(self) -> int:
        return hash((self.initial_date, self.total_duration))


class DailyTimeRange(TimeRange):
    """A time range that lasts one day."""

    def __init__(self, date: datetime) -> None:
        super().__init__(date, relativedelta(days=1))

    @property
    def date(self) -> datetime:
        """Return the date of the time range."""
        return self.initial_date

    def replace(self, **kwargs: Any) -> "DailyTimeRange":
        new_initial_date = kwargs.get("initial_date", self.initial_date)
        if not isinstance(new_initial_date, datetime):
            raise TypeError(
                f"initial_date must be datetime, got {type(new_initial_date)}"
            )
        return DailyTimeRange(
            date=new_initial_date,
        )


class PeriodicTimeRange(TimeRangeInterface):
    """A time range that repeats at a given period."""

    def __init__(
        self,
        initial_time_range: TimeRangeInterface,
        period: relativedelta,
        expiration_date: datetime | None = None,
    ) -> None:
        self._initial_time_range = initial_time_range
        self._period = period
        self._expiration_date = expiration_date or datetime.max

    @property
    def initial_date(self) -> datetime:
        return self._initial_time_range.initial_date

    @property
    def last_date(self) -> datetime:
        return self._expiration_date

    @property
    def base_time_range(self) -> TimeRangeInterface:
        """Return the base time range that repeats."""
        return self._initial_time_range

    @property
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""
        return self.last_date - self.initial_date + timedelta(days=1)

    @property
    def duration(self) -> relativedelta:
        """Return the duration of each period as a relativedelta."""
        return self._initial_time_range.duration

    @property
    def period(self) -> relativedelta:
        """Return the period of the time range."""
        return self._period

    def is_expired(self, date: datetime) -> bool:
        return self._expiration_date < date

    def is_future(self, date: datetime) -> bool:
        return self._initial_time_range.is_future(date)

    def is_within(
        self,
        date: datetime,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        """Check if the date is within the time range."""
        return self.current_time_range(date, approx_before, approx_after) is not None

    def iterate_over_time_ranges(
        self, from_date: datetime | None = None
    ) -> Iterator[TimeRangeInterface]:
        """Iterate over the time ranges."""
        start = 0
        if from_date is not None and from_date > self.initial_date:
            days_diff = (from_date - self.initial_date).days

            # Estimate period length in days (approximate for months)
            approx_period_days = (
                self._period.years * 365
                + self._period.months * 30
                + self._period.weeks * 7
                + self._period.days
            )

            if approx_period_days > 0:
                # -1 to never skip too far
                start = max(0, days_diff // approx_period_days - 1)

            # Fine-tune: advance to the correct position (0-3 iterations max)
            while self.initial_date + (start + 1) * self._period < from_date:
                start += 1

        time_ranges = (
            self._initial_time_range.replace(
                initial_date=self.initial_date + n * self._period
            )
            for n in itertools.count(start)
        )
        return itertools.takewhile(
            lambda tr: tr.last_date <= self.last_date, time_ranges
        )

    def split_at(
        self, date: datetime
    ) -> tuple["PeriodicTimeRange", "PeriodicTimeRange"]:
        """Split this time range at the given date.

        Finds the first iteration at or after the given date and returns
        a terminated version of this time range (ending the day before)
        and a new time range starting at that iteration with the original
        expiration date.

        Args:
            date: The date from which to split.

        Returns:
            Tuple of (terminated_time_range, new_time_range).

        Raises:
            ValueError: If no iteration exists at or after the given date,
                or if the date is not after the initial date.
        """
        if date <= self.initial_date:
            raise ValueError("Split date must be after the first iteration")

        first_new_iteration = next(
            (
                tr.initial_date
                for tr in self.iterate_over_time_ranges()
                if tr.initial_date >= date
            ),
            None,
        )
        if first_new_iteration is None:
            raise ValueError("No iteration found at or after split date")

        terminated = self.replace(
            expiration_date=first_new_iteration - timedelta(days=1)
        )
        continuation = self.replace(
            initial_date=first_new_iteration,
        )
        return terminated, continuation

    def current_time_range(
        self,
        date: datetime,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> TimeRangeInterface | None:
        """Get the time range that is active at the given date."""
        for time_range in self.iterate_over_time_ranges(date):
            if time_range.is_within(date, approx_before, approx_after):
                return time_range
            if time_range.is_future(date):
                break
        return None

    def next_time_range(self, date: datetime) -> TimeRangeInterface | None:
        """Get the next time range after the given date."""
        for time_range in self.iterate_over_time_ranges(date):
            if time_range.is_future(date):
                return time_range
        return None

    def last_time_range(self, date: datetime) -> TimeRangeInterface | None:
        """Get the last applicable time range before or at the given date."""
        for previous, current in itertools.pairwise(
            self.iterate_over_time_ranges(date)
        ):
            if current.is_within(date):
                return current
            if current.is_future(date):
                return previous
        return None

    def replace(self, **kwargs: Any) -> "PeriodicTimeRange":
        new_period = kwargs.get("period", self._period)
        if not isinstance(new_period, relativedelta):
            raise TypeError(f"period must be relativedelta, got {type(new_period)}")
        new_expiration_date = kwargs.get("expiration_date", self._expiration_date)
        if new_expiration_date is not None and not isinstance(
            new_expiration_date, datetime
        ):
            raise TypeError(
                f"expiration_date must be datetime or None, got {type(new_expiration_date)}"
            )
        return PeriodicTimeRange(
            initial_time_range=self._initial_time_range.replace(**kwargs),
            period=new_period,
            expiration_date=new_expiration_date,
        )

    def __repr__(self) -> str:
        return (
            f"{self._initial_time_range} every {self._period} until "
            f"{self._expiration_date if self._expiration_date != datetime.max else 'forever'}"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PeriodicTimeRange):
            return NotImplemented
        return (
            self.initial_date == other.initial_date
            and self.total_duration == other.total_duration
            and self._period == other._period
            and self._expiration_date == other._expiration_date
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.initial_date,
                self.total_duration,
                self._period,
                self._expiration_date,
            )
        )


class PeriodicDailyTimeRange(PeriodicTimeRange):
    """A periodic time range that lasts one day."""

    def __init__(
        self,
        initial_date: datetime,
        period: relativedelta,
        expiration_date: datetime | None = None,
    ) -> None:
        super().__init__(DailyTimeRange(initial_date), period, expiration_date)

    def replace(self, **kwargs: Any) -> "PeriodicDailyTimeRange":
        new_initial_date = kwargs.get("initial_date", self.initial_date)
        if not isinstance(new_initial_date, datetime):
            raise TypeError(
                f"initial_date must be datetime, got {type(new_initial_date)}"
            )
        new_period = kwargs.get("period", self._period)
        if not isinstance(new_period, relativedelta):
            raise TypeError(f"period must be relativedelta, got {type(new_period)}")
        new_expiration_date = kwargs.get("expiration_date", self._expiration_date)
        if new_expiration_date is not None and not isinstance(
            new_expiration_date, datetime
        ):
            raise TypeError(
                f"expiration_date must be datetime or None, got {type(new_expiration_date)}"
            )
        return PeriodicDailyTimeRange(
            initial_date=new_initial_date,
            period=new_period,
            expiration_date=new_expiration_date,
        )
