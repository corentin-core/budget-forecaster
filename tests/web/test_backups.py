"""Tests for the web backup management routes."""

import fcntl
import inspect
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.web.routes import settings as settings_module


def _db_path(app: FastAPI) -> Path:
    return app.state.config.database_path


def _backups(app: FastAPI) -> tuple:
    return app.state.backup_service.get_backups()


def _threshold(client: TestClient) -> str:
    """Read the margin threshold shown on the settings page (over HTTP).

    The DB connection is bound to the serving thread, so the test never reads
    the ApplicationService directly.
    """
    page = client.get("/settings").text
    match = re.search(r'name="threshold"[^>]*value="([0-9.]+)"', page)
    assert match is not None
    return match.group(1)


class TestBackupListing:
    """The Backups card on the settings page."""

    def test_empty_state_when_no_backups(self, client: TestClient) -> None:
        """A fresh database shows the empty backups state."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert "Aucune sauvegarde" in response.text

    def test_created_backup_is_listed_as_manual(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """An on-demand backup appears tagged as manual."""
        client.post("/settings/backup", follow_redirects=False)
        response = client.get("/settings")
        assert "Sauvegardes" in response.text
        assert "Manuelle" in response.text
        assert len(_backups(app)) == 1

    def test_create_returns_redirect(self, client: TestClient, app: FastAPI) -> None:
        """Creating a backup writes a file and redirects back to settings."""
        response = client.post("/settings/backup", follow_redirects=False)
        assert response.status_code == 303
        assert len(_backups(app)) == 1


class TestPreview:
    """GET /settings/backup/preview."""

    def test_shows_metrics_without_mutating(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Preview renders both DBs' metrics and never changes the live data."""
        client.post("/settings/backup", follow_redirects=False)
        name = _backups(app)[0].path.name
        before = _db_path(app).read_bytes()

        response = client.get(f"/settings/backup/preview?name={name}")

        assert response.status_code == 200
        assert "backup-preview-table" in response.text
        assert "Par rapport" in response.text
        assert _db_path(app).read_bytes() == before

    def test_unknown_backup_shows_error_fragment(self, client: TestClient) -> None:
        """Previewing an unknown backup renders an in-fragment error."""
        response = client.get("/settings/backup/preview?name=nope.db")
        assert response.status_code == 200
        assert "pas pu être lue" in response.text


