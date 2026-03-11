# Operation Links

Operation links connect historic bank operations to planned operations or budgets,
enabling accurate forecast tracking even when automatic matching fails.

## Overview

When you import bank statements, Budget Forecaster automatically tries to match each
operation to a planned operation or budget using heuristic rules (amount, date,
category, description). However, automatic matching can fail when:

- An operation arrives on an unexpected date (e.g., salary on the 2nd instead of the
  28th)
- The amount differs slightly (e.g., electricity bill €102 instead of €95)
- The description doesn't match (e.g., "TRANSFER LANDLORD" instead of "RENT")

Operation links solve this by allowing both automatic and manual associations between
operations and their corresponding forecast entries.

## How Links Work

### Link Types

An operation can be linked to either:

- **Planned Operation**: A specific iteration of a recurring or one-time planned
  operation
- **Budget**: A budget category that tracks spending limits

### Link Modes

| Mode      | Description                   | Behavior                                    |
| --------- | ----------------------------- | ------------------------------------------- |
| Automatic | Created by heuristic matching | Can be overwritten by user or recalculation |
| Manual    | Created by user in TUI        | Protected from automatic recalculation      |

### Iteration Identification

For recurring planned operations, each occurrence is identified by its iteration date.
For example, a monthly rent payment creates iterations on the 1st of each month. When
linking an operation, you select the specific iteration it corresponds to.

## Automatic Linking

Automatic links are created when:

1. **Importing operations**: New operations are matched against existing planned
   operations and budgets
2. **Editing a planned operation or budget**: Links are recalculated for all unlinked
   operations

### Matching Criteria

The matcher uses these criteria (same as forecast actualization):

| Criterion   | Weight | Description                               |
| ----------- | ------ | ----------------------------------------- |
| Amount      | 40%    | Within configured tolerance (default 5%)  |
| Date        | 30%    | Within configured range (default ±5 days) |
| Category    | 20%    | Exact category match                      |
| Description | 10%    | Contains configured keywords              |

An operation matches if all criteria pass. When multiple targets match, the one with the
highest score is selected.

## Automatic Link from Planned Operation Creation

When you create a planned operation from a historic operation (using `P` key in the
Operations tab), a manual link is automatically created between the source historic
operation and the new planned operation. This saves you from having to manually link
them afterwards.

## Manual Linking in TUI

### Viewing Link Status

In the Operations tab, the "Lien" column shows linked operations:

```
┌──────────┬─────────────────────┬──────────┬─────────────┬──────────────┐
│ Date     │ Description         │ Montant  │ Catégorie   │ Lien         │
├──────────┼─────────────────────┼──────────┼─────────────┼──────────────┤
│ 02/01/25 │ TRANSFER LANDLORD   │  -800.00 │ Loyer       │ 🔗 Loyer     │
│ 15/01/25 │ EDF INVOICE         │   -95.00 │ Electricité │              │
│ 28/01/25 │ SALARY COMPANY      │ +2500.00 │ Salaire     │ 🔗 Salaire   │
└──────────┴─────────────────────┴──────────┴─────────────┴──────────────┘
```

### Creating a Link

There are two ways to create or edit a link:

#### From the Operations tab

1. Select one or more operations in the Operations tab (see Multi-selection below)
2. Press `L` to open the link modal
3. Choose the target type (Planned Operation or Budget)
4. Select a target from the list (sorted by match score)
5. Click "Suivant" to proceed
6. Select the specific iteration date
7. Click "Lier" to confirm

**Note:** When linking multiple operations, all are linked to the same target and
iteration. This is useful for split payments or grouping similar transactions.

#### From the Operation Detail Modal

1. Press `Enter` on an operation to open its detail modal
2. Click the "Link" button (or press `L`)
3. Follow the same target selection and iteration flow
4. The modal updates the link label and button text after changes

If the operation already has a link, the button shows "Edit link" instead of "Link". You
can also unlink from this modal by clicking "Supprimer le lien" in the target selection
step.

### Multi-selection

You can select multiple operations before pressing `L` or `C`:

