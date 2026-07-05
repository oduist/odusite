# Portal Authentication (JWT)

Implemented in `odusite_portal`. Odoo sessions are not used.

## Tokens

- **Access JWT** — HS256, secret `odusite.jwt_secret` (system parameter,
  auto-generated 64 hex chars). TTL 15 min.
  Payload: `{sub: uid, pid: partner_id, typ: "access", iat, exp, jti}`.
- **Refresh token** — random 48 bytes (base64url). Stored in Odoo in the
  `odusite.refresh.token` model **as a sha256 hash**. TTL 30 days, rotated on
  every refresh (the old one is revoked); revoking all sessions is supported.

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
| `/auth/login` | POST | `{login, password}` → `{access_token, refresh_token, expires_in, user}`. Credentials verified via the stock res.users mechanism (no session created). Portal or internal users only. MFA users → 409 `mfa_required` (MFA support — phase 2). |
| `/auth/refresh` | POST | `{refresh_token}` → new pair (rotation). Invalid/revoked → 401. |
| `/auth/logout` | POST | `{refresh_token}` — revoke. With JWT + `{all: true}` — revoke all. |
| `/auth/signup` | POST | `{name, email, password, token?}` — b2c signup (when `auth_signup.invitation_scope=b2c`) or by invitation (token from the email). Uses `res.users.signup`. |
| `/auth/password/forgot` | POST | `{login}` → always 200; Odoo sends the stock reset email. The email link points to the site: `/portal/reset/<token>`. |
| `/auth/password/reset` | POST | `{token, password}` → sets the password via the auth_signup mechanism. |

`user` in responses: `{id, name, email, partner_id, lang, is_portal}`.

## Emails

The auth_signup templates (invitation, reset) are overridden in `odusite_portal`
so links point to the site domain (system parameter `odusite.site_url`)
instead of `/web/...`.

## Guest cart

Not tied to JWT: the cart is a draft `sale.order` with an `access_token`,
bound via the `X-Odusite-Cart: <id>:<token>` header (see
`modules/odusite_sale.md`). On login the guest cart is re-assigned to the
user's partner (merge).
