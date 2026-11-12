"""Guessing categories: planned operation first, then history, then rules."""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category, CategorySource
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.auto_categorizer import (
    auto_categorize,
    suggest_categories,
)
from budget_forecaster.services.operation.category_rules import rule_category
from budget_forecaster.services.operation.operation_matcher import OperationMatcher

_DAY = date(2026, 9, 15)


def _op(
    unique_id: int,
    description: str,
    category: Category = Category.UNCATEGORIZED,
    source: CategorySource | None = None,
    amount: float = -42.0,
    days_ago: int = 0,
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(amount),
        category=category,
        operation_date=_DAY - timedelta(days=days_ago),
        category_source=source,
    )


def _manual(
    unique_id: int, description: str, category: Category, days_ago: int
) -> HistoricOperation:
    return _op(
        unique_id, description, category, CategorySource.MANUAL, days_ago=days_ago
    )


def _planned(
    description: str, hints: set[str], category: Category, amount: float = -42.0
) -> OperationMatcher:
    planned = PlannedOperation(
        record_id=1,
        description=description,
        amount=Amount(amount),
        category=category,
        date_range=RecurringDay(date(2026, 1, 15), relativedelta(months=1)),
    ).set_matcher_params(description_hints=hints)
    return planned.matcher


def _guesses(
    operations: tuple[HistoricOperation, ...],
    matchers: tuple[OperationMatcher, ...] = (),
    linked: dict[int, Category] | None = None,
) -> dict[int, tuple[Category, CategorySource | None]]:
    return {
        op.unique_id: (op.category, op.category_source)
        for op in auto_categorize(operations, matchers, linked)
    }


class TestPriority:
    """Each source applies only when the ones before it have nothing to say."""

    def test_linked_target_wins_over_rules(self) -> None:
        """A loan payment linked by hand is not read as groceries from its label."""
        guesses = _guesses(
            (_op(10, "PRLV SEPA CARREFOUR BANQUE"),),
            linked={10: Category.HOUSE_LOAN},
        )

        assert guesses == {10: (Category.HOUSE_LOAN, CategorySource.PLANNED)}

    def test_uncategorized_linked_target_gives_way_to_rules(self) -> None:
        """A target with no category has none to give."""
        guesses = _guesses(
            (_op(10, "CB CARREFOUR"),), linked={10: Category.UNCATEGORIZED}
        )

        assert guesses == {10: (Category.GROCERIES, CategorySource.RULE)}

    def test_planned_operation_wins_over_history_and_rules(self) -> None:
        """An operation fulfilling a planned operation takes its category."""
        history = tuple(
            _manual(i, "PRLV SEPA EDF", Category.OTHER, days_ago=30 * i)
            for i in range(1, 4)
        )
        matcher = _planned("Electricity", {"EDF"}, Category.ELECTRICITY)

        guesses = _guesses((*history, _op(10, "PRLV SEPA EDF")), (matcher,))

        assert guesses == {10: (Category.ELECTRICITY, CategorySource.PLANNED)}

    def test_history_wins_over_rules(self) -> None:
        """The user's own habit beats a generic rule for the same payee."""
        history = tuple(
            _manual(i, "CB INTERMARCHE", Category.OTHER, days_ago=i)
            for i in range(1, 4)
        )

        guesses = _guesses((*history, _op(10, "CB INTERMARCHE 12/09")))

        assert guesses == {10: (Category.OTHER, CategorySource.HISTORY)}

    def test_rule_applies_to_an_unknown_payee(self) -> None:
        """A payee never categorized by hand falls back to the built-in rules."""
        guesses = _guesses((_op(10, "FACTURE CARTE PHARMACIE DU CENTRE"),))

        assert guesses == {10: (Category.HEALTH_CARE, CategorySource.RULE)}

    def test_unknown_payee_stays_uncategorized(self) -> None:
        """Nothing is guessed when no source applies."""
        assert _guesses((_op(10, "CHEQUE 1234567"),)) == {}


class TestNeverOverwrites:
    """A guess only fills an empty category the user did not leave empty."""

    def test_manual_uncategorized_is_left_alone(self) -> None:
        """The user may decide an operation stays uncategorized."""
        operation = _op(10, "PHARMACIE", source=CategorySource.MANUAL)

        assert _guesses((operation,)) == {}

    def test_categorized_operation_is_left_alone(self) -> None:
        """An earlier guess or a manual category is not guessed again."""
        operation = _op(10, "PHARMACIE", Category.GROCERIES, CategorySource.HISTORY)

        assert _guesses((operation,)) == {}


