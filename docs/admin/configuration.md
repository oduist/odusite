# Configuration reference (Odoo)

## System parameters (created/used by odusite addons)

| Parameter | Purpose |
|---|---|
| `odusite.token` | API shared secret (`X-Odusite-Token`). Auto-generated. |
| `odusite.jwt_secret` | JWT signing key. Auto-generated. Rotating it logs every portal user out. |
| `odusite.site_url` | Public site URL: email links, webhook target. |
| `odusite.revalidate_secret` | HMAC secret of cache webhooks. |
| `odusite.website_id` | Which Odoo website the API exposes. |
| `odusite.form_rate_limit` / `odusite.form_rate_window` | Contact-form throttle: max submissions per IP per window (defaults in code). |

All of them are editable from **Website → Configuration → Settings → Odusite**.

## Publishing content

The API only exposes records that are **published** (the standard Odoo
`Published` toggle) and belong to the configured website (or to all websites).
Time-gated content (blog posts, job publish dates) additionally respects its
publish date. Unpublishing a record removes it from the site within a minute
(webhook) or after the cache TTL at most.

## Languages

The site serves the languages enabled on the configured website
(**Website → Configuration → Languages**). Translated fields are returned in
the requested language; the site sends `?lang=` on every API call.

## Portal access

Portal users are managed the standard Odoo way (contact → *Grant portal
access*). Invitation and password-reset emails link to the Astro site
(`odusite.site_url`) instead of the Odoo login page. Self-registration on the
site follows **Settings → General → Customer Account** (b2c enables free
signup).

## Webhooks (cache invalidation)

Watched models enqueue events into **Odusite webhook events**
(`odusite.webhook.event`, visible via developer mode → Technical). Delivery
state, attempts and a retry action are available there. Delivery requires both
`odusite.site_url` and `odusite.revalidate_secret` to be set — otherwise events
stay pending and the queue is skipped silently.

## Security notes

- Rotate `odusite.token` by generating a new value in settings and updating
  the site secret; do both within one deploy window.
- The API refuses every request without a valid token, including health.
- Portal JWT lifetime: 15 minutes (access) / 30 days (refresh, rotating).
  Refresh sessions are visible to each user under portal *Security* and can be
  revoked.
