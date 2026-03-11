"""Threshold edit modal — set the minimum balance threshold for margin."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from budget_forecaster.i18n import _
from budget_forecaster.tui.symbols import DisplaySymbol


class ThresholdEditModal(ModalScreen[float | None]):
    """Modal for editing the margin threshold value.

    Returns the new threshold value, or None if cancelled.
    """

    DEFAULT_CSS = """
    ThresholdEditModal {
        align: center middle;
    }

    ThresholdEditModal #modal-container {
        width: 50;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    ThresholdEditModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
        height: 2;
    }

    ThresholdEditModal .form-row {
        height: 3;
        margin-bottom: 1;
    }

    ThresholdEditModal .form-label {
        width: 18;
        padding: 0 1;
    }

    ThresholdEditModal .form-input {
        width: 1fr;
    }

    ThresholdEditModal #buttons-row {
        height: 3;
        margin-top: 1;
    }

    ThresholdEditModal Button {
        margin-left: 1;
    }

    ThresholdEditModal #error-message {
        color: $error;
        height: 2;
    }
    """

    BINDINGS = [("escape", "cancel", _("Cancel"))]

    def __init__(
        self,
        current_threshold: float,
        *,
        title: str = "",
        unit: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize the threshold edit modal.

        Args:
            current_threshold: Current threshold value to pre-fill.
            title: Modal title. Defaults to "Edit margin threshold".
            unit: Unit label shown next to the input. Defaults to currency symbol.
        """
        super().__init__(**kwargs)
        self._current_threshold = current_threshold
        self._title = title or _("Edit margin threshold")
        self._unit = unit or DisplaySymbol.EURO

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Static(self._title, id="modal-title")

            with Horizontal(classes="form-row"):
                yield Label(
                    f"{_('Threshold')} ({self._unit})",
                    classes="form-label",
                )
                yield Input(
                    value=f"{self._current_threshold:g}",
                    placeholder="0",
                    id="input-threshold",
                    classes="form-input",
                    type="number",
                )

            yield Static("", id="error-message")

            with Horizontal(id="buttons-row"):
                yield Button(_("Cancel"), id="btn-cancel", variant="default")
                yield Button(_("Save"), id="btn-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()

    def _save(self) -> None:
        """Validate and save the threshold."""
        error = self.query_one("#error-message", Static)
        error.update("")

        raw = self.query_one("#input-threshold", Input).value.strip()

        try:
            value = float(raw)
        except ValueError:
            error.update(_("Invalid number"))
            return

        if value < 0:
            error.update(_("Threshold must be positive or zero"))
            return

        self.dismiss(value)

    def action_cancel(self) -> None:
        """Cancel the edit."""
        self.dismiss(None)
