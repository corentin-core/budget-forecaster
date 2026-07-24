"""Reusable duration input widget (number + unit selector)."""

from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Select

from budget_forecaster.core.duration import (
    DurationUnit,
    relativedelta_to_unit,
    unit_to_relativedelta,
)
from budget_forecaster.i18n import _

__all__ = [
    "DurationUnit",
    "relativedelta_to_unit",
    "unit_to_relativedelta",
    "DurationInput",
]


def _unit_options() -> list[tuple[str, str]]:
    """Return translated unit options for the Select widget."""
    return [
        (_("Days"), DurationUnit.DAYS),
        (_("Weeks"), DurationUnit.WEEKS),
        (_("Months"), DurationUnit.MONTHS),
        (_("Years"), DurationUnit.YEARS),
    ]


class DurationInput(Horizontal):
    """Composite widget: number input + unit selector.

    Usage in compose():
        yield DurationInput(relativedelta(months=3), id="input-duration")

    Reading the value:
        rd = self.query_one("#input-duration", DurationInput).duration
    """

    DEFAULT_CSS = """
    DurationInput {
        height: 3;
    }

    DurationInput .duration-value {
        width: 1fr;
    }

    DurationInput .duration-unit {
        width: 2fr;
    }
    """

    def __init__(
        self,
        value: relativedelta | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if value is None:
            value = relativedelta(months=1)
        self._initial_value, self._initial_unit = relativedelta_to_unit(value)

    def compose(self) -> ComposeResult:
        """Create the number input and unit selector."""
        yield Input(
            value=str(self._initial_value),
            classes="duration-value",
        )
        yield Select(
            _unit_options(),
            value=self._initial_unit,
            classes="duration-unit",
        )

    @property
    def duration(self) -> relativedelta:
        """Read and validate the current duration.

        Raises ValueError if the value is not a positive integer.
        """
        value_str = self.query_one(".duration-value", Input).value.strip()
        try:
            if (value := int(value_str)) <= 0:
                raise ValueError("must be positive")
        except ValueError as exc:
            raise ValueError(_("Duration must be a positive integer")) from exc

        unit_select = self.query_one(".duration-unit", Select)
        if unit_select.value == Select.BLANK:
            raise ValueError(_("Unit is required"))
        unit = DurationUnit(str(unit_select.value))

        return unit_to_relativedelta(value, unit)
