#!/usr/bin/env python3
"""Generate date-relative demo data for the Budget Forecaster application.

All dates are relative to today so the demo always feels "current".
Run from anywhere:
    python examples/generate_demo.py

Outputs:
    examples/demo.db                        — SQLite V6 database
    examples/data/bnp-export-demo.xls       — BNP export for the current month
    examples/data/swile-export-YYYY-MM-DD.zip — Swile export for the current month
"""

from __future__ import annotations

import itertools
import json
import random
import zipfile
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

import xlsxwriter
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
)
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
EXAMPLES_DIR = Path(__file__).resolve().parent
DATA_DIR = EXAMPLES_DIR / "data"
DB_PATH = EXAMPLES_DIR / "demo.db"

# ---------------------------------------------------------------------------
# Date layout
# ---------------------------------------------------------------------------
TODAY = date.today()
BASE = TODAY.replace(day=1)  # 1st of current month
M_MINUS_3 = BASE - relativedelta(months=3)
M_MINUS_2 = BASE - relativedelta(months=2)
M_MINUS_1 = BASE - relativedelta(months=1)
M_CURRENT = BASE
BALANCE_DATE = M_MINUS_1 - timedelta(days=1) + relativedelta(months=1)  # last day M-1


# ---------------------------------------------------------------------------
# Unique ID counter
# ---------------------------------------------------------------------------
_id_counter = itertools.count(1)


ID_COUNTER = _id_counter


# ---------------------------------------------------------------------------
# Planned operations & budgets definitions
# ---------------------------------------------------------------------------
PLANNED_OPS: list[dict] = [
    {
        "desc": "Salary",
        "amount": 3200.00,
        "category": Category.SALARY,
        "day": 28,
        "hints": ["SALARY TRANSFER", "SALARY"],
    },
    {
        "desc": "Rent",
        "amount": -950.00,
        "category": Category.RENT,
        "day": 5,
        "hints": ["RENT PAYMENT", "RENT"],
    },
    {
        "desc": "Electricity",
        "amount": -75.00,
        "category": Category.ELECTRICITY,
        "day": 10,
        "hints": ["POWER COMPANY", "ELECTRICITY"],
    },
    {
        "desc": "Internet",
        "amount": -35.90,
        "category": Category.INTERNET,
        "day": 8,
        "hints": ["FREE MOBILE", "INTERNET"],
    },
    {
        "desc": "Phone",
        "amount": -19.99,
        "category": Category.PHONE,
        "day": 8,
        "hints": ["PHONE PLAN", "PHONE"],
    },
    {
        "desc": "Transit pass",
        "amount": -84.10,
        "category": Category.PUBLIC_TRANSPORT,
        "day": 1,
        "hints": ["TRANSIT PASS", "TRANSPORT"],
    },
    {
        "desc": "Savings",
        "amount": -500.00,
        "category": Category.SAVINGS,
        "day": 29,
        "hints": ["SAVINGS TRANSFER", "SAVINGS"],
    },
    {
        "desc": "Spotify",
        "amount": -10.99,
        "category": Category.ENTERTAINMENT,
        "day": 15,
        "hints": ["SPOTIFY"],
    },
    {
        "desc": "Home insurance",
        "amount": -25.00,
        "category": Category.HOUSE_INSURANCE,
        "day": 12,
        "hints": ["HOME INSURANCE", "INSURANCE"],
    },
]

ONE_TIME_PAST = {
    "desc": "Washing machine repair",
    "amount": -400.00,
    "category": Category.FURNITURE,
    "month": M_MINUS_2,
    "day": 18,
    "hints": ["DARTY", "REPAIR"],
}

# One-time future expense — makes the margin dip below the 500€ threshold
ONE_TIME_FUTURE = {
    "desc": "Apartment security deposit",
    "amount": -2500.00,
    "category": Category.UNCATEGORIZED,
    "month": M_CURRENT,
    "day": 25,
    "hints": ["DEPOSIT TRANSFER"],
}

BUDGETS: list[dict] = [
    {
        "desc": "Groceries",
        "amount": -450.00,
        "category": Category.GROCERIES,
    },
    {
        "desc": "Entertainment",
        "amount": -120.00,
        "category": Category.ENTERTAINMENT,
    },
]

