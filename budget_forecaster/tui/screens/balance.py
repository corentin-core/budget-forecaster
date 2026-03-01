"""Balance tab — full-height chart + export button."""

import logging
from datetime import date
from typing import Any

from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widgets import Button, Static

from budget_forecaster.exceptions import AccountNotLoadedError, BudgetForecasterError
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.modals.export_forecast import ExportForecastModal

logger = logging.getLogger(__name__)


class BalanceWidget(Vertical):
    """Balance tab: chart showing balance evolution over time."""

    DEFAULT_CSS = """
    BalanceWidget {
        height: 1fr;
    }

    BalanceWidget #balance-header {
        height: 3;
        margin-bottom: 1;
    }

    BalanceWidget #balance-title {
        width: 1fr;
        text-style: bold;
        padding: 1 1;
    }

    BalanceWidget #btn-export {
        margin-right: 1;
    }

    BalanceWidget #balance-chart-center {
        height: 1fr;
    }

    BalanceWidget #balance-chart {
        height: 1fr;
        width: 120;
        border: solid $primary;
        padding: 0 1;
    }

    BalanceWidget #balance-status {
        dock: bottom;
        height: 1;
        color: $text-muted;
    }

    BalanceWidget .computing {
        color: $warning;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="balance-header"):
            yield Static(_("Balance evolution"), id="balance-title")
            yield Button(_("Export"), id="btn-export", variant="default")
        with Center(id="balance-chart-center"):
            yield Static("", id="balance-chart")
        yield Static("", id="balance-status")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and update display."""
        self._app_service = service
        self._update_export_button()

    def refresh_data(self) -> None:
        """Refresh data — invalidate cached report so next tab open recomputes."""
        if self._app_service is not None:
            self._app_service.load_forecast()
        self._update_export_button()

    def compute_and_display(self) -> None:
        """Auto-compute forecast and display the chart.

        Called when the tab becomes active and no report is cached.
        """
        if self._app_service is None:
            return

        if self._app_service.report is not None:
            self._refresh_display()
            return

        # Show computing state
        status = self.query_one("#balance-status", Static)
        status.update(_("Computing..."))
        status.add_class("computing")
        self.query_one("#btn-export", Button).disabled = True

        self.call_after_refresh(self._do_compute)

    def _do_compute(self) -> None:
        """Perform the computation after UI refresh."""
        status = self.query_one("#balance-status", Static)

        try:
            if self._app_service is not None:
                self._app_service.compute_report()
            self._refresh_display()
        except AccountNotLoadedError as e:
            logger.error("No account loaded: %s", e)
            self.app.notify(f"{e}", severity="error")
        except BudgetForecasterError as e:
            logger.error("Error computing forecast: %s", e)
            self.app.notify(_("Error: {}").format(e), severity="error")
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error computing forecast")
            self.app.notify(_("An unexpected error occurred"), severity="error")
        finally:
            status.remove_class("computing")
            status.update("")
            self._update_export_button()

    def _refresh_display(self) -> None:
        """Refresh chart and status after computation."""
        self._update_balance_chart()
        self._update_status()
        self._update_export_button()

    def _update_export_button(self) -> None:
        """Enable/disable export button based on report availability."""
        has_report = (
            self._app_service is not None and self._app_service.report is not None
        )
        self.query_one("#btn-export", Button).disabled = not has_report

    def _update_status(self) -> None:
        """Update the status bar with report date range."""
        status = self.query_one("#balance-status", Static)
        if self._app_service is None or self._app_service.report is None:
            status.update("")
            return

        report = self._app_service.report
        status.update(_("Report: {} to {}").format(report.start_date, report.end_date))

    def _update_balance_chart(self) -> None:
        """Update the balance evolution chart."""
        if self._app_service is None or self._app_service.report is None:
            return

        chart = self.query_one("#balance-chart", Static)
        if not (balance_data := self._app_service.get_balance_evolution_summary()):
            chart.update(_("No data"))
            return

        # Use available widget dimensions (minus border/padding)
        chart_height = max(8, chart.content_size.height - 2)  # -2 for axis + date line
        chart_width = max(20, chart.content_size.width - 15)  # -15 for Y-axis labels
        chart_lines = self._render_ascii_chart(
            balance_data, width=chart_width, height=chart_height
        )
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
        step = max(1, len(data) // width)
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

    def on_resize(self) -> None:
        """Re-render chart when widget is resized."""
        if self._app_service is not None and self._app_service.report is not None:
            self._update_balance_chart()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle export button press."""
        if event.button.id == "btn-export":
            self._open_export_modal()

    def _open_export_modal(self) -> None:
        """Open the export forecast modal."""
        if self._app_service is None or self._app_service.report is None:
            self.app.notify(_("No report to export"), severity="warning")
            return

        report = self._app_service.report
        self.app.push_screen(
            ExportForecastModal(
                app_service=self._app_service,
                default_start=report.start_date,
                default_end=report.end_date,
            )
        )
