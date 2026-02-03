"""Tests for TUI message communication (DataRefreshRequested, SaveRequested)."""

from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import OptionList

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.messages import DataRefreshRequested, SaveRequested
from budget_forecaster.tui.screens.operations import (
    CategoryEditModal,
    OperationDetailPanel,
)
from budget_forecaster.tui.widgets.category_select import CategorySelect
from budget_forecaster.types import Category


def make_test_operation(unique_id: int = 1) -> HistoricOperation:
    """Create a test operation."""
    return HistoricOperation(
        unique_id=unique_id,
        date=datetime(2025, 1, 15),
        description="Test operation",
        amount=Amount(-100.00, "EUR"),
        category=Category.UNCATEGORIZED,
    )


class MessageTrackingApp(App[None]):
    """Base test app that tracks messages."""

    def __init__(self) -> None:
        super().__init__()
        self.received_messages: list[Any] = []

    def on_save_requested(self, event: SaveRequested) -> None:
        """Track SaveRequested messages."""
        self.received_messages.append(event)

    def on_data_refresh_requested(self, event: DataRefreshRequested) -> None:
        """Track DataRefreshRequested messages."""
        self.received_messages.append(event)


class CategoryEditModalTestApp(MessageTrackingApp):
    """Test app for CategoryEditModal."""

    def __init__(self, app_service: ApplicationService | None = None) -> None:
        super().__init__()
        self._app_service = app_service
        self.modal_result: bool | None = None

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self) -> None:
        """Open the category edit modal."""
        self.push_screen(
            CategoryEditModal(operation_id=1, app_service=self._app_service),
            self._on_modal_closed,
        )

    def _on_modal_closed(self, result: bool | None) -> None:
        """Track modal result."""
        self.modal_result = result


class OperationDetailPanelTestApp(MessageTrackingApp):
    """Test app for OperationDetailPanel."""

    def compose(self) -> ComposeResult:
        panel = OperationDetailPanel()
        yield panel

    def on_mount(self) -> None:
        """Set up the panel with a test operation."""
        panel = self.query_one(OperationDetailPanel)
        # Set the operation_id so _on_category_edited works
        panel._operation_id = 1  # pylint: disable=protected-access