# ---------------------------------------------------------------------------
# BNP category strings (reverse mapping from category_mapping.yaml)
# ---------------------------------------------------------------------------
BNP_CATEGORY_MAP: dict[Category, str] = {
    Category.SALARY: "Salary",
    Category.RENT: "Rent",
    Category.ELECTRICITY: "Electricity",
    Category.INTERNET: "Internet",
    Category.PHONE: "Phone",
    Category.PUBLIC_TRANSPORT: "Transport",
    Category.SAVINGS: "Savings",
    Category.ENTERTAINMENT: "Entertainment",
    Category.HOUSE_INSURANCE: "Home insurance",
    Category.FURNITURE: "Appliances",
    Category.GROCERIES: "Groceries",
    Category.LEISURE: "Restaurant",
    Category.UNCATEGORIZED: "Other",
}

# ---------------------------------------------------------------------------
# Historic operation generators (for one month)
# ---------------------------------------------------------------------------
GROCERY_DESCS = [
    "CB CARREFOUR",
    "CB MONOPRIX",
    "CB LIDL",
    "CB FRANPRIX",
    "CB PICARD",
    "CB BIOCOOP",
]

ENTERTAINMENT_DESCS = [
    "CB CINEMA UGC",
    "CB FNAC",
    "CB CULTURA",
]

UNCATEGORIZED_DESCS = [
    "CB TABAC PRESSE",
    "CB RELAY",
]

SWILE_DESCS = [
    "Pokawa",
    "McDonald's",
    "Boulangerie Paul",
    "Jour",
    "Cojean",
]


def _vary_amount(base: float, pct: float = 0.05) -> float:
    """Return base amount with small random variance."""
    variation = base * random.uniform(-pct, pct)
    return round(base + variation, 2)


def _vary_date(base: date, days: int = 2) -> date:
    """Return base date shifted by up to ±days, clamped to same month."""
    delta = random.randint(-days, days)
    result = base + timedelta(days=delta)
    # Clamp to same month
    if result.month != base.month or result.year != base.year:
        result = base
    return result


def _generate_planned_op_operations(
    month_start: date,
) -> list[tuple[HistoricOperation, dict]]:
    """Generate one operation per planned op for the given month."""
    ops: list[tuple[HistoricOperation, dict]] = []
    for po in PLANNED_OPS:
        day = min(po["day"], monthrange(month_start.year, month_start.month)[1])
        op_date = _vary_date(month_start.replace(day=day))
        amount = _vary_amount(po["amount"], 0.02)
        desc = po["hints"][0] + " " + month_start.strftime("%m/%Y")
        op = HistoricOperation(
            unique_id=next(ID_COUNTER),
            description=desc,
            amount=Amount(amount),
            category=po["category"],
            operation_date=op_date,
        )
        ops.append((op, po))
    return ops


def _generate_one_time_operation() -> tuple[HistoricOperation, dict]:
    """Generate the one-time washing machine repair operation."""
    ot = ONE_TIME_PAST
    op_date = ot["month"].replace(day=ot["day"])
    op = HistoricOperation(
        unique_id=next(ID_COUNTER),
        description=f"{ot['hints'][0]} {ot['hints'][1]}",
        amount=Amount(ot["amount"]),
        category=ot["category"],
        operation_date=op_date,
    )
    return op, ot


def _generate_grocery_operations(month_start: date) -> list[HistoricOperation]:
    """Generate 8-10 grocery operations for the month."""
    count = random.randint(8, 10)
    last_day = monthrange(month_start.year, month_start.month)[1]
    ops: list[HistoricOperation] = []
    # Target total: 350-400
    target_total = random.uniform(350.0, 400.0)
    amounts = [random.uniform(20.0, 80.0) for _ in range(count)]
    scale = target_total / sum(amounts)
    amounts = [round(a * scale, 2) for a in amounts]

    for i in range(count):
        day = random.randint(1, last_day)
        op_date = month_start.replace(day=day)
        desc = random.choice(GROCERY_DESCS)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=desc,
                amount=Amount(-abs(amounts[i])),
                category=Category.GROCERIES,
                operation_date=op_date,
            )
        )
    return ops


