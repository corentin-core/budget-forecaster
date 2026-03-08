# TUI - Balance

The Balance tab displays the balance evolution chart — a day-by-day projection of your
account balance combining real bank history with the forecast.

## Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ Balance Evolution                                                      │
│                                                                        │
│  3200 ┤                    ╭──╮        ╭──╮        ╭──╮                │
│  2800 ┤───╮    ╭───────────╯  │  ╭─────╯  │  ╭─────╯  │               │
│  2400 ┤   ╰────╯              ╰──╯        ╰──╯        ╰──── ...       │
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

## Balance Evolution Chart

The chart shows your account balance over the report period:

- **Past dates** (left of today) — Actual balance computed from real bank operations
- **Future dates** (right of today) — Projected balance from planned operations and
  budgets
- **Balance date** — The pivot point where actual data meets the forecast

The salary peaks and expense dips are clearly visible, giving you a quick sense of your
monthly cash flow pattern.

## Auto-Compute

The forecast is computed automatically when the Balance tab is first activated. The
result is cached and shared with the Review tab — switching tabs does not trigger a
recomputation.

Press `R` to refresh data and force a recompute (e.g. after importing new bank
statements).

## Excel Export

Press `X` to open the export modal. You can select a date range for the export, which
generates an Excel file containing:

- Balance evolution chart
- Monthly summary by category (Actual / Planned / Forecast)
- Budget statistics (total and monthly average per category)

## Keyboard Shortcuts

| Key | Action                           |
| --- | -------------------------------- |
| `X` | Open Excel export modal          |
| `R` | Refresh data (invalidates cache) |
