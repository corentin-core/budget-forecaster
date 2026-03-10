# TUI - Dashboard

The Dashboard is the first screen displayed when launching the application. It provides
an at-a-glance overview of your financial situation: account balance, upcoming planned
operations, expense breakdown, and recent transactions.

## Layout

The dashboard is composed of four sections, from top to bottom:

1. **Summary statistics** — Balance, monthly operations count, monthly expenses,
   uncategorized count
2. **Upcoming planned operations** — Next 30 days of scheduled transactions
3. **Expenses by category** — Current month breakdown with progress bars
4. **Recent operations table** — Last 3 months of bank transactions

```
┌────────────────────────┬─────────────────────────┬──────────────────────────┐
│ Balance: 1,234.56 EUR  │ Operations this month: 7│ Uncategorized: 3         │
├────────────────────────┴─────────────────────────┴──────────────────────────┤
│ Upcoming planned operations (next 30 days)                                  │
│ Date       Description                  Amount           Period             │
│ Mar 01     Rent                         -800.00 EUR      1 mo.              │
│ Mar 05     Electricity                   -95.00 EUR      1 mo.              │
│ Mar 15     Insurance                    -120.00 EUR      1 mo.              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Expenses by category (this month)                                           │
│ Rent                            -800.00 €   ████████████████████            │
│ Groceries                       -320.50 €   ████████                        │
│ Electricity                      -95.00 €   ██                              │
├──────────┬──────────────────────────────┬───────────┬────────────┬──────────┤
│ Date     │ Description                  │ Amount    │ Category   │ Link     │
├──────────┼──────────────────────────────┼───────────┼────────────┼──────────┤
│ 02/03/25 │ TRANSFER LANDLORD            │  -800.00€ │ Rent       │ 🔗 Rent  │
│ 01/03/25 │ SUPERMARKET CARREFOUR        │   -45.20€ │ Groceries  │          │
│ 28/02/25 │ SALARY COMPANY               │ +2500.00€ │ Salary     │ 🔗 Sal.  │
│ ...      │                              │           │            │          │
└──────────┴──────────────────────────────┴───────────┴────────────┴──────────┘
```

## Summary Statistics

The top bar displays three key indicators:

| Indicator             | Description                                         |
| --------------------- | --------------------------------------------------- |
| Balance               | Current account balance, colored green or red       |
| Operations this month | Number of operations in the current month           |
| Expenses this month   | Total expenses for the current month                |
| Uncategorized         | Count of operations without a category (red if > 0) |

## Upcoming Planned Operations

This section lists all planned operation iterations scheduled within the next 30 days,
sorted by date (closest first). Both recurring and one-time operations are included.

### Columns

| Column      | Description                                                        |
| ----------- | ------------------------------------------------------------------ |
| Date        | Scheduled date of the iteration (e.g. `Mar 01`)                    |
| Description | Name of the planned operation                                      |
| Amount      | Expected amount, colored red (expense) or green (income)           |
| Period      | Recurrence interval (`1 mo.`, `2 wk.`, `1 yr.`) or `-` if one-time |

### Behavior

- Recurring operations may appear multiple times if several iterations fall within the
  30-day window (e.g. a weekly operation will show ~4 rows)
- Operations that have expired (end date in the past) are excluded
- If no operations are scheduled, the message "No upcoming planned operations" is
  displayed

## Expenses by Category

This section shows the top 10 expense categories for the current calendar month. Each
row displays:

- **Category name** — The spending category
- **Amount** — Total spent this month (negative value)
- **Progress bar** — Visual indicator scaled relative to the highest expense category

Only negative amounts (expenses) are shown. Income categories are excluded.

## Recent Operations Table

The bottom section displays a standard operations table covering the last 3 months. It
supports the same interactions as the Operations tab:

- Row navigation with arrow keys
- Press `Enter` on any operation to open the
  [operation detail modal](tui-operations.md#operation-detail-modal) with full
  description and actions
- Multi-selection with `Space`, `Shift+↑/↓`, `Ctrl+A`
- Categorization with `C` and linking with `L`

See [Managing Operations](tui-operations.md) for the full keyboard shortcuts and
workflow documentation.

## Keyboard Shortcuts

| Key | Action                                       |
| --- | -------------------------------------------- |
| `R` | Refresh all dashboard data                   |
| `C` | Categorize selected operation(s)             |
| `L` | Link selected operation(s) to a planned item |
| `Q` | Quit the application                         |