def _generate_entertainment_operations(month_start: date) -> list[HistoricOperation]:
    """Generate 2-3 entertainment operations for the month."""
    count = random.randint(2, 3)
    last_day = monthrange(month_start.year, month_start.month)[1]
    ops: list[HistoricOperation] = []
    target_total = random.uniform(80.0, 100.0)
    amounts = [random.uniform(10.0, 50.0) for _ in range(count)]
    scale = target_total / sum(amounts)
    amounts = [round(a * scale, 2) for a in amounts]

    for i in range(count):
        day = random.randint(1, last_day)
        op_date = month_start.replace(day=day)
        desc = random.choice(ENTERTAINMENT_DESCS)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=desc,
                amount=Amount(-abs(amounts[i])),
                category=Category.ENTERTAINMENT,
                operation_date=op_date,
            )
        )
    return ops


def _generate_uncategorized_operations(month_start: date) -> list[HistoricOperation]:
    """Generate 1-2 uncategorized operations for the month."""
    count = random.randint(1, 2)
    last_day = monthrange(month_start.year, month_start.month)[1]
    ops: list[HistoricOperation] = []
    for _ in range(count):
        day = random.randint(1, last_day)
        op_date = month_start.replace(day=day)
        amount = -round(random.uniform(10.0, 50.0), 2)
        desc = random.choice(UNCATEGORIZED_DESCS)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=desc,
                amount=Amount(amount),
                category=Category.UNCATEGORIZED,
                operation_date=op_date,
            )
        )
    return ops


def _generate_swile_operations(month_start: date) -> list[HistoricOperation]:
    """Generate 3-5 Swile meal voucher operations for the month."""
    count = random.randint(3, 5)
    last_day = monthrange(month_start.year, month_start.month)[1]
    ops: list[HistoricOperation] = []
    for _ in range(count):
        day = random.randint(1, last_day)
        op_date = month_start.replace(day=day)
        amount = -round(random.uniform(8.0, 15.0), 2)
        desc = random.choice(SWILE_DESCS)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=desc,
                amount=Amount(amount, "EUR"),
                category=Category.UNCATEGORIZED,
                operation_date=op_date,
            )
        )
    return ops


# ---------------------------------------------------------------------------
# Current-month generators (partial month up to today)
# ---------------------------------------------------------------------------
def _generate_current_month_bnp_operations() -> list[HistoricOperation]:
    """Generate BNP operations for current month up to today."""
    ops: list[HistoricOperation] = []

    # Planned ops that fall before today
    for po in PLANNED_OPS:
        if (
            day := min(po["day"], monthrange(M_CURRENT.year, M_CURRENT.month)[1])
        ) <= TODAY.day:
            op_date = min(_vary_date(M_CURRENT.replace(day=day), days=1), TODAY)
            amount = _vary_amount(po["amount"], 0.02)
            desc = po["hints"][0] + " " + M_CURRENT.strftime("%m/%Y")
            ops.append(
                HistoricOperation(
                    unique_id=next(ID_COUNTER),
                    description=desc,
                    amount=Amount(amount),
                    category=po["category"],
                    operation_date=op_date,
                )
            )

    # Partial grocery ops
    fraction = TODAY.day / monthrange(M_CURRENT.year, M_CURRENT.month)[1]
    grocery_count = max(2, int(9 * fraction))
    target_total = random.uniform(350.0, 400.0) * fraction
    amounts = [random.uniform(20.0, 80.0) for _ in range(grocery_count)]
    scale = target_total / sum(amounts)
    amounts = [round(a * scale, 2) for a in amounts]
    for i in range(grocery_count):
        day = random.randint(1, TODAY.day)
        op_date = M_CURRENT.replace(day=day)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=random.choice(GROCERY_DESCS),
                amount=Amount(-abs(amounts[i])),
                category=Category.GROCERIES,
                operation_date=op_date,
            )
        )

    # Partial entertainment ops
    ent_count = max(1, int(3 * fraction))
    target_total = random.uniform(80.0, 100.0) * fraction
    amounts = [random.uniform(10.0, 50.0) for _ in range(ent_count)]
    scale = target_total / sum(amounts)
    amounts = [round(a * scale, 2) for a in amounts]
    for i in range(ent_count):
        day = random.randint(1, TODAY.day)
        op_date = M_CURRENT.replace(day=day)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=random.choice(ENTERTAINMENT_DESCS),
                amount=Amount(-abs(amounts[i])),
                category=Category.ENTERTAINMENT,
                operation_date=op_date,
            )
        )

    # 1 uncategorized
    day = random.randint(1, TODAY.day)
    ops.append(
        HistoricOperation(
            unique_id=next(ID_COUNTER),
            description=random.choice(UNCATEGORIZED_DESCS),
            amount=Amount(-round(random.uniform(10.0, 50.0), 2)),
            category=Category.UNCATEGORIZED,
            operation_date=M_CURRENT.replace(day=day),
        )
    )

    return ops


