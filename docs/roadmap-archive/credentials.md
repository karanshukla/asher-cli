# §13 — Account management — credential & token persistence ✅

> Archived from [`ROADMAP.md`](../ROADMAP.md) §13. The shipped subsections only — what's still open stays in the roadmap. Original text, preserved verbatim.

### Credential persistence ✅ — OS keyring

Credentials (email + password) are stored in the OS keyring after the first
`/login`. On subsequent runs `_keyring_load()` retrieves them — no re-entry
needed. `.env` is still supported as a fallback for CI and existing users.

Helper functions in `asher/connection/__init__.py`:
- `_keyring_load() → tuple[str, str]` — returns `(email, password)` or `("", "")`
- `_keyring_save(email, password) → bool`
- `_keyring_delete()` — called by `/logout`

Keyring service name: `asher-cli`, keys `email` and `password`.

### Token persistence ✅ — avoid API re-auth on every run

`Account.__init__()` accepts a pre-existing `token` dict and a
`token_update_callback`; `connect()` with no username/password reuses a valid
token or silently refreshes it via the refresh token. The cached session token
is stored as a JSON blob in the OS keyring (key `"token"` under service
`asher-cli`), so subsequent launches skip the OAuth password login entirely —
faster startup, less password exposure, more resilient to rate-limiting.

`_connect_worker` tries the token first (via `_try_token_connect`), and only
falls back to the email/password path if the token is absent, expired, or
rejected — in which case the stale token is wiped so a poisoned token can't
loop. `token_update_callback=_keyring_save_token` is also wired into the
password-login `Account()` construction, so refreshes during a session are
captured for the next launch. Users only re-enter their password when the
refresh token itself expires (typically months).

Helpers in `asher/connection/__init__.py`:
- `_keyring_load_token() → dict | None` — returns the cached token or `None`
- `_keyring_save_token(token: dict | None)` — persists, or clears when `None`
- `_keyring_delete()` now also clears `"token"` (so `/logout` invalidates it)
