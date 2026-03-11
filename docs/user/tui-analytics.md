# TUI - Analytics

The Analytics tab combines two sub-views for financial analysis:

- **Balance evolution** — Day-by-day balance projection chart
- **Expense breakdown** — Category distribution of past expenses

Switch between views using the radio buttons at the top of the tab.

## Balance Evolution

```
┌────────────────────────────────────────────────────────────────────────┐
│ Balance Evolution                                                      │
│                                                                        │
│  3200 ┤                    ╭──╮        ╭──╮        ╭──╮                │
│  2800 ┤───╮    ╭───────────╯  │  ╭─────╯  │  ╭─────╯  │                │
│  2400 ┤   ╰────╯              ╰──╯        ╰──╯        ╰──── ...        │
│  2000 ┤                                                                │
│  1600 ┤                                                                │
│       └───────────────────────────────────────────────────────         │
│        Jan       Feb       Mar       Apr       May                     │
│                                                                        │
│                            ▲ Today                                     │
├────────────────────────────────────────────────────────────────────────┤
│  R Refresh   X Export                                                  │
└────────────────────────────────────────────────────────────────────────┘
```

The chart shows your account balance over the report period:

- **Past dates** (left of today) — Actual balance computed from real bank operations
- **Future dates** (right of today) — Projected balance from planned operations and
  budgets
- **Balance date** — The pivot point where actual data meets the forecast

The salary peaks and expense dips are clearly visible, giving you a quick sense of your
monthly cash flow pattern.

### Auto-Compute

The forecast is computed automatically when the Analytics tab is first activated. The
result is cached and shared with the Review tab — switching tabs does not trigger a
recomputation.

Press `R` to refresh data and force a recompute (e.g. after importing new bank
statements).

### Excel Export

Press `X` to open the export modal. You can select a date range for the export, which
generates an Excel file containing:

- Balance evolution chart
- Monthly summary by category (Actual / Planned / Forecast)
- Budget statistics (total and monthly average per category)

## Expense Breakdown

A horizontal bar chart showing expense distribution by category, averaged over a
selectable time period.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Expense breakdown                              [1M] [3M] [6M] [1Y]              │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                      Avg/mo €      Total €       │
│  Groceries    ████████████████████████████████  35%  1,250.00 €  3,750.00 €      │
│  House Loan   ██████████████████████████████    30%  1,070.00 €  3,210.00 €      │
│  Car Fuel     ████████████                      12%    430.00 €  1,290.00 €      │
│  Leisure      ██████                             8%    285.00 €    855.00 €      │
│  Health Care  █████                              6%    215.00 €    645.00 €      │
│  Other        ████                               9%    320.00 €    960.00 €      │
│                                                                                  │
│  Period: Dec 2025 — Feb 2026 (3 months)                    Total: 10,710.00 €    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Period Selection

Use the period buttons to select the analysis window:

| Button | Period        |
| ------ | ------------- |
| `1M`   | Last month    |
| `3M`   | Last 3 months |
| `6M`   | Last 6 months |
| `1Y`   | Last year     |

Each row shows two amounts: the **monthly average** (Avg/mo) and the **cumulative
total** over the selected period, making it easy to compare spending patterns across
different time horizons.

### Threshold

Categories representing less than the configured threshold (default 2%) are grouped into
an "Other" bucket. The threshold is configurable in the application settings.

### Data Source

The breakdown uses only **completed (past) expense operations** — income and future
projections are excluded. This gives an accurate picture of actual spending habits.
