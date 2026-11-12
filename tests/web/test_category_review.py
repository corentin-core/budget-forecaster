"""Reviewing guessed categories in the ledger, and the one-click suggestion."""

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.core.types import Category, CategorySource
from budget_forecaster.services.application_service import ApplicationService

_HX = {"HX-Request": "true"}


def _service(app: FastAPI) -> ApplicationService:
    service: ApplicationService = app.state.app_service
    return service


def _row_ids(html: str) -> set[int]:
    return {int(i) for i in re.findall(r'id="op-row-(\d+)"', html)}


def _target(html: str, operation_id: int) -> str | None:
    """The linked target a ledger row points to, if any."""
    row = html[html.index(f'id="op-row-{operation_id}"') :]
    found = re.search(r'href="(/targets/[^"?]+)', row[: row.index("</tr>")])
    return found.group(1) if found else None


def _guessed_ids(app: FastAPI) -> set[int]:
    return {op.unique_id for op in _service(app).operations if op.is_category_guessed}


class TestReviewFilter:
    """The "To review" filter lists the categories the import guessed."""

    def test_lists_only_guessed_categories(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Every guessed operation is listed, and nothing else."""
        guessed = _guessed_ids(app)
        assert guessed, "the demo database should have guessed categories"

        html = client.get("/operations?review=true").text

        assert _row_ids(html) == guessed

    def test_rows_mark_the_automatic_category(self, client: TestClient) -> None:
        """An automatic row shows "(auto)" in its dropdown and a validate button."""
        html = client.get("/operations?review=true").text

        assert "(auto)</option>" in html
        assert "/confirm" in html

    def test_picking_the_plain_entry_validates(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The plain entry of the same category is a choice of its own."""
        operation_id = min(_guessed_ids(app))
        category = _service(app).get_operation_by_id(operation_id).category

        client.post(
            f"/operations/{operation_id}/categorize",
            data={"category": category.value},
            headers=_HX,
        )

        after = _service(app).get_operation_by_id(operation_id)
        assert (after.category, after.category_source) == (
            category,
            CategorySource.MANUAL,
        )


class TestConfirm:
    """Confirming makes a guess the user's, without changing the category."""

    def test_confirm_one(self, client: TestClient, app: FastAPI) -> None:
        """The row loses its review line and the category becomes manual."""
        operation_id = min(_guessed_ids(app))
        before = _service(app).get_operation_by_id(operation_id)

        response = client.post(f"/operations/{operation_id}/confirm", headers=_HX)

        assert response.status_code == 200
        assert f'id="op-row-{operation_id}"' in response.text
        assert "/confirm" not in response.text
        after = _service(app).get_operation_by_id(operation_id)
        assert (after.category, after.category_source) == (
            before.category,
            CategorySource.MANUAL,
        )

    def test_confirm_keeps_the_link(self, client: TestClient, app: FastAPI) -> None:
        """The category does not change, so neither does the link."""
        html = client.get("/operations?review=true").text
        operation_id, target = next(
            (int(i), _target(html, int(i)))
            for i in sorted(_guessed_ids(app))
            if _target(html, int(i))
        )

        response = client.post(f"/operations/{operation_id}/confirm", headers=_HX)

        assert _target(response.text, operation_id) == target

    def test_confirm_in_bulk_empties_the_filter(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Confirming every guessed row from the filter leaves it empty."""
        guessed = sorted(_guessed_ids(app))

        response = client.post(
            "/operations/confirm",
            data={"ids": [str(i) for i in guessed], "review": "true"},
            headers=_HX,
        )

        assert response.status_code == 200
        assert not _row_ids(response.text)
        assert not _guessed_ids(app)

    def test_confirm_leaves_a_manual_category_alone(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Selecting a manual row along with a guessed one changes nothing on it."""
        manual = next(
            op for op in _service(app).operations if op.is_categorized_by_hand
        )
        guessed = min(_guessed_ids(app))

        client.post(
            "/operations/confirm",
            data={"ids": [str(manual.unique_id), str(guessed)]},
            headers=_HX,
        )

        assert _service(app).get_operation_by_id(manual.unique_id) == manual
        assert _service(app).get_operation_by_id(guessed).is_categorized_by_hand

    def test_confirm_keeps_the_review_filter(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The swapped row links back to the filtered ledger."""
        operation_id = min(_guessed_ids(app))

        response = client.post(
            f"/operations/{operation_id}/confirm?review=true", headers=_HX
        )

        assert "review%3Dtrue" in response.text

    def test_changing_the_category_ends_the_review(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Picking another category is a review too: the row leaves the filter."""
        operation_id = min(_guessed_ids(app))

        client.post(
            f"/operations/{operation_id}/categorize",
            data={"category": Category.OTHER.value},
            headers=_HX,
        )

        assert operation_id not in _row_ids(client.get("/operations?review=true").text)


class TestSuggestion:
    """An uncategorized operation offers the category its payee usually gets."""

    def test_suggestion_categorizes_in_one_click(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Categorizing one payment of a payee suggests it for the others."""
        service = _service(app)
        uncategorized = service.get_uncategorized_operations()
        first, second = next(
            (a, b)
            for a in uncategorized
            for b in uncategorized
            if a.unique_id != b.unique_id and a.description == b.description
        )
        client.post(
            f"/operations/{first.unique_id}/categorize",
            data={"category": Category.LEISURE.value},
            headers=_HX,
        )

        html = client.get("/operations?uncategorized=true").text
        row = html[html.index(f'id="op-row-{second.unique_id}"') :]
        row = row[: row.index("</tr>")]
        assert '"category": "leisure"' in row

        client.post(
            f"/operations/{second.unique_id}/categorize",
            data={"category": Category.LEISURE.value},
            headers=_HX,
        )
        after = service.get_operation_by_id(second.unique_id)
        assert (after.category, after.category_source) == (
            Category.LEISURE,
            CategorySource.MANUAL,
        )

    def test_no_suggestion_without_a_manual_categorization(
        self, client: TestClient
    ) -> None:
        """A payee the user never categorized gets no suggestion."""
        html = client.get("/operations?uncategorized=true").text

        assert "hx-vals" not in html
