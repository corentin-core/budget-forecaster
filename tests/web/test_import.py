"""Manual file upload on the settings page.

The upload goes through the shared import service; these tests drive the real
route with the bundled BNP and Swile example exports.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from budget_forecaster.web.routes import settings as settings_route

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "data"
_BNP_EXPORT = _EXAMPLES / "bnp-export-demo.xls"
# The demo generator stamps the Swile export with its generation date, so find it
# by pattern: pinning the date would break the suite on every regeneration.
_SWILE_EXPORT = next(
    _EXAMPLES.glob("swile-export-*.zip"), _EXAMPLES / "swile-export.zip"
)


def _upload(client: TestClient, name: str, data: bytes) -> str:
    """Post one file to the import route and return the rendered fragment."""
    response = client.post(
        "/settings/import", files={"file": (name, data, "application/octet-stream")}
    )
    assert response.status_code == 200
    return response.text


class TestUploadForm:
    """The settings page exposes the upload entry point."""

    def test_form_is_shown(self, client: TestClient) -> None:
        """The Imports card carries the upload form posting to the route."""
        html = client.get("/settings").text
        assert "Importer un relevé bancaire" in html
        assert 'hx-post="/settings/import"' in html

    def test_accepts_bnp_and_swile_extensions(self, client: TestClient) -> None:
        """The file picker filters to the supported export extensions."""
        html = client.get("/settings").text
        assert 'accept=".xls,.zip"' in html


class TestSupportedImport:
    """A supported export is imported and summarised inline."""

    def test_bnp_export_imported(self, client: TestClient) -> None:
        """A BNP .xls upload is imported and its summary rendered."""
        html = _upload(client, _BNP_EXPORT.name, _BNP_EXPORT.read_bytes())
        assert "Importé" in html
        assert "opération(s)" in html

    def test_swile_export_imported(self, client: TestClient) -> None:
        """A Swile .zip upload is imported and its summary rendered."""
        html = _upload(client, _SWILE_EXPORT.name, _SWILE_EXPORT.read_bytes())
        assert "Importé" in html
        assert "opération(s)" in html

    def test_swile_needs_its_naming_pattern(self, client: TestClient) -> None:
        """The Swile adapter matches on the file name, so a renamed zip is
        rejected — the upload must preserve the original basename."""
        html = _upload(client, "renamed.zip", _SWILE_EXPORT.read_bytes())
        assert "Fichier non supporté" in html


class TestRejectedImport:
    """Unsupported uploads are rejected without importing."""

    def test_unsupported_file(self, client: TestClient) -> None:
        """An unknown format is refused, naming the rejected file."""
        html = _upload(client, "photo.png", b"not a bank export")
        assert "Fichier non supporté : photo.png" in html

    def test_empty_filename(self, client: TestClient) -> None:
        """A submission with no file gets the no-file message, not an error."""
        response = client.post(
            "/settings/import", files={"file": ("", b"", "application/octet-stream")}
        )
        assert response.status_code == 200
        assert "Aucun fichier sélectionné" in response.text

    def test_requires_authentication(self, anon_client: TestClient) -> None:
        """The route is behind the session guard like every other page."""
        response = anon_client.post(
            "/settings/import",
            files={"file": ("photo.png", b"x", "application/octet-stream")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login")


def _pin_temp_dir(monkeypatch: pytest.MonkeyPatch, box: Path) -> None:
    """Force the route to use `box` as its temp dir, created fresh each call."""

    def fake_mkdtemp(**_: object) -> str:
        box.mkdir(parents=True, exist_ok=True)
        return str(box)

    monkeypatch.setattr(settings_route.tempfile, "mkdtemp", fake_mkdtemp)


class TestTempFileHandling:
    """The upload writes to a throwaway dir that must never leak."""

    def test_temp_dir_removed_after_import(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The temp dir is gone after a success and after a rejection."""
        box = tmp_path / "box"
        _pin_temp_dir(monkeypatch, box)
        _upload(client, _BNP_EXPORT.name, _BNP_EXPORT.read_bytes())
        assert not box.exists()

        _upload(client, "photo.png", b"not a bank export")
        assert not box.exists()

    def test_traversal_filename_stays_in_the_box(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A ../-laden name is reduced to its basename, so nothing is written
        outside the temp dir — an escaped file would survive the cleanup."""
        box = tmp_path / "box"
        _pin_temp_dir(monkeypatch, box)
        response = client.post(
            "/settings/import",
            files={"file": ("../escaped.xls", b"x", "application/octet-stream")},
        )
        assert response.status_code == 200
        assert not (tmp_path / "escaped.xls").exists()


@pytest.mark.parametrize("missing", [_BNP_EXPORT, _SWILE_EXPORT])
def test_example_files_exist(missing: Path) -> None:
    """Guard: the suite depends on the bundled example exports."""
    assert missing.is_file()
