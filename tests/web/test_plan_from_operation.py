"""Creating a planned operation from an operation already in the ledger.

Everything goes through the routes: the app's SQLite connection belongs to the
serving thread, so the test thread must not read the database directly.
"""

import html as html_module
import re
from datetime import date
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient


class LedgerOperation(NamedTuple):
    """An operation as the ledger shows it, and what counts it."""

    operation_id: int
    description: str
    operation_date: date
    link_target: str
    """The name of the target the row points at, empty when unlinked."""


def _ledger_operations(client: TestClient, **params: str) -> list[LedgerOperation]:
    """Read the expense rows of the ledger, newest first."""
    listing = client.get("/operations", params=params).text
    operations = []
    for block in listing.split('<tr id="op-row-')[1:]:
        if 'class="num negative"' not in block:
            continue
        found = re.search(r'<a href="/operations/(\d+)[^"]*">([^<]+)</a>', block)
        day = re.search(r'class="date"[^>]*>(\d{2}/\d{2}/\d{4})<', block)
        if not found or not day:
            continue
        tag = re.search(r'class="link-tag"[^>]*>→ ([^<]+)<', block)
        operations.append(
            LedgerOperation(
                operation_id=int(found.group(1)),
                description=html_module.unescape(found.group(2)).strip(),
                operation_date=date(
                    *(int(p) for p in reversed(day.group(1).split("/")))
                ),
                link_target=tag.group(1).strip() if tag else "",
            )
        )
    return operations


def _unlinked(client: TestClient, **params: str) -> LedgerOperation:
    """An expense nothing counts yet, the case the feature is for."""
    for operation in _ledger_operations(client, **params):
        if not operation.link_target:
            return operation
    raise AssertionError("the demo ledger should hold an unlinked expense")


def _linked(client: TestClient) -> LedgerOperation:
    """An expense that already counts for something."""
    for operation in _ledger_operations(client):
        if operation.link_target:
            return operation
    raise AssertionError("the demo ledger should hold a linked expense")


def _seeded_page(client: TestClient, operation: LedgerOperation) -> str:
    """The create form as the operation's detail page opens it."""
    return client.get(
        "/targets/planned/new",
        params={
            "from_operation": str(operation.operation_id),
            "return_to": f"/operations/{operation.operation_id}",
        },
    ).text


def _form_fields(page: str) -> dict[str, str]:
    """The create form's values, as a browser would submit them."""
    start = page.find('id="target-form"')
    form = page[start : page.find("</form>", start)]
    fields: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", form):
        name = re.search(r'name="([^"]+)"', tag)
        if not name or ('type="checkbox"' in tag and "checked" not in tag):
            continue
        value = re.search(r'value="([^"]*)"', tag)
        fields[name.group(1)] = html_module.unescape(value.group(1) if value else "")
    for name, options in re.findall(
        r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', form, re.DOTALL
    ):
        if selected := re.search(r'value="([^"]+)"[^>]*selected', options):
            fields[name] = selected.group(1)
    return fields


