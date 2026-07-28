"""Main module for the Budget Forecaster application."""

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_store import (
    ConsentStore,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.bank_sources.sync_all import sync_all_sources
from budget_forecaster.infrastructure.bootstrap import open_repository
from budget_forecaster.infrastructure.config import Config, EnableBankingConfig
from budget_forecaster.infrastructure.db_lock import database_lock
from budget_forecaster.web.auth import hash_password
from budget_forecaster.web.config import ENV_SECRET_KEY

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


def _consent_service(config: Config) -> ConsentService | None:
    """Build the Enable Banking consent service, or None when not configured."""
    if config.enable_banking is None:
        return None
    return ConsentService(_build_client(config.enable_banking), ConsentStore.default())


def _swile_token_store(config: Config) -> SwileTokenStore | None:
    """Build the Swile token store, or None when no web secret key is available.

    The token is encrypted with the web secret key (env first, config fallback);
    without it the timer can't decrypt the token, so Swile is skipped silently.
    """
    if not (secret_key := os.environ.get(ENV_SECRET_KEY) or config.web.secret_key):
        logger.info("Swile sync skipped: no web secret key configured")
        return None
    return SwileTokenStore.default(secret_key)


def _report_sync_runs(runs: tuple[SyncRun, ...]) -> None:
    """Print one line per attempted source; failures go to stderr."""
    if not runs:
        print("No connected source to sync.")
        return
    for run in runs:
        label = "Swile" if run.source is SyncSource.SWILE else "Bank"
        if run.status is SyncRunStatus.OK:
            balance = f" Balance: {run.balance:.2f}" if run.balance is not None else ""
            print(
                f"{label}: {run.new_count} new, "
                f"{run.duplicate_count} duplicates skipped.{balance}"
            )
        else:
            print(f"{label}: failed — {run.error}", file=sys.stderr)


def _run_sync(config_path: Path) -> None:
    """Sync every connected source; exit non-zero if any attempted source failed."""
    config = Config()
    config.parse(config_path)
    config.setup_logging()

    consent_service = _consent_service(config)
    swile_token_store = _swile_token_store(config)

    # Hold the lock for the whole session so a web-app restore cannot swap the
    # database file while this process has it open.
    with database_lock(config.database_path):
        repository = open_repository(config)
        try:
            runs = sync_all_sources(
                repository, config, consent_service, swile_token_store
            )
        finally:
            repository.close()

    _report_sync_runs(runs)
    if any(run.status is SyncRunStatus.FAILED for run in runs):
        sys.exit(1)


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


def _run_hash_password() -> None:
    """Prompt for a password and print its hash for the web app secret."""
    try:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm: ")
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        sys.exit(1)
    print(hash_password(password))


def main() -> None:
    """Entry point: run a subcommand such as sync, or print help."""
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
        "consent-status", help="Show the Enable Banking consent status and expiry"
    )
    subparsers.add_parser(
        "hash-password", help="Hash a web app password for BUDGET_WEB_PASSWORD_HASH"
    )
    args = parser.parse_args()

    # No subcommand: nothing to do (the web app runs via uvicorn/systemd).
    if args.command is None:
        parser.print_help()
        return

    # Config-independent: no config file needed to hash a password.
    if args.command == "hash-password":
        _run_hash_password()
        return

    config_path = args.config.expanduser()

    if not config_path.exists():
        _create_default_config(config_path)
        print(f"Created default configuration at: {config_path}")
        print("Please edit it to customize your settings, then run again.")
        sys.exit(0)

    if args.command == "sync":
        _run_sync(config_path)
    elif args.command == "consent-status":
        _run_consent_status(config_path)


if __name__ == "__main__":
    main()
