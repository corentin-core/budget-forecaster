"""Linking an overdue iteration to the operation that actually paid it.

Everything goes through the routes: the app's SQLite connection belongs to the
serving thread, so the test thread must not read the database directly.
"""

import re
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_DESCRIPTION = "Zzz unmatched insurance"


class Picker:
    """The picker for one unmatched iteration, and how to read it."""

    def __init__(
        self, client: TestClient, op_id: int, iteration: date, description: str
    ) -> None:
        self.client = client
        self.op_id = op_id
        self.iteration = iteration
        self.description = description
        self.path = f"/overdue/{op_id}/{iteration}/link"

    def page(self) -> str:
        """The picker page as the row opens it."""
        return self.client.get(self.path).text

    def list_fragment(self, **params: str) -> str:
        """The candidate list as search and show-all fetch it."""
        return self.client.get(f"{self.path}/candidates", params=params).text

    def candidate_ids(self, html: str) -> list[int]:
        """The operation ids the list offers, in the order it offers them."""
        return [int(m) for m in re.findall(r'name="operation_id" value="(\d+)"', html)]

    def scores(self, html: str) -> list[float]:
        """The match percentages shown, in list order."""
        return [float(m.replace(",", ".")) for m in re.findall(r"· ([\d,]+)\s*%", html)]

    def link(self, operation_id: int, return_to: str = "/") -> object:
        """Confirm one candidate, as its confirm form does."""
        return self.client.post(
            self.path,
            data={"operation_id": str(operation_id), "return_to": return_to},
            follow_redirects=False,
        )


