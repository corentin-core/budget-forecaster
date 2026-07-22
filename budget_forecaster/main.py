"""Main module for the Budget Forecaster application."""

import argparse
import logging
import sys
from pathlib import Path

from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.source import (
    EnableBankingSource,
)
from budget_forecaster.infrastructure.bootstrap import open_repository
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.services.bank_sync_service import BankSyncService
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases import MatcherCache, SyncUseCase
from budget_forecaster.tui.app import run_app

logger = logging.getLogger(__name__)

# Local account name for the Enable Banking source. Must match the BNP file
# adapter so xls and API operations reconcile into the same sub-account.
_BNP_ACCOUNT_NAME = "bnp"


def _create_default_config(config_path: Path) -> None:
    """Create a default configuration file from the template."""
    # Read the template from the package
    template_path = Path(__file__).parent / "default_config.yaml"
    template_content = template_path.read_text(encoding="utf-8")

    # Create parent directories
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the config file
    config_path.write_text(template_content, encoding="utf-8")


def _run_sync(config_path: Path) -> None:
    """Sync the configured Enable Banking account into the local database."""
    config = Config()
    config.parse(config_path)
    config.setup_logging()

    if (enable_banking := config.enable_banking) is None:
        print(
            "Enable Banking is not configured. "
            "Add an 'enable_banking' section to your config file.",
            file=sys.stderr,
        )
        sys.exit(1)

    repository = None
    try:
        repository = open_repository(config)
        persistent_account = PersistentAccount(repository)
        client = EnableBankingClient(
            enable_banking.application_id,
            enable_banking.private_key_path,
            enable_banking.redirect_url,
        )
        source = EnableBankingSource(client, name=_BNP_ACCOUNT_NAME)
        sync_use_case = SyncUseCase(
            BankSyncService(persistent_account, source),
            persistent_account,
            OperationLinkService(repository),
            MatcherCache(ForecastService(persistent_account, repository)),
        )
        stats = sync_use_case.sync(enable_banking.account_uid)
        account = persistent_account.account
        print(
            f"Synced {source.name}: {stats.new_operations} new, "
            f"{stats.duplicates_skipped} duplicates skipped. "
            f"Balance: {account.balance:.2f} {account.currency}"
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("Sync failed")
        print("Sync failed. See the log for details.", file=sys.stderr)
        sys.exit(1)
    finally:
        if repository is not None:
            repository.close()


def main() -> None:
    """Entry point: launch the TUI, or run a subcommand such as sync."""
    default_config_path = Path("~/.config/budget-forecaster/config.yaml").expanduser()

    parser = argparse.ArgumentParser(
        description="Budget Forecaster - Personal budget management with forecasting"
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Path to the configuration file",
        type=Path,
        default=default_config_path,
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("sync", help="Sync a linked bank account via Enable Banking")
    args = parser.parse_args()

    config_path = args.config.expanduser()

    if not config_path.exists():
        _create_default_config(config_path)
        print(f"Created default configuration at: {config_path}")
        print("Please edit it to customize your settings, then run again.")
        sys.exit(0)

    if args.command == "sync":
        _run_sync(config_path)
    else:
        run_app(config_path)


if __name__ == "__main__":
    main()
