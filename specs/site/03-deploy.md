# Astro Site — Deploy (Cloudflare)

## Target

Cloudflare Workers (via `@astrojs/cloudflare`), single Worker serving SSR +
static assets. Wrangler config in `site/wrangler.jsonc`.

## Resources

- **KV namespace `ODUSITE_CACHE_TAGS`** — tag → [cache keys] index used by
  `/api/revalidate` to purge tagged entries (Cache API holds the bodies).
- Static assets uploaded with the Worker (Astro `dist/`).
- Custom domain routed to the Worker; Odoo host reachable from the Worker
  (public HTTPS), never referenced in HTML.

## Secrets / vars (wrangler)

| Name | Kind | Purpose |
|---|---|---|
| `ODOO_URL` | var | Odoo base URL |
| `ODUSITE_TOKEN` | secret | API shared secret |
| `ODUSITE_REVALIDATE_SECRET` | secret | webhook HMAC |
| `TURNSTILE_SECRET_KEY` / `PUBLIC_TURNSTILE_SITE_KEY` | secret / var | forms |
| `PUBLIC_SITE_URL` | var | canonical origin |

Build-time (CI env): `ODUSITE_BLOCK_*`, `ODUSITE_THEME`.

## Environments

`preview` (staging Odoo, test PSP keys) and `production` — separate wrangler
environments, separate tokens. CI: typecheck (`astro check`) + build must pass;
deploy `preview` on PR, `production` on main.

## Caching policy

| Page type | Strategy |
|---|---|
| marketing (prerender) | static assets, `max-age=3600, s-maxage` long |
| blog/shop/events/jobs/partners lists & details | edge cache, TTL 10 min + tag purge |
| search results | no store |
| cart/checkout/portal/auth | `private, no-store` |
| `/img/**` | `immutable` when `unique` param present, else 1 day |
