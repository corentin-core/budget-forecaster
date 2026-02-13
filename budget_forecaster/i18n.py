"""Internationalization support using Python's gettext.

This module provides the translation function ``_()`` used throughout the
application. Call :func:`setup_i18n` once at startup with the configured
language code before any translated strings are accessed.

The source strings (msgid) are in English. French translations live in
``locales/fr/LC_MESSAGES/messages.po``.
"""

import gettext
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locales"

# Default to no-op translations until setup_i18n is called
_translation: gettext.GNUTranslations | gettext.NullTranslations = (
    gettext.NullTranslations()
)


def setup_i18n(language: str) -> None:
    """Initialize translations for the given language.

    Args:
        language: ISO 639-1 language code (e.g. ``"en"``, ``"fr"``).
    """
    global _translation  # noqa: PLW0603  # pylint: disable=global-statement
    _translation = gettext.translation(
        "messages",
        localedir=str(_LOCALE_DIR),
        languages=[language],
        fallback=True,
    )


def _(message: str) -> str:
    """Return the translated string for *message*."""
    return _translation.gettext(message)
