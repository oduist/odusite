# Astro Site — Structure

## Stack

Astro 5, TypeScript strict, pnpm, `@astrojs/cloudflare` adapter (SSR),
Wrangler for deploy. No UI framework by default — Astro components + minimal
vanilla TS islands; heavier islands (variant picker, payment sheet) may use
Preact if needed (decision per component, keep JS budget small).

## Directory layout (`site/`)

```
astro.config.mjs        adapter, integrations (odusite blocks integration)
odusite.config.mjs      block activation + theme + site metadata (build-time)
wrangler.jsonc          Worker config, /img route, KV for cache tags
src/
  lib/
    api/                typed Odoo API client (fetch wrapper, one file per module:
                        base.ts, blog.ts, shop.ts, portal.ts, ...)
    auth/               JWT cookie handling, refresh middleware helpers
    cache/              edge-cache helpers (tagged put/match, purge)
    img.ts              /web/image → /img URL rewriting
  middleware.ts         locale detection, auth refresh, security headers
  blocks/<name>/        one folder per block: pages/, components/, index.ts
  components/           core shared UI (Header, Footer, Pagination, Form, SEO)
  layouts/              Base.astro, Portal.astro
  themes/<name>/        tokens.css + component overrides (see 02-theming.md)
  content/              Astro content collections: marketing pages (MDX)
  i18n/                 UI string catalogs per language
  pages/                core routes only (index, [...marketing], api/revalidate,
                        img/[...path], sitemap.xml, robots.txt, 404)
```

## Core pages & endpoints

- `/` and marketing pages — from `src/content/pages/` (MDX + section
  components), `prerender = true`.
- `/api/revalidate` — POST, HMAC-verified (`ODUSITE_REVALIDATE_SECRET`),
  purges tagged cache entries (see specs/06).
- `/img/[...path]` — image proxy to `ODOO_URL/web/image/...` with edge caching
  (immutable when `unique` present).
- `/sitemap.xml` — merges static routes + `GET /odusite/v1/sitemap`.
- Block routes are injected by the blocks integration (01-blocks.md).

## API client rules

- Single `apiFetch(path, opts)`: adds `X-Odusite-Token`, `Accept-Language`,
  optional `Authorization` and `X-Odusite-Cart` (from cookies), JSON parse,
  typed error (`OdusiteApiError { status, code, message, details }`).
- Runs **server-side only** (SSR/endpoints). Browser islands call same-origin
  site endpoints (`/api/...` inside blocks) which proxy via apiFetch — the
  token never leaves the server.
- Response types mirror the module specs (`src/lib/api/types.ts`).

## Middleware

1. Locale: URL prefix → `Astro.locals.lang`; sets `od_lang`.
2. Auth: if `od_access` expired and `od_refresh` present → refresh against
   Odoo, set new cookies; `Astro.locals.user` populated from JWT claims.
3. Cache: public GET pages get tagged edge caching per block config;
   `/portal`, `/cart`, `/checkout` → `Cache-Control: private, no-store`.
4. Security headers (CSP allowing Stripe JS, frame-ancestors none, etc.).
