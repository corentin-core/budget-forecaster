# Enable Banking

Enable Banking imports your transactions and account balance directly from your bank
over Open Banking (PSD2), as an alternative to loading exported files. Once set up, a
single `sync` command replaces the manual export-and-load routine.

The free "restricted production" tier is self-service (no business verification) and
gives access to your own linked accounts only. It covers BNP Paribas and other French
banks.

## How it works

You authorize your bank once in a browser. The bank issues a consent valid for a limited
period (about 180 days for BNP; other banks may grant less). While the consent is valid,
you can sync as often as you like without re-authenticating. When it expires, you
authorize again.

Only booked transactions are imported; pending ones are ignored. The balance reflects
the closing booked balance reported by the bank.

## One-time portal setup

This is done once on the [Enable Banking](https://enablebanking.com/) portal. You need
three things from it: an application id, an RS256 key pair, and a redirect URL.

1. **Create an account** and open the control panel.
2. **Register an application** on the restricted-production tier. Note the **application
   id** it assigns — the app uses it as the signing key identifier (`kid`) when it
   authenticates.
3. **Generate an RS256 key pair.** Keep the **private key** as a PEM file on your
   machine; upload the **public key** to the application. The private key never leaves
   your machine and is what the app signs its requests with.
4. **Set a redirect URL** on the application. The bank sends you back to it with an
   authorization code after you authenticate. Point it at the web app's callback, so the
   browser hands the code straight back to the app with no copy-paste:
   `https://<your-host>.ts.net/settings/bank/callback`. This must be a URL the web app
   actually serves; see [Linking a bank](#linking-a-bank) and the
   [web app guide](web-app.md).

Store the private key outside the repository, for example at
`~/.config/budget-forecaster/enable_banking_key.pem`, readable only by you
(`chmod 600`).

## Configuration

Add an `enable_banking` block to your `config.yaml`:

```yaml
enable_banking:
  application_id: "your-application-id"
  private_key_path: ~/.config/budget-forecaster/enable_banking_key.pem
  redirect_url: "https://your-redirect-url"
  aspsp_country: FR
  aspsp_name: "the-bank-name" # optional: skip the bank picker in the web app
  account_uid: "..." # optional: pick one when a consent has several
  local_account_name: bnp # local account the sync merges into
```

See the [configuration reference](configuration.md#syncing-bank-data-enable-banking) for
what each key means and its default.

## Usage

You link and renew a bank in the **web app**; two CLI commands cover the rest:

```bash
budget-forecaster sync            # import transactions and balance
budget-forecaster consent-status  # show whether the consent is valid, expiring, or expired
```

### Linking a bank

Linking happens in the web app, under **Réglages → Bank connection**. Because the bank
redirects your browser to the web app's callback, there is no code to copy by hand.

1. Open the web app and go to Réglages. With Enable Banking configured but no bank
   linked yet, a **Link a bank** button appears.
2. Pick your bank from the list (a filter box helps). If you set `aspsp_name` in the
   config, the picker is skipped.
3. You're sent to your bank to sign in and authorize access, then brought back
   automatically. A confirmation appears once you return.

Your bank password stays with your bank; the app never sees it. The session and its
expiry are stored outside the repository, under
`$XDG_STATE_HOME/budget-forecaster/enable_banking/` (falling back to
`~/.local/state/...`), readable only by you.

See the [web app guide](web-app.md) for how the flow looks on the connection page.

### Syncing

`sync` reads the stored consent and imports transactions and the balance, so you never
paste an account id by hand:

```
Synced bnp: 12 new, 320 duplicates skipped. Balance: 1543.20 EUR
```

Re-running `sync` is safe. Already-imported operations are skipped, and operations that
overlap with a manual file import are reconciled rather than duplicated.

When the account is declared in the `accounts` registry, its IBAN becomes its stable
identity: file imports and API syncs of the same account reconcile by that id, and
several accounts of the same bank stay distinct. See the
[configuration reference](configuration.md#syncing-bank-data-enable-banking) for the
registry.

### Checking and renewing consent

`consent-status` reports the current state:

```
Consent valid, valid until 2026-12-15.
```

When the consent is expiring or expired (or `sync` reports no valid consent), open the
web app and use **Renew** on the Réglages connection card, or the link in the expiry
banner. The same bank and account are reused.

## Troubleshooting

| Symptom                                                    | Cause                                                             | Fix                                                                      |
| ---------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------ |
| No bank linked yet                                         | Consent never created                                             | Link a bank from Réglages in the web app                                 |
| `sync` fails with an expired-consent message               | Consent past its expiry                                           | Renew from Réglages in the web app                                       |
| Sync picks the wrong account, or a consent unlocks several | Ambiguous account                                                 | Set `account_uid` to the account to sync                                 |
| Authentication errors                                      | Wrong `private_key_path`, or public key not uploaded / mismatched | Check the path and that the uploaded public key matches your private key |
| The bank list is empty when linking                        | Wrong `aspsp_country`                                             | Set it to your bank's country (default `FR`)                             |
| Linking never returns / the callback errors                | `redirect_url` does not match the web app's callback              | Set it to `https://<your-host>.ts.net/settings/bank/callback`            |
