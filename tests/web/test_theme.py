"""The theme switcher: what the server must render for the client to drive it."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestThemeSwitcher:
    """Auto / Light / Dark in Réglages, remembered per device."""

    def test_settings_offers_the_three_modes(self, client: TestClient) -> None:
        """The card renders the three buttons and loads the script."""
        markup = client.get("/settings").text
        for mode in ("auto", "light", "dark"):
            assert f'data-theme="{mode}"' in markup
        assert "/static/theme.js" in markup

    def test_no_mode_is_marked_server_side(self, client: TestClient) -> None:
        """The choice lives in the browser: a rendered active state is a guess."""
        markup = client.get("/settings").text
        assert 'aria-pressed="true"' not in markup
        assert 'class="active"' not in markup

    def test_a_stored_theme_is_applied_before_the_first_paint(
        self, client: TestClient
    ) -> None:
        """Deferred or in the body, it would flash the other theme first."""
        markup = client.get("/").text
        head, _, body = markup.partition("</head>")
        assert "localStorage.getItem('theme')" in head
        assert "colorScheme" in head
        assert "localStorage.getItem('theme')" not in body