class TestCategoryEditModalMessages:
    """Tests for CategoryEditModal message emission."""

    @pytest.mark.asyncio
    async def test_emits_save_requested_on_category_selection(self) -> None:
        """Verify SaveRequested is emitted when a category is selected."""
        # Create mock app service with proper return values
        mock_service = Mock(spec=ApplicationService)
        mock_service.categorize_operations = Mock()
        mock_service.get_operation_by_id = Mock(return_value=make_test_operation())
        mock_service.suggest_category = Mock(return_value=None)

        app = CategoryEditModalTestApp(app_service=mock_service)
        async with app.run_test() as pilot:
            # Open the modal
            app.open_modal()
            await pilot.pause()

            # The modal is on the screen stack - query from the active screen
            modal = app.screen
            option_list = modal.query_one("#category-list", OptionList)
            option_list.focus()
            await pilot.pause()
            # Highlight first option and select
            option_list.action_first()
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            # Verify SaveRequested was emitted
            save_messages = [
                m for m in app.received_messages if isinstance(m, SaveRequested)
            ]
            assert len(save_messages) == 1, "Expected one SaveRequested message"

    @pytest.mark.asyncio
    async def test_no_save_requested_on_cancel(self) -> None:
        """Verify SaveRequested is NOT emitted when modal is cancelled."""
        app = CategoryEditModalTestApp(app_service=None)
        async with app.run_test() as pilot:
            # Open the modal
            app.open_modal()
            await pilot.pause()

            # Cancel with escape
            await pilot.press("escape")
            await pilot.pause()

            # Verify no SaveRequested was emitted
            save_messages = [
                m for m in app.received_messages if isinstance(m, SaveRequested)
            ]
            assert len(save_messages) == 0, "Expected no SaveRequested on cancel"
            assert app.modal_result is False

    @pytest.mark.asyncio
    async def test_modal_dismisses_with_true_on_selection(self) -> None:
        """Verify modal dismisses with True when category is selected."""
        mock_service = Mock(spec=ApplicationService)
        mock_service.categorize_operations = Mock()
        mock_service.get_operation_by_id = Mock(return_value=make_test_operation())
        mock_service.suggest_category = Mock(return_value=None)

        app = CategoryEditModalTestApp(app_service=mock_service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            # The modal is on the screen stack - query from the active screen
            modal = app.screen
            option_list = modal.query_one("#category-list", OptionList)
            option_list.focus()
            await pilot.pause()
            # Highlight first option and select
            option_list.action_first()
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert app.modal_result is True


class TestCategorySelectMessages:
    """Tests for CategorySelect widget message emission."""

    @pytest.mark.asyncio
    async def test_emits_category_selected_on_option_select(self) -> None:
        """Verify CategorySelected is emitted when an option is selected."""

        class CategorySelectTestApp(App[None]):
            """Test app that tracks category selection."""

            def __init__(self) -> None:
                super().__init__()
                self.selected_category: Category | None = None

            def compose(self) -> ComposeResult:
                """Compose the test app."""
                yield CategorySelect()

            def on_category_select_category_selected(
                self, event: CategorySelect.CategorySelected
            ) -> None:
                """Track selected category."""
                self.selected_category = event.category

        app = CategorySelectTestApp()
        async with app.run_test() as pilot:
            # Wait for mount and options to load
            await pilot.pause()

            # Focus the option list, move to first option, and select
            option_list = app.query_one("#category-list", OptionList)
            option_list.focus()
            await pilot.pause()
            # Highlight first option and select
            option_list.action_first()
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert app.selected_category is not None
            assert isinstance(app.selected_category, Category)

    @pytest.mark.asyncio
    async def test_emits_category_selected_on_search_submit(self) -> None:
        """Verify CategorySelected is emitted when Enter is pressed in search."""

        class CategorySelectTestApp(App[None]):
            """Test app that tracks category selection."""

            def __init__(self) -> None:
                super().__init__()
                self.selected_category: Category | None = None

            def compose(self) -> ComposeResult:
                """Compose the test app."""
                yield CategorySelect()

            def on_category_select_category_selected(
                self, event: CategorySelect.CategorySelected
            ) -> None:
                """Track selected category."""
                self.selected_category = event.category

        app = CategorySelectTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Focus the search input and press Enter
            search_input = app.query_one("#category-search")
            search_input.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert app.selected_category is not None


class TestOperationDetailPanelMessages:
    """Tests for OperationDetailPanel message emission."""

    @pytest.mark.asyncio
    async def test_emits_data_refresh_on_category_edit_success(self) -> None:
        """Verify DataRefreshRequested is emitted after successful category edit."""
        app = OperationDetailPanelTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(OperationDetailPanel)

            # Simulate the callback being called with True (successful edit)
            # pylint: disable=protected-access
            panel._on_category_edited(True)
            await pilot.pause()

            # Verify DataRefreshRequested was emitted
            refresh_messages = [
                m for m in app.received_messages if isinstance(m, DataRefreshRequested)
            ]
            assert len(refresh_messages) == 1

    @pytest.mark.asyncio
    async def test_no_data_refresh_on_category_edit_cancel(self) -> None:
        """Verify DataRefreshRequested is NOT emitted when edit is cancelled."""
        app = OperationDetailPanelTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(OperationDetailPanel)

            # Simulate the callback being called with False (cancelled)
            # pylint: disable=protected-access
            panel._on_category_edited(False)
            await pilot.pause()

            # Verify no DataRefreshRequested was emitted
            refresh_messages = [
                m for m in app.received_messages if isinstance(m, DataRefreshRequested)
            ]
            assert len(refresh_messages) == 0

    @pytest.mark.asyncio
    async def test_no_data_refresh_on_category_edit_none(self) -> None:
        """Verify DataRefreshRequested is NOT emitted when result is None."""
        app = OperationDetailPanelTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(OperationDetailPanel)

            # Simulate the callback being called with None
            # pylint: disable=protected-access
            panel._on_category_edited(None)
            await pilot.pause()

            # Verify no DataRefreshRequested was emitted
            refresh_messages = [
                m for m in app.received_messages if isinstance(m, DataRefreshRequested)
            ]
            assert len(refresh_messages) == 0


class TestBudgetAppMessageHandlers:
    """Tests for BudgetApp message handlers (on_data_refresh_requested, on_save_requested)."""

    def test_on_data_refresh_requested_calls_action_refresh_data(self) -> None:
        """Verify on_data_refresh_requested stops event and calls action_refresh_data."""
        # Import here to avoid pulling in BudgetApp dependencies at module level
        # pylint: disable-next=import-outside-toplevel
        from budget_forecaster.tui.app import BudgetApp

        app = BudgetApp.__new__(BudgetApp)
        app.action_refresh_data = Mock()  # type: ignore[method-assign]

        event = DataRefreshRequested()
        event.stop = Mock()  # type: ignore[method-assign]

        # Call handler directly
        app.on_data_refresh_requested(event)

        event.stop.assert_called_once()
        app.action_refresh_data.assert_called_once()

    def test_on_save_requested_calls_save_changes(self) -> None:
        """Verify on_save_requested stops event and calls save_changes."""
        # pylint: disable-next=import-outside-toplevel
        from budget_forecaster.tui.app import BudgetApp

        app = BudgetApp.__new__(BudgetApp)
        app.save_changes = Mock()  # type: ignore[method-assign]

        event = SaveRequested()
        event.stop = Mock()  # type: ignore[method-assign]

        # Call handler directly
        app.on_save_requested(event)

        event.stop.assert_called_once()
        app.save_changes.assert_called_once()