class TestRestore:
    """POST /settings/backup/restore."""

    def test_restore_reverts_changes_and_flashes_undo(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Restoring reverts a later change and offers an undo."""
        original = _threshold(client)
        client.post("/settings/backup", follow_redirects=False)
        name = _backups(app)[0].path.name

        bumped = f"{float(original) + 500:.2f}"
        client.post("/settings/threshold", data={"threshold": bumped})
        assert _threshold(client) == bumped

        response = client.post(
            "/settings/backup/restore", data={"name": name}, follow_redirects=True
        )

        assert "Base de données restaurée" in response.text
        assert _threshold(client) == original
        # A safety snapshot was taken and is offered as the undo target.
        assert any(b.is_safety_copy for b in _backups(app))

    def test_undo_reverts_and_consumes_the_snapshot(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Undo restores the pre-restore state, takes no new copy, and drops it."""
        original = _threshold(client)
        client.post("/settings/backup", follow_redirects=False)
        name = _backups(app)[0].path.name

        bumped = f"{float(original) + 500:.2f}"
        client.post("/settings/threshold", data={"threshold": bumped})
        client.post("/settings/backup/restore", data={"name": name})
        assert _threshold(client) == original

        snapshot = next(b for b in _backups(app) if b.is_safety_copy)
        response = client.post(
            "/settings/backup/restore",
            data={"name": snapshot.path.name, "undo": "1"},
            follow_redirects=True,
        )

        assert _threshold(client) == bumped
        assert "Restauration annulée" in response.text
        # The consumed safety copy is gone and no new one was created.
        assert not any(b.is_safety_copy for b in _backups(app))

    def test_restore_unknown_backup_flashes_error(self, client: TestClient) -> None:
        """Restoring an unknown backup surfaces an error and changes nothing."""
        response = client.post(
            "/settings/backup/restore", data={"name": "nope.db"}, follow_redirects=True
        )
        assert "Échec de la restauration" in response.text

    def test_restore_while_locked_reports_busy(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A restore fails fast with a retry message when the DB lock is held."""
        client.post("/settings/backup", follow_redirects=False)
        name = _backups(app)[0].path.name
        lock_file = _db_path(app).with_name(_db_path(app).name + ".lock")
        lock_file.touch()

        with open(lock_file, "w", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            response = client.post(
                "/settings/backup/restore",
                data={"name": name},
                follow_redirects=True,
            )

        assert "synchronisation est en cours" in response.text
        # No safety snapshot was taken (restore aborted at the lock) and the app
        # is still usable after the closed-then-busy path.
        assert not any(b.is_safety_copy for b in _backups(app))
        assert client.get("/settings").status_code == 200


class TestDelete:
    """POST /settings/backup/delete."""

    def test_deletes_named_backup(self, client: TestClient, app: FastAPI) -> None:
        """The named backup is removed, including the last one."""
        client.post("/settings/backup", follow_redirects=False)
        name = _backups(app)[0].path.name

        response = client.post(
            "/settings/backup/delete", data={"name": name}, follow_redirects=False
        )

        assert response.status_code == 303
        assert _backups(app) == ()

    def test_delete_unknown_flashes_error(self, client: TestClient) -> None:
        """Deleting an unknown backup surfaces an error."""
        response = client.post(
            "/settings/backup/delete", data={"name": "nope.db"}, follow_redirects=True
        )
        assert "Impossible de supprimer la sauvegarde" in response.text


class TestDownload:
    """GET /settings/backup/download."""

    def test_streams_backup_as_attachment(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Download returns the raw file with an attachment disposition."""
        client.post("/settings/backup", follow_redirects=False)
        backup = _backups(app)[0]

        response = client.get(f"/settings/backup/download?name={backup.path.name}")

        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert response.content == backup.path.read_bytes()

    def test_unknown_download_redirects(self, client: TestClient) -> None:
        """An unknown download name redirects instead of erroring."""
        response = client.get(
            "/settings/backup/download?name=nope.db", follow_redirects=False
        )
        assert response.status_code == 303


class TestPathTraversal:
    """The web routes inherit resolve_backup's traversal guard."""

    _NAME = "../../../etc/passwd"

    def test_preview_rejects_traversal(self, client: TestClient) -> None:
        """Preview of a traversal name renders the error fragment, not a file."""
        response = client.get(f"/settings/backup/preview?name={self._NAME}")
        assert response.status_code == 200
        assert "pas pu être lue" in response.text

    @pytest.mark.parametrize("path", ["restore", "delete"])
    def test_post_routes_reject_traversal(self, client: TestClient, path: str) -> None:
        """Restore/delete of a traversal name redirect with an error, no side effect."""
        response = client.post(
            f"/settings/backup/{path}",
            data={"name": self._NAME},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_download_rejects_traversal(self, client: TestClient) -> None:
        """Download of a traversal name redirects instead of serving the file."""
        response = client.get(
            f"/settings/backup/download?name={self._NAME}", follow_redirects=False
        )
        assert response.status_code == 303


@pytest.mark.parametrize("route", ["create_backup", "restore_backup", "delete_backup"])
def test_backup_routes_are_async(route: str) -> None:
    """All backup routes run on the event loop, not a sync worker thread.

    A plain def route would reopen the shared SQLite connection on a worker
    thread and break unrelated requests.
    """
    assert inspect.iscoroutinefunction(getattr(settings_module, route))