| Shortcut     | Action                          |
| ------------ | ------------------------------- |
| `Space`      | Toggle selection of current row |
| `Shift+↑`    | Extend selection upward         |
| `Shift+↓`    | Extend selection downward       |
| `Ctrl+A`     | Select all operations           |
| `Ctrl+Click` | Toggle selection of clicked row |
| `Click`      | Clear selection (if any exists) |
| `Escape`     | Clear all selections            |

Selected operations display a `►` marker before the date.

#### Step 1: Select Target

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Lier l'opération                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ TRANSFER LANDLORD                                                   │ │
│ │ 02/01/2025 | -800.00 €                                              │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ 🔗 Lié à: Loyer                                                         │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Opérations planifiées                                           [v] │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ Score  Description                      Montant   Catégorie             │
│ ────────────────────────────────────────────────────────────────────────│
│  85%   Loyer                             -800 €   Loyer       [selected]│
│  42%   Electricité                        -95 €   Electricité           │
│  30%   Salaire                          +2500 €   Salaire               │
│   -    Abonnement téléphone               -20 €   Téléphone             │
│                                                                         │
│ [Supprimer le lien]                           [Annuler]  [Suivant]      │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Step 2: Select Iteration

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Sélectionner l'itération                                                │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ TRANSFER LANDLORD                                                   │ │
│ │ 02/01/2025 | -800.00 €                                              │ │
│ │ → Loyer                                                             │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│              [<]     Nov 2024 - Mar 2025     [>]                        │
│                                                                         │
│ Score  Itération                                                        │
│ ────────────────────────────────────────────────────────────────────────│
│  55%  01/11/2024                                                        │
│  70%  01/12/2024                                                        │
│  85%  01/01/2025                                              [selected]│
│  70%  01/02/2025                                                        │
│  55%  01/03/2025                                                        │
│                                                                         │
│                                                   [Annuler]  [Lier]     │
└─────────────────────────────────────────────────────────────────────────┘
```

The modal displays a match score (0-100%) for each target to help you choose.

### Removing a Link

1. Select a linked operation (shows 🔗 in the Lien column)
2. Press `L` to open the link modal
3. Click "Supprimer le lien" at the bottom

## Impact on Forecasts

### Planned Operations

When an operation is linked to a planned operation iteration:

- The iteration is marked as **adjusted** and excluded from future forecasts
- The actual amount replaces the planned amount for balance calculations
- Other operations won't automatically match this iteration

### Budgets

When an operation is linked to a budget:

- The operation amount **decrements** the remaining budget for that period
- Multiple operations can be linked to the same budget iteration
- The forecast shows the remaining budget amount

## Match Score Calculation

The match score helps identify the most likely target for an operation:

```
Score = Amount (40%) + Date (30%) + Category (20%) + Description (10%)
```

**Note**: Budget targets don't use amount scoring since budget amounts represent total
limits, not individual operation amounts. This ensures planned operations are
prioritized when both match on other criteria.

### Score Interpretation

| Score   | Interpretation                             |
| ------- | ------------------------------------------ |
| 80-100% | Excellent match, very likely correct       |
| 60-79%  | Good match, review recommended             |
| 40-59%  | Possible match, manual verification needed |
| < 40%   | Weak match, probably incorrect             |

## Troubleshooting

### Operation not automatically linked

- Check that the operation's category matches the target
- Verify the operation date is within the tolerance range
- Ensure the amount is within the configured ratio
- If using description hints, confirm the keywords appear in the operation description

### Wrong automatic link created

1. Open the link modal (`L` key)
2. Click "Supprimer le lien" to remove the incorrect link
3. Select the correct target and iteration
4. The new link will be manual and protected from recalculation

### Link disappeared after editing planned operation

Automatic links are recalculated when you edit a planned operation or budget. If the
operation no longer matches the criteria, the link is removed. To preserve links:

1. Create manual links instead of relying on automatic matching
2. Or adjust the planned operation's matching criteria (tolerance, date range, keywords)

### Multiple operations for same iteration

Each operation can only have one link, but multiple operations can link to the same
iteration. This is useful for:

- Split payments (e.g., paying rent in two transfers)
- Reimbursements followed by the actual expense
