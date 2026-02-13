"""Tests for the i18n module."""

from budget_forecaster.i18n import _, setup_i18n


class TestI18n:
    """Tests for internationalization setup and translation."""

    def test_default_returns_english(self) -> None:
        """Without setup, _() returns the original English string."""
        setup_i18n("en")
        assert _("Dashboard") == "Dashboard"
        assert _("Salary") == "Salary"

    def test_french_translation(self) -> None:
        """After setup_i18n('fr'), _() returns French translations."""
        setup_i18n("fr")
        assert _("Dashboard") == "Tableau de bord"
        assert _("Salary") == "Salaire"
        assert _("Groceries") == "Alimentation"
        assert _("Balance evolution") == "Évolution du solde"
        # Restore to English for other tests
        setup_i18n("en")

    def test_unknown_language_falls_back_to_english(self) -> None:
        """An unknown language code falls back to English (no-op)."""
        setup_i18n("de")
        assert _("Dashboard") == "Dashboard"
        assert _("Salary") == "Salary"
        # Restore
        setup_i18n("en")

    def test_unknown_msgid_returns_original(self) -> None:
        """An untranslated msgid returns the original string."""
        setup_i18n("fr")
        assert _("this string has no translation") == "this string has no translation"
        setup_i18n("en")