def _generate_current_month_swile_operations() -> list[HistoricOperation]:
    """Generate Swile operations for current month up to today."""
    fraction = TODAY.day / monthrange(M_CURRENT.year, M_CURRENT.month)[1]
    count = max(1, int(4 * fraction))
    ops: list[HistoricOperation] = []
    for _ in range(count):
        day = random.randint(1, TODAY.day)
        op_date = M_CURRENT.replace(day=day)
        amount = -round(random.uniform(8.0, 15.0), 2)
        ops.append(
            HistoricOperation(
                unique_id=next(ID_COUNTER),
                description=random.choice(SWILE_DESCS),
                amount=Amount(amount, "EUR"),
                category=Category.UNCATEGORIZED,
                operation_date=op_date,
            )
        )
    return ops


# ---------------------------------------------------------------------------
# BNP XLS writer
# ---------------------------------------------------------------------------
def write_bnp_xls(
    path: Path, balance: float, balance_date: date, operations: list[HistoricOperation]
) -> None:
    """Write a BNP Paribas-format .xls export file."""
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet()

    # Row 0: headers with balance info
    worksheet.write(0, 0, "Date de consultation")
    worksheet.write(0, 1, f"Solde au {balance_date.strftime('%d/%m/%Y')}")
    worksheet.write(0, 2, balance)

    # Row 1: empty
    # Row 2: column headers
    headers = [
        "Date operation",
        "Libelle operation",
        "Montant operation",
        "Sous Categorie operation",
    ]
    for col, header in enumerate(headers):
        worksheet.write(2, col, header)

    # Row 3+: operations
    for row_idx, op in enumerate(operations, start=3):
        worksheet.write(row_idx, 0, op.operation_date.strftime("%d-%m-%Y"))
        worksheet.write(row_idx, 1, op.description)
        worksheet.write(row_idx, 2, op.amount)
        bnp_cat = BNP_CATEGORY_MAP.get(op.category, "Autre")
        worksheet.write(row_idx, 3, bnp_cat)

    workbook.close()


# ---------------------------------------------------------------------------
# Swile ZIP writer
# ---------------------------------------------------------------------------
def write_swile_zip(
    path: Path, balance_centimes: int, operations: list[HistoricOperation]
) -> None:
    """Write a Swile-format .zip export file."""
    # Build operations.json
    items = []
    for op in operations:
        amount_centimes = int(round(op.amount * 100))
        items.append(
            {
                "name": op.description,
                "transactions": [
                    {
                        "status": "CAPTURED",
                        "payment_method": "Wallets::MealVoucherWallet",
                        "amount": {
                            "value": amount_centimes,
                            "currency": {"iso_3": "EUR"},
                        },
                        "date": op.operation_date.isoformat() + "T12:00:00.000+01:00",
                    }
                ],
            }
        )
    operations_json = {"items": items}

    # Build wallets.json
    wallets_json = {
        "wallets": [
            {
                "type": "meal_voucher",
                "balance": {"value": balance_centimes / 100.0},
            }
        ]
    }

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("operations.json", json.dumps(operations_json, indent=2))
        zf.writestr("wallets.json", json.dumps(wallets_json, indent=2))


