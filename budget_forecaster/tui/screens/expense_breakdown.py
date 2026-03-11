"""Expense breakdown widget — horizontal bar chart by category."""

import logging
from datetime import date
from typing import Any, Literal

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widgets import Button, Static

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.tui.modals.threshold_edit import ThresholdEditModal
from budget_forecaster.tui.symbols import DisplaySymbol

logger = logging.getLogger(__name__)

_ButtonVariant = Literal["default", "primary", "success", "warning", "error"]

# Period options: months only, labels are translated at render time
_PERIOD_MONTHS: tuple[int, ...] = (1, 3, 6, 12)


def _period_label(months: int) -> str:
    """Return a translated label for a period in months."""
    if months >= 12:
        years = months // 12
        return f"{years}{_('Y')}"
    return f"{months}{_('M')}"


_DEFAULT_PERIOD_MONTHS = 3
_BAR_CHAR = "\u2588"  # █
_MAX_BAR_WIDTH = 32


def _format_bar_line(
    name: str,
    monthly_avg: float,
    cumulative: float,
    grand_total: float,
    max_value: float,
    max_name_len: int,
) -> str:
    """Format a single bar line with name, bar, percentage, average and total."""
    pct = (monthly_avg / grand_total) * 100
    bar_width = int((monthly_avg / max_value) * _MAX_BAR_WIDTH)
    bar_str = _BAR_CHAR * max(1, bar_width)
    euro = DisplaySymbol.EURO
    return (
        f"  {name:<{max_name_len}}  {bar_str:<{_MAX_BAR_WIDTH}}  "
        f"{pct:4.0f}%  {monthly_avg:>10,.2f} {euro}  {cumulative:>10,.2f} {euro}"
    )


def _format_header(max_name_len: int) -> str:
    """Format the header line above the bar chart."""
    euro = DisplaySymbol.EURO
    avg_label = _("Avg/mo")
    total_label = _("Total")
    return (
        f"  {'':<{max_name_len}}  {'':<{_MAX_BAR_WIDTH}}  "
        f"      {avg_label:>10} {euro}  {total_label:>10} {euro}"
    )


