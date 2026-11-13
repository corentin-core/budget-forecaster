"""Tests for the fingerprinted URLs of the static files."""

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from budget_forecaster.web import app as web_app
from budget_forecaster.web.app import static_url


def test_url_carries_a_hash_of_the_file() -> None:
    """The query changes with the file's content."""
    content = (Path(web_app.__file__).parent / "static" / "app.css").read_bytes()

    assert static_url("app.css") == (
        f"/static/app.css?v={hashlib.sha256(content).hexdigest()[:12]}"
    )


def test_pages_link_the_fingerprinted_stylesheet(client: TestClient) -> None:
    """Every static file a page links is fingerprinted, and served."""
    html = client.get("/trends").text

    assert f'href="{static_url("app.css")}"' in html
    assert 'src="/static/charts.js"' not in html
    assert client.get(static_url("charts.js")).status_code == 200
