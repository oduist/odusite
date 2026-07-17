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

**Implemented:** a single `production` Worker. The `Deploy site` GitHub Actions
workflow (`.github/workflows/deploy-site.yml`) builds and runs `wrangler deploy`
on every push to `main` under `site/**` (plus `workflow_dispatch`), authed with
repo secrets `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`. The `ci.yml`
`site` job still gates PRs with typecheck (`astro check`) + build. See
[ADR-014](../decisions.md) and [site-deploy.md](../../docs/admin/site-deploy.md).

**Deferred:** a separate `preview` environment (staging Odoo, test PSP keys,
its own tokens) deployed on PRs — not yet wired into `wrangler.jsonc`/CI.

## Caching policy

| Page type | Strategy |
|---|---|
| marketing (prerender) | static assets, `max-age=3600, s-maxage` long |
| blog/shop/events/jobs/partners lists & details | edge cache, TTL 10 min + tag purge |
| search results | no store |
| cart/checkout/portal/auth | `private, no-store` |
| `/img/**` | `immutable` when `unique` param present, else 1 day |
