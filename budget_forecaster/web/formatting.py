"""Jinja filters for locale-aware display of amounts, dates and categories.

French conventions: narrow no-break space for thousands, comma decimal.
"""

import unicodedata
from datetime import date, datetime

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


def format_eur_rounded(amount: float, currency: str = "EUR") -> str:
    """Format an amount without decimals, for at-a-glance large figures."""
    rounded = round(amount)
    sign = "-" if rounded < 0 else ""
    return f"{sign}{_group_thousands(str(abs(rounded)))}{_NBSP}{currency}"


def format_signed_eur(amount: float, currency: str = "EUR") -> str:
    """Format an amount with an explicit sign, e.g. '+2 600,00 EUR'."""
    whole, frac = f"{abs(amount):.2f}".split(".")
    sign = "-" if amount < 0 else "+"
    return f"{sign}{_group_thousands(whole)},{frac}{_NBSP}{currency}"


def format_date(value: date) -> str:
    """Format a date as dd/mm/YYYY."""
    return value.strftime("%d/%m/%Y")


def format_datetime(value: datetime) -> str:
    """Format an aware datetime in local time as dd/mm/YYYY HH:MM."""
    return value.astimezone().strftime("%d/%m/%Y %H:%M")


def format_sync_error(error: str | None) -> str:
    """Turn a recorded sync error into a short user-facing message.

    The raw error ("ClassName: message") stays in storage for debugging; the UI
    shows a translated summary, never the raw exception text.
    """
    if error and error.startswith("NoConsentError"):
        return _("Consent expired or missing")
    return _("Sync failed")


def format_month(value: date) -> str:
    """Format a month as a translated 'Month YYYY' label."""
    return f"{_(value.strftime('%B'))} {value.year}"


def format_pct(ratio: float) -> str:
    """Format a 0..1 ratio as a rounded percentage, e.g. '82 %'."""
    return f"{ratio * 100:.0f}{_NBSP}%"


def format_filesize(num_bytes: int) -> str:
    """Format a byte count with French units, e.g. '1,2 Mo'."""
    size = float(num_bytes)
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024 or unit == "Go":
            if unit == "o":
                return f"{int(size)}{_NBSP}{unit}"
            return f"{size:.1f}".replace(".", ",") + f"{_NBSP}{unit}"
        size /= 1024
    return f"{size:.1f}".replace(".", ",") + f"{_NBSP}Go"


def category_name(key: str) -> str:
    """Translate a category identifier to its display name, or echo it back."""
    try:
        return Category(key).display_name
    except ValueError:
        return key


def _fold(text: str) -> str:
    """Accent- and case-insensitive sort key, so 'Épargne' sorts with the E's."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )
    return stripped.casefold()


def sorted_categories() -> tuple[Category, ...]:
    """Categories ordered by display name for dropdowns, accents folded.

    Sorted per call: display_name is locale-aware, so the order must follow the
    active language, not whatever was active at import time.
    """
    return tuple(sorted(Category, key=lambda c: _fold(c.display_name)))


def register_filters(env: Environment) -> None:
    """Register the formatting filters on a Jinja environment."""
    env.filters["eur"] = format_eur
    env.filters["eur0"] = format_eur_rounded
    env.filters["signed_eur"] = format_signed_eur
    env.filters["frdate"] = format_date
    env.filters["frdatetime"] = format_datetime
    env.filters["sync_error"] = format_sync_error
    env.filters["month_label"] = format_month
    env.filters["pct"] = format_pct
    env.filters["filesize"] = format_filesize
    env.filters["category_name"] = category_name
