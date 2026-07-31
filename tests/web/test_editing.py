"""Write routes (#305): target CRUD/split, categorize, link, and the drill-down.

Each test drives the HTTP layer over a copy of the demo database and checks the
observable result (persisted state, refreshed fragment, forecast reload).
"""

import re
import unicodedata
from datetime import date

from fastapi.testclient import TestClient

from budget_forecaster.web.formatting import category_name

_RECURRING_BUDGET = {
    "description": "Test Budget",
    "amount": "-300",
    "category": "GROCERIES",
    "start_date": "2026-01-01",
    "duration_value": "1",
    "duration_unit": "months",
    "recurring": "yes",
    "period_value": "1",
    "period_unit": "months",
    "end_date": "",
    "return_to": "/targets",
}


def _budget_id(client: TestClient, description: str) -> int:
    """Return the id of the first budget row matching the description."""
    if not (ids := _budget_ids(client, description)):
        raise AssertionError(f"budget {description!r} not found in /targets")
    return ids[0]


def _budget_ids(client: TestClient, description: str) -> list[int]:
    """Return every budget id whose row links show the given description.

    Queries with active-only off so past split segments are visible too.
    """
    page = client.get("/targets?submitted=1").text
    return [
        int(bid)
        for bid, label in re.findall(
            r"/targets/budget/(\d+)\?return_to[^>]*>\s*([^<]+)", page
        )
        if description in label
    ]


def _period_value(client: TestClient, budget_id: int) -> str:
    """Read the period value shown on a budget's edit form."""
    form = client.get(f"/targets/budget/{budget_id}").text
    return re.search(r'name="period_value"[^>]*value="(\d+)"', form).group(1)


def _amount_value(client: TestClient, budget_id: int) -> str:
    """Read the amount shown on a budget's edit form."""
    form = client.get(f"/targets/budget/{budget_id}").text
    return re.search(r'name="amount"[^>]*value="(-?\d+(?:\.\d+)?)"', form).group(1)


