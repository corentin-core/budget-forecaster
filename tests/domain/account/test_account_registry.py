"""Tests for AccountRegistry."""

from budget_forecaster.domain.account.account_registry import AccountRegistry


def test_resolves_declared_external_id() -> None:
    """A declared name resolves to its external id."""
    registry = AccountRegistry({"bnp": "FR76", "swile": "wallet-1"})

    assert registry.external_id_for("bnp") == "FR76"
    assert registry.external_id_for("swile") == "wallet-1"


def test_undeclared_name_resolves_to_none() -> None:
    """An unknown name resolves to no external id."""
    registry = AccountRegistry({"bnp": "FR76"})

    assert registry.external_id_for("unknown") is None


def test_empty_registry_resolves_to_none() -> None:
    """An empty registry resolves any name to None."""
    assert AccountRegistry().external_id_for("bnp") is None
