"""Manual file upload on the settings page.

The upload goes through the shared import service; these tests drive the real
route with the bundled BNP and Swile example exports.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "data"
_BNP_EXPORT = _EXAMPLES / "bnp-export-demo.xls"
_SWILE_EXPORT = _EXAMPLES / "swile-export-2026-03-04.zip"


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


@pytest.mark.parametrize("missing", [_BNP_EXPORT, _SWILE_EXPORT])
def test_example_files_exist(missing: Path) -> None:
    """Guard: the suite depends on the bundled example exports."""
    assert missing.is_file()
