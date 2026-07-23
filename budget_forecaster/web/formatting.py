"""Jinja filters for locale-aware display of amounts, dates and categories.

French conventions: narrow no-break space for thousands, comma decimal.
"""

from datetime import date

from jinja2 import Environment

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _

_THIN_SPACE = " "
_NBSP = " "


def _group_thousands(digits: str) -> str:
    groups: list[str] = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    return _THIN_SPACE.join(groups)


def format_eur(amount: float, currency: str = "EUR") -> str:
    """Format an amount as '1 234,56 EUR' (unsigned)."""
    whole, frac = f"{abs(amount):.2f}".split(".")
    sign = "-" if amount < 0 else ""
    return f"{sign}{_group_thousands(whole)},{frac}{_NBSP}{currency}"


def format_signed_eur(amount: float, currency: str = "EUR") -> str:
    """Format an amount with an explicit sign, e.g. '+2 600,00 EUR'."""
    whole, frac = f"{abs(amount):.2f}".split(".")
    sign = "-" if amount < 0 else "+"
    return f"{sign}{_group_thousands(whole)},{frac}{_NBSP}{currency}"


def format_date(value: date) -> str:
    """Format a date as dd/mm/YYYY."""
    return value.strftime("%d/%m/%Y")


def format_month(value: date) -> str:
    """Format a month as a translated 'Month YYYY' label."""
    return f"{_(value.strftime('%B'))} {value.year}"


def format_pct(ratio: float) -> str:
    """Format a 0..1 ratio as a rounded percentage, e.g. '82 %'."""
    return f"{ratio * 100:.0f}{_NBSP}%"


def category_name(key: str) -> str:
    """Translate a category identifier to its display name, or echo it back."""
    try:
        return Category(key).display_name
    except ValueError:
        return key


def register_filters(env: Environment) -> None:
    """Register the formatting filters on a Jinja environment."""
    env.filters["eur"] = format_eur
    env.filters["signed_eur"] = format_signed_eur
    env.filters["frdate"] = format_date
    env.filters["month_label"] = format_month
    env.filters["pct"] = format_pct
    env.filters["category_name"] = category_name
