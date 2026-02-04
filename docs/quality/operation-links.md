# Operation Links - Test Scenarios

## Manual Link Takes Priority Over Matching Criteria

> **Given** an operation manually linked to a planned operation
>
> **When** the forecast is computed
>
> **Then** the link is used even if the operation doesn't match the criteria (amount,
> date, category)

## Automatic Link Creation After Import

> **Given** a new bank operation imported, and a planned operation with matching
> criteria (amount ±5%, date ±5 days, same category)
>
> **When** the import completes
>
> **Then** an automatic link is created between the operation and the planned operation

## Manual Links Preserved When Editing

> **Given** a manual link between an operation and a planned operation
>
> **When** the user edits the planned operation (changes amount, date, or category)
>
> **Then** the manual link is preserved

## Automatic Links Recalculated When Editing

> **Given** an automatic link between an operation and a planned operation
>
> **When** the user edits the planned operation so the criteria no longer match
>
> **Then** the automatic link is removed

## Linking to Different Target Replaces Existing Link

> **Given** an operation linked to planned operation A
>
> **When** the user links it to planned operation B
>
> **Then** the link to A is replaced by the link to B (operation can only have one link)

## Unlinking an Operation

> **Given** an operation linked to a planned operation
>
> **When** the user removes the link
>
> **Then** the operation is no longer associated with the planned operation and won't
> count toward its actualization

## Deleting Target Removes Associated Links

> **Given** a planned operation with several linked bank operations
>
> **When** the user deletes the planned operation
>
> **Then** all links to that planned operation are removed

## Budgets and Planned Operations Share Link Behavior

> **Given** an operation that can be linked to either a planned operation or a budget
>
> **When** the user creates, edits, or removes links
>
> **Then** the behavior is identical for both target types (manual/auto priority,
> preservation rules, replacement)
