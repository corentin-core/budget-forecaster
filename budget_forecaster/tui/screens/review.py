"""Review tab — monthly budget review (placeholder for PR2)."""

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger(__name__)


class ReviewWidget(Vertical):
    """Review tab: per-category planned vs actual for one month.

    This is a placeholder — the full monthly review table, margin section,
    and category drill-down will be implemented in subsequent PRs.
    """

    DEFAULT_CSS = """
    ReviewWidget {
        height: 1fr;
    }

    ReviewWidget #review-placeholder {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            _("Monthly review — coming in a future update"),
            id="review-placeholder",
        )

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service

    def refresh_data(self) -> None:
        """Refresh data — invalidate cached report so next tab open recomputes."""
        if self._app_service is not None:
            self._app_service.load_forecast()

    def compute_and_display(self) -> None:
        """Auto-compute forecast when tab becomes active.

        Triggers computation if no report is cached, then displays data.
        Placeholder — full implementation in PR2.
        """
        if self._app_service is None:
            return

        if self._app_service.report is not None:
            return

        # Trigger computation so the report is cached for Balance tab too
        try:
            self._app_service.compute_report()
        except BudgetForecasterError as e:
            logger.error("Error computing forecast: %s", e)
            self.app.notify(_("Error: {}").format(e), severity="error")
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error computing forecast")
            self.app.notify(_("An unexpected error occurred"), severity="error")
