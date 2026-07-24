"""Duration as a (value, unit) pair, and conversions to/from relativedelta.

Shared by any UI that edits a period or duration, so the TUI and the web build
identical relativedeltas from the same value+unit inputs.
"""

from enum import StrEnum

from dateutil.relativedelta import relativedelta


class DurationUnit(StrEnum):
    """Available duration units."""

    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


def relativedelta_to_unit(rd: relativedelta) -> tuple[int, DurationUnit]:
    """Extract (value, unit) from a relativedelta.

    Detection priority: years > months > weeks > days, fallback to 1 month.
    """
    if rd.years and rd.years > 0:
        return rd.years, DurationUnit.YEARS
    if rd.months and rd.months > 0:
        return rd.months, DurationUnit.MONTHS
    if rd.days and rd.days > 0:
        if rd.days % 7 == 0:
            return rd.days // 7, DurationUnit.WEEKS
        return rd.days, DurationUnit.DAYS
    return 1, DurationUnit.MONTHS


def unit_to_relativedelta(value: int, unit: DurationUnit) -> relativedelta:
    """Convert (value, unit) to a relativedelta."""
    match unit:
        case DurationUnit.DAYS:
            return relativedelta(days=value)
        case DurationUnit.WEEKS:
            return relativedelta(weeks=value)
        case DurationUnit.MONTHS:
            return relativedelta(months=value)
        case DurationUnit.YEARS:
            return relativedelta(years=value)
