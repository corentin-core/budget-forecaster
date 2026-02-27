"""Review tab — monthly per-category planned vs actual review."""

import logging
from datetime import date
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import (
    CategoryBudget,
    MonthlySummary,
)

logger = logging.getLogger(__name__)

# Column widths
_COL_CATEGORY = 20
_COL_AMOUNT = 10
_COL_CONSUMPTION = 16


def _format_amount(value: float) -> Text:
    """Format an amount as absolute value, right-aligned."""
    return Text(f"{abs(value):,.0f}", justify="right")


def _format_remaining(projected: float, actual: float) -> Text:
    """Format the Remaining column (Projected - Actual)."""
    if (remaining := abs(projected) - abs(actual)) == 0:
        return Text("0", justify="right")
    sign = "+" if remaining > 0 else ""
    return Text(f"{sign}{remaining:,.0f}", justify="right")


def _render_consumption_bar(actual: float, planned: float) -> Text:
    """Render an ASCII consumption bar with color."""
    if planned == 0:
        return Text("")

    ratio = abs(actual) / abs(planned)
    bar_width = 10
    filled = min(bar_width, int(ratio * bar_width))
    empty = bar_width - filled
    is_over = ratio > 1.0

    style = "red" if is_over else "green"
    pct_str = f"{ratio * 100:.0f}%"

    result = Text("[")
    result.append("\u2593" * filled, style=style)
    if is_over:
        result.append("!", style="bold red")
        empty = max(0, empty - 1)
    result.append("\u2591" * empty)
    result.append("]")
    result.append(pct_str.rjust(4))
    return result


def _direction_indicator(is_income: bool) -> str:
    """Return direction arrow for income/expense."""
    return "\u2191" if is_income else "\u2193"


class _ReviewTable(DataTable):
    """DataTable that redirects Left/Right to parent for month navigation."""

    BINDINGS = [
        Binding("left", "navigate_previous_month", show=False),
        Binding("right", "navigate_next_month", show=False),
    ]

    def action_navigate_previous_month(self) -> None:
        """Forward to parent for month navigation."""
        parent = self.parent
        if parent is not None and hasattr(parent, "action_previous_month"):
            parent.action_previous_month()

    def action_navigate_next_month(self) -> None:
        """Forward to parent for month navigation."""
        parent = self.parent
        if parent is not None and hasattr(parent, "action_next_month"):
            parent.action_next_month()


