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
