"""Built-in keyword rules for payees whose category does not depend on the payer.

Payees selling a bit of everything (Amazon, Decathlon, a meal-voucher card) get
no rule. Keywords are label signatures and match whole words: ESSO does not
fire on ESSONNE.
"""

from typing import Final, NamedTuple

from budget_forecaster.core.types import Category


class CategoryRule(NamedTuple):
    """A payee keyword and the category it implies."""

    keyword: str
    category: Category


def _rules(category: Category, *keywords: str) -> tuple[CategoryRule, ...]:
    return tuple(CategoryRule(keyword, category) for keyword in keywords)


CATEGORY_RULES: Final[tuple[CategoryRule, ...]] = (
    *_rules(
        Category.GROCERIES,
        "INTERMARCHE",
        "CARREFOUR",
        "LECLERC",
        "LIDL",
        "ALDI",
        "AUCHAN",
        "BIOCOOP",
        "MONOPRIX",
        "FRANPRIX",
        "NETTO",
        "SUPER U",
        "HYPER U",
        "GRAND FRAIS",
        "PICARD",
        "NATURALIA",
        "LA VIE CLAIRE",
    ),
    *_rules(Category.HEALTH_CARE, "PHARMACIE", "CPAM"),
    *_rules(Category.PUBLIC_TRANSPORT, "SNCF", "OUIGO", "TRAINLINE", "RATP"),
    *_rules(Category.ENTERTAINMENT, "NETFLIX", "SPOTIFY", "DEEZER", "GOOGLE PLAY"),
    *_rules(Category.CAR_FUEL, "CHARGEMAP", "IONITY", "TOTALENERGIES", "ESSO"),
    *_rules(Category.PARKING, "PARKING", "CITEDIA", "INDIGO", "EFFIA"),
    *_rules(Category.TOLL, "APRR", "SANEF", "VINCI AUTOROUTES"),
    *_rules(Category.HOLIDAYS, "BOOKING", "AIRBNB"),
    *_rules(Category.ELECTRICITY, "EDF"),
    *_rules(Category.HOUSE_WORKS, "LEROY MERLIN", "CASTORAMA", "BRICO DEPOT"),
    *_rules(Category.FURNITURE, "IKEA"),
    *_rules(Category.CLOTHING, "KIABI", "ZARA"),
    *_rules(Category.TAXES, "DGFIP"),
    *_rules(Category.BENEFITS, "CAF"),
)


def rule_category(signature: str) -> Category | None:
    """The category of the first rule whose keyword appears as whole words."""
    padded = f" {signature} "
    return next(
        (rule.category for rule in CATEGORY_RULES if f" {rule.keyword} " in padded),
        None,
    )
