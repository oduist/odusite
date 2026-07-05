# Portal Authentication (JWT)

Implemented in `odusite_portal`. Odoo sessions are not used.

## Tokens

- **Access JWT** — HS256, secret `odusite.jwt_secret` (system parameter,
  auto-generated 64 hex chars). TTL 15 min.
  Payload: `{sub: uid, pid: partner_id, typ: "access", iat, exp, jti}`.
- **Refresh token** — random 48 bytes (base64url). Stored in Odoo in the
  `odusite.refresh.token` model **as a sha256 hash**. TTL 30 days, rotated on
  every refresh (the old one is revoked); revoking all sessions is supported.
- **Email-confirmation JWT** — HS256, same secret `odusite.jwt_secret`. TTL
  48 h. Payload `{sub: uid, typ: "email_confirm", iat, exp, jti}`. Stateless,
  emailed in the double opt-in link; the dedicated `typ` means it can never be
  accepted as an access token. Built by `res.users._odusite_email_confirm_token()`.

### Model `odusite.refresh.token`
| Field | Type | Purpose |
|---|---|---|
| user_id | m2o res.users, required, ondelete=cascade | owner |
| token_hash | char, index, unique | sha256 of the refresh token |
| expires_at | datetime | expiry |
| revoked | boolean | revoked flag |
| user_agent, ip | char | audit |
| last_used_at | datetime | audit |

A daily cron deletes expired/revoked records older than 7 days.

## Endpoints (`/odusite/v1/auth/*`)

| Route | Method | Description |
|---|---|---|
| `/auth/login` | POST | `{login, password}` → `{access_token, refresh_token, expires_in, user}`. Credentials verified via the stock res.users mechanism (no session created). Portal or internal users only. MFA users → 409 `mfa_required` (MFA support — phase 2). A b2c account whose email is not yet confirmed (so still inactive) with the **correct** password → 403 `email_not_confirmed` (wrong password still → generic 401, no enumeration). |
| `/auth/refresh` | POST | `{refresh_token}` → new pair (rotation). Invalid/revoked → 401. |
| `/auth/logout` | POST | `{refresh_token}` — revoke. With JWT + `{all: true}` — revoke all. |
| `/auth/signup` | POST | `{name, email, password, token?}`. **Invited** (valid `token`): creates/updates the user, marks it confirmed + active, auto-logs in → same shape as `/auth/login`. **b2c** (no token, requires `auth_signup.invitation_scope=b2c`): creates the user **inactive + unconfirmed**, emails a confirmation link, returns `{status: "confirmation_sent", email}` (200, **no tokens**). Uses `res.users.signup`. |
| `/auth/confirm` | POST | `{token}` — verify the `email_confirm` JWT (signature/exp/typ), set the user confirmed + active, auto-log in → same shape as `/auth/login`. Invalid/wrong-typ → 400 `invalid_token`; expired → 401 `token_expired`. |
| `/auth/confirm/resend` | POST | `{email}` → re-sends the confirmation email if an unconfirmed account with that email exists. Always 200 `{ok: true}` (no enumeration). |
| `/auth/password/forgot` | POST | `{login}` → always 200; Odoo sends the stock reset email. The email link points to the site: `/portal/reset/<token>`. |
| `/auth/password/reset` | POST | `{token, password}` → sets the password via the auth_signup mechanism. |

`user` in responses: `{id, name, email, partner_id, lang, is_portal}`.

## Self-service registration (email double opt-in)

Enabled by the **Website → Odusite → Public Sign Up** setting
(`res.config.settings.odusite_allow_signup`), which flips the standard
`auth_signup.invitation_scope` system parameter between `b2c` (on) and `b2b`
(off) — the same parameter `res.users._get_signup_invitation_scope()` reads.

Flow: visitor submits name/email/password → `res.users.signup` creates a portal
user, which the handler then marks `active=False`,
`odusite_email_confirmed=False` → a confirmation email is sent with a link to
`<odusite.site_url>/confirm/<email_confirm-JWT>` → the site posts the token to
`/auth/confirm`, which sets `odusite_email_confirmed=True`, `active=True` and
issues the token pair (auto-login). Because unconfirmed accounts are inactive,
`/auth/login` rejects them; the handler detects the inactive-but-unconfirmed
case (looking the user up by login with sudo, after verifying the password) and
returns `email_not_confirmed` so the site can offer "resend".

`res.users.odusite_email_confirmed` (Boolean, default False) is the confirmation
flag. Invited signups are treated as already confirmed (the invitation implies a
verified address) and stay active.

## Emails

The auth_signup templates (invitation, reset) are overridden in `odusite_portal`
so links point to the site domain (system parameter `odusite.site_url`)
instead of `/web/...`. A dedicated **email-confirmation** template
(`odusite_portal.mail_template_odusite_email_confirm`, model `res.users`) links
its button to `<odusite.site_url>/confirm/<token>` via
`res.users._odusite_confirm_url()` (falls back to the Odoo base URL when
`odusite.site_url` is unset).

## Guest cart

Not tied to JWT: the cart is a draft `sale.order` with an `access_token`,
bound via the `X-Odusite-Cart: <id>:<token>` header (see
`modules/odusite_sale.md`). On login the guest cart is re-assigned to the
user's partner (merge).
