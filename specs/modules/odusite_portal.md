# odusite_portal

Depends: `odusite_base`, `portal`, `auth_signup`. Provides JWT auth
(see `../03-auth.md`) and the portal core ("/my" equivalents).

## Models

- `odusite.refresh.token` — see `03-auth.md`.
- Mail template overrides (signup invite, password reset) pointing links to
  `odusite.site_url`.

## Endpoints

Auth endpoints — see `../03-auth.md` (`/auth/login`, `/auth/refresh`,
`/auth/logout`, `/auth/signup`, `/auth/password/forgot`, `/auth/password/reset`).

All routes below require JWT (`auth_user=True`) unless noted.

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/me` | GET | Profile: `{id, name, email, phone, lang, partner: {id, name, street..., country, vat, company_name}}`. |
| `/odusite/v1/me` | PUT | Update profile/main address. Writable fields = `res.partner._get_frontend_writable_fields()` whitelist; VAT/commercial-fields rules as in `/my/account`. 422 with per-field errors. |
| `/odusite/v1/me/password` | PUT | `{old_password, new_password}` — change password (revokes all other refresh tokens). |
| `/odusite/v1/me/addresses` | GET | Address book: billing/delivery children of the commercial partner (mirrors `/my/addresses`). |
| `/odusite/v1/me/addresses` | POST | Create address, `{address_type: billing\|delivery, ...fields}` — validation like `/my/address/submit`. |
| `/odusite/v1/me/addresses/<id>` | PUT/DELETE | Update / archive an address (only own, non-commercial ones). |
| `/odusite/v1/me/counters` | GET | `?counters=orders,invoices,tasks,...` → `{orders: 3, ...}`. Registry: each odusite module contributes a counter callable (mirrors `/my/counters`). |
| `/odusite/v1/me/sessions` | GET/DELETE | List / revoke refresh-token sessions (audit fields). |

## Chatter (shared portal messaging)

Generic endpoints used by all portal document types (orders, invoices, tasks…):

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/chatter/<model>/<id>/messages` | GET | Paginated messages: comment subtype only, share-safe domain (no internal notes). Item shape mirrors `portal_message_format`: `{id, body, date, author: {name, avatar}, attachments[], rating?}`. Access: JWT record rules **or** `?access_token=` of the record. |
| `/odusite/v1/chatter/<model>/<id>/messages` | POST | `{body, attachment_ids?}` → `message_post` as the JWT user (or token-authenticated public author, `hash`+`pid` flow phase 2). |
| `/odusite/v1/chatter/attachments` | POST | multipart upload → pending attachment (+ access token), to attach to a message. |

Only models registered in a whitelist (`odusite.chatter.models` registry) are
reachable; each module registers its own (sale.order, account.move,
project.task, helpdesk.ticket…).

## Site block

Block `portal`: `/portal` home (counter cards), `/portal/account`,
`/portal/addresses`, `/portal/security` (password + sessions), login/signup/
reset pages, auth middleware (cookie ↔ refresh flow in the Worker).
Document sections (orders, invoices, tasks) are contributed by their blocks.