class TestTargetCrud:
    """Create, edit, split and delete budgets and planned operations."""

    def test_create_budget_appears_in_list(self, client: TestClient) -> None:
        """A created budget shows up on the management page."""
        response = client.post(
            "/targets/budget", data=_RECURRING_BUDGET, follow_redirects=False
        )
        assert response.status_code == 303
        assert "Test Budget" in client.get("/targets").text

    def test_update_budget_changes_amount(self, client: TestClient) -> None:
        """Editing a budget persists the new amount into its edit form."""
        client.post("/targets/budget", data=_RECURRING_BUDGET, follow_redirects=False)
        budget_id = _budget_id(client, "Test Budget")
        client.post(
            f"/targets/budget/{budget_id}",
            data={**_RECURRING_BUDGET, "amount": "-350"},
            follow_redirects=False,
        )
        form = client.get(f"/targets/budget/{budget_id}").text
        assert 'value="-350"' in form

    def test_delete_budget_removes_it(self, client: TestClient) -> None:
        """A deleted budget disappears from the management page."""
        client.post("/targets/budget", data=_RECURRING_BUDGET, follow_redirects=False)
        budget_id = _budget_id(client, "Test Budget")
        response = client.post(
            f"/targets/budget/{budget_id}/delete",
            data={"return_to": "/targets"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "Test Budget" not in client.get("/targets").text

    def test_invalid_amount_rerenders_form_without_saving(
        self, client: TestClient
    ) -> None:
        """A non-numeric amount re-renders the form with an error, no create."""
        response = client.post(
            "/targets/budget",
            data={**_RECURRING_BUDGET, "amount": "abc"},
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "form-error" in response.text
        assert "Test Budget" not in client.get("/targets").text

    def test_create_planned_operation(self, client: TestClient) -> None:
        """A planned operation with recurrence is created and listed."""
        response = client.post(
            "/targets/planned",
            data={
                "description": "Test Planned",
                "amount": "-90",
                "category": "OTHER",
                "start_date": "2026-02-15",
                "recurring": "yes",
                "period_value": "1",
                "period_unit": "months",
                "end_date": "",
                "keywords": "foo, bar",
                "approx_days": "5",
                "approx_ratio": "0.05",
                "return_to": "/targets",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "Test Planned" in client.get("/targets?view=planned").text

    def test_budgets_search_filters(self, client: TestClient) -> None:
        """The Budgets search narrows the list by description."""
        client.post(
            "/targets/budget",
            data={**_RECURRING_BUDGET, "description": "Zzz Unique Budget"},
            follow_redirects=False,
        )
        assert "Zzz Unique Budget" in client.get("/targets?submitted=1&q=Zzz").text
        assert (
            "Zzz Unique Budget" not in client.get("/targets?submitted=1&q=nomatch").text
        )

    def test_targets_views_are_separate(self, client: TestClient) -> None:
        """The default view lists budgets; ?view=planned lists planned operations."""
        budgets_view = client.get("/targets").text
        planned_view = client.get("/targets?view=planned").text
        assert "/targets/budget/" in budgets_view
        assert "/targets/planned/" not in budgets_view
        assert "/targets/planned/" in planned_view
        assert "/targets/budget/" not in planned_view

    def test_split_budget_produces_two_segments(self, client: TestClient) -> None:
        """Splitting a recurring budget leaves two rows sharing its description."""
        client.post("/targets/budget", data=_RECURRING_BUDGET, follow_redirects=False)
        budget_id = _budget_id(client, "Test Budget")
        response = client.post(
            f"/targets/budget/{budget_id}/split",
            data={
                "split_date": "2026-06-01",
                "split_amount": "-400",
                "split_period_value": "1",
                "split_period_unit": "months",
                "split_duration_value": "1",
                "split_duration_unit": "months",
                "return_to": "/targets",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert client.get("/targets?submitted=1").text.count("Test Budget") >= 2

    def test_split_keeps_original_cadence(self, client: TestClient) -> None:
        """Splitting a quarterly budget keeps both segments quarterly (regression:
        the split form used to force the continuation to a monthly cadence)."""
        client.post(
            "/targets/budget",
            data={
                **_RECURRING_BUDGET,
                "description": "Quarterly Budget",
                "period_value": "3",
                "period_unit": "months",
            },
            follow_redirects=False,
        )
        budget_id = _budget_id(client, "Quarterly Budget")
        # Change only the amount; period/duration carry the form's prefilled values.
        client.post(
            f"/targets/budget/{budget_id}/split",
            data={
                "split_date": "2026-07-01",
                "split_amount": "-400",
                "split_period_value": "3",
                "split_period_unit": "months",
                "split_duration_value": "1",
                "split_duration_unit": "months",
                "return_to": "/targets",
            },
            follow_redirects=False,
        )
        ids = _budget_ids(client, "Quarterly Budget")
        assert len(ids) == 2
        assert all(_period_value(client, bid) == "3" for bid in ids)

    def test_split_new_amount_lands_on_continuation(self, client: TestClient) -> None:
        """The split's new amount applies to the post-split segment."""
        client.post("/targets/budget", data=_RECURRING_BUDGET, follow_redirects=False)
        budget_id = _budget_id(client, "Test Budget")
        client.post(
            f"/targets/budget/{budget_id}/split",
            data={
                "split_date": "2026-07-01",
                "split_amount": "-400",
                "split_period_value": "1",
                "split_period_unit": "months",
                "split_duration_value": "1",
                "split_duration_unit": "months",
                "return_to": "/targets",
            },
            follow_redirects=False,
        )
        amounts = {
            _amount_value(client, bid) for bid in _budget_ids(client, "Test Budget")
        }
        assert "-400" in amounts

    def test_split_section_sits_below_save(self, client: TestClient) -> None:
        """Save submits the form above it and ignores the split fields, so the
        split section comes after the actions and owns its own primary button."""
        client.post("/targets/budget", data=_RECURRING_BUDGET, follow_redirects=False)
        page = client.get(f"/targets/budget/{_budget_id(client, 'Test Budget')}").text
        assert page.index("data-save-button") < page.index("data-split-section")
        split_form = re.search(r"data-split-section.*?</details>", page, re.S).group(0)
        assert 'class="btn primary"' in split_form


class TestCategorize:
    """Inline and bulk categorization, and the uncategorized badge."""

    def _uncategorized_ids(self, client: TestClient) -> list[str]:
        page = client.get("/operations?uncategorized=true").text
        return re.findall(r'name="ids" value="(\d+)"', page)

    def test_category_options_are_alphabetical(self, client: TestClient) -> None:
        """The per-row category dropdown lists categories alphabetically, with
        accents folded so 'Épargne' sorts with the E's rather than last."""
        html = client.get("/operations").text
        select = re.search(
            r'<select class="row-category".*?</select>', html, re.S
        ).group(0)
        labels = re.findall(r"<option[^>]*>([^<]+)</option>", select)

        def fold(text: str) -> str:
            decomposed = unicodedata.normalize("NFD", text)
            return "".join(
                c for c in decomposed if not unicodedata.combining(c)
            ).casefold()

        assert labels == sorted(labels, key=fold)

    def test_single_categorize_swaps_row_and_badge(self, client: TestClient) -> None:
        """Categorizing one operation returns its row plus an OOB badge."""
        ids = self._uncategorized_ids(client)
        assert ids, "demo database should have uncategorized operations"
        response = client.post(
            f"/operations/{ids[0]}/categorize",
            data={"category": "groceries"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert f'id="op-row-{ids[0]}"' in response.text
        assert 'hx-swap-oob="true"' in response.text

    def test_single_categorize_lowers_the_uncategorized_count(
        self, client: TestClient
    ) -> None:
        """One fewer operation is uncategorized after an inline categorization."""
        before = self._uncategorized_ids(client)
        client.post(
            f"/operations/{before[0]}/categorize",
            data={"category": "groceries"},
            headers={"HX-Request": "true"},
        )
        after = self._uncategorized_ids(client)
        assert len(after) == len(before) - 1

    def test_bulk_categorize_applies_to_all_selected(self, client: TestClient) -> None:
        """Bulk categorization re-renders the ledger area and the badge."""
        ids = self._uncategorized_ids(client)
        assert len(ids) >= 2
        response = client.post(
            "/operations/categorize",
            data={"ids": ids[:2], "bulk_category": "leisure"},
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert 'hx-swap-oob="true"' in response.text

    def test_bulk_categorize_keeps_the_active_filter(self, client: TestClient) -> None:
        """The filter bar is posted in the body, so the re-rendered ledger stays
        narrowed to the uncategorized rows."""
        ids = self._uncategorized_ids(client)
        assert len(ids) >= 2
        response = client.post(
            "/operations/categorize",
            data={
                "ids": ids[:2],
                "bulk_category": "leisure",
                "uncategorized": "true",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        rendered = re.findall(r'name="ids" value="(\d+)"', response.text)
        assert set(rendered) == set(ids[2:])

    def test_bulk_categorize_without_selection_redirects(
        self, client: TestClient
    ) -> None:
        """No selected ids means nothing to do; the route just redirects."""
        response = client.post(
            "/operations/categorize",
            data={"bulk_category": "leisure"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_bulk_picker_names_no_category_at_first(self, client: TestClient) -> None:
        """The bulk picker names no category until the user does, and the button
        that would apply it cannot be pressed meanwhile."""
        html = client.get("/operations").text
        bulk_bar = re.search(r'<div id="bulk-bar".*?</div>', html, re.S)
        assert bulk_bar, "no bulk bar on the ledger"
        first_option = re.search(r"<option[^>]*>", bulk_bar.group(0))
        apply_button = re.search(
            r"<button[^>]*data-bulk-apply[^>]*>", bulk_bar.group(0)
        )
        assert first_option and apply_button, "the bulk bar lost its picker"
        assert 'value=""' in first_option.group(0)
        assert "disabled" in apply_button.group(0)

    def test_row_states_its_category_in_text_too(self, client: TestClient) -> None:
        """Selecting rows takes the select away on a phone, so the row also says
        its category in plain text. The two must not disagree."""
        html = client.get("/operations").text
        rows = re.findall(r'<tr id="op-row-\d+".*?</tr>', html, re.S)
        assert rows
        for row in rows[:5]:
            chosen = re.search(r'<option value="([a-z_]+)" selected', row)
            label = re.search(r'class="cat-label">(.*?)</span>\s*</td>', row, re.S)
            assert chosen and label, "a row states no category"
            spoken = re.sub(r"<[^>]+>", "", label.group(1)).strip()
            assert spoken.endswith(category_name(chosen.group(1)))

    def test_bulk_categorize_with_no_category_changes_nothing(
        self, client: TestClient
    ) -> None:
        """The placeholder reaching the server categorizes nothing."""
        before = self._uncategorized_ids(client)
        assert len(before) >= 2
        response = client.post(
            "/operations/categorize",
            data={"ids": before[:2], "bulk_category": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert self._uncategorized_ids(client) == before


class TestLinkFlow:
    """The two-step link page and unlink."""

    def _first_operation_id(self, client: TestClient) -> str:
        page = client.get("/operations").text
        return re.findall(r'name="ids" value="(\d+)"', page)[0]

    def test_link_page_lists_ranked_candidates(self, client: TestClient) -> None:
        """The link page renders candidate targets."""
        operation_id = self._first_operation_id(client)
        response = client.get(f"/operations/{operation_id}/link")
        assert response.status_code == 200
        assert "candidate" in response.text

    def test_link_two_step_creates_and_shows_the_link(self, client: TestClient) -> None:
        """Picking a target and an iteration creates a link shown afterwards."""
        operation_id = self._first_operation_id(client)
        page = client.get(f"/operations/{operation_id}/link").text
        target_type, target_id = re.findall(
            r"target_type=(\w+)&target_id=(\d+)&offset=0", page
        )[0]
        fragment = client.get(
            f"/operations/{operation_id}/link/iterations"
            f"?target_type={target_type}&target_id={target_id}&offset=0",
            headers={"HX-Request": "true"},
        ).text
        iteration = re.findall(r'name="iteration_date" value="([^"]+)"', fragment)[0]
        created = client.post(
            f"/operations/{operation_id}/link",
            data={
                "target_type": target_type,
                "target_id": target_id,
                "iteration_date": iteration,
            },
            follow_redirects=False,
        )
        assert created.status_code == 303
        assert "current-link" in client.get(f"/operations/{operation_id}/link").text

    def test_operation_detail_honors_return_to(self, client: TestClient) -> None:
        """A same-app return_to (e.g. back to the month) is used for the back link."""
        operation_id = self._first_operation_id(client)
        html = client.get(
            f"/operations/{operation_id}?return_to=/month/2026-07?open=groceries"
        ).text
        assert "/month/2026-07?open=groceries" in html

    def test_operation_detail_rejects_external_return_to(
        self, client: TestClient
    ) -> None:
        """An off-site return_to falls back to the ledger."""
        operation_id = self._first_operation_id(client)
        html = client.get(f"/operations/{operation_id}?return_to=//evil.example").text
        assert "//evil.example" not in html

    def test_link_candidate_search_and_show_all(self, client: TestClient) -> None:
        """The candidate fragment filters on search and expands via show-all."""
        operation_id = self._first_operation_id(client)
        empty = client.get(
            f"/operations/{operation_id}/link/candidates"
            "?target_type=planned&q=zzznomatch",
            headers={"HX-Request": "true"},
        ).text
        assert empty.count('class="candidate"') == 0
        shown_all = client.get(
            f"/operations/{operation_id}/link/candidates?target_type=planned&all=true",
            headers={"HX-Request": "true"},
        ).text
        default = client.get(f"/operations/{operation_id}/link").text
        assert shown_all.count('class="candidate"') >= default.count(
            'class="candidate"'
        )

    def test_unlink_removes_the_link(self, client: TestClient) -> None:
        """Unlinking clears an operation's link."""
        operation_id = self._first_operation_id(client)
        page = client.get(f"/operations/{operation_id}/link").text
        target_type, target_id = re.findall(
            r"target_type=(\w+)&target_id=(\d+)&offset=0", page
        )[0]
        fragment = client.get(
            f"/operations/{operation_id}/link/iterations"
            f"?target_type={target_type}&target_id={target_id}&offset=0",
            headers={"HX-Request": "true"},
        ).text
        iteration = re.findall(r'name="iteration_date" value="([^"]+)"', fragment)[0]
        client.post(
            f"/operations/{operation_id}/link",
            data={
                "target_type": target_type,
                "target_id": target_id,
                "iteration_date": iteration,
            },
            follow_redirects=False,
        )
        client.post(f"/operations/{operation_id}/unlink", follow_redirects=False)
        assert "current-link" not in client.get(f"/operations/{operation_id}/link").text


class TestRobustness:
    """Redirect safety, stale-link 404s, and malformed input."""

    def test_missing_budget_is_404(self, client: TestClient) -> None:
        """A stale link to a deleted budget yields 404, not 500."""
        assert client.get("/targets/budget/999999").status_code == 404

    def test_missing_operation_is_404(self, client: TestClient) -> None:
        """A stale link to a missing operation yields 404, not 500."""
        assert client.get("/operations/999999").status_code == 404

    def test_unknown_kind_is_404(self, client: TestClient) -> None:
        """An unknown target kind is rejected rather than treated as a budget."""
        assert client.get("/targets/garbage/1").status_code == 404

    def test_split_missing_target_is_404(self, client: TestClient) -> None:
        """Splitting a missing target 404s instead of 500 on the error path."""
        response = client.post(
            "/targets/budget/999999/split",
            data={"split_date": "2026-07-01", "return_to": "/targets"},
            follow_redirects=False,
        )
        assert response.status_code == 404

    def test_back_link_rejects_off_site_return_to(self, client: TestClient) -> None:
        """Scheme-relative, backslash and control-char return_to fall back."""
        operation_id = client.get("/operations").text
        operation_id = re.findall(r'name="ids" value="(\d+)"', operation_id)[0]
        for bad in ("//evil.example", "/%09/evil.example", "/%5Cevil.example"):
            html = client.get(f"/operations/{operation_id}?return_to={bad}").text
            assert "evil.example" not in html

    def test_bulk_categorize_ignores_malformed_ids(self, client: TestClient) -> None:
        """Non-numeric ids are dropped, not crashed on."""
        response = client.post(
            "/operations/categorize",
            data={"ids": ["abc", "x1"], "bulk_category": "groceries"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_budget_created_without_recurring_is_one_off(
        self, client: TestClient
    ) -> None:
        """Omitting the recurring checkbox creates a non-recurring budget."""
        data = {k: v for k, v in _RECURRING_BUDGET.items() if k != "recurring"}
        client.post("/targets/budget", data=data, follow_redirects=False)
        budget_id = _budget_id(client, "Test Budget")
        form = client.get(f"/targets/budget/{budget_id}").text
        assert re.search(r'name="recurring"[^>]*checked', form) is None


class TestDrilldownAndReload:
    """The Mois drill-down fragment and forecast invalidation on write."""

    def test_category_drilldown_renders(self, client: TestClient) -> None:
        """A category present in a month renders its drill-down fragment."""
        month = client.get("/month", follow_redirects=True).text
        category = re.findall(r'data-url="/month/([\d-]+)/([^"]+)"', month)[0]
        response = client.get(
            f"/month/{category[0]}/{category[1]}", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "cat-detail" in response.text

    def test_new_budget_shows_in_the_month_view(self, client: TestClient) -> None:
        """A created budget reaches the month view, proving the forecast reloaded."""
        this_month = date.today().replace(day=1)
        client.post(
            "/targets/budget",
            data={
                **_RECURRING_BUDGET,
                "description": "Reload Probe",
                "category": "GIFTS",
                "amount": "-123.45",
                "start_date": this_month.strftime("%Y-%m-01"),
                "return_to": "/targets",
            },
            follow_redirects=False,
        )
        month_page = client.get(f"/month/{this_month:%Y-%m}").text
        assert "123" in month_page
