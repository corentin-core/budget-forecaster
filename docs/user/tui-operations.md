# TUI - Managing Operations

This document describes how to use the TUI interface for managing bank operations:
navigation, multi-selection, categorization, and linking.

## Navigating the Operations Table

The operations table is available in the **Dashboard** and **Operations** tabs. It
displays imported operations with their date, description, amount, category, and any
existing link.

```
┌──────────┬──────────────────────────────┬───────────┬─────────────┬─────────────┐
│ Date     │ Description                  │ Amount    │ Category    │ Link        │
├──────────┼──────────────────────────────┼───────────┼─────────────┼─────────────┤
│ 02/01/25 │ TRANSFER LANDLORD            │  -800.00€ │ Rent        │ 🔗 Rent     │
│ 15/01/25 │ EDF INVOICE                  │   -95.00€ │ Electricity │             │
│ 28/01/25 │ SALARY COMPANY               │ +2500.00€ │ Salary      │ 🔗 Salary   │
│►02/02/25 │ SUPERMARKET PURCHASE         │   -45.20€ │ Groceries   │             │
│ 03/02/25 │ RESTAURANT LE PETIT BISTRO   │   -32.00€ │ Restaurant  │             │
└──────────┴──────────────────────────────┴───────────┴─────────────┴─────────────┘
```

The `►` symbol indicates a selected operation.

### Keyboard Shortcuts

| Key          | Action                          |
| ------------ | ------------------------------- |
| `↑` / `↓`    | Navigate between operations     |
| `Space`      | Toggle selection of current row |
| `Shift+↑`    | Extend selection upward         |
| `Shift+↓`    | Extend selection downward       |
| `Ctrl+A`     | Select all operations           |
| `Ctrl+Click` | Toggle selection of clicked row |
| `Click`      | Clear selection (if any exists) |
| `Escape`     | Clear all selections            |
| `C`          | Categorize selected operations  |
| `L`          | Link selected operations        |
| `P`          | Create planned operation        |

## Operation Detail Modal

Press `Enter` on any operation to open a detail modal showing the full operation
information: date, complete description (without truncation), amount, category, and link
status.

The modal provides action buttons and keyboard shortcuts:

| Key   | Action                   |
| ----- | ------------------------ |
| `c`   | Change category          |
| `p`   | Create planned operation |
| `Esc` | Close                    |

This modal is available from any screen that displays operations: the Operations tab,
the category detail drill-down in the Review tab, and the Dashboard.

```
┌────────────────────────────────────────────────────┐
│ Operation detail                                   │
├────────────────────────────────────────────────────┤
│                                                    │
│ Date         15/01/2025                            │
│                                                    │
│ Description  PAIEMENT CB AU PASSAGE 22 DE          │
│              03/01/26 A PARIS 1. CARTE             │
│              4978XXXXXXXX1234                       │
│                                                    │
│ Amount       -58.90 €                              │
│                                                    │
│ Category     Groceries                             │
│                                                    │
│ Link         🔗 Courses hebdo                      │
│                                                    │
│  [Change category]  [Create planned op]  [Close]   │
└────────────────────────────────────────────────────┘
```

## Creating a Planned Operation from History (P key)

When you spot a recurring payment or subscription in your operations, you can quickly
create a planned operation pre-filled with the operation's data.

1. Highlight the operation in the table
2. Press `P` or open the detail modal and press `p`
3. The planned operation form opens with pre-filled fields:
   - Description, amount, category, and date from the historic operation
4. Adjust fields as needed (e.g., set recurrence to monthly)
5. Click "Save"

On save, the planned operation is created **and** a link is automatically created
between the source historic operation and the new planned operation.

## Multi-Selection

Multi-selection enables bulk actions (categorization, linking) on multiple operations at
once.

### Selection Example

```
┌──────────┬──────────────────────────────┬───────────┬─────────────┬─────────────┐
│ Date     │ Description                  │ Amount    │ Category    │ Link        │
├──────────┼──────────────────────────────┼───────────┼─────────────┼─────────────┤
│►02/01/25 │ SUPERMARKET CARREFOUR        │   -85.20€ │ Misc        │             │
│►05/01/25 │ SUPERMARKET LECLERC          │   -42.30€ │ Misc        │             │
│►08/01/25 │ SUPERMARKET AUCHAN           │   -63.50€ │ Misc        │             │
│ 10/01/25 │ RESTAURANT LE BISTRO         │   -28.00€ │ Restaurant  │             │
│►12/01/25 │ SUPERMARKET CARREFOUR        │   -91.00€ │ Misc        │             │
└──────────┴──────────────────────────────┴───────────┴─────────────┴─────────────┘

4 operations selected
```

**Selection Techniques:**

1. **Single selection**: `Space` or `Ctrl+Click` to toggle an operation
2. **Range selection**: `Shift+↑` or `Shift+↓` to extend from anchor
3. **Select all**: `Ctrl+A` to select everything
4. **Clear**: `Escape` or simple click to deselect all

## Categorization (C key)

The categorization modal appears when you press `C` with one or more operations
selected.