def _create_unmatched(
    client: TestClient,
    app: FastAPI,
    *,
    amount: str,
    description: str = _DESCRIPTION,
    days_before_balance: int = 7,
) -> Picker:
    """Create a monthly payment whose iterations nothing will ever match."""
    iteration = app.state.app_service.balance_date - timedelta(days=days_before_balance)
    client.post(
        "/targets/planned",
        data={
            "description": description,
            "amount": amount,
            "category": "HOUSE_INSURANCE",
            "start_date": iteration.isoformat(),
            "recurring": "yes",
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
    listing = client.get("/targets?view=planned").text
    row = listing[listing.find(description) - 400 : listing.find(description)]
    found = re.findall(r"/targets/planned/(\d+)", row)
    assert found, "the new planned operation should be listed"
    return Picker(client, int(found[-1]), iteration, description)


@pytest.fixture(name="picker")
def picker_fixture(client: TestClient, app: FastAPI) -> Picker:
    """A picker for an expense nothing matched a week before the balance date."""
    return _create_unmatched(client, app, amount="-42.50")


def _card(client: TestClient) -> str:
    """The overdue card's markup, or an empty string when it is hidden."""
    html = client.get("/").text
    start = html.find('class="card overdue-card"')
    return html[start : html.find("</section>", start)] if start > 0 else ""


def _margin(client: TestClient) -> float:
    """The available margin as the home page shows it."""
    found = re.search(r'metric-value big">([^<]+)<', client.get("/").text)
    assert found, "the home page should show a margin"
    raw = found.group(1).replace(" ", "").replace("\xa0", "").replace(" ", "")
    return float(raw.replace("EUR", "").replace("€", "").replace(",", "."))


def _link_target(client: TestClient, operation_id: int) -> str:
    """What the operation's detail page says counts it, or an empty string."""
    html = client.get(f"/operations/{operation_id}").text
    found = re.search(r"<dd>\s*([^<]*?)\s*<form[^>]*/unlink", html, re.DOTALL)
    return found.group(1).strip() if found else ""


def _an_expense_label(client: TestClient, *, date_to: date | None = None) -> str:
    """An expense's label, so the candidate sign filter does not drop the match."""
    params = {"date_to": date_to.isoformat()} if date_to else {}
    listing = client.get("/operations", params=params).text
    for block in listing.split('<tr id="op-row-')[1:]:
        if 'class="num negative"' not in block:
            continue
        if found := re.search(r'<a href="/operations/\d+">([^<]+)</a>', block):
            return found.group(1).strip()
    raise AssertionError("the ledger should list an expense")


class TestRanking:
    """The list agrees with the matching the user already trusts."""

    def test_candidates_come_best_first(self, picker: Picker) -> None:
        """Ranked by the same score, so the top row is the likeliest payment."""
        scores = picker.scores(picker.page())
        assert scores, "the picker should offer candidates"
        assert scores == sorted(scores, reverse=True)

    def test_only_the_same_sign_is_offered(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A credit is never proposed as the payment of an expense."""
        expense = _create_unmatched(client, app, amount="-42.50", description="Zzz out")
        income = _create_unmatched(client, app, amount="42.50", description="Zzz in")

        for_expense = set(expense.candidate_ids(expense.list_fragment(all="true")))
        for_income = set(income.candidate_ids(income.list_fragment(all="true")))

        assert for_expense and for_income
        assert not for_expense & for_income


class TestWeakCandidates:
    """A padded list reads as an answer, so it is not padded."""

    def test_nothing_close_shows_nothing(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """An amount no operation comes near leaves the list empty, and says so."""
        odd = _create_unmatched(client, app, amount="-3333.33", description="Zzz odd")

        html = odd.page()

        assert not odd.candidate_ids(html)
        assert "ne correspond nettement" in html

    def test_the_weak_ones_stay_reachable(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Held back, not dropped: show-all reveals them."""
        odd = _create_unmatched(client, app, amount="-3333.33", description="Zzz odd")

        assert "?all=true" in odd.page()
        assert odd.candidate_ids(odd.list_fragment(all="true"))


class TestSearch:
    """The search reaches past the window the default list uses."""

    def test_it_finds_an_operation_the_default_list_leaves_out(
        self, client: TestClient, picker: Picker
    ) -> None:
        """Typing a remembered label must not answer "nothing"."""
        within = set(picker.candidate_ids(picker.list_fragment(all="true")))
        outside = picker.iteration - timedelta(days=61)
        needle = _an_expense_label(client, date_to=outside)[:8]

        found = picker.candidate_ids(picker.list_fragment(q=needle))

        assert found, f"searching {needle!r} should reach outside the window"
        assert set(found) - within, "the search should widen the candidate set"

    def test_a_search_that_finds_nothing_says_so(self, picker: Picker) -> None:
        """Distinct from "nothing matches closely": the user asked for this."""
        html = picker.list_fragment(q="zzz-no-such-label")

        assert not picker.candidate_ids(html)
        assert "correspond à cette recherche" in html


class TestLinking:
    """Linking settles the iteration."""

    def test_the_row_leaves_the_card_and_the_forecast_stops_expecting_it(
        self, client: TestClient, picker: Picker
    ) -> None:
        """The payment happened, so the amount is no longer awaited."""
        before = _margin(client)
        candidate = picker.candidate_ids(picker.page())[0]

        response = picker.link(candidate)

        assert response.status_code == 303
        assert picker.description not in _card(client)
        assert _margin(client) == pytest.approx(before + 42.50, abs=0.01)

    def test_it_asks_before_writing(self, picker: Picker) -> None:
        """Every candidate carries a confirm, since the undo is a trip away."""
        html = picker.page()
        start = html.find('<ul class="candidate-list">')
        block = html[start : html.find("</ul>", start)]
        offered = len(picker.candidate_ids(html))
        assert offered
        assert block.count("data-confirm-trigger") == offered
        assert block.count("data-confirm-cancel") == offered

    def test_return_to_off_the_app_falls_back_home(self, picker: Picker) -> None:
        """A back target is user input, so it is validated like any other."""
        candidate = picker.candidate_ids(picker.page())[0]

        response = picker.link(candidate, return_to="https://elsewhere.example")

        assert response.headers["location"] == "/"

    def test_an_iteration_that_is_not_overdue_is_refused(self, picker: Picker) -> None:
        """A stale row must not link to an iteration nothing derives."""
        settled = picker.iteration + timedelta(days=3)
        response = picker.client.get(f"/overdue/{picker.op_id}/{settled}/link")
        assert response.status_code == 404


class TestRePointing:
    """Correcting a mis-attribution is the case that sends the user here."""

    def test_an_already_linked_operation_says_what_counts_it(
        self, client: TestClient, picker: Picker
    ) -> None:
        """Hiding it would hide the very operation being looked for."""
        html = picker.list_fragment(all="true")
        badged = re.search(r'cand-badge">\s*déjà comptée pour ([^,<]+)', html)
        assert badged, "the demo data links operations, so a badge should show"

    def test_it_moves_the_link_and_hands_the_amount_back(
        self, client: TestClient, picker: Picker
    ) -> None:
        """One link per operation, and the previous target expects it again."""
        html = picker.list_fragment(all="true")
        offered = picker.candidate_ids(html)
        linked = [
            operation_id
            for operation_id in offered
            if _link_target(client, operation_id)
        ]
        assert linked, "the demo data should offer an already-linked candidate"
        stolen = linked[0]
        previous = _link_target(client, stolen)

        picker.link(stolen)

        assert _link_target(client, stolen) == picker.description
        assert previous != picker.description


class TestDecisionBecomesMoot:
    """A link outranks whatever the user had decided."""

    def test_the_picker_is_gone_once_a_decision_is_recorded(
        self, client: TestClient, picker: Picker
    ) -> None:
        """A decided iteration leaves the card, so its picker leaves with it."""
        client.post(f"/overdue/{picker.op_id}/{picker.iteration}/skip")

        assert client.get(picker.path).status_code == 404

    def test_restoring_a_decision_cannot_resurrect_a_linked_iteration(
        self, client: TestClient, picker: Picker
    ) -> None:
        """Undoing the decision leaves the link in charge, not the iteration."""
        candidate = picker.candidate_ids(picker.page())[0]
        client.post(f"/overdue/{picker.op_id}/{picker.iteration}/skip")
        client.post(
            f"/operations/{candidate}/link",
            data={
                "target_type": "planned",
                "target_id": str(picker.op_id),
                "iteration_date": picker.iteration.isoformat(),
            },
            follow_redirects=False,
        )

        client.post(f"/overdue/{picker.op_id}/{picker.iteration}/restore")

        assert picker.description not in _card(client)
        assert _link_target(client, candidate) == picker.description


class TestSettlingWithoutAnOperation:
    """The picker is not a dead end when no operation is the payment."""

    def test_both_decisions_are_offered_on_the_page(self, picker: Picker) -> None:
        """Otherwise an empty list says "go back and press what you cannot see"."""
        html = picker.page()
        assert f"/overdue/{picker.op_id}/{picker.iteration}/postpone" in html
        assert f"/overdue/{picker.op_id}/{picker.iteration}/skip" in html

    def test_a_decision_taken_there_redirects_instead_of_swapping(
        self, client: TestClient, picker: Picker
    ) -> None:
        """The picker carries neither the row nor the out-of-band figures."""
        response = client.post(
            f"/overdue/{picker.op_id}/{picker.iteration}/skip",
            data={"return_to": "/"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert picker.description not in _card(client)


def _break_the_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every alert derivation report a failed sync."""
    for module in ("home", "overdue"):
        monkeypatch.setattr(
            f"budget_forecaster.web.routes.{module}.sync_is_broken",
            lambda repository, consent_service: True,
        )


class TestFailedSync:
    """Linking an operation that is there is safe; deciding on absence is not."""

    def test_the_picker_opens_and_warns(
        self, picker: Picker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The list may be incomplete, which it says rather than refusing."""
        _break_the_sync(monkeypatch)

        html = picker.page()

        assert "peut-être absente" in html
        assert picker.candidate_ids(html)

    def test_it_withholds_the_two_decisions(
        self, picker: Picker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stopping to count a payment that did happen would be worse."""
        _break_the_sync(monkeypatch)

        html = picker.page()

        assert f"/overdue/{picker.op_id}/{picker.iteration}/skip" not in html

    def test_the_decision_routes_still_refuse(
        self, client: TestClient, picker: Picker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hiding the buttons is not the barrier."""
        _break_the_sync(monkeypatch)

        response = client.post(
            f"/overdue/{picker.op_id}/{picker.iteration}/skip", data={"return_to": "/"}
        )

        assert response.status_code == 409

    def test_linking_still_goes_through(
        self, client: TestClient, picker: Picker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The operation is in the database whatever the sync left out."""
        candidate = picker.candidate_ids(picker.page())[0]
        _break_the_sync(monkeypatch)

        response = picker.link(candidate)

        assert response.status_code == 303
        assert _link_target(client, candidate) == picker.description
