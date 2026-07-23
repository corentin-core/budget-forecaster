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
   authorization code after you authenticate. With the current CLI flow you copy that
   code by hand (see [Linking a bank](#linking-a-bank)), so any URL registered here
   works — it does not need to point at a running server. A dedicated web callback is
   planned separately.

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
  aspsp_name: "the-bank-name" # optional: skip the bank picker in `link`
  account_uid: "..." # optional: pick one when a consent has several
  local_account_name: bnp # local account the sync merges into
```

See the [configuration reference](configuration.md#syncing-bank-data-enable-banking) for
what each key means and its default.

## Usage

Three commands cover the whole lifecycle:

```bash
budget-forecaster link            # authorize a bank (once per consent period)
budget-forecaster sync            # import transactions and balance
budget-forecaster consent-status  # show whether the consent is valid, expiring, or expired
```

### Linking a bank

`link` lists the banks available in `aspsp_country` and lets you pick yours, so you
never type an exact bank name (set `aspsp_name` to skip the picker). It then prints an
authorization URL:

1. Open the URL and authenticate at your bank.
2. Your bank redirects to the `redirect_url` with a `code` parameter in it.
3. Copy that code and paste it back into the prompt.

The command confirms the link, how many accounts the consent unlocks, and the expiry
date:

```
Linked BNP Paribas: 1 account(s), consent valid until 2026-12-15.
```

The session and its expiry are stored outside the repository, under
`$XDG_STATE_HOME/budget-forecaster/enable_banking/` (falling back to
`~/.local/state/...`), readable only by you.

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

When the consent is expired (or `sync` reports no valid consent), run `link` again to
renew it. Nothing else changes — the same bank and account are reused.

## Troubleshooting

| Symptom                                                    | Cause                                                             | Fix                                                                      |
| ---------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `No consent stored. Run 'link' to authorize a bank.`       | No bank linked yet                                                | Run `link`                                                               |
| `sync` fails with an expired-consent message               | Consent past its expiry                                           | Run `link` to renew                                                      |
| Sync picks the wrong account, or a consent unlocks several | Ambiguous account                                                 | Set `account_uid` to the account to sync                                 |
| Authentication errors                                      | Wrong `private_key_path`, or public key not uploaded / mismatched | Check the path and that the uploaded public key matches your private key |
| `link` shows no banks                                      | Wrong `aspsp_country`                                             | Set it to your bank's country (default `FR`)                             |
