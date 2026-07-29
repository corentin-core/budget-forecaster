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

| Mode      | Description                    | Behavior                                    |
| --------- | ------------------------------ | ------------------------------------------- |
| Automatic | Created by heuristic matching  | Can be overwritten by user or recalculation |
| Manual    | Created by user in the web app | Protected from automatic recalculation      |

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

Creating a planned operation from an operation links that operation to the occurrence it
falls in, so the payment counts from the start. The link is a manual one and survives
later edits to the planned operation, and an operation already linked to something else
keeps that link.

## Manual Linking

Beyond automatic matching, you can create, edit, and remove links by hand from the
operation view. Each link targets a specific dated occurrence of a planned operation or
budget, chosen from candidates ranked by match score. See [Web App](web-app.md) for the
step-by-step interface.

Wherever the app names what counts an operation, the name is a link: the `→ target` tag
in the ledger, the link line on an operation's page, the same tag in the Mois
drill-down. It opens the budget or planned operation for editing and comes back to where
you left, filters included.

The same thing works from the other end: an overdue occurrence offers the operations
that could be it, ranked by the same score. Since a link belongs to the operation,
linking one that another target already counts moves it rather than duplicating it. The
occurrence it leaves goes back to being unmatched, and the forecast expects its amount
again — unless that occurrence had already passed the late horizon, or belongs to a
budget month already closed, in which case it had left the forecast and nothing comes
back.

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

1. Open the operation from the ledger
2. Use "Unlink" to remove the incorrect link
3. Use "Link…" to pick the right target and iteration
4. The new link is manual, so recalculation leaves it alone

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