# ---------------------------------------------------------------------------
# Database population helpers
# ---------------------------------------------------------------------------
def _create_planned_operations(
    repo: SqliteRepository,
) -> tuple[dict[str, int], int, int]:
    """Create all planned operations in the database.

    Returns (planned_op_ids, past_one_time_id, future_one_time_id).
    """
    planned_op_ids: dict[str, int] = {}
    for po in PLANNED_OPS:
        planned = PlannedOperation(
            record_id=None,
            description=po["desc"],
            amount=Amount(po["amount"]),
            category=po["category"],
            date_range=RecurringDay(
                start_date=M_MINUS_3.replace(
                    day=min(po["day"], monthrange(M_MINUS_3.year, M_MINUS_3.month)[1])
                ),
                period=relativedelta(months=1),
            ),
        )
        planned.matcher.update_params(
            description_hints=set(po["hints"]),
            approximation_date_range=timedelta(days=5),
            approximation_amount_ratio=0.1,
        )
        po_id = repo.upsert_planned_operation(planned)
        planned_op_ids[po["desc"]] = po_id

    # One-time past: washing machine repair in M-2
    ot = ONE_TIME_PAST
    past_planned = PlannedOperation(
        record_id=None,
        description=ot["desc"],
        amount=Amount(ot["amount"]),
        category=ot["category"],
        date_range=RecurringDay(
            start_date=ot["month"].replace(day=ot["day"]),
            period=relativedelta(months=1),
            expiration_date=ot["month"].replace(day=ot["day"]),
        ),
    )
    past_planned.matcher.update_params(
        description_hints=set(ot["hints"]),
        approximation_date_range=timedelta(days=5),
        approximation_amount_ratio=0.1,
    )
    past_one_time_id = repo.upsert_planned_operation(past_planned)

    # One-time future: security deposit this month — makes margin dip below threshold
    ft = ONE_TIME_FUTURE
    future_planned = PlannedOperation(
        record_id=None,
        description=ft["desc"],
        amount=Amount(ft["amount"]),
        category=ft["category"],
        date_range=RecurringDay(
            start_date=ft["month"].replace(day=ft["day"]),
            period=relativedelta(months=1),
            expiration_date=ft["month"].replace(day=ft["day"]),
        ),
    )
    future_planned.matcher.update_params(
        description_hints=set(ft["hints"]),
        approximation_date_range=timedelta(days=5),
        approximation_amount_ratio=0.1,
    )
    future_one_time_id = repo.upsert_planned_operation(future_planned)

    return planned_op_ids, past_one_time_id, future_one_time_id


def _create_budgets(repo: SqliteRepository) -> dict[str, int]:
    """Create all budgets in the database. Returns IDs."""
    budget_ids: dict[str, int] = {}
    for bu in BUDGETS:
        budget = Budget(
            record_id=None,
            description=bu["desc"],
            amount=Amount(bu["amount"]),
            category=bu["category"],
            date_range=RecurringDateRange(
                initial_date_range=DateRange(M_MINUS_3, relativedelta(months=1)),
                period=relativedelta(months=1),
            ),
        )
        b_id = repo.upsert_budget(budget)
        budget_ids[bu["desc"]] = b_id
    return budget_ids


def _generate_history(
    planned_op_ids: dict[str, int],
    past_one_time_id: int,
    budget_ids: dict[str, int],
) -> tuple[list[HistoricOperation], list[HistoricOperation], list[OperationLink]]:
    """Generate 3 months of history + current month (partial) with links."""
    all_bnp_ops: list[HistoricOperation] = []
    all_swile_ops: list[HistoricOperation] = []
    links: list[OperationLink] = []

    for month_start in (M_MINUS_3, M_MINUS_2, M_MINUS_1):
        _add_month_ops(
            month_start, planned_op_ids, budget_ids, all_bnp_ops, all_swile_ops, links
        )

        # One-time operation (only in M-2)
        if month_start == M_MINUS_2:
            ot = ONE_TIME_PAST
            op, _ = _generate_one_time_operation()
            all_bnp_ops.append(op)
            links.append(
                OperationLink(
                    operation_unique_id=op.unique_id,
                    target_type=LinkType.PLANNED_OPERATION,
                    target_id=past_one_time_id,
                    iteration_date=ot["month"].replace(day=ot["day"]),
                )
            )

    # Current month: partial data up to today, with links
    _add_current_month_ops(
        planned_op_ids, budget_ids, all_bnp_ops, all_swile_ops, links
    )

    return all_bnp_ops, all_swile_ops, links


