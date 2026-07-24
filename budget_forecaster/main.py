"""Main module for the Budget Forecaster application."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from budget_forecaster.core.types import SyncRunStatus
from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_store import (
    ConsentStore,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.sync_runner import (
    perform_sync,
)
from budget_forecaster.infrastructure.bootstrap import open_repository
from budget_forecaster.infrastructure.config import Config, EnableBankingConfig
from budget_forecaster.tui.app import run_app

logger = logging.getLogger(__name__)


def _create_default_config(config_path: Path) -> None:
    """Create a default configuration file from the template."""
    # Read the template from the package
    template_path = Path(__file__).parent / "default_config.yaml"
    template_content = template_path.read_text(encoding="utf-8")

    # Create parent directories
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the config file
    config_path.write_text(template_content, encoding="utf-8")


def _require_enable_banking(config: Config) -> EnableBankingConfig:
    """Return the Enable Banking config or exit with a helpful message."""
    if config.enable_banking is None:
        print(
            "Enable Banking is not configured. "
            "Add an 'enable_banking' section to your config file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return config.enable_banking


def _build_client(enable_banking: EnableBankingConfig) -> EnableBankingClient:
    """Build the Enable Banking client from the configured credentials."""
    return EnableBankingClient(
        enable_banking.application_id,
        enable_banking.private_key_path,
        enable_banking.redirect_url,
    )


def _run_sync(config_path: Path) -> None:
    """Sync the consented Enable Banking account, recording the run."""
    config = Config()
    config.parse(config_path)
    config.setup_logging()
    enable_banking = _require_enable_banking(config)
    client = _build_client(enable_banking)
    consent_service = ConsentService(client, ConsentStore.default())

    repository = open_repository(config)
    try:
        run = perform_sync(repository, consent_service, enable_banking, config.accounts)
    finally:
        repository.close()

    if run.status is SyncRunStatus.FAILED:
        print(run.error, file=sys.stderr)
        sys.exit(1)
    print(
        f"Synced {enable_banking.local_account_name}: {run.new_count} new, "
        f"{run.duplicate_count} duplicates skipped. Balance: {run.balance:.2f}"
    )


def _choose_aspsp_name(banks: tuple[dict[str, Any], ...], selection: str) -> str:
    """Return the bank name for a 1-based selection string, raising on a bad one."""
    try:
        index = int(selection)
    except ValueError as error:
        raise ValueError(f"Not a number: {selection!r}") from error
    if not 1 <= index <= len(banks):
        raise ValueError(f"Selection out of range: {index}")
    return banks[index - 1]["name"]


def _select_bank(consent_service: ConsentService, country: str) -> str:
    """List the banks and prompt the user to pick one; return its name."""
    if not (banks := consent_service.list_banks(country)):
        print(f"No banks available for {country}.", file=sys.stderr)
        sys.exit(1)
    print(f"Available banks ({country}):")
    for position, bank in enumerate(banks, start=1):
        print(f"  {position}. {bank['name']}")
    try:
        return _choose_aspsp_name(banks, input(f"Select a bank [1-{len(banks)}]: "))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)


def _run_link(config_path: Path) -> None:
    """Link a bank via manual copy-paste: pick the bank, print the URL, read the code."""
    config = Config()
    config.parse(config_path)
    config.setup_logging()
    enable_banking = _require_enable_banking(config)
    consent_service = ConsentService(
        _build_client(enable_banking), ConsentStore.default()
    )
    country = enable_banking.aspsp_country
    aspsp_name = enable_banking.aspsp_name or _select_bank(consent_service, country)

    url = consent_service.start_enrollment(aspsp_name, country)
    print("Open this URL, authenticate at your bank, then paste the returned code:")
    print(url)
    if not (code := input("code: ").strip()):
        print("No code provided.", file=sys.stderr)
        sys.exit(1)

    consent = consent_service.complete_enrollment(code, aspsp_name, country)
    print(
        f"Linked {consent.aspsp_name}: {len(consent.account_uids)} account(s), "
        f"consent valid until {consent.valid_until.date()}."
    )


def _run_consent_status(config_path: Path) -> None:
    """Print the current consent status and expiry date."""
    config = Config()
    config.parse(config_path)
    config.setup_logging()
    enable_banking = _require_enable_banking(config)
    consent_service = ConsentService(
        _build_client(enable_banking), ConsentStore.default()
    )
    state = consent_service.state()
    if state.valid_until is None:
        print("No consent stored. Run 'link' to authorize a bank.")
        return
    print(f"Consent {state.status.value}, valid until {state.valid_until.date()}.")


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
    subparsers.add_parser(
        "link", help="Link a bank via Enable Banking (manual code copy-paste)"
    )
    subparsers.add_parser(
        "consent-status", help="Show the Enable Banking consent status and expiry"
    )
    args = parser.parse_args()

    config_path = args.config.expanduser()

    if not config_path.exists():
        _create_default_config(config_path)
        print(f"Created default configuration at: {config_path}")
        print("Please edit it to customize your settings, then run again.")
        sys.exit(0)

    if args.command == "sync":
        _run_sync(config_path)
    elif args.command == "link":
        _run_link(config_path)
    elif args.command == "consent-status":
        _run_consent_status(config_path)
    else:
        run_app(config_path)


if __name__ == "__main__":
    main()
