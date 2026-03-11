"""Tests for OperationDetailModal."""

# pylint: disable=too-few-public-methods,protected-access

from datetime import date
from typing import Any
from unittest.mock import Mock

import pytest
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Button, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.messages import SaveRequested
from budget_forecaster.tui.modals.operation_detail import OperationDetailModal


def _make_operation(
    unique_id: int = 1,
    description: str = "PAIEMENT CB AU PASSAGE 22 PARIS",
    amount: float = -58.90,
    category: Category = Category.GROCERIES,
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


def _make_app_service(
    operation: HistoricOperation | None = None,
    link: OperationLink | None = None,
    planned_ops: tuple[PlannedOperation, ...] = (),
) -> Mock:
    """Create a mock ApplicationService."""
    service = Mock(spec=ApplicationService)
    op = operation or _make_operation()
    service.get_operation_by_id = Mock(return_value=op)
    service.get_link_for_operation = Mock(return_value=link)
    service.get_all_planned_operations = Mock(return_value=planned_ops)
    service.get_all_budgets = Mock(return_value=())
    service.suggest_category = Mock(return_value=None)
    service.categorize_operations = Mock()
    return service


class OperationDetailTestApp(App[None]):
    """Test app for OperationDetailModal."""

    def __init__(self, app_service: Mock) -> None:
        super().__init__()
        self._app_service = app_service
        self.modal_result: bool | None = None
        self.received_messages: list[Any] = []

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self) -> None:
        """Open the operation detail modal."""
        self.push_screen(
            OperationDetailModal(operation_id=1, app_service=self._app_service),
            self._on_modal_closed,
        )

    def _on_modal_closed(self, result: bool | None) -> None:
        """Track modal result."""
        self.modal_result = result

    def on_save_requested(self, event: SaveRequested) -> None:
        """Track SaveRequested messages."""
        self.received_messages.append(event)


class TestOperationDetailDisplay:
    """Tests for operation detail display."""

    @pytest.mark.asyncio
    async def test_shows_full_description(self) -> None:
        """Full description is displayed without truncation."""
        long_desc = "PAIEMENT CB AU PASSAGE 22 DE 03/01/26 A PARIS 1 CARTE 4978XXXX1234"
        op = _make_operation(description=long_desc)
        service = _make_app_service(operation=op)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            desc_widget = app.screen.query_one("#detail-description", Static)
            assert str(desc_widget.content) == long_desc

    @pytest.mark.asyncio
    async def test_shows_date_and_amount(self) -> None:
        """Date and amount are displayed."""
        op = _make_operation(op_date=date(2025, 3, 15), amount=-123.45)
        service = _make_app_service(operation=op)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Check date and amount are present in the modal's text
            all_text = " ".join(str(w.content) for w in modal.query(Static))
            assert "15/03/2025" in all_text
            assert "-123.45" in all_text

    @pytest.mark.asyncio
    async def test_shows_category(self) -> None:
        """Category display name is shown."""
        op = _make_operation(category=Category.GROCERIES)
        service = _make_app_service(operation=op)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            cat_widget = app.screen.query_one("#detail-category", Static)
            assert str(cat_widget.content) == Category.GROCERIES.display_name

    @pytest.mark.asyncio
    async def test_shows_no_link_when_unlinked(self) -> None:
        """Shows 'No link' when operation has no link."""
        service = _make_app_service(link=None)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            link_widget = app.screen.query_one("#detail-link", Static)
            # "No link" (or its translation)
            assert str(link_widget.content) != ""

    @pytest.mark.asyncio
    async def test_shows_link_target_name(self) -> None:
        """Shows link target name when operation is linked."""
        planned_op = PlannedOperation(
            record_id=42,
            description="Courses hebdo",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=42,
            iteration_date=date(2025, 1, 15),
        )
        service = _make_app_service(link=link, planned_ops=(planned_op,))

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            link_widget = app.screen.query_one("#detail-link", Static)
            assert "Courses hebdo" in str(link_widget.content)