def _create(client: TestClient, fields: dict[str, str], description: str) -> None:
    """Save the seeded form under a name the test can look for."""
    response = client.post(
        "/targets/planned",
        data={**fields, "description": description},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _link_target(client: TestClient, operation_id: int) -> str:
    """What the operation's detail page says counts it, or an empty string."""
    html = client.get(f"/operations/{operation_id}").text
    found = re.search(
        r"<dd>\s*<a[^>]*>([^<]*)</a>\s*<form[^>]*/unlink", html, re.DOTALL
    )
    return found.group(1).strip() if found else ""


class TestSeededForm:
    """What the form carries when it is opened from an operation."""

    def test_offers_the_action_on_the_operation(self, client: TestClient) -> None:
        """The detail page is where the flow starts."""
        operation = _unlinked(client)
        page = client.get(f"/operations/{operation.operation_id}").text
        assert f"/targets/planned/new?from_operation={operation.operation_id}" in page
        assert "Créer une opération planifiée" in page

    def test_seeds_a_monthly_operation_from_the_operation(
        self, client: TestClient
    ) -> None:
        """Amount, category and date come from the operation, monthly by default."""
        operation = _unlinked(client)
        fields = _form_fields(_seeded_page(client, operation))
        assert fields["source_operation_id"] == str(operation.operation_id)
        assert fields["start_date"] == operation.operation_date.isoformat()
        assert fields["recurring"] == "yes"
        assert (fields["period_value"], fields["period_unit"]) == ("1", "months")
        assert float(fields["amount"]) < 0

    def test_derives_the_name_and_the_keyword_from_the_label(
        self, client: TestClient
    ) -> None:
        """A word of the label, not the label: it has to still match next month."""
        operation = _unlinked(client)
        page = _seeded_page(client, operation)
        fields = _form_fields(page)
        assert fields["description"] in operation.description
        assert fields["keywords"] == fields["description"]
        assert "Reconnaître par" in page
        assert operation.description in html_module.unescape(page)

    def test_warns_when_the_first_occurrences_are_already_late(
        self, client: TestClient
    ) -> None:
        """Months of occurrences with nothing to match them land on Accueil."""
        old = _unlinked(client, date_to="2026-04-30")
        assert "apparaîtront en retard" in _seeded_page(client, old)

    def test_says_nothing_about_lateness_for_a_recent_operation(
        self, client: TestClient
    ) -> None:
        """This month's payment forecasts forward, so there is nothing to warn."""
        assert "apparaîtront en retard" not in _seeded_page(client, _unlinked(client))

    def test_an_unknown_operation_leaves_the_form_empty(
        self, client: TestClient
    ) -> None:
        """A stale link starts a blank form rather than failing."""
        fields = _form_fields(
            client.get("/targets/planned/new", params={"from_operation": "999999"}).text
        )
        assert "source_operation_id" not in fields
        assert fields["description"] == ""


class TestLinkingBack:
    """The operation the form came from, once the planned operation exists."""

    def test_counts_the_source_operation(self, client: TestClient) -> None:
        """The whole point: the payment you saw is the first occurrence."""
        operation = _unlinked(client)
        _create(
            client, _form_fields(_seeded_page(client, operation)), "Zzz seeded plan"
        )
        assert _link_target(client, operation.operation_id) == "Zzz seeded plan"

    def test_leaves_an_operation_linked_elsewhere_alone(
        self, client: TestClient
    ) -> None:
        """An existing link is the user's decision, not ours to move."""
        operation = _linked(client)
        before = _link_target(client, operation.operation_id)
        _create(client, _form_fields(_seeded_page(client, operation)), "Zzz other plan")
        assert _link_target(client, operation.operation_id) == before
        assert before != "Zzz other plan"


class TestNearDuplicateNotice:
    """What the form says when the payment may already be forecast."""

    @pytest.fixture(name="duplicated")
    def duplicated_fixture(self, client: TestClient) -> LedgerOperation:
        """An operation a planned operation already fits closely."""
        operation = _unlinked(client)
        _create(client, _form_fields(_seeded_page(client, operation)), "Zzz existing")
        return operation

    def test_names_the_operation_that_may_already_be_it(
        self, client: TestClient, duplicated: LedgerOperation
    ) -> None:
        """Unlinked again, the payment could still belong to what exists."""
        client.post(f"/operations/{duplicated.operation_id}/unlink")
        page = _seeded_page(client, duplicated)
        assert "pourrait déjà être ce paiement" in page
        assert f"/operations/{duplicated.operation_id}/link" in page
        assert "Zzz existing" in page

    def test_says_when_the_operation_already_counts_for_it(
        self, client: TestClient, duplicated: LedgerOperation
    ) -> None:
        """A second entry here would double-count the payment every month."""
        page = _seeded_page(client, duplicated)
        assert "compte déjà pour" in page
        assert "Zzz existing" in page

    def test_stays_quiet_without_a_close_match(self, client: TestClient) -> None:
        """No notice on an operation nothing forecasts."""
        page = _seeded_page(client, _unlinked(client))
        assert "pourrait déjà être ce paiement" not in page
        assert "compte déjà pour" not in page


class TestSeedSurvivesAnError:
    """A rejected form comes back seeded, not stripped."""

    def test_keeps_the_source_operation_and_the_label(self, client: TestClient) -> None:
        """The link would be lost silently if the hidden field vanished."""
        operation = _unlinked(client)
        fields = _form_fields(_seeded_page(client, operation))
        response = client.post(
            "/targets/planned",
            data={**fields, "end_date": "2000-01-01"},
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert f'name="source_operation_id" value="{operation.operation_id}"' in (
            response.text
        )
        assert "Reconnaître par" in response.text

    def test_keeps_what_the_user_typed(self, client: TestClient) -> None:
        """The edited name comes back, not the seeded one."""
        operation = _unlinked(client)
        fields = _form_fields(_seeded_page(client, operation))
        response = client.post(
            "/targets/planned",
            data={**fields, "description": "Zzz edited", "end_date": "2000-01-01"},
            follow_redirects=False,
        )
        assert 'value="Zzz edited"' in response.text
