"""Tests for creating planned operations from historic operations."""

# pylint: disable=protected-access,too-few-public-methods

from datetime import date
from unittest.mock import Mock

from textual.app import App, ComposeResult

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.modals.planned_operation_edit import (
    PlannedOperationEditModal,
)
from budget_forecaster.tui.screens.operations import (
    OperationDetailPanel,
    OperationsScreen,
)


def _make_operation(
    unique_id: int = 1,
    description: str = "NETFLIX",
    amount: float = -17.99,
    category: Category = Category.ENTERTAINMENT,
    op_date: date | None = None,
) -> HistoricOperation:
    """Create a test operation."""
    return HistoricOperation(
        unique_id=unique_id,
        operation_date=op_date or date(2025, 1, 15),
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
    )


SAMPLE_OPERATIONS = (_make_operation(),)


def _make_app_service(
    operations: tuple[HistoricOperation, ...] = SAMPLE_OPERATIONS,
) -> Mock:
    """Create a mock ApplicationService."""
    service = Mock(spec=ApplicationService)
    service.get_operations = Mock(return_value=operations)
    service.get_all_links = Mock(return_value=())
    service.get_all_planned_operations = Mock(return_value=())
    service.get_all_budgets = Mock(return_value=())

    ops_by_id = {op.unique_id: op for op in operations}
    service.get_operation_by_id = Mock(side_effect=lambda uid: ops_by_id[uid])

    return service


class DetailPanelTestApp(App[None]):
    """Test app wrapping OperationsScreen to test detail panel."""

    def __init__(self) -> None:
        super().__init__()
        self._service = _make_app_service()

    def compose(self) -> ComposeResult:
        yield OperationsScreen(id="ops-screen")

    def on_mount(self) -> None:
        """Inject the mock service."""
        screen = self.query_one(OperationsScreen)
        screen.set_app_service(self._service)


class TestPlanOperationEditModalIsNew:
    """Tests for _is_new logic with pre-filled operations."""

    def test_is_new_when_no_operation(self) -> None:
        """Modal is new when no operation is passed."""
        modal = PlannedOperationEditModal(operation=None)
        assert modal._is_new is True

    def test_is_new_when_operation_has_no_id(self) -> None:
        """Modal is new when operation has no record_id (pre-filled from historic)."""
        prefilled = PlannedOperation(
            record_id=None,
            description="NETFLIX",
            amount=Amount(-17.99, "EUR"),
            category=Category.ENTERTAINMENT,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        modal = PlannedOperationEditModal(operation=prefilled)
        assert modal._is_new is True

    def test_is_not_new_when_operation_has_id(self) -> None:
        """Modal is not new when editing an existing operation."""
        existing = PlannedOperation(
            record_id=42,
            description="NETFLIX",
            amount=Amount(-17.99, "EUR"),
            category=Category.ENTERTAINMENT,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        modal = PlannedOperationEditModal(operation=existing)
        assert modal._is_new is False


class TestDetailPanelIntegration:
    """Integration tests for the operation detail panel."""

    async def test_detail_panel_shows_operation_on_highlight(self) -> None:
        """Detail panel updates when an operation is highlighted."""
        app = DetailPanelTestApp()
        async with app.run_test():
            detail = app.query_one(OperationDetailPanel)
            assert detail._operation_id is not None

    async def test_plan_button_visible_when_operation_highlighted(self) -> None:
        """The 'Create planned operation' button is visible after highlight."""
        app = DetailPanelTestApp()
        async with app.run_test():
            app.query_one("#btn-plan-operation")
            # Button should be in the visible container
            container = app.query_one("#action-buttons-container")
            assert "hidden" not in container.classes

    async def test_plan_button_posts_message(self) -> None:
        """Pressing the plan button emits PlanOperationRequested."""
        received: list[OperationDetailPanel.PlanOperationRequested] = []

        class CapturingApp(DetailPanelTestApp):
            """App that captures PlanOperationRequested messages."""

            def on_operation_detail_panel_plan_operation_requested(
                self, event: OperationDetailPanel.PlanOperationRequested
            ) -> None:
                """Capture the message."""
                received.append(event)

        app = CapturingApp()
        async with app.run_test() as pilot:
            btn = app.query_one("#btn-plan-operation")
            btn.press()
            await pilot.pause()
            assert len(received) == 1
            assert received[0].operation_id == 1


class TestPrefilledPlannedOperation:
    """Tests for building a pre-filled PlannedOperation from HistoricOperation."""

    def test_prefilled_operation_has_correct_fields(self) -> None:
        """Pre-filled operation copies description, amount, category, date."""
        historic = _make_operation(
            description="NETFLIX",
            amount=-17.99,
            category=Category.ENTERTAINMENT,
            op_date=date(2025, 1, 15),
        )

        prefilled = PlannedOperation(
            record_id=None,
            description=historic.description,
            amount=Amount(historic.amount, historic.currency),
            category=historic.category,
            date_range=SingleDay(historic.operation_date),
        )

        assert prefilled.id is None
        assert prefilled.description == "NETFLIX"
        assert prefilled.amount == -17.99
        assert prefilled.category == Category.ENTERTAINMENT
        assert prefilled.date_range.start_date == date(2025, 1, 15)