def _add_month_ops(
    month_start: date,
    planned_op_ids: dict[str, int],
    budget_ids: dict[str, int],
    all_bnp_ops: list[HistoricOperation],
    all_swile_ops: list[HistoricOperation],
    links: list[OperationLink],
) -> None:
    """Add a full month of operations and links."""
    # Planned op operations
    po_ops = _generate_planned_op_operations(month_start)
    for op, po_def in po_ops:
        all_bnp_ops.append(op)
        po_id = planned_op_ids[po_def["desc"]]
        iteration_date = month_start.replace(
            day=min(
                po_def["day"],
                monthrange(month_start.year, month_start.month)[1],
            )
        )
        links.append(
            OperationLink(
                operation_unique_id=op.unique_id,
                target_type=LinkType.PLANNED_OPERATION,
                target_id=po_id,
                iteration_date=iteration_date,
            )
        )

    # Grocery operations (linked to budget)
    grocery_ops = _generate_grocery_operations(month_start)
    for op in grocery_ops:
        all_bnp_ops.append(op)
        links.append(
            OperationLink(
                operation_unique_id=op.unique_id,
                target_type=LinkType.BUDGET,
                target_id=budget_ids["Groceries"],
                iteration_date=month_start,
            )
        )

    # Entertainment operations (linked to budget)
    ent_ops = _generate_entertainment_operations(month_start)
    for op in ent_ops:
        all_bnp_ops.append(op)
        links.append(
            OperationLink(
                operation_unique_id=op.unique_id,
                target_type=LinkType.BUDGET,
                target_id=budget_ids["Entertainment"],
                iteration_date=month_start,
            )
        )

    # Uncategorized operations (no links)
    all_bnp_ops.extend(_generate_uncategorized_operations(month_start))

    # Swile operations (no links)
    all_swile_ops.extend(_generate_swile_operations(month_start))


def _link_current_month_ops(
    bnp_ops: list[HistoricOperation],
    planned_op_ids: dict[str, int],
    budget_ids: dict[str, int],
    links: list[OperationLink],
) -> None:
    """Create links for current-month BNP operations."""
    # The first N ops correspond to planned ops whose day <= today
    cursor = 0
    for po in PLANNED_OPS:
        if (
            day := min(po["day"], monthrange(M_CURRENT.year, M_CURRENT.month)[1])
        ) <= TODAY.day:
            if cursor < len(bnp_ops):
                links.append(
                    OperationLink(
                        operation_unique_id=bnp_ops[cursor].unique_id,
                        target_type=LinkType.PLANNED_OPERATION,
                        target_id=planned_op_ids[po["desc"]],
                        iteration_date=M_CURRENT.replace(day=day),
                    )
                )
                cursor += 1

    # Grocery operations come after planned ops
    fraction = TODAY.day / monthrange(M_CURRENT.year, M_CURRENT.month)[1]
    grocery_end = cursor + max(2, int(9 * fraction))
    for op in bnp_ops[cursor:grocery_end]:
        links.append(
            OperationLink(
                operation_unique_id=op.unique_id,
                target_type=LinkType.BUDGET,
                target_id=budget_ids["Groceries"],
                iteration_date=M_CURRENT,
            )
        )

    # Entertainment operations come after groceries
    ent_end = grocery_end + max(1, int(3 * fraction))
    for op in bnp_ops[grocery_end:ent_end]:
        links.append(
            OperationLink(
                operation_unique_id=op.unique_id,
                target_type=LinkType.BUDGET,
                target_id=budget_ids["Entertainment"],
                iteration_date=M_CURRENT,
            )
        )
    # Last op is uncategorized — no link needed


def _add_current_month_ops(
    planned_op_ids: dict[str, int],
    budget_ids: dict[str, int],
    all_bnp_ops: list[HistoricOperation],
    all_swile_ops: list[HistoricOperation],
    links: list[OperationLink],
) -> None:
    """Add current-month partial operations (up to today) with links."""
    bnp_ops = _generate_current_month_bnp_operations()
    _link_current_month_ops(bnp_ops, planned_op_ids, budget_ids, links)
    all_bnp_ops.extend(bnp_ops)
    all_swile_ops.extend(_generate_current_month_swile_operations())


def _save_accounts(
    repo: SqliteRepository,
    bnp_ops: list[HistoricOperation],
    swile_ops: list[HistoricOperation],
    links: list[OperationLink],
) -> tuple[float, float]:
    """Save accounts and links to the database. Returns (bnp_balance, swile_balance)."""
    bnp_balance = 2800.0
    swile_balance = 87.50

    bnp_account = Account(
        name="bnp",
        balance=bnp_balance,
        currency="EUR",
        balance_date=BALANCE_DATE,
        operations=tuple(sorted(bnp_ops, key=lambda o: o.operation_date)),
    )
    repo.upsert_account(bnp_account)

    swile_account = Account(
        name="swile",
        balance=swile_balance,
        currency="EUR",
        balance_date=BALANCE_DATE,
        operations=tuple(sorted(swile_ops, key=lambda o: o.operation_date)),
    )
    repo.upsert_account(swile_account)

    for link in links:
        repo.upsert_link(link)

    repo.set_setting("margin_threshold", "500")
    return bnp_balance, swile_balance


