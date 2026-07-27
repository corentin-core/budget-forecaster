"""Public Swile web constants.

The client_id and API key are the ones the Swile web app ships to every
browser; they are not secrets. The refresh token (per user) is the only
credential and lives encrypted in the token store. These endpoints are
unofficial and may change without notice.
"""

CLIENT_ID = "533bf5c8dbd05ef18fd01e2bbbab3d7f69e3511dd08402862b5de63b9a238923"
X_API_KEY = "393e1b0abfebf6da88aa57cfa1a126f97bf0b818"

TOKEN_URL = "https://directory.swile.co/oauth/token"
OPERATIONS_URL = "https://neobank-api.swile.co/api/v3/user/operations"
WALLETS_URL = "https://employee-bff-api.swile.co/api/wallets/get-wallets"
