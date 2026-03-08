# Monthly Review - Test Scenarios

## Auto-Compute on Tab Open

> **Given** the Balance or Review tab has never been opened in this session
>
> **When** the user switches to the Review tab
>
> **Then** the forecast is computed automatically and the review table displays the
> current month

## Shared Cache Between Tabs

> **Given** the forecast has been computed from the Balance tab
>
> **When** the user switches to the Review tab
>
> **Then** the review table is populated immediately without recomputation

## Cache Invalidation on Refresh

> **Given** the user is on the Review tab with data displayed
>
> **When** the user presses `R` to refresh
>
> **Then** the cached report is invalidated, and switching to either the Balance or
> Review tab triggers a fresh computation

## Margin Calculation Uses Lowest Future Balance

> **Given** a projected balance that dips to 1,740 EUR on March 29th and recovers to
> 3,200 EUR on March 30th, with a threshold of 500 EUR
>
> **When** the user views March in the Review tab
>
> **Then** the available margin is 1,240 EUR (1,740 - 500), using the lowest point, not
> the end-of-month balance

## Alert When Below Threshold

> **Given** a month where the lowest projected balance is 300 EUR and the threshold is
> 500 EUR
>
> **When** the user views that month in the Review tab
>
> **Then** the margin shows -200 EUR, the margin section turns red, and a warning
> message indicates the date when the balance drops below threshold

## Cross-Month Attribution (Early Payment)

> **Given** a rent operation paid on January 25th linked to the February 1st iteration
>
> **When** the user views February in the Review tab
>
> **Then** the rent operation appears in February's Actual column (not January's), with
> a cross-month annotation indicating it was paid early

## Cross-Month Attribution (Late Payment)

> **Given** a rent operation paid on February 8th linked to the January 5th iteration
>
> **When** the user views January in the Review tab
>
> **Then** the rent operation appears in January's Actual column (not February's), with
> a cross-month annotation indicating it was paid late

## Planned Operation Takes Priority Over Budget

> **Given** a monthly grocery budget of 100 EUR and a planned grocery operation of 50
> EUR on the same category
>
> **When** a 50 EUR grocery operation occurs and is linked to the planned operation
>
> **Then** the operation is attributed to the planned operation, not to the budget — the
> budget remains fully unconsumed, and the Forecast shows 150 EUR (50 EUR realized from
> the planned operation plus 100 EUR unrealized from the budget)

## Unlinked Operation Adds to Budget Forecast

> **Given** a monthly grocery budget of 100 EUR
>
> **When** a 50 EUR grocery operation occurs but is not linked to the budget
>
> **Then** the Forecast shows 150 EUR (50 EUR actual plus 100 EUR unrealized from the
> budget), because unlinked spending is added on top of the planned amount

## Consumption Bar Over 100%

> **Given** a monthly entertainment budget of 120 EUR and actual spending of 150 EUR
> linked to the budget
>
> **When** the user views that month in the Review tab
>
> **Then** the consumption bar shows 125% in red with the over-budget indicator

## Margin Hidden for Past Months

> **Given** today is March 15th and the user is on the Review tab
>
> **When** the user navigates to February (a past month)
>
> **Then** the available margin section is hidden

## Forecast Column Formula

> **Given** a category with a planned amount of 450 EUR, and 3 of 9 planned operations
> have been linked with actual amounts of 80, 95, and 45 EUR
>
> **When** the forecast is computed for that month
>
> **Then** the Forecast column shows 450 EUR (the full planned amount) because the
> budget is not yet fully consumed — remaining iterations use the planned daily rate
