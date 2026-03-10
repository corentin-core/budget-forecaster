"""Tests for editing planned sources from CategoryDetailModal."""

# pylint: disable=too-few-public-methods

from datetime import date
from unittest.mock import Mock

import pytest
from dateutil.relativedelta import relativedelta
from textual.app import App, ComposeResult
from textual.containers import Container

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import (
    CategoryDetail,
    ForecastSourceType,
    PlannedSourceDetail,
)
from budget_forecaster.tui.modals.budget_edit import BudgetEditModal
from budget_forecaster.tui.modals.category_detail import CategoryDetailModal
from budget_forecaster.tui.modals.planned_operation_edit import (
    PlannedOperationEditModal,
)


def _make_budget(budget_id: int = 1) -> Budget:
    """Create a test budget."""
    return Budget(
        record_id=budget_id,
        description="Groceries budget",
        amount=Amount(-400.0, "EUR"),
        category=Category.GROCERIES,
        date_range=RecurringDay(
            date(2025, 1, 1),
            period=relativedelta(months=1),
        ),
    )


def _make_planned_operation(op_id: int = 2) -> PlannedOperation:
    """Create a test planned operation."""
    return PlannedOperation(
        record_id=op_id,
        description="Weekly groceries",
        amount=Amount(-100.0, "EUR"),
        category=Category.GROCERIES,
        date_range=RecurringDay(
            date(2025, 1, 1),
            period=relativedelta(months=1),
        ),
    )


def _make_detail(
    budget_id: int | None = 1,
    planned_op_id: int | None = 2,
) -> CategoryDetail:
    """Create a CategoryDetail with planned sources."""
    sources: list[PlannedSourceDetail] = []
    if budget_id is not None:
        sources.append(
            PlannedSourceDetail(
                source_id=budget_id,
                forecast_source_type=ForecastSourceType.BUDGET,
                description="Groceries budget",
                periodicity="400/month",
                amount=-400.0,
                iteration_day=1,
            )
        )
    if planned_op_id is not None:
        sources.append(
            PlannedSourceDetail(
                source_id=planned_op_id,
                forecast_source_type=ForecastSourceType.PLANNED_OPERATION,
                description="Weekly groceries",
                periodicity="monthly, 1st",
                amount=-100.0,
                iteration_day=1,
            )
        )
    return CategoryDetail(
        category=Category.GROCERIES,
        month=date(2025, 2, 1),
        planned_sources=tuple(sources),
        operations=(),
        total_planned=-500.0,
        total_actual=0.0,
        forecast=0.0,
        remaining=0.0,
        is_income=False,
    )


def _make_app_service(
    budget: Budget | None = None,
    planned_op: PlannedOperation | None = None,
) -> Mock:
    """Create a mock ApplicationService."""
    service = Mock(spec=ApplicationService)
    service.get_budget_by_id = Mock(return_value=budget)
    service.get_planned_operation_by_id = Mock(return_value=planned_op)
    service.update_budget = Mock()
    service.update_planned_operation = Mock()
    service.get_category_detail = Mock(return_value=_make_detail())
    return service


class CategoryDetailEditTestApp(App[None]):
    """Test app for CategoryDetailModal edit actions."""

    def __init__(self, detail: CategoryDetail, app_service: Mock) -> None:
        super().__init__()
        self._detail = detail
        self._app_service = app_service

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self) -> None:
        """Open the category detail modal."""
        self.push_screen(
            CategoryDetailModal(self._detail, app_service=self._app_service)
        )


class TestSourceRowFocus:
    """Tests for source row focus and navigation."""

    @pytest.mark.asyncio
    async def test_source_rows_are_focusable(self) -> None:
        """Source rows can receive focus."""
        detail = _make_detail()
        service = _make_app_service()

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            source_rows = app.screen.query(".source-row")
            assert len(source_rows) == 2
            for row in source_rows:
                assert row.can_focus is True

    @pytest.mark.asyncio
    async def test_source_row_name_contains_type_and_id(self) -> None:
        """Source row name encodes the source type and ID."""
        detail = _make_detail(budget_id=10, planned_op_id=20)
        service = _make_app_service()

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            source_rows = app.screen.query(".source-row")
            names = {row.name for row in source_rows}
            assert "BUDGET:10" in names
            assert "PLANNED_OPERATION:20" in names


class TestEditFromSourceRow:
    """Tests for opening edit modals from source rows."""

    @pytest.mark.asyncio
    async def test_enter_on_budget_row_opens_budget_edit(self) -> None:
        """Pressing Enter on a budget source row opens BudgetEditModal."""
        budget = _make_budget(budget_id=1)
        detail = _make_detail(budget_id=1, planned_op_id=None)
        service = _make_app_service(budget=budget)

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            # Focus the source row
            source_row = app.screen.query_one(".source-row")
            source_row.focus()
            await pilot.pause()

            # Press Enter to open edit
            await pilot.press("enter")
            await pilot.pause()

            # BudgetEditModal should be on the screen stack
            assert isinstance(app.screen, BudgetEditModal)
            service.get_budget_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_enter_on_planned_op_row_opens_planned_edit(self) -> None:
        """Pressing Enter on a planned op source row opens PlannedOperationEditModal."""
        planned_op = _make_planned_operation(op_id=2)
        detail = _make_detail(budget_id=None, planned_op_id=2)
        service = _make_app_service(planned_op=planned_op)

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            source_row = app.screen.query_one(".source-row")
            source_row.focus()
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, PlannedOperationEditModal)
            service.get_planned_operation_by_id.assert_called_once_with(2)


class TestRefreshAfterEdit:
    """Tests for modal refresh after editing a source."""

    @pytest.mark.asyncio
    async def test_budget_save_refreshes_detail(self) -> None:
        """After saving a budget edit, category detail is refreshed."""
        budget = _make_budget(budget_id=1)
        detail = _make_detail(budget_id=1, planned_op_id=None)
        service = _make_app_service(budget=budget)

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            source_row = app.screen.query_one(".source-row")
            source_row.focus()
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            # Dismiss the edit modal with a budget result
            assert isinstance(app.screen, BudgetEditModal)
            app.screen.dismiss(budget)
            await pilot.pause()

            # update_budget should have been called
            service.update_budget.assert_called_once_with(budget)
            # get_category_detail should have been called to refresh
            service.get_category_detail.assert_called_once()

    @pytest.mark.asyncio
    async def test_planned_op_save_refreshes_detail(self) -> None:
        """After saving a planned op edit, category detail is refreshed."""
        planned_op = _make_planned_operation(op_id=2)
        detail = _make_detail(budget_id=None, planned_op_id=2)
        service = _make_app_service(planned_op=planned_op)

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            source_row = app.screen.query_one(".source-row")
            source_row.focus()
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, PlannedOperationEditModal)
            app.screen.dismiss(planned_op)
            await pilot.pause()

            service.update_planned_operation.assert_called_once_with(planned_op)
            service.get_category_detail.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_edit_does_not_refresh(self) -> None:
        """Cancelling the edit modal does not refresh the detail."""
        budget = _make_budget(budget_id=1)
        detail = _make_detail(budget_id=1, planned_op_id=None)
        service = _make_app_service(budget=budget)

        app = CategoryDetailEditTestApp(detail, service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            source_row = app.screen.query_one(".source-row")
            source_row.focus()
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            # Cancel the edit
            assert isinstance(app.screen, BudgetEditModal)
            app.screen.dismiss(None)
            await pilot.pause()

            service.update_budget.assert_not_called()
            service.get_category_detail.assert_not_called()
