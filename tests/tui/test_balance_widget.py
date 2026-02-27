"""Tests for BalanceWidget (formerly ForecastWidget)."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from budget_forecaster.tui.modals.export_forecast import ExportForecastModal
from budget_forecaster.tui.screens.balance import BalanceWidget


class BalanceTestApp(App[None]):
    """Test app containing a BalanceWidget."""

    def __init__(self, app_service: MagicMock) -> None:
        super().__init__()
        self._app_service = app_service

    def compose(self) -> ComposeResult:
        yield BalanceWidget(id="balance-widget")

    def on_mount(self) -> None:
        """Inject app_service into the widget."""
        widget = self.query_one(BalanceWidget)
        widget.set_app_service(self._app_service)


def _make_app_service(*, has_report: bool = False) -> MagicMock:
    """Create a mock ApplicationService."""
    app_service = MagicMock()

    if has_report:
        report = MagicMock()
        report.start_date = date(2025, 6, 1)
        report.end_date = date(2026, 6, 1)
        app_service.report = report
    else:
        app_service.report = None

    app_service.get_balance_evolution_summary.return_value = [
        (date(2025, 6, 1), 3000.0),
        (date(2025, 12, 1), 2500.0),
        (date(2026, 6, 1), 3500.0),
    ]
    return app_service


@pytest.mark.asyncio
async def test_export_button_disabled_without_report() -> None:
    """Export button is disabled when no report has been computed."""
    app_service = _make_app_service(has_report=False)
    app = BalanceTestApp(app_service)

    async with app.run_test():
        btn = app.query_one("#btn-export", Button)
        assert btn.disabled is True


@pytest.mark.asyncio
async def test_export_button_enabled_with_report() -> None:
    """Export button is enabled when a report is available."""
    app_service = _make_app_service(has_report=True)
    app = BalanceTestApp(app_service)

    async with app.run_test():
        btn = app.query_one("#btn-export", Button)
        assert btn.disabled is False


@pytest.mark.asyncio
async def test_compute_and_display_triggers_computation() -> None:
    """compute_and_display triggers compute_report when no report is cached."""
    app_service = _make_app_service(has_report=False)

    # After compute_report, set a report
    def set_report(*_args: object, **_kwargs: object) -> MagicMock:
        report = MagicMock()
        report.start_date = date(2025, 6, 1)
        report.end_date = date(2026, 6, 1)
        app_service.report = report
        return report

    app_service.compute_report.side_effect = set_report

    app = BalanceTestApp(app_service)
    async with app.run_test() as pilot:
        widget = app.query_one(BalanceWidget)
        widget.compute_and_display()
        await pilot.pause()

        app_service.compute_report.assert_called_once()


@pytest.mark.asyncio
async def test_compute_and_display_skips_if_report_cached() -> None:
    """compute_and_display does not recompute if a report already exists."""
    app_service = _make_app_service(has_report=True)

    app = BalanceTestApp(app_service)
    async with app.run_test() as pilot:
        widget = app.query_one(BalanceWidget)
        widget.compute_and_display()
        await pilot.pause()

        app_service.compute_report.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_data_calls_load_forecast() -> None:
    """refresh_data calls load_forecast to invalidate the cache."""
    app_service = _make_app_service(has_report=True)

    app = BalanceTestApp(app_service)
    async with app.run_test():
        widget = app.query_one(BalanceWidget)
        widget.refresh_data()

        app_service.load_forecast.assert_called_once()


@pytest.mark.asyncio
async def test_chart_updates_after_compute() -> None:
    """Chart update is called after computation completes."""
    app_service = _make_app_service(has_report=False)

    def set_report(*_args: object, **_kwargs: object) -> MagicMock:
        report = MagicMock()
        report.start_date = date(2025, 6, 1)
        report.end_date = date(2026, 6, 1)
        app_service.report = report
        return report

    app_service.compute_report.side_effect = set_report

    app = BalanceTestApp(app_service)
    async with app.run_test() as pilot:
        widget = app.query_one(BalanceWidget)
        widget.compute_and_display()
        await pilot.pause()

        # Verify that balance evolution data was requested for the chart
        app_service.get_balance_evolution_summary.assert_called()


@pytest.mark.asyncio
async def test_export_button_opens_modal() -> None:
    """Clicking Export opens the ExportForecastModal."""
    app_service = _make_app_service(has_report=True)

    app = BalanceTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.click("#btn-export")
        await pilot.pause()

        # Modal should be pushed onto the screen stack
        assert any(
            isinstance(screen, ExportForecastModal) for screen in app.screen_stack
        )
