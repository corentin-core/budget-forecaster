# Archive Operations - Test Scenarios

## Default View Shows Only Active Items

> **Given** a mix of active, expired, and archived planned operations
>
> **When** the user opens the planned operations tab
>
> **Then** only active (not expired, not archived) items are displayed

## Expired Items Hidden from Active View

> **Given** a monthly planned operation ending December 31st, 2025
>
> **When** viewed on January 15th, 2026 with the "Active" filter
>
> **Then** the operation is not displayed (it is expired)

## Archiving Moves Item Out of Current View

> **Given** an expired planned operation visible in the "Expired" filter view
>
> **When** the user selects it and presses `a` to archive
>
> **Then** the item disappears from the expired view and appears in the "Archived" view

## Unarchiving Restores Item to Appropriate View

> **Given** an archived planned operation whose end date is in the future
>
> **When** the user unarchives it from the "Archived" filter view
>
> **Then** the item appears in the "Active" view

## Bulk Archive All Expired

> **Given** 3 expired and 2 active planned operations
>
> **When** the user switches to "Expired" filter and clicks "Archive all expired"
>
> **Then** all 3 expired operations are archived, and the expired view becomes empty

## Archived Items Still Used in Forecast Reports

> **Given** an archived planned operation with past linked iterations
>
> **When** a forecast report is computed
>
> **Then** the archived operation's historical links are included in the actual vs
> planned comparison

## Archive State Persists Across Sessions

> **Given** a planned operation that has been archived
>
> **When** the application is closed and reopened
>
> **Then** the operation remains archived (stored in database)
