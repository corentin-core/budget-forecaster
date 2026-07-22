"""Tests for the CLI entry point."""

from pathlib import Path

import pytest

from budget_forecaster import main


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