### Modal with Single Operation

```
┌──────────────────────────────────────────────────────────────────────┐
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Operation to categorize                                          │ │
│ │ 02/01/2025  SUPERMARKET CARREFOUR                     -85.20 €   │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Similar operations                                               │ │
│ │ SUPERMARKET LECLERC                             → Groceries      │ │
│ │ SUPERMARKET AUCHAN                              → Groceries      │ │
│ │ CARREFOUR MARKET                                → Groceries      │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ Suggestion: Groceries                                                │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ ★ Groceries (suggestion)                            [selected]   │ │
│ │   Electricity                                                    │ │
│ │   Misc                                                           │ │
│ │   Rent                                                           │ │
│ │   Restaurant                                                     │ │
│ │   Salary                                                         │ │
│ │   ...                                                            │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### Modal with Multiple Operations

```
┌──────────────────────────────────────────────────────────────────────┐
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 4 operations to categorize                                       │ │
│ │ 02/01/2025  SUPERMARKET CARREFOUR                     -85.20 €   │ │
│ │ 05/01/2025  SUPERMARKET LECLERC                       -42.30 €   │ │
│ │ 08/01/2025  SUPERMARKET AUCHAN                        -63.50 €   │ │
│ │ 12/01/2025  SUPERMARKET CARREFOUR                     -91.00 €   │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Similar operations                                               │ │
│ │ SUPERMARKET LECLERC                             → Groceries      │ │
│ │ CARREFOUR MARKET                                → Groceries      │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ Suggestion: Groceries                                                │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ ★ Groceries (suggestion)                            [selected]   │ │
│ │   Misc                                                           │ │
│ │   ...                                                            │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**Features:**

- **Operations list**: Displays up to 8 selected operations
- **Similar operations**: Based on the first operation, shows categories assigned to
  similar operations in history
- **Suggestion**: Automatically suggested category, pre-selected in the list
- **Validation**: Press `Enter` to apply the category to all selected operations

## Linking Operations (L key)

The link modal allows you to associate one or more operations with a planned operation
or budget.

### Step 1: Select Target

```
┌──────────────────────────────────────────────────────────────────────┐
│ Link 3 operations                                                    │
├──────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 3 operations to link                                             │ │
│ │ 02/01/2025  SUPERMARKET CARREFOUR                     -85.20 €   │ │
│ │ 05/01/2025  SUPERMARKET LECLERC                       -42.30 €   │ │
│ │ 08/01/2025  SUPERMARKET AUCHAN                        -63.50 €   │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Planned operations                                           [v] │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ Score  Description                    Amount     Category            │
│ ─────────────────────────────────────────────────────────────────────│
│  75%   Groceries budget                -400 €    Groceries [selected]│
│  42%   Electricity                      -95 €    Electricity         │
│  30%   Rent                            -800 €    Rent                │
│   -    Salary                         +2500 €    Salary              │
│                                                                      │
│                                              [Cancel]  [Next]        │
└──────────────────────────────────────────────────────────────────────┘
```

### Step 2: Select Iteration

```
┌──────────────────────────────────────────────────────────────────────┐
│ Select iteration                                                     │
├──────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ SUPERMARKET CARREFOUR                                            │ │
│ │ 02/01/2025 | -85.20 €                                            │ │
│ │ → Groceries budget                                               │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│              [<]     Nov 2024 - Mar 2025     [>]                     │
│                                                                      │
│ Score  Iteration                                                     │
│ ─────────────────────────────────────────────────────────────────────│
│  55%   01/11/2024                                                    │
│  70%   01/12/2024                                                    │
│  85%   01/01/2025                                         [selected] │
│  70%   01/02/2025                                                    │
│  55%   01/03/2025                                                    │
│                                                                      │
│                                              [Cancel]  [Link]        │
└──────────────────────────────────────────────────────────────────────┘
```

**Features:**

- **Match score**: Indicates the probability of match (0-100%)
- **Target type**: Toggle between "Planned operations" and "Budgets"
- **Sorted by score**: Targets are sorted by descending score
- **Remove link**: The "Remove link" button removes existing links from selected
  operations

**Notes:**

- When linking multiple operations, all are linked to the same target and iteration
- The score is calculated based on the first selected operation
- When removing links from multiple operations, only operations with existing links are
  affected (operations without links are silently ignored)

## Typical Workflows

### Categorize Similar Operations

1. Identify uncategorized operations (category "Misc")
2. Select them with `Shift+↓` or `Space`
3. Press `C`
4. Check the suggestion based on similar operations
5. Validate with `Enter`

### Link Multiple Payments to a Budget

1. Select operations corresponding to the same budget
2. Press `L`
3. Choose "Budgets" in the type selector
4. Select the appropriate budget
5. Choose the corresponding iteration (month)
6. Validate with "Link"

### Track a New Recurring Payment

1. Spot a new subscription or recurring payment in the operations list
2. Highlight it and press `P`
3. Review the pre-filled form, set recurrence to "Monthly"
4. Save — the planned operation is created and automatically linked
