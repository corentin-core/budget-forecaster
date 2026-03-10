"""Actions that can be triggered from edit modals besides save/cancel."""

from enum import StrEnum


class EditAction(StrEnum):
    """Special actions returned by edit modals instead of a saved entity."""

    SPLIT = "split"
    DELETE = "delete"
