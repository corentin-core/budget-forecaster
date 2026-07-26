"""Tests for the CLI entry point."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_forecaster import main
from budget_forecaster.core.types import SyncRunStatus
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.web.auth import verify_password


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


def test_hash_password_prints_verifiable_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash-password prints a verifiable hash and never touches the config file."""
    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr(main.getpass, "getpass", lambda _prompt: "s3cret")
    monkeypatch.setattr(
        "sys.argv", ["budget-forecaster", "-c", str(config_file), "hash-password"]
    )

    main.main()

    printed = capsys.readouterr().out.strip()
    assert verify_password("s3cret", printed)
    assert not verify_password("wrong", printed)
    assert not config_file.exists()


def test_hash_password_exits_on_mismatch(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash-password exits 1 when the confirmation does not match."""
    answers = iter(["one", "two"])
    monkeypatch.setattr(main.getpass, "getpass", lambda _prompt: next(answers))
    monkeypatch.setattr("sys.argv", ["budget-forecaster", "hash-password"])

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1
    assert "do not match" in capsys.readouterr().err


def test_hash_password_exits_on_empty(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash-password rejects an empty password."""
    monkeypatch.setattr(main.getpass, "getpass", lambda _prompt: "")
    monkeypatch.setattr("sys.argv", ["budget-forecaster", "hash-password"])

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1
    assert "must not be empty" in capsys.readouterr().err
