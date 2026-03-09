"""Export forecast modal — date range selection for Excel export."""

import logging
from datetime import date
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from budget_forecaster.exceptions import AccountNotLoadedError, BudgetForecasterError
from budget_forecaster.i18n import _
from budget_forecaster.services.account.account_analysis_renderer import (
    AccountAnalysisRendererExcel,
)
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger(__name__)


class ExportForecastModal(ModalScreen[bool]):
    """Modal for exporting forecast to Excel with date range selection.

    Pre-filled with the cached report date range. If the user adjusts dates
    beyond the cached range, the export recomputes the forecast for the wider
    range before exporting.
    """

    DEFAULT_CSS = """
    ExportForecastModal {
        align: center middle;
    }

    ExportForecastModal #modal-container {
        width: 55;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    ExportForecastModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    ExportForecastModal .form-row {
        height: 3;
        margin-bottom: 1;
    }

    ExportForecastModal .form-label {
        width: 10;
        padding: 0 1;
    }

    ExportForecastModal .form-input {
        width: 1fr;
    }

    ExportForecastModal #buttons-row {
        height: 3;
        margin-top: 1;
    }

    ExportForecastModal Button {
        margin-left: 1;
    }

    ExportForecastModal #error-message {
        color: $error;
        height: 2;
        margin-top: 1;
    }

    ExportForecastModal #export-status {
        color: $warning;
        height: 1;
    }
    """

    BINDINGS = [("escape", "cancel", _("Cancel"))]

    def __init__(
        self,
        app_service: ApplicationService,
        default_start: date,
        default_end: date,
        **kwargs: Any,
    ) -> None:
        """Initialize the export modal.

        Args:
            app_service: The application service for computation and export.
            default_start: Default start date (from cached report).
            default_end: Default end date (from cached report).
        """
        super().__init__(**kwargs)
        self._app_service = app_service
        self._default_start = default_start
        self._default_end = default_end

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Static(_("Export forecast to Excel"), id="modal-title")

            with Horizontal(classes="form-row"):
                yield Label(_("From"), classes="form-label")
                yield Input(
                    value=self._default_start.isoformat(),
                    placeholder="YYYY-MM-DD",
                    id="input-start-date",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("To"), classes="form-label")
                yield Input(
                    value=self._default_end.isoformat(),
                    placeholder="YYYY-MM-DD",
                    id="input-end-date",
                    classes="form-input",
                )

            yield Static("", id="export-status")
            yield Static("", id="error-message")

            with Horizontal(id="buttons-row"):
                yield Button(_("Cancel"), id="btn-cancel", variant="default")
                yield Button(_("Export"), id="btn-export", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(False)
        elif event.button.id == "btn-export":
            self._export()

    def _parse_dates(self) -> tuple[date, date] | None:
        """Parse and validate date inputs."""
        error = self.query_one("#error-message", Static)
        error.update("")

        start_str = self.query_one("#input-start-date", Input).value.strip()
        end_str = self.query_one("#input-end-date", Input).value.strip()

        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except ValueError:
            error.update(_("Invalid date format (use YYYY-MM-DD)"))
            return None

        if start_date >= end_date:
            error.update(_("Start date must be before end date"))
            return None

        return start_date, end_date

    def _export(self) -> None:
        """Validate dates and export."""
        if (dates := self._parse_dates()) is None:
            return

        start_date, end_date = dates

        # Show computing state and defer to allow UI update
        status = self.query_one("#export-status", Static)
        btn = self.query_one("#btn-export", Button)
        btn.disabled = True
        status.update(_("Exporting..."))

        self.call_after_refresh(self._do_export, start_date, end_date)

    def _do_export(self, start_date: date, end_date: date) -> None:
        """Perform the export after UI refresh."""
        status = self.query_one("#export-status", Static)
        error = self.query_one("#error-message", Static)
        btn = self.query_one("#btn-export", Button)

        try:
            report = self._app_service.report

            # Recompute if requested range is wider than cached report
            if report is None or (
                start_date < report.start_date or end_date > report.end_date
            ):
                status.update(_("Computing..."))
                report = self._app_service.compute_report(start_date, end_date)

            output_path = Path(f"forecast-{date.today().isoformat()}.xlsx")

            with AccountAnalysisRendererExcel(output_path) as renderer:
                renderer(report)

            logger.info("Exported forecast to %s", output_path)
            self.app.notify(_("Exported to {}").format(output_path))
            self.dismiss(True)

        except AccountNotLoadedError as e:
            logger.error("No account loaded: %s", e)
            error.update(str(e))
        except BudgetForecasterError as e:
            logger.error("Error exporting forecast: %s", e)
            error.update(_("Export error: {}").format(e))
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error exporting forecast")
            error.update(_("An unexpected error occurred"))
        finally:
            btn.disabled = False
            status.update("")

    def action_cancel(self) -> None:
        """Cancel the export."""
        self.dismiss(False)
