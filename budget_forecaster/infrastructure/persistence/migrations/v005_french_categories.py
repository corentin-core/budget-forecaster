"""v4 -> v5: convert French category values to language-neutral keys."""

import sqlite3

# Old French enum values mapped to their lowercase English keys.
CATEGORY_MAP: dict[str, str] = {
    "Non catégorisé": "uncategorized",
    "Salaire": "salary",
    "Crédit d'impot": "tax_credit",
    "Allocations": "benefits",
    "Prêt maison": "house_loan",
    "Prêt travaux": "works_loan",
    "Loyer": "rent",
    "Assurance prêt": "loan_insurance",
    "Travaux": "house_works",
    "Mobilier, electromenager, deco.": "furniture",
    "Epargne": "savings",
    "Assurance auto": "car_insurance",
    "Assurance habitation": "house_insurance",
    "Autre assurance": "other_insurance",
    "Enfants": "childcare",
    "Pension alimentaire": "child_support",
    "Divertissement": "entertainment",
    "Loisirs": "leisure",
    "Voyages, vacances": "holidays",
    "Electricité": "electricity",
    "Eau": "water",
    "Internet": "internet",
    "Téléphone": "phone",
    "Courses": "groceries",
    "Habillement": "clothing",
    "Santé": "health_care",
    "Coiffeur, cosmétique, soins": "care",
    "Transports publics": "public_transport",
    "Carburant": "car_fuel",
    "Stationnement": "parking",
    "Péage": "toll",
    "Entretien automobile": "car_maintenance",
    "Crédit auto": "car_loan",
    "Cadeaux": "gifts",
    "Frais professionnels": "professional_expenses",
    "Autre": "other",
    "Dons": "charity",
    "Commissions bancaires": "bank_fees",
    "Impôts, taxes": "taxes",
}


def run(conn: sqlite3.Connection) -> None:
    """Rewrite category values across every table holding a category."""
    for old_value, new_value in CATEGORY_MAP.items():
        for table in ("operations", "budgets", "planned_operations"):
            conn.execute(
                f"UPDATE {table} SET category = ? WHERE category = ?",  # noqa: S608
                (new_value, old_value),
            )
    conn.commit()
