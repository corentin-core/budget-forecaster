# TUI - Monthly Review

The Monthly Review tab provides a per-category comparison of planned versus actual
spending for any given month. It helps answer: "Am I on track with my budget?"

## Layout

The screen has three sections: month navigation at the top, review table on the left,
and available margin panel on the right.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        ◀  March 2026  ▶                                         │
├──────────────────────────────────────────────────┬───────────────────────────────┤
│ Category          Planned  Actual  Forecast  Rem.│ Available margin: 1,240 €     │
├──────────────────────────────────────────────────┤ Minimum threshold: 500 €      │
│ Forecasted                                       │                               │
│ ↓ Rent              950     952     952    -2    │ Balance at Mar 1: 2,800 €     │
│ ↓ Groceries         450     280     450   170    │ Lowest balance: 1,740 €       │
│ ↓ Electricity        75      72      72     3    │   (Mar 29, 2026)              │
│ ↓ Entertainment     120      45     120    75    │                               │
│ ↓ Spotify            11      11      11     0    │ = the most you can spend      │
│ ↑ Salary           3200    3200    3200     0    │   freely without going below  │
│                                                  │   500 €                       │
│ Unforecasted                                     │                               │
│ ↓ Uncategorized       -      25      25    --    │                     [Edit]    │
│                                                  │                               │
│ TOTAL             -1606   -1385   -1606  -221    │                               │
├──────────────────────────────────────────────────┴───────────────────────────────┤
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Month Navigation

Use the `◀` / `▶` buttons or keyboard shortcuts to browse months. The review opens on
the current month by default.

The forecast is auto-computed when opening the tab for the first time. The result is
cached and shared with the Balance tab — switching between the two does not recompute.

## Column Explanations

| Column      | Description                                                                 |
| ----------- | --------------------------------------------------------------------------- |
| Category    | Spending/income category with direction indicator (↓ expense, ↑ income)     |
| Planned     | Total amount from planned operations and budgets for this month             |
| Actual      | Sum of real bank operations linked to this category                         |
| Forecast    | Projected amount accounting for links (actual if linked, planned otherwise) |
| Remaining   | Forecast minus Actual — how much is left to spend or receive                |
| Consumption | Visual progress bar showing Actual / Planned ratio                          |

### Consumption Bar

The consumption bar uses a 10-character progress bar:

- **Green** — Under budget (ratio ≤ 100%)
- **Red with `!`** — Over budget (ratio > 100%)

Example: `[▓▓▓▓▓▓░░░░] 60%` means 60% of the planned amount has been spent.

## Forecasted vs Unforecasted

Categories are split into two sections:

- **Forecasted** — Categories with a planned operation or budget. Shows full comparison
  with consumption tracking.
- **Unforecasted** — Categories with actual spending but no planned counterpart. The
  Planned column shows `-` and Remaining shows `--`.

Within each section, expenses (↓) appear before income (↑), sorted alphabetically.

## Category Detail Modal

Press `Enter` on any category row to open the detail modal. It shows:

- **Planned sources** — Which planned operations and budgets contribute to the Planned
  amount, with their individual amounts
- **Attributed operations** — Bank operations linked to this category, with cross-month
  annotations when an operation was paid early or late relative to the selected month

## Available Margin

The margin panel shows how much you can freely spend this month. See
[Available Margin](available-margin.md) for the full explanation.

The margin section is only visible for the current and future months — it is hidden when
reviewing past months.

## Keyboard Shortcuts

| Key     | Action                                |
| ------- | ------------------------------------- |
| `,`     | Previous month                        |
| `;`     | Next month                            |
| `Enter` | Open category detail for selected row |
| `E`     | Edit margin threshold                 |
| `R`     | Refresh data (invalidates cache)      |
