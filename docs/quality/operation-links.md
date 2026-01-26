# Operation Links - Test Scenarios

## Link Priority Over Heuristics

> **Given** an operation linked to a planned operation
>
> **When** the matcher checks if the operation matches
>
> **Then** it returns true even if heuristic criteria (amount, date, category) don't
> match

## Heuristic Link Creation

> **Given** a new operation imported without any link, and a planned operation with
> matching criteria (amount ±5%, date ±5 days, same category)
>
> **When** `create_heuristic_links()` is called
>
> **Then** an automatic link is created with `is_manual=false`

## Manual Link Preservation

> **Given** a manual link between an operation and a planned operation
>
> **When** the planned operation is edited and `recalculate_links_for_target()` is
> called
>
> **Then** the manual link is preserved (not deleted)

## Automatic Link Recalculation

> **Given** an automatic link between an operation and a planned operation
>
> **When** the planned operation criteria change so the operation no longer matches, and
> `recalculate_links_for_target()` is called
>
> **Then** the automatic link is deleted

## Upsert Replaces Existing Link

> **Given** an operation already linked to planned operation A
>
> **When** `upsert_link()` is called with a link to planned operation B
>
> **Then** the link to A is replaced by the link to B