class ReviewWidget(Vertical):
    """Review tab: per-category planned vs actual for one month."""

    DEFAULT_CSS = """
    ReviewWidget {
        height: 1fr;
    }

    ReviewWidget #review-nav {
        height: 3;
        content-align: center middle;
        text-style: bold;
    }

    ReviewWidget #review-table {
        height: 1fr;
    }

    ReviewWidget #review-status {
        dock: bottom;
        height: 1;
        color: $text-muted;
    }

    ReviewWidget .computing {
        color: $warning;
    }
    """

    BINDINGS = [
        Binding("left", "previous_month", _("Previous month"), show=False),
        Binding("right", "next_month", _("Next month"), show=False),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._summaries: list[MonthlySummary] = []
        self._current_index: int = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="review-nav")
        yield _ReviewTable(id="review-table", cursor_type="row")
        yield Static("", id="review-status")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service

    def refresh_data(self) -> None:
        """Refresh data — invalidate cached report so next tab open recomputes."""
        if self._app_service is not None:
            self._app_service.load_forecast()
        self._summaries = []

    def compute_and_display(self) -> None:
        """Auto-compute forecast when tab becomes active."""
        if self._app_service is None:
            return

        if self._app_service.report is not None:
            self._load_summaries_and_display()
            return

        status = self.query_one("#review-status", Static)
        status.update(_("Computing..."))
        status.add_class("computing")

        self.call_after_refresh(self._do_compute)

    def _do_compute(self) -> None:
        """Perform the computation after UI refresh."""
        status = self.query_one("#review-status", Static)
        try:
            if self._app_service is not None:
                self._app_service.compute_report()
            self._load_summaries_and_display()
        except BudgetForecasterError as e:
            logger.error("Error computing forecast: %s", e)
            self.app.notify(_("Error: {}").format(e), severity="error")
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error computing forecast")
            self.app.notify(_("An unexpected error occurred"), severity="error")
        finally:
            status.remove_class("computing")
            status.update("")

    def _load_summaries_and_display(self) -> None:
        """Load summaries from cached report and display current month."""
        if self._app_service is None:
            return

        self._summaries = self._app_service.get_monthly_summary()
        if not self._summaries:
            self._show_empty_state()
            return

        # Select current month by default
        self._current_index = self._find_current_month_index()
        self._display_month()

    def _find_current_month_index(self) -> int:
        """Find the index of the current month in summaries."""
        today_month = date.today().replace(day=1)
        for i, summary in enumerate(self._summaries):
            month = summary["month"]
            month_date = month.date() if hasattr(month, "date") else month
            if month_date.replace(day=1) >= today_month:
                return i
        return len(self._summaries) - 1

    def _display_month(self) -> None:
        """Display the review table for the current month."""
        if not self._summaries:
            self._show_empty_state()
            return

        summary = self._summaries[self._current_index]
        month = summary["month"]
        month_date = month.date() if hasattr(month, "date") else month

        # Update navigation
        nav = self.query_one("#review-nav", Static)
        month_label = month_date.strftime("%B %Y").capitalize()
        has_prev = self._current_index > 0
        has_next = self._current_index < len(self._summaries) - 1
        prev_arrow = "\u25c0  " if has_prev else "   "
        next_arrow = "  \u25b6" if has_next else ""
        nav.update(f"{prev_arrow}{month_label}{next_arrow}")

        # Build table
        self._build_review_table(summary["categories"])

    def _build_review_table(self, categories: dict[str, CategoryBudget]) -> None:
        """Build the review DataTable from category data."""
        table = self.query_one("#review-table", DataTable)
        table.clear(columns=True)

        table.add_columns(
            _("Category"),
            _("Planned"),
            _("Actual"),
            _("Projected"),
            _("Remaining"),
            _("Consumption"),
        )

        # Separate forecasted vs unforecasted
        forecasted: list[tuple[str, CategoryBudget]] = []
        unforecasted: list[tuple[str, CategoryBudget]] = []

        for cat_name, cat_data in categories.items():
            if cat_data["planned"] != 0:
                forecasted.append((cat_name, cat_data))
            else:
                unforecasted.append((cat_name, cat_data))

        # Sort forecasted by absolute planned descending
        forecasted.sort(key=lambda x: abs(x[1]["planned"]), reverse=True)
        # Sort unforecasted by absolute actual descending
        unforecasted.sort(key=lambda x: abs(x[1]["actual"]), reverse=True)

        # Forecasted section
        if forecasted:
            table.add_row(
                Text(_("Forecasted"), style="bold dim"),
                "",
                "",
                "",
                "",
                "",
            )
            for cat_name, cat_data in forecasted:
                direction = _direction_indicator(cat_data["is_income"])
                table.add_row(
                    Text(f"{direction} {cat_name}"),
                    _format_amount(cat_data["planned"]),
                    _format_amount(cat_data["actual"]),
                    _format_amount(cat_data["projected"]),
                    _format_remaining(
                        cat_data["projected"],
                        cat_data["actual"],
                    ),
                    _render_consumption_bar(cat_data["actual"], cat_data["planned"]),
                )

        # Unforecasted section
        if unforecasted:
            table.add_row(
                Text(_("Unforecasted"), style="bold dim"),
                "",
                "",
                "",
                "",
                "",
            )
            for cat_name, cat_data in unforecasted:
                direction = _direction_indicator(cat_data["is_income"])
                actual_text = _format_amount(cat_data["actual"])
                table.add_row(
                    Text(f"{direction} {cat_name}"),
                    Text("-", justify="right"),
                    actual_text,
                    _format_amount(cat_data["projected"]),
                    Text("--", justify="right"),
                    Text(f"{abs(cat_data['actual']):,.0f} EUR"),
                )

        # Total row
        if categories:
            total_planned = sum(c["planned"] for c in categories.values())
            total_actual = sum(c["actual"] for c in categories.values())
            total_projected = sum(c["projected"] for c in categories.values())
            total_remaining = abs(total_projected) - abs(total_actual)

            sign = "+" if total_remaining > 0 else ""
            remaining_text = (
                f"{sign}{total_remaining:,.0f}" if total_remaining != 0 else "0"
            )

            table.add_row(
                Text(_("TOTAL"), style="bold"),
                Text(f"{total_planned:,.0f}", justify="right", style="bold"),
                Text(f"{total_actual:,.0f}", justify="right", style="bold"),
                Text(f"{total_projected:,.0f}", justify="right", style="bold"),
                Text(remaining_text, justify="right", style="bold"),
                Text(""),
            )

    def _show_empty_state(self) -> None:
        """Show empty state when no data is available."""
        table = self.query_one("#review-table", DataTable)
        table.clear(columns=True)
        table.add_column(_("Category"))
        table.add_row(
            Text(
                _("No planned operations or budgets for this month"),
                style="dim",
            )
        )
        nav = self.query_one("#review-nav", Static)
        nav.update("")

    def action_previous_month(self) -> None:
        """Navigate to the previous month."""
        if self._current_index > 0:
            self._current_index -= 1
            self._display_month()

    def action_next_month(self) -> None:
        """Navigate to the next month."""
        if self._current_index < len(self._summaries) - 1:
            self._current_index += 1
            self._display_month()
