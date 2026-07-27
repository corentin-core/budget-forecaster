# Web app

A mobile-first web interface over the same budget database as the TUI. It shows your
balance, monthly review, operations ledger, trends, and connection status, and lets you
categorize operations, link them to budgets or planned operations, and manage budgets
and planned operations. Every interaction stays on the page or opens a dedicated page —
there are no blocking pop-up dialogs. To run it as a background service reachable from
your phone and other PCs over Tailscale, see the [deployment guide](deployment.md).

## Running the app

The app is served by uvicorn as a factory:

```bash
uvicorn --factory budget_forecaster.web.app:create_app
```

By default it reads `config.yaml` from the working directory. Point it at another config
with an environment variable:

```bash
BUDGET_CONFIG=~/.config/budget-forecaster/config.yaml uvicorn --factory budget_forecaster.web.app:create_app
```

The app binds to `127.0.0.1:8000` by default. Open http://127.0.0.1:8000 and sign in
with the shared password.

## Authentication

Access is gated by a single shared password, so you and anyone you share it with reach
the same household budget. The password never leaves the server: each device just opens
the URL, lands on the login page, and types the password. There is nothing to install or
configure on the phones and PCs that connect.

The server needs two secrets: a signing key for the session cookie and the password
hash.

Generate the password hash once (prompts for the password, keeps it off your shell
history):

```bash
python -m budget_forecaster.main hash-password
```

Provide both secrets through the environment (recommended for a deployed server):

```bash
export BUDGET_WEB_SECRET_KEY="a-long-random-string"
export BUDGET_WEB_PASSWORD_HASH="pbkdf2_sha256$480000$...."
```

For local development you can instead put them in a `web:` section of the config file
(see Configuration). The environment always wins over the config file. The app refuses
to start if neither source provides both secrets.

## Sections

| Section    | What it shows                                                                                |
| ---------- | -------------------------------------------------------------------------------------------- |
| Accueil    | Balance, available margin for the month, this-month expense health, upcoming operations      |
| Mois       | Per-category planned vs actual for one month; switch months from the URL or the arrows       |
| Budgets    | All budgets and planned operations, whatever month they fall in; create, edit, split, delete |
| Opérations | The full ledger, filterable by search text, category, month, and "uncategorized"             |
| Tendances  | Balance evolution over time and expense breakdown by category                                |
| Réglages   | Bank connection status and sync history, import inbox, and the margin threshold              |

Navigation is a bottom bar on phones and a left sidebar on wider screens, each tab with
an icon.

Accueil leads with the **available margin**, coloured green / amber / red against your
safety threshold, so an at-a-glance screen tells you whether you are within budget.
Réglages lets you edit that threshold, and holds the log-out action (reachable on
mobile, where there is no sidebar).

The Accueil upcoming list also surfaces **overdue** iterations: an income or expense
whose due date just passed but that has not been matched to a real operation yet (e.g. a
salary paid a day or two late) is marked with a ⚠ and an amber date, sorted to the top,
instead of silently disappearing. Overdue detection uses each operation's matching
tolerance window; older unmatched iterations are assumed settled.

## Categorizing operations

In Opérations, each row carries a category dropdown: change it and the row updates on
the spot. The "N to categorize" badge on the Operations tab counts what is still
uncategorized and drops as you go.

To categorize several at once, tick the rows you want. A bar appears at the bottom with
a category picker; choose one and apply it to the whole selection. While rows are
selected the per-row dropdowns are disabled, so you always categorize one way at a time.
Clear the selection to go back to per-row editing.

## Linking an operation

Open an operation, then "Lier…". A search box narrows the candidates, and weak matches
stay behind a "show all" toggle so the list is short by default. The link page lists
candidate targets ranked by how well they match, each with its match score and a hint
such as "même montant". Pick a target and its dated occurrences appear below; the best
match is preselected. Step the window with the arrows when the occurrence you want is
further out. Confirm to create the link, or use "Délier" on an already-linked operation
to remove it.

## Budgets and planned operations

The month drill-down and the Budgets tab both edit the same items.

- **In context**: in Mois, tap a category to expand its budgets, planned operations, and
  the operations attributed to them. Tap any of them to edit it.
- **All of them**: the Budgets tab lists every budget and planned operation, whatever
  month they fall in — the place to reach items that don't appear in the current month
  (an annual budget, say). Budgets and planned operations sit under their own sub-tabs;
  each list has a search box, a category filter, and shows only active items by default
  (untick "active only" to see expired ones).

Editing opens on its own page with a working back button. From there you set the amount,
category, dates, and recurrence, split a recurring item from a chosen date, or delete it
(deletion asks for a confirmation inline first). Saving returns you to wherever you came
from.

## Linking a bank

When Enable Banking is configured but no bank is linked yet, Réglages shows a **Link a
bank** button. It opens a page listing the banks in your country, with a filter box;
pick yours and continue. You're sent to your bank to sign in and authorize access, then
brought back automatically, and a confirmation appears on Réglages. Your bank password
stays with your bank.

Once a bank is linked, the same page offers **Renew** to re-authorize before the consent
expires — the expiry banner links straight to it. The
[Enable Banking guide](enable-banking.md) covers the portal setup and the `redirect_url`
the callback needs.

## Consent banner

When a bank connection is configured and its consent is expiring (within 14 days) or
already expired, a banner appears on every page with a link to renew it. No banner shows
when the connection is valid or when Enable Banking is not configured.

## Sync history and failures

The bank data refreshes on its own through a background sync that runs while the host is
on. Réglages lists the recent runs — when each ran, whether it succeeded, how many
operations were new or duplicates, and the resulting balance (or the error, for a failed
run). Because that sync runs outside the app, a failure would otherwise go unnoticed:
when the most recent run failed, a red banner appears on every page pointing to
Réglages.

The banner clears once a later sync succeeds. It also stays silent for a failure that
predates your current bank authorization — if a sync failed because the consent had
expired and you have since renewed it, that old failure is treated as resolved and no
banner shows. A failure that happened under the current authorization (a bank outage,
say) still raises the banner.

"Sync now" in Réglages triggers a sync immediately, without waiting for the next
scheduled run. It records a run just like the background sync does.
