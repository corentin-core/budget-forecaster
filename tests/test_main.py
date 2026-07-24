"""Tests for the CLI entry point."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_forecaster import main
from budget_forecaster.core.types import SyncRunStatus
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

_BANKS = ({"name": "BNP Paribas"}, {"name": "Boursorama"})


def test_sync_without_enable_banking_exits(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sync command exits with an error when Enable Banking is unconfigured."""
    monkeypatch.setattr(main.Config, "setup_logging", lambda self: None)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"database_path: {tmp_path / 'x.db'}\n"
        'account_name: "Test"\n'
        "account_currency: EUR\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv", ["budget-forecaster", "-c", str(config_file), "sync"]
    )

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1
    assert "Enable Banking is not configured" in capsys.readouterr().err


def _write_eb_config(tmp_path: Path) -> Path:
    """Write a config with an Enable Banking section and no aspsp_name."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"database_path: {tmp_path / 'x.db'}\n"
        'account_name: "Test"\n'
        "account_currency: EUR\n"
        "enable_banking:\n"
        '  application_id: "app-1"\n'
        f"  private_key_path: {tmp_path / 'key.pem'}\n"
        '  redirect_url: "https://localhost/callback"\n',
        encoding="utf-8",
    )
    return config_file


def test_sync_records_failed_run_when_no_consent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sync with no stored consent exits 1 and records a FAILED run."""
    monkeypatch.setattr(main.Config, "setup_logging", lambda self: None)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(main, "_build_client", lambda _config: MagicMock())
    config_file = _write_eb_config(tmp_path)
    monkeypatch.setattr(
        "sys.argv", ["budget-forecaster", "-c", str(config_file), "sync"]
    )

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1
    assert capsys.readouterr().err
    with SqliteRepository(tmp_path / "x.db") as repo:
        (run,) = repo.get_recent_sync_runs(1)
    assert run.status is SyncRunStatus.FAILED


def _prime_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inputs: list[str]
) -> MagicMock:
    """Set up the link command with a mock client and scripted user inputs."""
    monkeypatch.setattr(main.Config, "setup_logging", lambda self: None)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    client = MagicMock()
    client.list_aspsps.return_value = _BANKS
    client.start_authorization.return_value = "https://bank.example/consent"
    client.create_session.return_value = {
        "session_id": "sess-1",
        "accounts": ["acc-1"],
        "access": {"valid_until": "2026-12-31T00:00:00Z"},
    }
    monkeypatch.setattr(main, "_build_client", lambda _config: client)

    answers = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(
        "sys.argv",
        ["budget-forecaster", "-c", str(_write_eb_config(tmp_path)), "link"],
    )
    return client


def test_link_lists_banks_and_persists_consent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """link lists banks, links the picked one, and stores the consent under XDG."""
    client = _prime_link(tmp_path, monkeypatch, ["1", "the-code"])

    main.main()

    out = capsys.readouterr().out
    assert "1. BNP Paribas" in out
    assert "Linked BNP Paribas: 1 account(s)" in out
    assert client.start_authorization.call_args.kwargs["aspsp_name"] == "BNP Paribas"
    client.create_session.assert_called_once_with("the-code")
    consent_file = (
        tmp_path / "state" / "budget-forecaster" / "enable_banking" / "consent.json"
    )
    assert consent_file.exists()


@pytest.mark.parametrize("selection", ["9", "abc"], ids=["out-of-range", "non-numeric"])
def test_link_rejects_invalid_bank_selection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    selection: str,
) -> None:
    """An invalid bank pick exits without opening an authorization."""
    client = _prime_link(tmp_path, monkeypatch, [selection])

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1
    assert capsys.readouterr().err
    client.start_authorization.assert_not_called()
