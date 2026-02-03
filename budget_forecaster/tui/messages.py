"""Shared messages for TUI components."""

from textual.message import Message


class DataRefreshRequested(Message):
    """Request the app to refresh all data displays."""


class SaveRequested(Message):
    """Request the app to save pending changes."""
