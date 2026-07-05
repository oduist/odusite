# odusite_mass_mailing

Depends: `odusite_base`, `website_mass_mailing` (brings `mass_mailing`).
Newsletter subscription → mailing lists.

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/newsletter/subscribe` | POST | `{email, list_id?, website_hp?}` → creates/reuses `mailing.contact` and subscribes it to the list (`mailing.subscription`), same semantics as upstream `/website_mass_mailing/subscribe`: opted-out subscriptions are re-activated, an active subscription is a no-op (idempotent). Returns `{subscribed: true, list: <name>}`. 422 on invalid email; 404 `no_list` when the list is unknown/non-public or no public list exists. |
| `/odusite/v1/newsletter/lists` | GET | Public mailing lists (`is_public=True`): `[{id, name}]`. |

## List resolution

`list_id` must reference a `mailing.list` with `is_public=True` (private lists
are indistinguishable from missing ones → 404 `no_list`). Without `list_id`
the first public list (lowest id) is used — upstream has no per-website
default; its builder snippet also just binds a public list.

## Anti-spam

Honeypot field (`website_hp`) → silent success `{subscribed: true}` without
the list name, nothing created. No recaptcha (server-to-server API), no
Turnstile on the site side for this low-risk form.

## Webhooks / sitemap

None (write-only module).

## Site block `newsletter`

No pages: a compact subscribe form rendered inside the site footer (email +
button, inline JSON submit, success/error states) plus the same-origin
`/api/newsletter/subscribe` proxy endpoint.
