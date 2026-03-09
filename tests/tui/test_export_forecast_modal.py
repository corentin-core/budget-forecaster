"""Tests for ExportForecastModal."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Static

from budget_forecaster.tui.modals.export_forecast import ExportForecastModal


class ExportModalTestApp(App[None]):
    """Test app for ExportForecastModal."""

    def __init__(self, app_service: MagicMock) -> None:
        super().__init__()
        self._app_service = app_service
        self.modal_result: bool | None = None

    def compose(self) -> ComposeResult:
        yield Static("Host")

    def on_mount(self) -> None:
        """Push the export modal."""
        report = self._app_service.report
        self.push_screen(
            ExportForecastModal(
                app_service=self._app_service,
                default_start=report.start_date,
                default_end=report.end_date,
            ),
            self._on_dismiss,
        )

    def _on_dismiss(self, result: bool) -> None:
        self.modal_result = result


def _make_app_service() -> MagicMock:
    """Create a mock ApplicationService with a cached report."""
    app_service = MagicMock()
    report = MagicMock()
    report.start_date = date(2025, 6, 1)
    report.end_date = date(2026, 6, 1)
    app_service.report = report
    return app_service


@pytest.mark.asyncio
async def test_modal_prefilled_with_report_dates() -> None:
    """Date inputs are pre-filled with the cached report date range."""
    app_service = _make_app_service()

    app = ExportModalTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.pause()

        start_input = app.screen.query_one("#input-start-date", Input)
        end_input = app.screen.query_one("#input-end-date", Input)

        assert start_input.value == "2025-06-01"
        assert end_input.value == "2026-06-01"


@pytest.mark.asyncio
async def test_cancel_dismisses_modal() -> None:
    """Cancel button dismisses the modal with False."""
    app_service = _make_app_service()

    app = ExportModalTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#btn-cancel")
        await pilot.pause()

        assert app.modal_result is False


@pytest.mark.asyncio
async def test_escape_dismisses_modal() -> None:
    """Escape key dismisses the modal."""
    app_service = _make_app_service()

    app = ExportModalTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.modal_result is False


@pytest.mark.asyncio
async def test_invalid_date_keeps_modal_open() -> None:
    """Invalid date format prevents export and keeps the modal open."""
    app_service = _make_app_service()

    app = ExportModalTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Set invalid date
        start_input = app.screen.query_one("#input-start-date", Input)
        start_input.value = "not-a-date"

        await pilot.click("#btn-export")
        await pilot.pause()

        # Modal should still be open (not dismissed)
        assert isinstance(app.screen, ExportForecastModal)
        assert app.modal_result is None


@pytest.mark.asyncio
async def test_start_after_end_keeps_modal_open() -> None:
    """Start date after end date prevents export and keeps the modal open."""
    app_service = _make_app_service()

    app = ExportModalTestApp(app_service)
    async with app.run_test() as pilot:
        await pilot.pause()

        start_input = app.screen.query_one("#input-start-date", Input)
        end_input = app.screen.query_one("#input-end-date", Input)
        start_input.value = "2027-01-01"
        end_input.value = "2026-01-01"

        await pilot.click("#btn-export")
        await pilot.pause()

        # Modal should still be open (not dismissed)
        assert isinstance(app.screen, ExportForecastModal)
        assert app.modal_result is None


@pytest.mark.asyncio
async def test_export_within_cached_range_does_not_recompute() -> None:
    """Export within the cached range does not call compute_report."""
    app_service = _make_app_service()

    with patch(
        "budget_forecaster.tui.modals.export_forecast.AccountAnalysisRendererExcel"
    ) as mock_renderer_cls:
        mock_renderer = MagicMock()
        mock_renderer_cls.return_value.__enter__ = MagicMock(return_value=mock_renderer)
        mock_renderer_cls.return_value.__exit__ = MagicMock(return_value=False)

        app = ExportModalTestApp(app_service)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-export")
            await pilot.pause()

            app_service.compute_report.assert_not_called()
            mock_renderer.assert_called_once()


@pytest.mark.asyncio
async def test_export_wider_range_recomputes() -> None:
    """Export with dates wider than cached range triggers recomputation."""
    app_service = _make_app_service()

    # compute_report returns a new report
    new_report = MagicMock()
    app_service.compute_report.return_value = new_report

    with patch(
        "budget_forecaster.tui.modals.export_forecast.AccountAnalysisRendererExcel"
    ) as mock_renderer_cls:
        mock_renderer = MagicMock()
        mock_renderer_cls.return_value.__enter__ = MagicMock(return_value=mock_renderer)
        mock_renderer_cls.return_value.__exit__ = MagicMock(return_value=False)

        app = ExportModalTestApp(app_service)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Widen the start date beyond cached range
            start_input = app.screen.query_one("#input-start-date", Input)
            start_input.value = "2024-01-01"

            await pilot.click("#btn-export")
            await pilot.pause()

            app_service.compute_report.assert_called_once_with(
                date(2024, 1, 1), date(2026, 6, 1)
            )
            mock_renderer.assert_called_once_with(new_report)
