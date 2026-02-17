"""Forecast screen for budget forecasting."""

import logging
from datetime import date
from pathlib import Path
from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

from budget_forecaster.exceptions import AccountNotLoadedError, BudgetForecasterError
from budget_forecaster.i18n import _
from budget_forecaster.services.account.account_analysis_renderer import (
    AccountAnalysisRendererExcel,
)
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger(__name__)


class ForecastWidget(Vertical):
    """Widget for displaying budget forecasts."""

    DEFAULT_CSS = """
    ForecastWidget {
        height: 1fr;
    }

    ForecastWidget #forecast-header {
        height: 3;
        margin-bottom: 1;
    }

    ForecastWidget #date-inputs {
        width: auto;
    }

    ForecastWidget .date-label {
        width: 5;
        padding: 0 1;
    }

    ForecastWidget .date-input {
        width: 16;
    }

    ForecastWidget #btn-compute {
        margin-left: 2;
    }

    ForecastWidget #forecast-status {
        height: 3;
        padding: 1;
        margin-bottom: 1;
    }

    ForecastWidget .status-ok {
        background: $success-darken-2;
    }

    ForecastWidget .status-warning {
        background: $warning-darken-2;
    }

    ForecastWidget .status-error {
        background: $error-darken-2;
    }

    ForecastWidget #balance-section {
        height: auto;
        max-height: 14;
        margin-bottom: 1;
    }

    ForecastWidget #balance-chart {
        height: 12;
        border: solid $primary;
        padding: 0 1;
    }

    ForecastWidget #tables-container {
        height: 1fr;
    }

    ForecastWidget #budget-table {
        height: 1fr;
    }

    ForecastWidget .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    ForecastWidget #table-legend {
        color: $text-muted;
        height: 1;
        margin-bottom: 1;
    }

    ForecastWidget .computing {
        color: $warning;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._start_date: date = date.today() - relativedelta(months=4)
        self._end_date: date = date.today() + relativedelta(months=12)

    def compose(self) -> ComposeResult:
        with Horizontal(id="forecast-header"):
            with Horizontal(id="date-inputs"):
                yield Static(_("From"), classes="date-label")
                yield Input(
                    value=self._start_date.isoformat(),
                    placeholder="YYYY-MM-DD",
                    id="start-date-input",
                    classes="date-input",
                )
                yield Static(_("to"), classes="date-label")
                yield Input(
                    value=self._end_date.isoformat(),
                    placeholder="YYYY-MM-DD",
                    id="end-date-input",
                    classes="date-input",
                )
            yield Button(_("Calculate"), id="btn-compute", variant="primary")
            yield Button(_("Export Excel"), id="btn-export", variant="default")

        yield Static("", id="forecast-status")

        with Vertical(id="balance-section"):
            yield Static(_("Balance evolution"), classes="section-title")
            yield Static("", id="balance-chart")

        with Vertical(id="tables-container"):
            yield Static(_("Budget by category"), classes="section-title")
            yield Static(
                _("R = Real | A = Adjusted | P = Planned"),
                id="table-legend",
            )
            yield DataTable(id="budget-table")

    def on_mount(self) -> None:
        """Initialize the tables."""
        budget_table = self.query_one("#budget-table", DataTable)
        budget_table.cursor_type = "row"

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service
        self._update_status()

    def refresh_data(self) -> None:
        """Refresh the forecast data from the database."""
        if self._app_service is not None:
            # Reload forecast from DB (budgets and planned operations may have changed)
            self._app_service.load_forecast()
        self._update_status()

    def _update_status(self) -> None:
        """Update the status display."""
        status = self.query_one("#forecast-status", Static)
        status.remove_class("status-ok", "status-warning", "status-error")

        if self._app_service is None:
            status.update(_("Service not initialized"))
            status.add_class("status-error")
            return

        self.query_one("#btn-compute", Button).disabled = False

        if self._app_service.report is None:
            status.update(_("Ready - Click 'Calculate' to generate forecasts"))
            status.add_class("status-ok")
            self.query_one("#btn-export", Button).disabled = True
        else:
            report = self._app_service.report
            status.update(
                _("Report calculated from {} to {}").format(
                    report.start_date, report.end_date
                )
            )
            status.add_class("status-ok")
            self.query_one("#btn-export", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-compute":
            self._compute_forecast()
        elif event.button.id == "btn-export":
            self._export_to_excel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in date inputs."""
        if event.input.id in ("start-date-input", "end-date-input"):
            self._compute_forecast()

    def _parse_dates(self) -> tuple[date, date] | None:
        """Parse and validate date inputs."""
        start_input = self.query_one("#start-date-input", Input)
        end_input = self.query_one("#end-date-input", Input)

        try:
            start_date = date.fromisoformat(start_input.value.strip())
            end_date = date.fromisoformat(end_input.value.strip())
        except ValueError:
            self.app.notify(_("Invalid date format (use YYYY-MM-DD)"), severity="error")
            return None

        if start_date >= end_date:
            self.app.notify(_("Start date must be before end date"), severity="error")
            return None

        return start_date, end_date

    def _compute_forecast(self) -> None:
        """Compute the forecast report."""
        if self._app_service is None:
            return

        if (dates := self._parse_dates()) is None:
            return

        start_date, end_date = dates
        logger.info("Computing forecast from %s to %s", start_date, end_date)

        # Show loading state
        btn = self.query_one("#btn-compute", Button)
        btn_export = self.query_one("#btn-export", Button)
        status = self.query_one("#forecast-status", Static)

        btn.label = _("Calculating...")
        btn.disabled = True
        btn_export.disabled = True
        status.update(_("Calculating forecasts..."))
        status.add_class("computing")

        # Use call_after_refresh to allow UI to update before blocking computation
        self.call_after_refresh(self._do_compute, start_date, end_date)

    def _do_compute(self, start_date: date, end_date: date) -> None:
        """Actually perform the computation after UI refresh."""
        btn = self.query_one("#btn-compute", Button)
        status = self.query_one("#forecast-status", Static)

        try:
            if self._app_service is not None:
                self._app_service.compute_report(start_date, end_date)
            self._refresh_display()
            self.app.notify(_("Forecasts calculated"))
        except AccountNotLoadedError as e:
            logger.error("No account loaded: %s", e)
            self.app.notify(f"{e}", severity="error")
            self._update_status()
        except BudgetForecasterError as e:
            logger.error("Error computing forecast: %s", e)
            self.app.notify(_("Error: {}").format(e), severity="error")
            self._update_status()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error computing forecast")
            self.app.notify(_("An unexpected error occurred"), severity="error")
            self._update_status()
        finally:
            # Restore button state
            btn.label = _("Calculate")
            btn.disabled = False
            status.remove_class("computing")

    def _refresh_display(self) -> None:
        """Refresh the display with computed data."""
        self._update_status()
        self._update_balance_chart()
        self._update_budget_table()

    def _update_balance_chart(self) -> None:
        """Update the balance evolution chart."""
        if self._app_service is None or self._app_service.report is None:
            return

        chart = self.query_one("#balance-chart", Static)
        if not (balance_data := self._app_service.get_balance_evolution_summary()):
            chart.update(_("No data"))
            return

        # Create a simple ASCII chart
        chart_lines = self._render_ascii_chart(balance_data)
        chart.update("\n".join(chart_lines))

    def _render_ascii_chart(  # pylint: disable=too-many-locals
        self, data: list[tuple[date, float]], width: int = 70, height: int = 8
    ) -> list[str]:
        """Render a simple ASCII line chart with axes."""
        if not data:
            return [_("No data")]

        values = [v for _d, v in data]
        raw_min = min(values)
        raw_max = max(values)

        # Round to nice multiples of 100€ for Y-axis
        min_val = (raw_min // 100) * 100
        max_val = ((raw_max // 100) + 1) * 100
        val_range = max_val - min_val if max_val != min_val else 100

        # Fixed Y-axis label width
        y_label_width = 12

        # Sample data to fit width
        target_width = min(width, 60)
        step = max(1, len(data) // target_width)
        display_data = [data[i] for i in range(0, len(data), step)]

        lines = []

        # Chart body with Y-axis labels
        for row in range(height - 1, -1, -1):
            y_value = min_val + (val_range * row / (height - 1))
            y_rounded = round(y_value / 100) * 100
            y_label = f"{y_rounded:>10,.0f} €"

            threshold = y_value
            line_chars = []
            for _d, val in display_data:
                if val >= threshold:
                    line_chars.append("█")
                elif val >= threshold - (val_range / height / 2):
                    line_chars.append("▄")
                else:
                    line_chars.append(" ")
            lines.append(f"{y_label} │{''.join(line_chars)}")

        # X-axis line
        chart_len = len(display_data)
        lines.append(" " * y_label_width + " └" + "─" * chart_len)

        # X-axis with dates - simple format below the chart
        if len(display_data) >= 2:
            first_date = display_data[0][0].strftime("%m/%Y")
            last_date = display_data[-1][0].strftime("%m/%Y")
            mid_idx = len(display_data) // 2
            mid_date = display_data[mid_idx][0].strftime("%m/%Y")

            # Build date line with proper spacing
            spacing = max(1, (chart_len - 21) // 2)  # 21 = 3 dates * 7 chars
            date_line = (
                f"{first_date}{' ' * spacing}{mid_date}{' ' * spacing}{last_date}"
            )
            lines.append(" " * (y_label_width + 2) + date_line)

        return lines

    def _update_budget_table(self) -> None:  # pylint: disable=too-many-locals
        """Update the budget forecast table with multi-columns per month."""
        if self._app_service is None or self._app_service.report is None:
            return

        table = self.query_one("#budget-table", DataTable)
        table.clear(columns=True)

        # Get budget forecast data
        df = self._app_service.report.budget_forecast

        if df.empty:
            return

        # Add category column
        table.add_column(_("Category"), key="category")

        # Build column structure from DataFrame columns
        # Columns are (month, type) tuples where type is "Actual", "Forecast", or "Adjusted"
        columns_info: list[tuple] = []  # (month, type, column_key, column_label)

        for col in df.columns:
            month = col[0]  # pandas Timestamp
            col_type = str(col[1])  # "Actual", "Forecast", or "Adjusted"
            month_str = month.strftime("%Y-%m")  # type: ignore[attr-defined]
            type_abbrev = {"Actual": "R", "Forecast": "P", "Adjusted": "A"}.get(
                col_type, col_type[0]
            )
            col_key = f"{month_str}_{type_abbrev}"
            col_label = f"{month_str} {type_abbrev}"
            columns_info.append((month, col_type, col_key, col_label))

        # Sort columns by month then by type order (R, A, P)
        type_order = {"Actual": 0, "Adjusted": 1, "Forecast": 2}
        columns_info.sort(key=lambda x: (x[0], type_order.get(x[1], 3)))

        # Add columns to table
        for _m, _t, col_key, col_label in columns_info:
            table.add_column(col_label, key=col_key)

        # Add rows
        for category in df.index:
            row_values = [
                category.display_name
                if hasattr(category, "display_name")
                else str(category)
            ]
            for month, col_type, _k, _l in columns_info:
                try:
                    if (value := df.loc[category, (month, col_type)]) != 0:
                        row_values.append(f"{int(value):,}")
                    else:
                        row_values.append("-")
                except KeyError:
                    row_values.append("-")

            table.add_row(*row_values, key=str(category))

    def _export_to_excel(self) -> None:
        """Export the forecast to Excel."""
        if self._app_service is None or self._app_service.report is None:
            self.app.notify(_("No report to export"), severity="warning")
            return

        report = self._app_service.report
        output_path = Path(f"forecast-{date.today().isoformat()}.xlsx")

        try:
            with AccountAnalysisRendererExcel(output_path) as renderer:
                renderer(report)
            logger.info("Exported forecast to %s", output_path)
            self.app.notify(_("Exported to {}").format(output_path))
        except BudgetForecasterError as e:
            logger.error("Error exporting forecast: %s", e)
            self.app.notify(_("Export error: {}").format(e), severity="error")
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error exporting forecast")
            self.app.notify(_("An unexpected error occurred"), severity="error")
