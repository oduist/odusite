# Architecture

## Components and flows

```
Browser ⇄ Cloudflare Worker (Astro SSR + edge cache)
              │  HTTPS, X-Odusite-Token (+ Authorization: Bearer JWT)
              ▼
          Odoo 19 (addons/odusite_*)  ⇄  PostgreSQL
              │
              └─ webhooks (HMAC) → Worker /api/revalidate → edge cache purge
Stripe (and other PSPs) ⇄ browser (JS SDK) ; PSP webhooks → directly to Odoo
```

## Rendering (hybrid SSR)

- Astro + `@astrojs/cloudflare`. Marketing pages — `prerender = true`
  (static at build time). Catalog, detail pages, listings — SSR + edge cache
  (Cache API, key = URL + language; TTL per page type) with tags for invalidation.
- Cart, checkout, portal — SSR without caching (`Cache-Control: private`).
- Invalidation: Odoo sends a webhook when published entities change
  (see `06-cache-invalidation.md`). No full rebuild is needed.

## Client-side state (first-party cookies, httpOnly)

| Cookie | Contents | Lifetime |
|---|---|---|
| `od_access` | JWT access token | 15 min |
| `od_refresh` | refresh token | 30 days |
| `od_cart` | `cart_id:cart_token` | 90 days |
| `od_lang` | language code | 1 year |

The Worker reads the cookies, adds `X-Odusite-Token` and (when present)
`Authorization`, and proxies calls to Odoo. Secrets never reach the browser.

## Security

- `X-Odusite-Token` is checked in Odoo with a constant-time comparison against
  the `odusite.token` system parameter. Without it any `/odusite/...` route → 401.
- JWT HS256, secret `odusite.jwt_secret` (auto-generated on install).
- Portal document access: record rules of the JWT user, or the record's
  `access_token` (the `_document_check_access` pattern).
- Rate limiting and bot protection — on Cloudflare (WAF/Turnstile on forms).
- Forms that create public records (lead, job application, subscription) —
  Turnstile, verified by the Worker before calling Odoo.

## Images and files

Worker route `/img/**` proxies to Odoo `/web/image/**` (resize, `unique` checksum →
`immutable` edge caching). Portal files/PDFs — `/odusite/v1/...` endpoints with
streamed responses (see module specs). Details — `05-media-seo-i18n.md`.

## Multi-website and companies

v1 targets a single Odoo website (set by the `odusite.website_id` system
parameter; defaults to the default website). All controllers execute in that
website's context (pricelists, languages, record domains). Multi-site =
multiple Astro deployments with different tokens/website_id (phase 2).

## Runtime environment

- Odoo 19.0, Python ≥ 3.10. Addons require no external pip dependencies
  (JWT implemented with stdlib: hmac + json + base64).
- Site: Node ≥ 20, pnpm, TypeScript strict, Astro 5, Wrangler.

## Deployment topologies (Worker → Odoo)

`ODOO_URL` is the only thing the Worker knows about Odoo. Two supported
exposures, same Worker code (ADR-013, `docs/admin/topologies.md`):

- **Tunnel (recommended)** — Odoo has no public ports; a `cloudflared` tunnel
  (outbound-only) maps a hostname to `127.0.0.1:8069`; `ODOO_URL` is that
  hostname.
- **Public origin** — Odoo runs on a public HTTPS URL; `ODOO_URL` points at it;
  edge lockdown is the operator's job.

Either origin can sit behind Cloudflare Access; when `CF_ACCESS_CLIENT_ID` /
`CF_ACCESS_CLIENT_SECRET` are set, the Worker adds the `CF-Access-Client-*`
service-token headers to every API and `/img` call. `X-Odusite-Token` stays
mandatory regardless. Odoo runs with `--proxy-mode`.
