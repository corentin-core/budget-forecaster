"""Review tab — monthly per-category planned vs actual review."""

import enum
import logging
from datetime import date, datetime
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.widgets import Button, DataTable, Static
from textual.widgets.data_table import RowKey

from budget_forecaster.core.types import Category
from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import (
    CategoryBudget,
    MarginInfo,
    MonthlySummary,
)
from budget_forecaster.tui.modals.category_detail import CategoryDetailModal
from budget_forecaster.tui.modals.threshold_edit import ThresholdEditModal
from budget_forecaster.tui.symbols import DisplaySymbol

logger = logging.getLogger(__name__)

# Column widths
_COL_CATEGORY = 30
_COL_AMOUNT = 12
_COL_CONSUMPTION = 20


class _BarChar(enum.StrEnum):
    """Characters used in the consumption progress bar."""

    FILLED = "\u2593"
    EMPTY = "\u2591"
    OVER_BUDGET = "!"


def _format_amount(value: float) -> Text:
    """Format a signed amount with currency, right-aligned."""
    return Text(f"{value:+,.0f} {DisplaySymbol.EURO}", justify="right")


def _format_remaining(projected: float, actual: float) -> Text:
    """Format the Remaining column (Projected - Actual)."""
    if (remaining := projected - actual) == 0:
        return Text(f"0 {DisplaySymbol.EURO}", justify="right")
    return Text(f"{remaining:+,.0f} {DisplaySymbol.EURO}", justify="right")


_CONSUMPTION_TOLERANCE = 1.01  # 1% tolerance before alerting


def _render_consumption_bar(
    actual: float, planned: float, *, is_income: bool = False
) -> Text:
    """Render an ASCII consumption bar with color."""
    if planned == 0:
        return Text("")

    ratio = abs(actual) / abs(planned)
    bar_width = 10
    filled = min(bar_width, int(ratio * bar_width))
    empty = bar_width - filled
    is_over = ratio > _CONSUMPTION_TOLERANCE

    # Opposite signs (e.g. expected reimbursement but got expense): always bad
    if (planned > 0) != (actual > 0) and actual != 0:
        is_bad = planned > 0 > actual
    else:
        # Alert when things go wrong: expense over budget OR income under expected
        is_bad = (is_over and not is_income) or (
            not is_over and is_income and ratio < 1.0 / _CONSUMPTION_TOLERANCE
        )
    style = "red" if is_bad else "green"
    pct_str = f"{ratio * 100:.0f}%"

    result = Text("[")
    result.append(_BarChar.FILLED * filled, style=style)
    if is_over:
        over_style = "bold red" if is_bad else "bold green"
        result.append(_BarChar.OVER_BUDGET, style=over_style)
        empty = max(0, empty - 1)
    result.append(_BarChar.EMPTY * empty)
    result.append("]")
    result.append(pct_str.rjust(4))
    return result


def _translate_category(name: str) -> str:
    """Translate a category identifier to its display name."""
    try:
        return Category(name).display_name
    except ValueError:
        return name


def _direction_indicator(is_income: bool) -> str:
    """Return direction arrow for income/expense."""
    return DisplaySymbol.ARROW_UP if is_income else DisplaySymbol.ARROW_DOWN