class ExpenseBreakdownWidget(Vertical):
    """Horizontal bar chart showing expense distribution by category."""

    DEFAULT_CSS = """
    ExpenseBreakdownWidget {
        height: 1fr;
    }

    ExpenseBreakdownWidget #breakdown-header {
        height: 3;
        margin-bottom: 1;
    }

    ExpenseBreakdownWidget #breakdown-title {
        width: 1fr;
        text-style: bold;
        padding: 1 1;
    }

    ExpenseBreakdownWidget .period-btn {
        min-width: 5;
        margin-right: 1;
    }

    ExpenseBreakdownWidget .period-btn-active {
        min-width: 5;
        margin-right: 1;
    }

    ExpenseBreakdownWidget #breakdown-chart-center {
        height: 1fr;
    }

    ExpenseBreakdownWidget #breakdown-chart {
        height: 1fr;
        width: 120;
        border: solid $primary;
        padding: 1 2;
    }

    ExpenseBreakdownWidget #breakdown-status {
        dock: bottom;
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._period_months: int = _DEFAULT_PERIOD_MONTHS

    def compose(self) -> ComposeResult:
        with Horizontal(id="breakdown-header"):
            yield Static(_("Expense breakdown"), id="breakdown-title")
            for months in _PERIOD_MONTHS:
                btn_id = f"period-{months}"
                variant: _ButtonVariant = (
                    "primary" if months == _DEFAULT_PERIOD_MONTHS else "default"
                )
                yield Button(
                    _period_label(months),
                    id=btn_id,
                    variant=variant,
                    classes="period-btn",
                )
        with Center(id="breakdown-chart-center"):
            yield Static("", id="breakdown-chart")
        yield Static("", id="breakdown-status")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service

    def refresh_data(self) -> None:
        """Refresh the chart display."""
        self._update_chart()

    def compute_and_display(self) -> None:
        """Compute and display the expense breakdown chart."""
        self._update_chart()

    def _update_chart(self) -> None:
        """Update the bar chart with current period data."""
        chart = self.query_one("#breakdown-chart", Static)
        status = self.query_one("#breakdown-status", Static)

        if self._app_service is None:
            chart.update(_("No data"))
            return

        today = date.today()
        date_to = today.replace(day=1) - relativedelta(days=1)
        date_from = (date_to + relativedelta(days=1)) - relativedelta(
            months=self._period_months
        )

        category_totals = self._app_service.get_category_totals(
            OperationFilter(date_from=date_from, date_to=date_to, max_amount=0)
        )

        if not category_totals:
            chart.update(_("No expense data for this period"))
            status.update("")
            return

        threshold = self._app_service.expense_breakdown_threshold
        lines = self._render_bars(category_totals, threshold)
        chart.update("\n".join(lines))

        start_label = f"{_(date_from.strftime('%B'))} {date_from.year}"
        end_label = f"{_(date_to.strftime('%B'))} {date_to.year}"
        total = abs(sum(category_totals.values()))
        status.update(
            _("Period: {} — {} ({} months) — monthly average").format(
                start_label, end_label, self._period_months
            )
            + f"          {_('Total')}: {total:,.2f} {DisplaySymbol.EURO}"
        )

    def _render_bars(
        self,
        totals: dict[Category, float],
        threshold: float,
    ) -> list[str]:
        """Render horizontal bars for each category.

        Args:
            totals: Category -> total amount (negative for expenses).
            threshold: Minimum percentage to display individually.

        Returns:
            Lines of the bar chart.
        """
        # Convert to absolute values and compute monthly averages
        items = [
            (cat.display_name, abs(amount) / self._period_months)
            for cat, amount in totals.items()
        ]

        if (grand_total := sum(v for _, v in items)) == 0:
            return [_("No expense data for this period")]

        # Group small categories into "Other", merging with the real
        # "Other" category if it exists to avoid duplicate lines.
        other_label = _("Other")
        main_items: list[tuple[str, float]] = []
        other_total = 0.0
        for name, value in items:
            if (value / grand_total) * 100 < threshold or name == other_label:
                other_total += value
            else:
                main_items.append((name, value))

        if other_total > 0:
            main_items.append((other_label, other_total))

        # Sort by amount descending
        main_items.sort(key=lambda x: x[1], reverse=True)

        max_value = main_items[0][1] if main_items else 1
        max_name_len = max(len(name) for name, _ in main_items)

        lines = [_format_header(max_name_len)]
        lines.extend(
            _format_bar_line(
                name,
                value,
                value * self._period_months,
                grand_total,
                max_value,
                max_name_len,
            )
            for name, value in main_items
        )
        return lines

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle period button press."""
        button_id = event.button.id or ""
        if not button_id.startswith("period-"):
            return

        months = int(button_id.split("-")[1])
        self._period_months = months

        # Update button variants
        for period_months in _PERIOD_MONTHS:
            btn = self.query_one(f"#period-{period_months}", Button)
            btn.variant = "primary" if period_months == months else "default"

        self._update_chart()

    def edit_threshold(self) -> None:
        """Open modal to edit the breakdown threshold percentage."""
        if self._app_service is None:
            return
        current = self._app_service.expense_breakdown_threshold
        self.app.push_screen(
            ThresholdEditModal(
                current,
                title=_("Edit breakdown threshold"),
                unit="%",
            ),
            callback=self._on_threshold_result,
        )

    def _on_threshold_result(self, result: float | None) -> None:
        """Handle threshold edit result."""
        if result is None or self._app_service is None:
            return
        self._app_service.expense_breakdown_threshold = result
        self._update_chart()

    def on_resize(self) -> None:
        """Re-render chart when widget is resized."""
        if self._app_service is not None:
            self._update_chart()
