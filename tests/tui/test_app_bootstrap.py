"""Tests for BudgetApp bootstrap with empty database."""

from pathlib import Path

import pytest

from budget_forecaster.tui.app import BudgetApp


@pytest.fixture
def empty_db_config(tmp_path: Path) -> Path:
    """Create a minimal config pointing to a non-existent database."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"database_path: {tmp_path / 'empty.db'}\n"
        "account_name: Test Account\n"
        "account_currency: EUR\n"
    )
    return config_path


@pytest.mark.asyncio
async def test_app_starts_with_empty_database(empty_db_config: Path) -> None:
    """App should bootstrap an aggregated account when DB is empty.

    No sub-accounts exist yet — they are created on first import.
    """
    app = BudgetApp(config_path=empty_db_config)
    async with app.run_test():
        service = app.app_service
        assert service.balance == 0.0
