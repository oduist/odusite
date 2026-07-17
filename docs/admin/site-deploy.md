# Site deployment (Cloudflare)

The site lives in `site/` (Astro 5 + `@astrojs/cloudflare`, deployed as a
single Cloudflare Worker with static assets).

## Prerequisites

- Node ≥ 20, pnpm.
- A Cloudflare account with Workers enabled; `wrangler` authenticated
  (`npx wrangler login`).

## One-time setup

```bash
cd site
pnpm install
npx wrangler kv namespace create ODUSITE_CACHE_TAGS   # put the id into wrangler.jsonc
npx wrangler secret put ODUSITE_TOKEN                 # from Odoo settings
npx wrangler secret put ODUSITE_REVALIDATE_SECRET     # same value as in Odoo
npx wrangler secret put TURNSTILE_SECRET_KEY          # optional, for forms
npx wrangler secret put CF_ACCESS_CLIENT_ID           # optional, if Odoo is behind Cloudflare Access
npx wrangler secret put CF_ACCESS_CLIENT_SECRET       # optional, pairs with the above
```

Edit `wrangler.jsonc` vars:

- `ODOO_URL` — base URL of the Odoo instance (must be reachable from Cloudflare;
  either a Cloudflare Tunnel hostname or a public Odoo origin — see
  [topologies.md](topologies.md)),
- `PUBLIC_SITE_URL` — the canonical site origin,
- `PUBLIC_TURNSTILE_SITE_KEY` — optional.

`CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` are optional: set both only
when Odoo sits behind a Cloudflare Access service-token policy, and the Worker
sends them on every Odoo request. Left unset, they are omitted. See
[topologies.md](topologies.md).

## Blocks and theme (build time)

Defaults live in `odusite.config.mjs`. Override per build via env:

```bash
ODUSITE_BLOCK_FORUM=1 ODUSITE_BLOCK_COURSES=1 ODUSITE_THEME=default pnpm build
```

A disabled block contributes no routes, no JS and no navigation entries.
A block only works when its Odoo addon is installed (see
[installation.md](installation.md)); otherwise its pages return errors.

## Deploy

```bash
pnpm deploy        # astro build && wrangler deploy
```

Attach a custom domain to the Worker in the Cloudflare dashboard, then set the
same URL as **Site URL** in Odoo settings.

## Local development

```bash
pnpm dev           # Astro dev server with Cloudflare platform proxy
```

Put dev values into `site/.dev.vars` (`ODOO_URL`, `ODUSITE_TOKEN`, ...).

## Cache behaviour

- Public pages are cached on the edge for anonymous visitors only, with tags
  (e.g. `blog`, `shop:42`).
- Odoo pushes invalidation webhooks to `POST /api/revalidate` (HMAC-signed
  with `ODUSITE_REVALIDATE_SECRET`); matching tagged pages are purged.
- `/img/**` proxies Odoo images; URLs carrying a `unique=` checksum are cached
  as immutable for a year.
- `/portal`, `/cart`, `/checkout` and auth pages are never cached.
