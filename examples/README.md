# Demo Data

Pre-populated example data to try the application without your own bank statements.

## Quick Start

```bash
# Install the application
pip install -e .

# Optionally regenerate demo data with fresh dates
python examples/generate_demo.py

# Run the TUI from the examples directory
cd examples/
python -m budget_forecaster.main -c config.yaml
```

## Contents

- **demo.db** — SQLite database with 3 months of categorized operations, planned
  operations, budgets, and operation links
- **data/bnp-export-demo.xls** — Anonymized BNP bank export for the current month (new
  data to import)
- **data/swile-export-YYYY-MM-DD.zip** — Anonymized Swile meal voucher export for the
  current month (new data to import)
- **config.yaml** — Configuration pointing to the demo database and import files

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

### Margin Threshold

The margin threshold is set to **500 EUR**. When reviewing the month containing the
washing machine repair (-400 EUR one-time expense), the available margin dips below the
threshold, triggering the alert indicator.

## Regenerating

To regenerate the demo data with fresh dates:

```bash
python examples/generate_demo.py
```

The script uses a fixed random seed for reproducibility — running it multiple times
produces the same data (with dates shifted to today).
