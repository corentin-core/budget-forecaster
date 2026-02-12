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

- **demo.db** — SQLite database with 4 months of categorized operations, planned
  operations, budgets, and operation links
- **data/bnp-export-demo.xls** — Anonymized BNP bank export (Oct 2025 – Jan 2026)
- **data/swile/** — Anonymized Swile meal voucher export (Nov 2025 – Jan 2026)
- **config.yaml** — Configuration pointing to the demo database and import files

## Scenario

A fictional Parisian developer with a typical budget: salary, rent, utilities,
groceries, public transport, savings, and leisure. The database is pre-loaded with
imported operations already linked to their planned counterparts, so the forecast works
out of the box.