def _generate_exports(bnp_balance: float, swile_balance: float) -> tuple[Path, Path]:
    """Generate BNP XLS and Swile ZIP exports for the current month."""
    current_bnp_ops = _generate_current_month_bnp_operations()
    current_bnp_balance = round(
        bnp_balance + sum(op.amount for op in current_bnp_ops), 2
    )
    bnp_xls_path = DATA_DIR / "bnp-export-demo.xls"
    write_bnp_xls(bnp_xls_path, current_bnp_balance, TODAY, current_bnp_ops)

    current_swile_ops = _generate_current_month_swile_operations()
    current_swile_balance_centimes = int(
        round((swile_balance + sum(op.amount for op in current_swile_ops)) * 100)
    )
    swile_zip_path = DATA_DIR / f"swile-export-{TODAY.isoformat()}.zip"
    write_swile_zip(swile_zip_path, current_swile_balance_centimes, current_swile_ops)

    return bnp_xls_path, swile_zip_path


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------
def generate_demo_db(
    db_path: Path,
    account_name: str = "My Budget",
    seed: int | None = None,
) -> None:
    """Populate a SQLite database with demo data (no file exports).

    Useful for benchmarks and tests that need a realistic dataset.

    Args:
        db_path: Path for the SQLite database file.
        account_name: Name for the aggregated account.
        seed: Random seed for reproducibility.
    """
    if seed is not None:
        random.seed(seed)
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.set_aggregated_account_name(account_name)

    planned_op_ids, past_one_time_id, _future_one_time_id = _create_planned_operations(
        repo
    )
    budget_ids = _create_budgets(repo)
    all_bnp_ops, all_swile_ops, links = _generate_history(
        planned_op_ids, past_one_time_id, budget_ids
    )
    _save_accounts(repo, all_bnp_ops, all_swile_ops, links)
    repo.close()


def main() -> None:
    """Generate all demo artifacts."""
    # Clean up existing files
    if DB_PATH.exists():
        DB_PATH.unlink()
    for f in DATA_DIR.glob("bnp-export-demo.*"):
        f.unlink()
    for f in DATA_DIR.glob("swile-export-*.zip"):
        f.unlink()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating demo data relative to {TODAY}...")
    print(f"  History: {M_MINUS_3.strftime('%b %Y')} — {M_MINUS_1.strftime('%b %Y')}")
    print(f"  Current month exports: {M_CURRENT.strftime('%b %Y')}")
    print(f"  Balance date: {BALANCE_DATE}")

    # --- Populate database ---
    repo = SqliteRepository(DB_PATH)
    repo.initialize()
    repo.set_aggregated_account_name("My Budget")

    planned_op_ids, past_one_time_id, _future_one_time_id = _create_planned_operations(
        repo
    )
    budget_ids = _create_budgets(repo)
    all_bnp_ops, all_swile_ops, links = _generate_history(
        planned_op_ids, past_one_time_id, budget_ids
    )
    bnp_balance, swile_balance = _save_accounts(repo, all_bnp_ops, all_swile_ops, links)
    repo.close()

    # --- Generate current month exports ---
    bnp_xls_path, swile_zip_path = _generate_exports(bnp_balance, swile_balance)

    # --- Summary ---
    n_planned = len(PLANNED_OPS) + 2  # + past one-time + future one-time
    print(f"\nGenerated files:\n  {DB_PATH}\n  {bnp_xls_path}\n  {swile_zip_path}")
    print(f"\nBNP balance at {BALANCE_DATE}: {bnp_balance:.2f} EUR")
    print(f"Swile balance at {BALANCE_DATE}: {swile_balance:.2f} EUR")
    print(f"Planned operations: {n_planned}")
    print(f"Budgets: {len(BUDGETS)}")
    print(f"Historic operations (BNP): {len(all_bnp_ops)}")
    print(f"Historic operations (Swile): {len(all_swile_ops)}")
    print(f"Operation links: {len(links)}")
    print("Margin threshold: 500 EUR")
    print("\nDone! Run the TUI with:")
    print("  cd examples/ && python -m budget_forecaster.main -c config.yaml")


if __name__ == "__main__":
    main()
