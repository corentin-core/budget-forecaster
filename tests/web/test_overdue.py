"""The Accueil overdue card and the decisions it offers.

Everything goes through the routes: the app's SQLite connection belongs to the
serving thread, so the test thread must not read the database directly.
"""

import re
from datetime import date, timedelta
from typing import NamedTuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.services.application_service import ApplicationService

_DESCRIPTION = "Zzz unmatched rent"


class Overdue(NamedTuple):
    """The unmatched iteration a test acts on."""

    op_id: int
    iteration: date
    amount: float


def _create_unmatched(
    client: TestClient,
    app: FastAPI,
    *,
    days_before_balance: int,
    amount: str,
    recurring: bool = True,
) -> Overdue:
    """Create a payment whose iterations nothing will ever match."""
    iteration = app.state.app_service.balance_date - timedelta(days=days_before_balance)
    client.post(
        "/targets/planned",
        data={
            "description": _DESCRIPTION,
            "amount": amount,
            "category": "RENT",
            "start_date": iteration.isoformat(),
            "recurring": "yes" if recurring else "no",
            "period_value": "1",
            "period_unit": "months",
            "end_date": "",
            "keywords": "zzz-nothing-matches-this",
            "approx_days": "5",
            "approx_ratio": "0.05",
            "return_to": "/targets",
        },
        follow_redirects=False,
    )
    # Past one-time payments are inactive, which the listing hides by default.
    listing = client.get("/targets?view=planned&submitted=1&active=false").text
    row = listing[listing.find(_DESCRIPTION) - 400 : listing.find(_DESCRIPTION)]
    found = re.findall(r"/targets/planned/(\d+)", row)
    assert found, "the new planned operation should be listed"
    return Overdue(int(found[-1]), iteration, abs(float(amount)))


@pytest.fixture(name="overdue")
def overdue_fixture(client: TestClient, app: FastAPI) -> Overdue:
    """A monthly payment whose iteration a week before the balance date is unmatched."""
    return _create_unmatched(client, app, days_before_balance=7, amount="-777")


def _card(client: TestClient) -> str:
    """The overdue card's markup; it is always on the page, settled or not."""
    html = client.get("/").text
    start = html.find('class="card overdue-card"')
    return html[start : html.find("</section>", start)] if start > 0 else ""


def _all_upcoming(client: TestClient) -> str:
    """Every page of the upcoming list, since the card shows only the first."""
    pages = [client.get("/").text]
    for offset in (10, 20, 30, 40):
        pages.append(client.get(f"/upcoming?offset={offset}").text)
    return "".join(pages)


def _margin_value(client: TestClient) -> float:
    """The available margin as the page shows it."""
    html = client.get("/").text
    hero = html[html.find('id="margin-hero"') :]
    found = re.search(r'metric-value">([^<]+)<', hero[: hero.find("</section>")])
    assert found, "the home page should show a margin"
    raw = found.group(1).replace("\u202f", "").replace("\xa0", "")
    raw = raw.replace(" ", "").replace("EUR", "").replace(",", ".")
    return float(raw)


def _decided_section(client: TestClient, op_id: int) -> str:
    """The decided-occurrences markup on a planned operation's edit page."""
    html = client.get(f"/targets/planned/{op_id}").text
    start = html.find('class="card decided-card"')
    return html[start : html.find("</section>", start)] if start > 0 else ""


