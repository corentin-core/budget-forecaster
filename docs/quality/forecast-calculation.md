# Forecast Calculation - Test Scenarios

## Linked Iteration Is Actualized

> **Given** a monthly planned operation (rent on 1st of each month), and an operation
> linked to the January iteration
>
> **When** the forecast is actualized
>
> **Then** the January iteration is marked as actualized, and future iterations
> (February, March...) remain in the forecast

## Budget Consumption Via Links

> **Given** a monthly budget of 500€ for groceries, and two operations linked to it:
> -80€ and -120€
>
> **When** the budget forecast is computed
>
> **Then** remaining budget is 300€ (500 - 80 - 120)

## Late Iteration Detection

> **Given** a planned operation expected on January 15th, and no operation linked to
> that iteration, and today is January 20th
>
> **When** the forecast is actualized
>
> **Then** the January 15th iteration is flagged as LATE

## One-Time Past Operation Removed

> **Given** a one-time planned operation dated January 10th, and today is January 15th,
> and no link exists for this operation
>
> **When** the forecast is actualized
>
> **Then** the planned operation is removed from the forecast

## Periodic Operation Advances Past Linked Iterations

> **Given** a monthly planned operation starting January 1st, and links exist for
> January and February iterations
>
> **When** the forecast is actualized
>
> **Then** the operation's effective start date advances to March 1st

## Anticipated Future Iteration Is Actualized

> **Given** a monthly planned operation (rent on 1st of each month), and today is
> January 25th, and an operation is linked to the February iteration (paid early)
>
> **When** the forecast is actualized
>
> **Then** the February iteration is marked as actualized and skipped in the forecast
