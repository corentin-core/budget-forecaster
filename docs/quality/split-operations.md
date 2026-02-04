# Split Operations - Test Scenarios

## Split Preserves History

> **Given** a monthly planned operation (e.g., rent on the 1st) with past iterations
> already linked to bank operations
>
> **When** the user splits it from a future date with a new amount
>
> **Then** past iterations remain linked to the original operation, and future
> iterations use the new amount

## Split Date Defaults to Next Unlinked Iteration

> **Given** a monthly planned operation where January 1st and February 1st are already
> linked
>
> **When** the user opens the split modal
>
> **Then** the default split date is March 1st (first iteration without a linked
> operation)

## Split Modal Pre-fills Current Values

> **Given** a monthly budget of 300€ with 1-month duration
>
> **When** the user opens the split modal
>
> **Then** the amount, period, and duration fields show the current values (300€,
> monthly, 1 month)

## Split Allows Modifying Amount, Period, and Duration

> **Given** a monthly budget of 300€ with 1-month duration
>
> **When** the user splits it from a future date, changing the amount to 400€, the
> period to quarterly, and the duration to 3 months
>
> **Then** the new budget uses the updated amount, period, and duration

## Split Creates Continuation

> **Given** a monthly salary of 2500€ on the 28th, starting January 28th
>
> **When** the user splits it from June 28th with a new amount of 2700€
>
> **Then** the original salary ends on June 27th, a new salary starts on June 28th at
> 2700€, and both share the same description and category

## Split Date Must Be After Initial Date

> **Given** a planned operation starting on January 15th
>
> **When** the user tries to split it with a date on or before January 15th
>
> **Then** an error message is displayed and the split is not performed

## Split Requires Periodic Element

> **Given** a one-time planned operation (non-recurring)
>
> **When** the user tries to split it
>
> **Then** the split action is not available (only periodic elements can be split)

## Links Follow Their Iterations After Split

> **Given** a planned operation with a link on a future iteration (e.g., March 1st)
>
> **When** the user splits it before that iteration (e.g., from March 1st)
>
> **Then** the link is automatically transferred to the new operation