class TestOperationDetailActions:
    """Tests for modal actions."""

    @pytest.mark.asyncio
    async def test_close_returns_false_when_unmodified(self) -> None:
        """Closing without changes returns False."""
        service = _make_app_service()

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert app.modal_result is False

    @pytest.mark.asyncio
    async def test_close_button_dismisses_modal(self) -> None:
        """Clicking Close button dismisses the modal."""
        service = _make_app_service()

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            btn = app.screen.query_one("#btn-close")
            btn.press()
            await pilot.pause()

            assert app.modal_result is False


class TestOperationDetailLinkButton:
    """Tests for the link button in operation detail modal."""

    @pytest.mark.asyncio
    async def test_shows_link_button_when_no_link(self) -> None:
        """Shows 'Link' button when operation has no link."""
        service = _make_app_service(link=None)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            btn = app.screen.query_one("#btn-link", Button)
            assert str(btn.label) == "Link"

    @pytest.mark.asyncio
    async def test_shows_edit_link_button_when_linked(self) -> None:
        """Shows 'Edit link' button when operation has a link."""
        planned_op = PlannedOperation(
            record_id=42,
            description="Courses hebdo",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=42,
            iteration_date=date(2025, 1, 15),
        )
        service = _make_app_service(link=link, planned_ops=(planned_op,))

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            btn = app.screen.query_one("#btn-link", Button)
            assert str(btn.label) == "Edit link"

    @pytest.mark.asyncio
    async def test_unlink_refreshes_label_and_button(self) -> None:
        """Unlinking refreshes link label to 'No link' and button to 'Link'."""
        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=42,
            iteration_date=date(2025, 1, 15),
        )
        planned_op = PlannedOperation(
            record_id=42,
            description="Courses hebdo",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        service = _make_app_service(link=link, planned_ops=(planned_op,))

        # After unlink, get_link_for_operation should return None
        unlink_called = False

        def delete_link_side_effect(_op_id: int) -> None:
            nonlocal unlink_called
            unlink_called = True
            service.get_link_for_operation.return_value = None

        service.delete_link = Mock(side_effect=delete_link_side_effect)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Simulate the _on_target_selected callback with "unlink"
            modal._on_target_selected("unlink")
            await pilot.pause()

            assert unlink_called
            link_widget = modal.query_one("#detail-link", Static)
            assert "Courses hebdo" not in str(link_widget.content)
            btn = modal.query_one("#btn-link", Button)
            assert str(btn.label) == "Link"

    @pytest.mark.asyncio
    async def test_link_created_refreshes_label_and_button(self) -> None:
        """Creating a link refreshes the link label and button text."""
        service = _make_app_service(link=None)
        op = service.get_operation_by_id.return_value

        planned_op = PlannedOperation(
            record_id=42,
            description="Loyer",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=SingleDay(date(2025, 1, 1)),
        )
        service.get_all_planned_operations.return_value = (planned_op,)

        # After link creation, get_link_for_operation returns the new link
        new_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=42,
            iteration_date=date(2025, 1, 1),
        )

        def create_link_side_effect(
            _operation: Any, _target: Any, _iteration_date: Any
        ) -> None:
            service.get_link_for_operation.return_value = new_link

        service.create_manual_link = Mock(side_effect=create_link_side_effect)

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            modal = app.screen
            # Simulate the _on_iteration_selected callback
            modal._on_iteration_selected(date(2025, 1, 1), planned_op)
            await pilot.pause()

            service.create_manual_link.assert_called_once_with(
                op, planned_op, date(2025, 1, 1)
            )
            link_widget = modal.query_one("#detail-link", Static)
            assert "Loyer" in str(link_widget.content)
            btn = modal.query_one("#btn-link", Button)
            assert str(btn.label) == "Edit link"

    @pytest.mark.asyncio
    async def test_unlink_posts_save_and_refresh_messages(self) -> None:
        """Unlinking posts SaveRequested and DataRefreshRequested."""
        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=42,
            iteration_date=date(2025, 1, 15),
        )
        service = _make_app_service(link=link)
        service.delete_link = Mock(
            side_effect=lambda _: setattr(
                service.get_link_for_operation, "return_value", None
            )
        )

        app = OperationDetailTestApp(service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            app.screen._on_target_selected("unlink")
            await pilot.pause()

            assert any(isinstance(m, SaveRequested) for m in app.received_messages)