class ReviewWidget(Vertical):
    """Review tab: per-category planned vs actual for one month."""

    # DataTable ignores width:auto and always fills its parent, so we must
    # give it an explicit width and wrap it in a Center container.
    _TABLE_WIDTH = _COL_CATEGORY + 4 * _COL_AMOUNT + _COL_CONSUMPTION + 6 * 2 + 2

    DEFAULT_CSS = """
    ReviewWidget {
        height: 1fr;
    }

    ReviewWidget #review-nav {
        height: 3;
        align: center middle;
    }

    ReviewWidget #review-prev {
        min-width: 5;
        height: 3;
    }

    ReviewWidget #review-next {
        min-width: 5;
        height: 3;
    }

    ReviewWidget #review-month-label {
        width: auto;
        content-align: center middle;
        text-style: bold;
        padding: 0 2;
    }

    ReviewWidget #review-content {
        height: 1fr;
    }

    ReviewWidget #review-table-center {
        width: 1fr;
        height: 1fr;
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

    ReviewWidget #margin-section {
        width: 55;
        height: auto;
        margin: 1 2;
        padding: 1 2;
        border: solid $primary;
    }

    ReviewWidget #margin-section.alert {
        border: solid $error;
    }

    ReviewWidget #margin-value {
        text-style: bold;
        width: auto;
        height: 1;
    }

    ReviewWidget #margin-value.negative {
        color: $error;
    }

    ReviewWidget #margin-threshold-row {
        height: 3;
        margin-top: 1;
    }

    ReviewWidget #margin-threshold-label {
        width: auto;
        color: $text-muted;
        padding: 1 0;
    }

    ReviewWidget #btn-edit-threshold {
        min-width: 10;
        margin-left: 1;
    }

    ReviewWidget #margin-details {
        height: auto;
        margin-top: 1;
    }

    ReviewWidget .margin-detail-line {
        height: 1;
        color: $text-muted;
    }

    ReviewWidget #margin-explanation {
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }

    ReviewWidget #margin-alert-msg {
        color: $error;
        text-style: bold;
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("comma", "previous_month", _("Previous month")),
        Binding("semicolon", "next_month", _("Next month")),
        Binding("e", "edit_threshold", _("Edit threshold")),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._summaries: list[MonthlySummary] = []
        self._current_index: int = 0
        self._row_to_category: dict[RowKey, str] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="review-nav"):
            yield Button("\u25c0", id="review-prev")
            yield Static("", id="review-month-label")
            yield Button("\u25b6", id="review-next")
        with Horizontal(id="review-content"):
            with Center(id="review-table-center"):
                yield DataTable(id="review-table", cursor_type="row")
            with Vertical(id="margin-section"):
                yield Static("", id="margin-value")
                with Horizontal(id="margin-threshold-row"):
                    yield Static("", id="margin-threshold-label")
                    yield Button(_("Edit"), id="btn-edit-threshold")
                yield Vertical(id="margin-details")
                yield Static("", id="margin-explanation")
                yield Static("", id="margin-alert-msg")
        yield Static("", id="review-status")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "review-prev":
            self.action_previous_month()
        elif event.button.id == "review-next":
            self.action_next_month()
        elif event.button.id == "btn-edit-threshold":
            self.action_edit_threshold()

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
            month_date = month.date() if isinstance(month, datetime) else month
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
        label = self.query_one("#review-month-label", Static)
        month_label = f"{_(month_date.strftime('%B'))} {month_date.year}"
        label.update(month_label)

        has_prev = self._current_index > 0
        has_next = self._current_index < len(self._summaries) - 1
        self.query_one("#review-prev", Button).disabled = not has_prev
        self.query_one("#review-next", Button).disabled = not has_next

        # Build table
        self._build_review_table(summary["categories"])

        # Update margin section
        self._update_margin(month_date)

    def _build_review_table(self, categories: dict[str, CategoryBudget]) -> None:
        """Build the review DataTable from category data."""
        table = self.query_one("#review-table", DataTable)
        table.clear(columns=True)
        self._row_to_category.clear()

        table.add_column(_("Category"), width=_COL_CATEGORY)
        table.add_column(_("Planned"), width=_COL_AMOUNT)
        table.add_column(_("Actual"), width=_COL_AMOUNT)
        table.add_column(_("Forecast"), width=_COL_AMOUNT)
        table.add_column(_("Remaining"), width=_COL_AMOUNT)
        table.add_column(_("Consumption"), width=_COL_CONSUMPTION)

        # DataTable always expands to fill its parent; set an explicit width
        # so the Center container can position it.
        table.styles.width = self._TABLE_WIDTH

        # Separate forecasted vs unforecasted
        forecasted: list[tuple[str, CategoryBudget]] = []
        unforecasted: list[tuple[str, CategoryBudget]] = []

        for cat_name, cat_data in categories.items():
            if cat_data["planned"] != 0:
                forecasted.append((cat_name, cat_data))
            else:
                unforecasted.append((cat_name, cat_data))

        # Sort: expenses first, then incomes, alphabetical within each group
        forecasted.sort(key=lambda x: (x[1]["is_income"], _translate_category(x[0])))
        unforecasted.sort(key=lambda x: (x[1]["is_income"], _translate_category(x[0])))

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
                row_key = table.add_row(
                    Text(f"{direction} {_translate_category(cat_name)}"),
                    _format_amount(cat_data["planned"]),
                    _format_amount(cat_data["actual"]),
                    _format_amount(cat_data["forecast"]),
                    _format_remaining(
                        cat_data["forecast"],
                        cat_data["actual"],
                    ),
                    _render_consumption_bar(
                        cat_data["actual"],
                        cat_data["planned"],
                        is_income=cat_data["is_income"],
                    ),
                )
                self._row_to_category[row_key] = cat_name

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
                row_key = table.add_row(
                    Text(f"{direction} {_translate_category(cat_name)}"),
                    Text("-", justify="right"),
                    _format_amount(cat_data["actual"]),
                    _format_amount(cat_data["forecast"]),
                    Text("--", justify="right"),
                    Text(f"{cat_data['actual']:+,.0f} {DisplaySymbol.EURO}"),
                )
                self._row_to_category[row_key] = cat_name

        # Total row
        if categories:
            self._add_total_row(table, categories)

    @staticmethod
    def _add_total_row(table: DataTable, categories: dict[str, CategoryBudget]) -> None:
        """Add the totals row to the review table."""
        total_planned = sum(c["planned"] for c in categories.values())
        total_actual = sum(c["actual"] for c in categories.values())
        total_projected = sum(c["forecast"] for c in categories.values())
        total_remaining = total_projected - total_actual
        euro = DisplaySymbol.EURO
        remaining_text = (
            f"{total_remaining:+,.0f} {euro}" if total_remaining != 0 else f"0 {euro}"
        )

        table.add_row(
            Text(_("TOTAL"), style="bold"),
            Text(f"{total_planned:+,.0f} {euro}", justify="right", style="bold"),
            Text(f"{total_actual:+,.0f} {euro}", justify="right", style="bold"),
            Text(f"{total_projected:+,.0f} {euro}", justify="right", style="bold"),
            Text(remaining_text, justify="right", style="bold"),
            Text(""),
        )

    def _update_margin(self, month_date: date) -> None:
        """Update the margin section for the selected month."""
        section = self.query_one("#margin-section", Vertical)
        if (month_first := month_date.replace(day=1)) < date.today().replace(day=1):
            section.display = False
            return

        if self._app_service is None:
            section.display = False
            return

        if (margin_info := self._app_service.get_available_margin(month_first)) is None:
            section.display = False
            return

        section.display = True
        is_alert = margin_info["available_margin"] < 0
        section.set_class(is_alert, "alert")

        self._render_margin_header(margin_info, is_alert)
        self._render_margin_details(margin_info, month_first)
        self._render_margin_footer(margin_info, is_alert)

    def _render_margin_header(self, margin_info: MarginInfo, is_alert: bool) -> None:
        """Render the margin value and threshold labels."""
        euro = DisplaySymbol.EURO
        margin_val = margin_info["available_margin"]

        value_widget = self.query_one("#margin-value", Static)
        value_widget.update(f"{_('Available margin')}: {margin_val:,.0f} {euro}")
        value_widget.set_class(is_alert, "negative")

        threshold = margin_info["threshold"]
        self.query_one("#margin-threshold-label", Static).update(
            f"{_('Minimum threshold')}: {threshold:,.0f} {euro}"
        )

    def _render_margin_details(
        self, margin_info: MarginInfo, month_first: date
    ) -> None:
        """Render balance and lowest balance detail lines."""
        euro = DisplaySymbol.EURO
        details = self.query_one("#margin-details", Vertical)
        details.remove_children()

        month_label = f"{_(month_first.strftime('%B'))} {month_first.day}"
        balance_line = (
            f"{_('Balance at')} {month_label}: "
            f"{margin_info['balance_at_month_start']:,.0f} {euro}"
        )

        lowest_date = margin_info["lowest_balance_date"]
        lowest_label = (
            f"{_(lowest_date.strftime('%B'))} {lowest_date.day}, {lowest_date.year}"
        )
        lowest_line = (
            f"{_('Lowest future balance')}: "
            f"{margin_info['lowest_balance']:,.0f} {euro}  ({lowest_label})"
        )
        details.mount(Static(balance_line, classes="margin-detail-line"))
        details.mount(Static(lowest_line, classes="margin-detail-line"))

    def _render_margin_footer(self, margin_info: MarginInfo, is_alert: bool) -> None:
        """Render explanation or alert message."""
        euro = DisplaySymbol.EURO
        threshold = margin_info["threshold"]
        explanation = self.query_one("#margin-explanation", Static)
        alert_msg = self.query_one("#margin-alert-msg", Static)

        if is_alert:
            lowest_date = margin_info["lowest_balance_date"]
            lowest_label = (
                f"{_(lowest_date.strftime('%B'))} {lowest_date.day}, "
                f"{lowest_date.year}"
            )
            explanation.update("")
            alert_msg.update(
                _("/!\\ The account will go below your {} {} threshold on {}").format(
                    f"{threshold:,.0f}", euro, lowest_label
                )
            )
        else:
            threshold_desc = (
                f"{threshold:,.0f} {euro}" if threshold > 0 else f"0 {euro}"
            )
            explanation.update(
                _("= the most you can spend freely without going below {}").format(
                    threshold_desc
                )
            )
            alert_msg.update("")

    def _hide_margin(self) -> None:
        """Hide the margin section."""
        self.query_one("#margin-section", Vertical).display = False

    def action_edit_threshold(self) -> None:
        """Open the threshold edit modal."""
        if self._app_service is None:
            return
        current = self._app_service.margin_threshold
        self.app.push_screen(
            ThresholdEditModal(current), callback=self._on_threshold_result
        )

    def _on_threshold_result(self, result: float | None) -> None:
        """Handle threshold edit result."""
        if result is None or self._app_service is None:
            return
        self._app_service.margin_threshold = result

        # Refresh margin display
        if self._summaries:
            summary = self._summaries[self._current_index]
            month = summary["month"]
            month_date = month.date() if hasattr(month, "date") else month
            self._update_margin(month_date)

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
        self.query_one("#review-month-label", Static).update("")
        self.query_one("#review-prev", Button).disabled = True
        self.query_one("#review-next", Button).disabled = True
        self._hide_margin()

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open category detail modal when a category row is clicked."""
        category = self._row_to_category.get(event.row_key)
        if category is None or self._app_service is None:
            return

        summary = self._summaries[self._current_index]
        month = summary["month"]
        month_date = month.date() if hasattr(month, "date") else month

        try:
            detail = self._app_service.get_category_detail(
                category, month_date.replace(day=1)
            )
            self.app.push_screen(
                CategoryDetailModal(detail, app_service=self._app_service)
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error loading category detail")
            self.app.notify(_("Error loading category detail"), severity="error")