class TestHistory:
    """The latest manual categorizations of a payee must agree."""

    def test_fewer_than_three_votes_teach_nothing(self) -> None:
        """Two categorizations are a coincidence, not a habit."""
        history = tuple(
            _manual(i, "TY VORN", Category.LEISURE, days_ago=i) for i in (1, 2)
        )

        assert _guesses((*history, _op(10, "TY VORN"))) == {}

    def test_any_disagreement_among_the_latest_five_blocks(self) -> None:
        """One dissenting vote among the latest five is enough to abstain."""
        history = (
            *(
                _manual(i, "JM PINAULT", Category.GROCERIES, days_ago=i)
                for i in range(1, 5)
            ),
            _manual(5, "JM PINAULT", Category.LEISURE, days_ago=5),
        )

        assert _guesses((*history, _op(10, "JM PINAULT"))) == {}

    def test_an_abandoned_habit_older_than_five_is_ignored(self) -> None:
        """Older categorizations from a convention since dropped do not vote."""
        history = (
            *(
                _manual(i, "LA COOP BIO", Category.GROCERIES, days_ago=i)
                for i in range(1, 6)
            ),
            *(
                _manual(i, "LA COOP BIO", Category.OTHER, days_ago=100 + i)
                for i in range(6, 20)
            ),
        )

        guesses = _guesses((*history, _op(30, "LA COOP BIO")))

        assert guesses == {30: (Category.GROCERIES, CategorySource.HISTORY)}

    def test_guesses_do_not_vote(self) -> None:
        """Only manual categories teach: a guess would repeat its own mistakes."""
        history = tuple(
            _op(i, "TY VORN", Category.LEISURE, CategorySource.HISTORY, days_ago=i)
            for i in range(1, 4)
        )

        assert _guesses((*history, _op(10, "TY VORN"))) == {}

    def test_refunds_do_not_vote_with_purchases(self) -> None:
        """A refund from a shop is not a purchase there."""
        history = tuple(
            _manual(i, "TY VORN", Category.LEISURE, days_ago=i) for i in range(1, 4)
        )

        assert _guesses((*history, _op(10, "TY VORN", amount=20.0))) == {}


class TestPlanned:
    """Matching a planned operation by hints, amount and date."""

    def test_planned_operations_that_disagree_abstain(self) -> None:
        """Two planned operations matching with different categories say nothing."""
        matchers = (
            _planned("Loan", {"KEREIS"}, Category.HOUSE_LOAN),
            _planned("Insurance", {"KEREIS"}, Category.LOAN_INSURANCE),
        )

        assert _guesses((_op(10, "PRLV SEPA KEREIS"),), matchers) == {}

    def test_uncategorized_planned_operation_gives_way_to_rules(self) -> None:
        """A planned operation with no category leaves the next sources to decide."""
        matcher = _planned("Groceries run", {"CARREFOUR"}, Category.UNCATEGORIZED)

        assert _guesses((_op(10, "CB CARREFOUR"),), (matcher,)) == {
            10: (Category.GROCERIES, CategorySource.RULE)
        }

    def test_planned_operation_without_hints_matches_nothing(self) -> None:
        """Without hints, any operation of the right amount would take the category."""
        matcher = _planned("Rent", set(), Category.RENT)

        assert _guesses((_op(10, "VIR SEPA SOMEONE"),), (matcher,)) == {}

    def test_amount_must_match(self) -> None:
        """Hints alone are not enough."""
        matcher = _planned("Electricity", {"EDF"}, Category.ELECTRICITY, amount=-120.0)

        guesses = _guesses((_op(10, "PRLV SEPA EDF"),), (matcher,))

        assert guesses == {10: (Category.ELECTRICITY, CategorySource.RULE)}


class TestRules:
    """Built-in rules match whole words."""

    def test_matches_a_multi_word_keyword(self) -> None:
        """A keyword of several words matches them in sequence."""
        assert rule_category("CB LEROY MERLIN DINAN") == Category.HOUSE_WORKS

    def test_does_not_match_inside_a_word(self) -> None:
        """ESSO does not fire on ESSONNE."""
        assert rule_category("BOULANGERIE ESSONNE") is None


class TestSuggestion:
    """The one-click suggestion is looser than the history guess."""

    def test_one_manual_categorization_is_enough(self) -> None:
        """A single categorization of the payee is suggested."""
        operations = (
            _manual(1, "CB RELAY", Category.LEISURE, days_ago=5),
            _op(10, "CB RELAY 12/09"),
        )

        assert suggest_categories(operations, operations) == {10: Category.LEISURE}

    def test_most_frequent_wins_and_a_tie_goes_to_the_latest(self) -> None:
        """Two against one wins; one against one goes to the newest."""
        majority = (
            _manual(1, "CB RELAY", Category.LEISURE, days_ago=1),
            _manual(2, "CB RELAY", Category.GROCERIES, days_ago=2),
            _manual(3, "CB RELAY", Category.GROCERIES, days_ago=3),
            _op(10, "CB RELAY"),
        )
        tie = (
            _manual(1, "CB RELAY", Category.LEISURE, days_ago=1),
            _manual(2, "CB RELAY", Category.GROCERIES, days_ago=2),
            _op(10, "CB RELAY"),
        )

        assert suggest_categories(majority, majority) == {10: Category.GROCERIES}
        assert suggest_categories(tie, tie) == {10: Category.LEISURE}

    def test_guesses_do_not_suggest(self) -> None:
        """Only the user's own categorizations are suggested."""
        operations = (
            _op(1, "CB RELAY", Category.LEISURE, CategorySource.RULE),
            _op(10, "CB RELAY"),
        )

        assert not suggest_categories(operations, operations)

    def test_only_uncategorized_operations_get_one(self) -> None:
        """A categorized operation needs no suggestion."""
        operations = (
            _manual(1, "CB RELAY", Category.LEISURE, days_ago=5),
            _op(10, "CB RELAY", Category.GROCERIES, CategorySource.HISTORY),
        )

        assert not suggest_categories(operations, operations)