class TestCardVisibility:
    """The card holds its place whether or not anything needs a decision."""

    def test_says_so_when_nothing_awaits_a_decision(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settled card, so the cards below it do not move between visits."""
        monkeypatch.setattr(
            ApplicationService, "get_overdue_iterations", lambda self: ()
        )

        card = _card(client)

        assert "réglées" in card
        assert "overdue-item" not in card

    def test_lists_the_unmatched_iteration(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """The row carries the amount and how late the payment is."""
        card = _card(client)
        assert _DESCRIPTION in card
        assert "777,00" in card
        assert "7 j" in card

    def test_offers_both_decisions(self, client: TestClient, overdue: Overdue) -> None:
        """Postpone and stop-counting are both reachable from the row."""
        card = _card(client)
        assert f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone" in card
        assert f"/overdue/{overdue.op_id}/{overdue.iteration}/skip" in card

    def test_the_row_leads_to_the_picker_not_a_description_filter(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """A planned operation and a bank line share no word, so no filter works.

        Both the description and the primary action open the picker instead.
        """
        card = _card(client)
        picker = f"/overdue/{overdue.op_id}/{overdue.iteration}/link"
        assert card.count(f'href="{picker}"') == 2
        assert "/operations?search=" not in card
        assert client.get(picker).status_code == 200

    def test_the_row_opens_the_planned_operation(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Fixing the amount, the day or the keywords starts from the row."""
        card = _card(client)
        assert f'href="/targets/planned/{overdue.op_id}?return_to=/"' in card
        assert "toutes les occurrences" in card

    def test_nav_badge_counts_them(self, client: TestClient, overdue: Overdue) -> None:
        """The count is visible from any page, and it is the real count."""
        rows = _card(client).count('class="overdue-item"')
        html = client.get("/trends").text
        badge = html.split('id="overdue-badge-side"')[1][:60]
        assert "hidden" not in badge
        assert f">{rows}<" in badge


class TestPostpone:
    """Moving an iteration to a later date."""

    def test_form_offers_chips_before_a_date_field(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Typing a date on a phone is the fallback, not the default."""
        html = client.get(f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone").text
        assert "Reporter au" in html
        assert "prochaine échéance" in html
        assert "demain" in html
        assert 'name="postponed_to"' in html

    def test_the_offered_dates_are_all_ahead_of_today(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """A chip pointing at a passed day would be late again at once."""
        html = client.get(f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone").text
        offered = re.findall(r'name="postponed_to"\s+value="([\d-]+)"', html)
        assert offered
        assert all(date.fromisoformat(value) > date.today() for value in offered)

    def test_records_the_chosen_date_and_refreshes_the_margin(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """The response settles the row and carries the out-of-band margin."""
        target = date.today() + timedelta(days=20)

        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone",
            data={"postponed_to": target.isoformat()},
        )

        assert response.status_code == 200
        assert "reportée au" in response.text
        assert 'id="margin-hero"' in response.text
        assert "hx-swap-oob" in response.text
        decided = _decided_section(client, overdue.op_id)
        assert target.strftime("%d/%m/%Y") in decided

    def test_a_chip_wins_over_the_empty_date_field_beside_it(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """A chip and the free date field share a name; flattening the form to a
        dict would keep the empty one and reject the request."""
        chosen = date.today() + timedelta(days=20)

        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone",
            data={"postponed_to": [chosen.isoformat(), ""]},
        )

        assert response.status_code == 200
        assert chosen.strftime("%d/%m/%Y") in _decided_section(client, overdue.op_id)

    def test_the_postponed_iteration_shows_in_upcoming(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """It leaves the card and reappears where it is now expected."""
        target = date.today() + timedelta(days=3)
        client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone",
            data={"postponed_to": target.isoformat()},
        )

        upcoming = _all_upcoming(client)

        assert f"reportée du {overdue.iteration.strftime('%d/%m/%Y')}" in upcoming
        assert _DESCRIPTION not in _card(client)

    def test_a_date_before_the_iteration_is_refused(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """The domain invariant surfaces as a bad request, nothing is stored."""
        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone",
            data={"postponed_to": (overdue.iteration - timedelta(days=1)).isoformat()},
        )

        assert response.status_code == 400
        assert _decided_section(client, overdue.op_id) == ""

    def test_a_broken_date_is_refused(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """A malformed date never reaches the domain."""
        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone",
            data={"postponed_to": "not-a-date"},
        )
        assert response.status_code == 400

    def test_a_broken_iteration_date_is_a_404(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """The iteration date comes from the path, so it is validated there."""
        assert (
            client.get(f"/overdue/{overdue.op_id}/not-a-date/postpone").status_code
            == 404
        )


class TestSkip:
    """Declaring that a payment never happened."""

    def test_states_the_amount_it_gives_back(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """The user sees the euro effect before confirming."""
        card = _card(client)
        assert "Ne plus la compter ?" in card
        assert "777,00" in card

    def test_records_the_decision(self, client: TestClient, overdue: Overdue) -> None:
        """The row settles and the decision is listed on the operation."""
        response = client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        assert response.status_code == 200
        assert "plus comptée" in response.text
        assert 'id="margin-hero"' in response.text
        assert "non comptée" in _decided_section(client, overdue.op_id)

    def test_the_amount_leaves_the_projection(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Not counting it raises the margin the user is looking at."""
        before = _margin_value(client)

        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        assert _margin_value(client) - before == pytest.approx(overdue.amount)

    def test_an_unknown_operation_is_a_404(self, client: TestClient) -> None:
        """A stale row must not record a decision about nothing."""
        assert client.post("/overdue/999999/2026-03-05/skip").status_code == 404


class TestRestore:
    """Undoing a decision."""

    def test_puts_the_row_back(self, client: TestClient, overdue: Overdue) -> None:
        """The iteration returns to its derived state, decision dropped."""
        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        response = client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/restore")

        assert response.status_code == 200
        assert _DESCRIPTION in response.text
        assert _decided_section(client, overdue.op_id) == ""

    def test_reachable_from_the_planned_operation(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Past the immediate undo, decisions live on the edit page."""
        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        decided = _decided_section(client, overdue.op_id)

        assert "Rétablir" in decided
        assert f"/overdue/{overdue.op_id}/{overdue.iteration}/restore" in decided


def _break_the_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every alert derivation report a failed sync."""
    for module in ("home", "overdue"):
        monkeypatch.setattr(
            f"budget_forecaster.web.routes.{module}.sync_is_broken",
            lambda repository, consent_service: True,
        )


class TestDegradedState:
    """A failed sync must not invite decisions on incomplete data."""

    def test_actions_are_withheld_from_the_card(
        self,
        client: TestClient,
        overdue: Overdue,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The card explains itself instead of offering buttons."""
        _break_the_sync(monkeypatch)

        card = _card(client)

        assert "Synchronisez avant de décider" in card
        assert "/postpone" not in card

    @pytest.mark.parametrize("action", ["skip", "postpone"])
    def test_the_writes_refuse_too(
        self,
        client: TestClient,
        overdue: Overdue,
        monkeypatch: pytest.MonkeyPatch,
        action: str,
    ) -> None:
        """Hiding the buttons is not the barrier: the routes enforce it."""
        _break_the_sync(monkeypatch)

        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/{action}",
            data={"postponed_to": (date.today() + timedelta(days=5)).isoformat()},
        )

        assert response.status_code == 409
        assert _decided_section(client, overdue.op_id) == ""

    def test_the_fragments_offer_nothing_either(
        self,
        client: TestClient,
        overdue: Overdue,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A row fetched while the sync is broken must not carry the actions."""
        _break_the_sync(monkeypatch)

        response = client.get(f"/overdue/{overdue.op_id}/{overdue.iteration}/row")

        assert response.status_code == 409

    def test_an_old_balance_date_alone_does_not_withhold_them(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Importing statements by hand always leaves an old balance date."""
        card = _card(client)
        assert "/postpone" in card


class TestUncountedIteration:
    """An iteration past the late horizon is listed, not counted."""

    def test_it_says_so(self, client: TestClient, app: FastAPI) -> None:
        """The money already left the forecast, which the row states."""
        _create_unmatched(client, app, days_before_balance=60, amount="-321")

        card = _card(client)

        assert _DESCRIPTION in card
        assert "non comptée" in card

    def test_it_can_still_be_pulled_back(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A forgotten payment the user finally owes is postponable."""
        overdue = _create_unmatched(client, app, days_before_balance=60, amount="-321")

        card = _card(client)

        assert f"/overdue/{overdue.op_id}/{overdue.iteration}/postpone" in card


class TestListingWindow:
    """The card stops one late horizon past the one that stopped counting."""

    def test_an_iteration_inside_the_window_is_listed(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The last day of the window still asks for a decision."""
        _create_unmatched(
            client, app, days_before_balance=62, amount="-321", recurring=False
        )

        assert _DESCRIPTION in _card(client)

    def test_an_iteration_past_the_window_is_gone(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """One day later nobody will act on it: it leaves the card and the badge."""
        before = _card(client).count('class="overdue-item"')

        _create_unmatched(
            client, app, days_before_balance=63, amount="-321", recurring=False
        )

        card = _card(client)
        assert _DESCRIPTION not in card
        assert card.count('class="overdue-item"') == before

    def test_its_actions_go_with_it(self, client: TestClient, app: FastAPI) -> None:
        """No route acts on a row the card no longer offers."""
        gone = _create_unmatched(
            client, app, days_before_balance=63, amount="-321", recurring=False
        )

        assert (
            client.get(f"/overdue/{gone.op_id}/{gone.iteration}/link").status_code
            == 404
        )
        assert (
            client.post(f"/overdue/{gone.op_id}/{gone.iteration}/skip").status_code
            == 404
        )


class TestUnknownIterations:
    """A decision must land on an iteration that actually awaits one."""

    @pytest.mark.parametrize("action", ["skip", "postpone", "restore"])
    def test_an_iteration_that_is_not_overdue_is_a_404(
        self, client: TestClient, overdue: Overdue, action: str
    ) -> None:
        """Otherwise a stale tab writes a decision about nothing, forever."""
        response = client.post(
            f"/overdue/{overdue.op_id}/2099-12-31/{action}",
            data={"postponed_to": "2100-01-01"},
        )
        assert response.status_code == 404
        assert _decided_section(client, overdue.op_id) == ""

    def test_a_week_date_is_a_404(self, client: TestClient, overdue: Overdue) -> None:
        """One URL per iteration: ISO week dates would alias another day."""
        assert client.get(f"/overdue/{overdue.op_id}/2026-W25-1/row").status_code == 404

    def test_cancelling_the_postpone_form_brings_the_row_back(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Same markup the card renders, so no affordance is lost."""
        response = client.get(f"/overdue/{overdue.op_id}/{overdue.iteration}/row")

        assert response.status_code == 200
        assert _DESCRIPTION in response.text
        assert f"/overdue/{overdue.op_id}/{overdue.iteration}/skip" in response.text


class TestUndoRefreshesEverything:
    """An undo moves the same figures the decision moved."""

    def test_it_carries_the_margin_and_the_badge(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Leaving them stale would show a number the data no longer supports."""
        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        response = client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/restore")

        assert 'id="margin-hero"' in response.text
        assert 'id="overdue-badge-side"' in response.text
        assert 'id="overdue-head"' in response.text

    def test_the_margin_goes_back_to_its_value(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """The decision and its undo cancel out."""
        before = _margin_value(client)
        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/restore")

        assert _margin_value(client) == pytest.approx(before)

    def test_from_the_planned_operation_page_it_swaps_nothing_else(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """That page has neither the card's markup nor its swap targets."""
        client.post(f"/overdue/{overdue.op_id}/{overdue.iteration}/skip")

        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/restore",
            headers={"HX-Target": f"decided-{overdue.op_id}-{overdue.iteration}"},
        )

        assert response.status_code == 200
        assert "overdue-item" not in response.text
        assert "margin-hero" not in response.text
        assert _decided_section(client, overdue.op_id) == ""

    def test_the_hero_says_there_is_no_forecast_yet(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The slot stays, pointing at what would fill it."""
        monkeypatch.setattr(
            ApplicationService, "get_available_margin", lambda self, month: None
        )

        html = client.get("/").text

        hero = html[html.find('id="margin-hero"') :]
        hero = hero[: hero.find("</section>")]
        assert "Pas encore de prévisionnel" in hero
        assert "Ajoute un budget ou une opération prévue" in hero
        assert "margin-None" not in html


class TestDecidingKeepsTheUndo:
    """A decision must not swap away the row it is writing into."""

    def test_the_last_decision_leaves_a_settled_row_to_undo(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """Settling the only overdue payment still offers to put it back."""
        response = client.post(
            f"/overdue/{overdue.op_id}/{overdue.iteration}/skip",
            headers={"HX-Request": "true"},
        )

        assert response.status_code == 200
        assert "overdue-item settled" in response.text
        assert f"/overdue/{overdue.op_id}/{overdue.iteration}/restore" in response.text

    def test_no_response_swaps_the_card_around_its_own_row(
        self, client: TestClient, overdue: Overdue
    ) -> None:
        """An out-of-band card swap would detach the row htmx targets."""
        for action in ("skip", "postpone"):
            response = client.post(
                f"/overdue/{overdue.op_id}/{overdue.iteration}/{action}",
                data={"until": "2026-12-01"},
                headers={"HX-Request": "true"},
            )
            body = response.text
            assert 'id="overdue-card"' not in body, action
