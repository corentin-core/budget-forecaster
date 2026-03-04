# Available Margin

The available margin tells you the maximum amount you can spend freely without your
account going below a safety threshold.

## Definition

```
Available margin = Lowest future balance − Threshold
```

Where:

- **Lowest future balance** is the minimum projected balance from the selected month
  onward, based on the forecast (all planned operations and budgets applied)
- **Threshold** is a configurable safety net (e.g. 500 EUR) that you want to keep as a
  minimum balance at all times

## How It Works

The forecast projects your balance day by day into the future. On some days the balance
dips (rent, bills) and on others it peaks (salary). The margin uses the **worst-case
point** — the day where your balance is lowest — to determine how much room you have.

```
Balance
  3200 ┤         ╭──╮
  2800 ┤─────────╯  │
  2400 ┤             ╰────╮
  2000 ┤                   ╰──╮
  1740 ┤.......................╰── ← Lowest future balance
       │
   500 ┤- - - - - - - - - - - - - ← Threshold
       └──────────────────────────
        Mar 1    Mar 15   Mar 29

  Available margin = 1,740 − 500 = 1,240 EUR
```

## Concrete Example

A developer with:

- Salary +3,200 EUR on the 28th
- Rent -950 EUR on the 5th
- Groceries budget -450 EUR (spread daily)
- Savings -500 EUR on the 29th
- Balance at March 1: 2,800 EUR
- Threshold: 500 EUR

The balance dips to 1,740 EUR on March 29th (after savings transfer, before next
salary). The available margin is **1,240 EUR** — that's how much extra spending is safe.

If a 400 EUR washing machine repair is added, the lowest balance drops to 1,340 EUR and
the margin shrinks to 840 EUR — still above threshold.

## Alert Mode

When the available margin goes **negative**, it means your balance is projected to fall
below the threshold at some point. The margin section turns red and shows a warning:

```
/!\ The account will go below your 500 € threshold on Mar 29, 2026
```

This happens when unexpected large expenses push the lowest balance below the safety
net.

## Configuring the Threshold

The threshold can be changed from the Review tab:

1. Press `E` or click the **Edit** button in the margin section
2. Enter the new threshold value
3. The margin recalculates immediately

A threshold of 0 means you only get an alert if the balance goes negative.

## Past Months

The margin section is **hidden** when viewing past months in the Review tab. It only
appears for the current month and future months, since the margin is a forward-looking
indicator.
