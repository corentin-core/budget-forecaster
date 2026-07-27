"""Fixtures for the web layer: a real app over a copy of the demo database."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.i18n import setup_i18n
from budget_forecaster.web.app import create_app
from budget_forecaster.web.auth import hash_password

PASSWORD = "test-pass"
_DEMO_DB = Path(__file__).resolve().parents[2] / "examples" / "demo.db"


@pytest.fixture(autouse=True)
def _restore_i18n() -> Iterator[None]:
    """Building the app sets the global language to French; restore it after
    each test so other suites keep the default English passthrough."""
    yield
    setup_i18n("en")


@pytest.fixture(name="config_path")
def config_path_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a config pointing at a private copy of the demo database.

    Secrets go in the config file, so env vars must not leak in and win.
    """
    monkeypatch.delenv("BUDGET_WEB_SECRET_KEY", raising=False)
    monkeypatch.delenv("BUDGET_WEB_PASSWORD_HASH", raising=False)
    # A stray Secure flag would drop cookies over the TestClient's http.
    monkeypatch.delenv("BUDGET_WEB_SECURE_COOKIES", raising=False)
    # Keep the EB consent and Swile token stores under tmp, not the real
    # user state dir (the app resolves both from XDG_STATE_HOME).
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    database = tmp_path / "demo.db"
    shutil.copy(_DEMO_DB, database)
    config = tmp_path / "config.yaml"
    config.write_text(
        f"database_path: {database}\n"
        "account_name: Foyer\n"
        "account_currency: EUR\n"
        "language: fr\n"
        "backup:\n  enabled: false\n"
        "web:\n"
        "  secret_key: test-secret-key\n"
        f"  password_hash: {hash_password(PASSWORD)}\n",
        encoding="utf-8",
    )
    return config


@pytest.fixture(name="app")
def app_fixture(config_path: Path) -> FastAPI:
    """Build the web application from the test config."""
    return create_app(config_path)


@pytest.fixture(name="anon_client")
def anon_client_fixture(app: FastAPI) -> Iterator[TestClient]:
    """An unauthenticated client (redirects not followed by default here)."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(name="client")
def client_fixture(app: FastAPI) -> Iterator[TestClient]:
    """An authenticated client with a valid session cookie."""
    with TestClient(app) as client:
        response = client.post(
            "/login", data={"password": PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 303
        yield client
