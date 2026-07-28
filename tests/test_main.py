"""Tests for the CLI entry point."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from budget_forecaster import main
from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.infrastructure.bank_sources.swile_oauth import (
    sync_runner as swile_runner,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.web.auth import verify_password
from tests.web.test_swile import _fake_client


def _write_config(tmp_path: Path, *, enable_banking: bool = False) -> Path:
    """Write a minimal config, optionally with an Enable Banking section."""
    body = (
        f"database_path: {tmp_path / 'x.db'}\n"
        'account_name: "Test"\n'
        "account_currency: EUR\n"
    )
    if enable_banking:
        (tmp_path / "key.pem").write_bytes(b"dummy-key")
        body += (
            "enable_banking:\n"
            '  application_id: "app-1"\n'
            f"  private_key_path: {tmp_path / 'key.pem'}\n"
            '  redirect_url: "https://localhost/callback"\n'
        )
    config_file = tmp_path / "config.yaml"
    config_file.write_text(body, encoding="utf-8")
    return config_file


def _run_cli_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **cfg: bool) -> None:
    monkeypatch.setattr(main.Config, "setup_logging", lambda self: None)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    config_file = _write_config(tmp_path, **cfg)
    monkeypatch.setattr(
        "sys.argv", ["budget-forecaster", "-c", str(config_file), "sync"]
    )
    main.main()


def test_sync_noop_when_nothing_connected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No configured source: sync is a clean no-op, not an error."""
    _run_cli_sync(tmp_path, monkeypatch)
    assert "No connected source to sync." in capsys.readouterr().out


def test_sync_skips_unlinked_enable_banking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enable Banking configured but never linked is skipped, recording no run."""
    _run_cli_sync(tmp_path, monkeypatch, enable_banking=True)
    with SqliteRepository(tmp_path / "x.db") as repo:
        assert not repo.get_recent_sync_runs(1)


def test_sync_syncs_swile_from_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a web secret key and a stored token, the CLI syncs Swile (the timer path)."""
    key = "cli-swile-secret"
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("BUDGET_WEB_SECRET_KEY", key)
    SwileTokenStore.default(key).save("stored-rt")
    monkeypatch.setattr(swile_runner, "SwileClient", _fake_client)

    _run_cli_sync(tmp_path, monkeypatch)

    with SqliteRepository(tmp_path / "x.db") as repo:
        (run,) = repo.get_recent_sync_runs(1)
    assert run.source is SyncSource.SWILE
    assert run.status is SyncRunStatus.OK
    assert "Swile:" in capsys.readouterr().out


def test_sync_exits_when_a_source_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FAILED run from any source makes the command exit non-zero."""

    def failed(*_args: object, **_kwargs: object) -> tuple[SyncRun, ...]:
        return (
            SyncRun(
                datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc),
                SyncRunStatus.FAILED,
                error="boom",
                source=SyncSource.SWILE,
            ),
        )

    monkeypatch.setattr(main, "sync_all_sources", failed)
    with pytest.raises(SystemExit) as exc_info:
        _run_cli_sync(tmp_path, monkeypatch)
    assert exc_info.value.code == 1


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


def test_no_subcommand_prints_help(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running with no subcommand prints help and returns without launching anything."""
    monkeypatch.setattr("sys.argv", ["budget-forecaster"])

    main.main()

    output = capsys.readouterr().out
    assert "usage:" in output
    assert "sync" in output
