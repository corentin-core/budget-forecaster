# Demo Data

Pre-populated example data to try the application without your own bank statements.

## Quick Start

```bash
# Install the application
pip install -e .

# Run the TUI from the examples directory
cd examples/
python -m budget_forecaster.main -c config.yaml
```

## Contents

- **demo.db** — SQLite database with 3 months of categorized operations (Oct–Dec 2025),
  planned operations, budgets, and operation links
- **data/bnp-export-demo.xls** — Anonymized BNP bank export for January 2026 (new data
  to import)
- **data/swile/** — Anonymized Swile meal voucher export for January 2026 (new data to
  import)
- **config.yaml** — Configuration pointing to the demo database and import files

## Scenario

A fictional Parisian developer with a typical budget: salary, rent, utilities,
groceries, public transport, savings, and leisure.

The database is pre-loaded with 3 months of imported operations already linked to their
planned counterparts, so the forecast works out of the box.

The export files in `data/` contain a new month (January 2026) that you can import to
see how the application handles new bank statements and updates the forecast.
