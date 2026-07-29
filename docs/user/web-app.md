# Web app

A mobile-first web interface over your budget database. It shows your balance, monthly
review, operations ledger, trends, and connection status, and lets you categorize
operations, link them to budgets or planned operations, and manage budgets and planned
operations. Every interaction stays on the page or opens a dedicated page — there are no
blocking pop-up dialogs. To run it as a background service reachable from your phone and
other PCs over Tailscale, see the [deployment guide](deployment.md).

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

The app binds to `127.0.0.1:8000` by default. Open <http://127.0.0.1:8000> and sign in
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
| Réglages   | Bank connection status and sync history, manual file import, and the margin threshold        |

Navigation is a bottom bar on phones and a left sidebar on wider screens, each tab with
an icon.

Accueil leads with the **available margin**, coloured green / amber / red against your
safety threshold, so an at-a-glance screen tells you whether you are within budget.
Réglages lets you edit that threshold, and holds the log-out action (reachable on
mobile, where there is no sidebar).

The Accueil upcoming list covers what is still ahead of your balance date. A planned
payment nothing matched by then is **overdue** instead, and gets its own card above the
list, with a count on the Accueil tab so you see it from any page.

Each overdue row says how late the payment is and whether the forecast still counts it:
for a month it does, on the day after your balance date, then it stops being counted and
the row says so. It stays listed a second month, which is there for you to notice it,
and then the row leaves the card, taking its two decisions with it — by that point the
amount has been out of the forecast for a month, so there is nothing left to settle. A
decision you took while the row was there is kept for good, so a postponement made in
time still moves the amount long after. Linking the payment stays possible whenever you
find it, from the operation's own row in Opérations.

The pencil beside the description opens the planned operation itself, for when the
payment keeps arriving late or off-amount and the recurrence is what needs fixing. It
edits the whole series, not the occurrence in front of you — for a single date,
**Reporter** on the row is the tool, and the edit page can split the recurrence from a
date. Names in the Accueil upcoming list open the same page.

**Lier…** is the first thing to try, and the description opens the same page. Most often
the payment did happen and the matcher did not recognize it, so the page lists the
operations that could be it, best first, ranked by the same score the automatic matching
uses. Each one shows its date, that score and a hint such as "même montant". A search
box reaches operations well outside the dates around the occurrence, for when you
remember the label but not the day, and weak matches stay behind a **Tout afficher**
toggle. When nothing comes close the list says so rather than filling up with
near-misses.

An operation another budget or planned payment already counts is offered too — the
matcher giving a payment to the wrong target is exactly the mistake this page exists to
fix. It carries a note saying what counts it today, and asks before it moves: the
confirmation tells you what the previous target gets back, whether that means an
occurrence going back overdue, one returning to the upcoming list, or a budget simply no
longer counting the operation. Every candidate asks before it links, since undoing means
finding the operation in Opérations and using **Délier**.

When no operation is the payment, the same page offers the two decisions. **Reporter**
moves the payment to a date you pick, offered as the next occurrence or tomorrow before
you type anything; the forecast then counts it there, and the upcoming list shows it on
its new date with where it came from. **Ne pas compter** declares that the payment never
happened; the confirmation tells you how much comes back to your margin first. Both are
on the overdue row as well, and the margin at the top of Accueil updates with your
decision. **Rétablir** undoes it — right away on the row, or later from the planned
operation's own page, which lists every occurrence you decided about. Linking the
payment afterwards drops the decision from that list: the operation settles the
occurrence, so there is nothing left to undo. A payment made in cash has no operation to
link, so not counting it is the answer there.

When a sync has failed the card and the page withhold both decisions and say so:
operations are probably missing, and stopping to count a payment that did happen would
be worse than waiting. Linking stays available, since an operation already imported is
there whatever the sync left out — the page warns that what you are looking for may be
among the missing.

On Tendances, the expense breakdown donut folds small categories into a single grey
**Other categories** slice. A slider below the donut sets the cutoff: any category below
that share of the period total is folded in, and the donut re-renders live as you drag.
Set it to 0% to show every category separately. The folded categories and their amounts
are listed under the Other slice in the legend. The setting is remembered across visits.

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

## Forecasting a payment you just saw

A recurring payment showing up in the ledger for the first time can become a planned
operation without retyping it. Open the operation, then "Créer une opération planifiée":
the form arrives filled from the payment — amount, category, its own date as the start
date, monthly recurrence — and named after the one word of the bank label that says who
was paid, with the raw label kept underneath so you can rename it. "Reconnaître par"
holds that same word as the keyword future payments must contain; trim it to what will
come back every month, since a reference number or a month never will.

Saving links the payment to the first occurrence, so it counts straight away. An
operation already linked to something else keeps that link. You land back on the
operation, where the "Lien" line names whatever counts it.

When an existing planned operation already fits the payment, a note above the form names
it and offers to link to it instead — worth taking, since a second entry for the same
payment would be forecast twice every month. Starting from an old payment also warns
you: the occurrences since that date are expected too, and those with no matching
operation show up as overdue on Accueil.

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
category, dates, and recurrence, or delete the item (deletion asks for a confirmation
inline first). Saving returns you to wherever you came from.

Splitting a recurring item from a chosen date is a separate submission, below the Save
button: open **Split from a date**, give the date and the new values, then confirm with
**Split**. Save is paused while that section is open, since it would store the item
unchanged and drop what you typed there. The original segment stops the day before the
split and keeps its history; the new one runs from the split date onward, so both appear
in the list.

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

Your data refreshes on its own through a background sync that runs while the host is on.
The Sync card in Réglages lists the recent runs — when each ran, its source (Bank or
Swile), whether it succeeded, how many operations were new or duplicates, and the
resulting balance (or the error, for a failed run). Because that sync runs outside the
app, a failure would otherwise go unnoticed: when the most recent run failed, a red
banner appears on every page pointing to Réglages.

The banner clears once a later sync succeeds. It also stays silent for a failure that
predates your current bank authorization — if a sync failed because the consent had
expired and you have since renewed it, that old failure is treated as resolved and no
banner shows. A failure that happened under the current authorization (a bank outage,
say) still raises the banner.

A single "Sync now" button in the Sync card syncs every connected source at once (the
bank and Swile), without waiting for the next scheduled run. Each source records its own
run. A source you have not connected is skipped, and one source failing does not stop
the others. The button is hidden when nothing is connected yet.

## Swile sync

Swile syncs alongside the bank, through the same "Sync now" button and the same daily
timer. See the [Swile sync guide](swile-sync.md) for the one-time enrollment.

## Manual file import

Manual import stays available as a fallback (for example if a Swile reconnect is due).
The Imports section of Réglages takes a bank export directly: pick a BNP `.xls` or a
Swile `.zip` and press Import. The file goes through the same import as the automatic
sync, so operations are deduplicated and categorized the same way.

The result appears right below the button: the account, its balance date, and how many
operations were new or skipped as duplicates. An unsupported file is refused with a
message and nothing is imported.

Keep the Swile export under its original name. The `.zip` is recognized by its
`swile-export-YYYY-MM-DD.zip` name, so a renamed file is not accepted.
