# Demo Data

Pre-populated example data to try the application without your own bank statements.

## Quick Start

```bash
# Install the application
pip install -e .

# Optionally regenerate demo data with fresh dates
python examples/generate_demo.py

# Run the web app from the examples directory
cd examples/
cp demo.db demo-run.db   # the app writes as you click; keeps demo.db pristine
BUDGET_CONFIG=config.yaml uvicorn --factory budget_forecaster.web.app:create_app
```

Skip the copy and you get an empty database: `config.yaml` points at `demo-run.db`,
which is ignored by git precisely so your clicks never land in the repository.

Open http://127.0.0.1:8000 and log in with the password **demo**. `config.yaml` carries
a throwaway signing key and password hash so the demo runs with one command; never reuse
that pair for a deployment holding real data.

## Contents

- **demo.db** — SQLite database with 3 months of categorized operations, planned
  operations, budgets, and operation links. Copy it to `demo-run.db` before playing with
  the app: every decision you take is written to the database.
- **data/bnp-export-demo.xls** — Anonymized BNP bank export for the current month (new
  data to import)
- **data/swile-export-YYYY-MM-DD.zip** — Anonymized Swile meal voucher export for the
  current month (new data to import)
- **config.yaml** — Configuration pointing to the demo database and import files, plus
  the throwaway web credentials

## Date-Relative Data

All dates are computed relative to **today** when running `generate_demo.py`:

- **M-3 to M-1**: 3 months of historic operations in the database
- **Current month**: Partial month in the BNP and Swile export files (for import)
- **Balance date**: Last day of M-1

This ensures the demo always feels current, regardless of when you run it.

## Scenario

A fictional Parisian developer with a typical budget: salary, rent, utilities,
groceries, public transport, savings, and leisure.

The database is pre-loaded with operations already linked to their planned counterparts,
so the forecast works out of the box.

The export files in `data/` contain the current month's operations that you can import
to see how the application handles new bank statements and updates the forecast.

### Missed Payments

Two planned payments were never matched by a bank operation, so the demo shows what the
app does with them:

- **Home insurance in M-1** (-25 EUR) — a direct debit that never went through. It is
  late, so the forecast still expects it and counts it the day after the balance date.
- **Plumber deposit in M-2** (-180 EUR) — older than the 31-day late horizon. It no
  longer weighs on the forecast, but it is still reported as overdue rather than
  silently dropped.

### Margin Threshold

The margin threshold is set to **500 EUR**. When reviewing the month containing the
washing machine repair (-400 EUR one-time expense), the available margin dips below the
threshold, triggering the alert indicator. The late home insurance debit weighs on it
too.

## Regenerating

To regenerate the demo data with fresh dates:

```bash
python examples/generate_demo.py
```

The script uses a fixed random seed for reproducibility — running it multiple times
produces the same data (with dates shifted to today).
