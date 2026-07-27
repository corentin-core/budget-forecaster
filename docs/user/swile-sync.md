# Swile sync

Swile syncs your meal-voucher operations and balance on its own, so you no longer have
to export a file and import it by hand. It works like the bank sync, but authorizes with
a token you copy from the Swile website once.

Swile has no Open Banking access, so this uses the Swile web session directly. It is a
convenience layer that can break if Swile changes its site; manual file import stays
available as the fallback (see the [web app guide](web-app.md)).

## How it works

You copy a token from your logged-in Swile session once (via a bookmarklet) and paste it
into Budget Forecaster. The app keeps that token encrypted and uses it to fetch fresh
data on its own: on every app startup and whenever you press Sync Swile. Only
meal-voucher operations are imported; card payments are ignored, since they already come
through the bank account.

If the token later stops working, a banner asks you to reconnect — you run the
bookmarklet again and paste a new token.

## One-time enrollment

1. Open the enrollment page (`scripts/swile_enroll_bookmarklet.html`) and drag the
   **Swile Enroll** button to your bookmarks bar.
2. Log in to [team.swile.co](https://team.swile.co).
3. Click the **Swile Enroll** bookmarklet. It copies your token to the clipboard.
4. In Budget Forecaster, open **Réglages → Swile**, paste the token into the field, and
   press **Enroll**.

Enrolling runs a first sync immediately, so your Swile operations appear right away.

Enrollment is desktop-only: bookmarklets do not run on mobile, and the Swile app hides
the token. From a phone you can still press Sync Swile once enrolled.

## Syncing

- **Automatic:** every time the web app starts (for example when your machine boots).
- **Manual:** the **Sync Swile** button in Réglages, from desktop or mobile.

Re-running a sync is safe: already-imported operations are recognized and skipped.

## Reconnecting

The stored token can expire or be revoked (for example after a long period with the app
offline). When a sync fails for that reason, a **reconnect** banner appears. Run the
bookmarklet again on team.swile.co and paste the new token into the Swile card. The
token is stored encrypted and never shown back in the interface.
