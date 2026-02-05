"""Time range module."""
import abc
import itertools
from datetime import date, timedelta
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
    def initial_date(self) -> date:
        """Return the initial date of the time range."""

    @property
    @abc.abstractmethod
    def last_date(self) -> date:
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
    def is_expired(self, target_date: date) -> bool:
        """Check if the time range is expired at the given date."""

    @abc.abstractmethod
    def is_future(self, target_date: date) -> bool:
        """Check if the time range is in the future at the given date."""

    @abc.abstractmethod
    def is_within(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        """Check if the date is within the time range."""

    @abc.abstractmethod
    def iterate_over_time_ranges(
        self, from_date: date | None = None
    ) -> Iterator["TimeRangeInterface"]:
        """Iterate over the time ranges."""

    @abc.abstractmethod
    def current_time_range(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> Optional["TimeRangeInterface"]:
        """Get the time range that is active at the given date."""

    @abc.abstractmethod
    def next_time_range(self, target_date: date) -> Optional["TimeRangeInterface"]:
        """Get the next time range after the given date."""

    @abc.abstractmethod
    def last_time_range(self, target_date: date) -> Optional["TimeRangeInterface"]:
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
        initial_date: date,
        duration: relativedelta,
    ) -> None:
        self._initial_date = initial_date
        self._duration = duration

    @property
    def initial_date(self) -> date:
        return self._initial_date

    @property
    def last_date(self) -> date:
        return self._initial_date + self._duration - timedelta(days=1)

    @property
    def total_duration(self) -> timedelta:
        """Return the total duration as a timedelta."""
        return self.last_date - self.initial_date + timedelta(days=1)

    @property
    def duration(self) -> relativedelta:
        """Return the duration as a relativedelta."""
        return self._duration

    def is_expired(self, target_date: date) -> bool:
        return self.last_date < target_date

    def is_future(self, target_date: date) -> bool:
        return self.initial_date > target_date

    def is_within(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        return (
            self.initial_date - approx_before
            <= target_date
            <= self.last_date + approx_after
        )

    def iterate_over_time_ranges(
        self, from_date: date | None = None
    ) -> Iterator[TimeRangeInterface]:
        yield self

    def current_time_range(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> TimeRangeInterface | None:
        if self.is_within(target_date, approx_before, approx_after):
            return self
        return None

    def next_time_range(self, target_date: date) -> TimeRangeInterface | None:
        if self.is_future(target_date):
            return self
        return None

    def last_time_range(self, target_date: date) -> TimeRangeInterface | None:
        if self.is_future(target_date):
            return None
        return self

    def replace(self, **kwargs: Any) -> "TimeRange":
        new_initial_date = kwargs.get("initial_date", self.initial_date)
        if not isinstance(new_initial_date, date):
            raise TypeError(f"initial_date must be date, got {type(new_initial_date)}")
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

    def __init__(
        self, initial_date: date  # pylint: disable=used-before-assignment
    ) -> None:
        super().__init__(initial_date, relativedelta(days=1))

    @property
    def date(self) -> "date":
        """Return the date of the time range."""
        return self.initial_date

    def replace(self, **kwargs: Any) -> "DailyTimeRange":
        new_initial_date = kwargs.get("initial_date", self.initial_date)
        if not isinstance(new_initial_date, date):
            raise TypeError(f"initial_date must be date, got {type(new_initial_date)}")
        return DailyTimeRange(
            initial_date=new_initial_date,
        )


class PeriodicTimeRange(TimeRangeInterface):
    """A time range that repeats at a given period."""

    def __init__(
        self,
        initial_time_range: TimeRangeInterface,
        period: relativedelta,
        expiration_date: date | None = None,
    ) -> None:
        self._initial_time_range = initial_time_range
        self._period = period
        self._expiration_date = expiration_date or date.max

    @property
    def initial_date(self) -> date:
        return self._initial_time_range.initial_date

    @property
    def last_date(self) -> date:
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

    def is_expired(self, target_date: date) -> bool:
        return self._expiration_date < target_date

    def is_future(self, target_date: date) -> bool:
        return self._initial_time_range.is_future(target_date)

    def is_within(
        self,
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> bool:
        """Check if the date is within the time range."""
        return (
            self.current_time_range(target_date, approx_before, approx_after)
            is not None
        )

    def iterate_over_time_ranges(
        self, from_date: date | None = None
    ) -> Iterator[TimeRangeInterface]:
        """Iterate over the time ranges."""
        start = 0
        if from_date is not None and from_date > self.initial_date:
            days_diff = (from_date - self.initial_date).days

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
        self, split_date: date
    ) -> tuple["PeriodicTimeRange", "PeriodicTimeRange"]:
        """Split this time range at the given date.

        Finds the first iteration at or after the given date and returns
        a terminated version of this time range (ending the day before)
        and a new time range starting at that iteration with the original
        expiration date.

        Args:
            split_date: The date from which to split.

        Returns:
            Tuple of (terminated_time_range, new_time_range).

        Raises:
            ValueError: If no iteration exists at or after the given date,
                or if the date is not after the initial date.
        """
        if split_date <= self.initial_date:
            raise ValueError("Split date must be after the first iteration")

        first_new_iteration = next(
            (
                tr.initial_date
                for tr in self.iterate_over_time_ranges()
                if tr.initial_date >= split_date
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
        target_date: date,
        approx_before: timedelta = timedelta(),
        approx_after: timedelta = timedelta(),
    ) -> TimeRangeInterface | None:
        """Get the time range that is active at the given date."""
        for time_range in self.iterate_over_time_ranges(target_date):
            if time_range.is_within(target_date, approx_before, approx_after):
                return time_range
            if time_range.is_future(target_date):
                break
        return None

    def next_time_range(self, target_date: date) -> TimeRangeInterface | None:
        """Get the next time range after the given date."""
        for time_range in self.iterate_over_time_ranges(target_date):
            if time_range.is_future(target_date):
                return time_range
        return None

    def last_time_range(self, target_date: date) -> TimeRangeInterface | None:
        """Get the last applicable time range before or at the given date."""
        for previous, current in itertools.pairwise(
            self.iterate_over_time_ranges(target_date)
        ):
            if current.is_within(target_date):
                return current
            if current.is_future(target_date):
                return previous
        return None

    def replace(self, **kwargs: Any) -> "PeriodicTimeRange":
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
        return PeriodicTimeRange(
            initial_time_range=self._initial_time_range.replace(**kwargs),
            period=new_period,
            expiration_date=new_expiration_date,
        )

    def __repr__(self) -> str:
        return (
            f"{self._initial_time_range} every {self._period} until "
            f"{self._expiration_date if self._expiration_date != date.max else 'forever'}"
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
        initial_date: date,
        period: relativedelta,
        expiration_date: date | None = None,
    ) -> None:
        super().__init__(DailyTimeRange(initial_date), period, expiration_date)

    def replace(self, **kwargs: Any) -> "PeriodicDailyTimeRange":
        new_initial_date = kwargs.get("initial_date", self.initial_date)
        if not isinstance(new_initial_date, date):
            raise TypeError(f"initial_date must be date, got {type(new_initial_date)}")
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
        return PeriodicDailyTimeRange(
            initial_date=new_initial_date,
            period=new_period,
            expiration_date=new_expiration_date,
        )
