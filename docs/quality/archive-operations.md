# Status Filtering - Test Scenarios

## Default View Shows Only Active Items

> **Given** a mix of active and expired planned operations
>
> **When** the user opens the planned operations tab
>
> **Then** only active (not expired) items are displayed

## Expired Items Hidden from Active View

> **Given** a monthly planned operation ending December 31st, 2025
>
> **When** viewed on January 15th, 2026 with the "Active" filter
>
> **Then** the operation is not displayed (it is expired)

## Expired Filter Shows Only Expired Items

> **Given** 3 expired and 2 active planned operations
>
> **When** the user switches to "Expired" filter
>
> **Then** only the 3 expired operations are shown

## All Filter Shows Everything

> **Given** 3 expired and 2 active planned operations
>
> **When** the user switches to "All" filter
>
> **Then** all 5 operations are shown
